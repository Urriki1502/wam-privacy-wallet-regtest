"""Q06 12-word REGTEST wallet using Q05's serialized owned-Core engine.

The independent seed-rescan path is read-only; Send requires a native-anchored
Q06 spend session. Neither path imports external custody or grants mainnet use.
"""
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import time

from .wallet_executor import ManagedWalletBackend, WalletExecutorError


class Q06ReadOnlyError(ValueError):
    pass


# ---- Backup-acknowledgement sidecar storage (CUR-003 + CDX-AUD-003) -------
# GUI metadata only: never spending authority, never a seed. The JSON/HMAC
# format is unchanged; only publication and reading are hardened:
#   * the ack directory is reached by native no-follow private-directory
#     walkers (macOS/Linux) or the NTFS DACL guard (Windows);
#   * an unpredictable O_EXCL|O_NOFOLLOW 0600 stage file is written, fsynced,
#     atomically renamed over the target (dir-fd relative on POSIX) and the
#     directory is fsynced where supported;
#   * an existing target that is not a single-link regular owned file
#     without group/other write is refused, never replaced or followed;
#   * reads are bounded and the decoded record is validated strictly.
# Retained profiles are never modified, repaired or migrated.
_ACK_LIMIT = 4096
_ACK_REQUIRED = frozenset(("version", "acknowledged", "deferred", "seed_id"))
_ACK_DENIED = "Q06_GUI_BACKUP_ACK_STORAGE_DENIED"


def _ack_name(folder):
    if (type(folder) is not type(Path())
            or re.fullmatch(r"bip39-12-[0-9a-f]{32}", folder.name) is None):
        raise Q06ReadOnlyError(_ACK_DENIED)
    return folder.name + ".json"


def _ack_file_ok(info):
    return (stat.S_ISREG(info.st_mode) and info.st_nlink == 1
            and (sys.platform == "win32" or info.st_uid == os.geteuid()
                 and not stat.S_IMODE(info.st_mode) & 0o022
                 and stat.S_IMODE(info.st_mode) & 0o600 == 0o600))


def _ack_posix_directory(directory):
    if sys.platform == "darwin":
        from .private_directory import open_macos_private_directory
        return open_macos_private_directory(directory)
    from .linux_private_storage import open_linux_private_directory
    return open_linux_private_directory(directory)


def _ack_absent(path):
    """Lenient no-follow absence probe; presence is then verified strictly."""
    try:
        os.lstat(path)
    except FileNotFoundError:
        return True
    return False


def _ack_read(directory, name):
    for component in (directory.parent, directory):
        if _ack_absent(component):
            return None
        if not stat.S_ISDIR(os.lstat(component).st_mode):
            raise Q06ReadOnlyError(_ACK_DENIED)  # symlink/junction or file
    if _ack_absent(directory / name):
        return None
    if sys.platform == "win32":
        from .windows_private_storage import directory_guard
        with directory_guard(directory):
            before = os.lstat(directory / name)
            if getattr(before, "st_file_attributes", 0) & 0x400 or not _ack_file_ok(before):
                raise Q06ReadOnlyError(_ACK_DENIED)
            with open(directory / name, "rb") as handle:
                info = os.fstat(handle.fileno())
                if (info.st_ino, info.st_dev) != (before.st_ino, before.st_dev):
                    raise Q06ReadOnlyError(_ACK_DENIED)
                raw = handle.read(_ACK_LIMIT + 1)
    else:
        dfd = _ack_posix_directory(directory)
        fd = None
        try:
            try:
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                             | os.O_CLOEXEC, dir_fd=dfd)
            except FileNotFoundError:
                return None
            before = os.fstat(fd)
            if not _ack_file_ok(before) or not 1 <= before.st_size <= _ACK_LIMIT:
                raise Q06ReadOnlyError(_ACK_DENIED)
            raw = os.read(fd, _ACK_LIMIT + 1)
            after = os.fstat(fd)
            if ((before.st_ino, before.st_size, before.st_mtime_ns)
                    != (after.st_ino, after.st_size, after.st_mtime_ns)):
                raise Q06ReadOnlyError(_ACK_DENIED)
        finally:
            if fd is not None:
                os.close(fd)
            os.close(dfd)
    if not 1 <= len(raw) <= _ACK_LIMIT:
        raise Q06ReadOnlyError(_ACK_DENIED)
    return raw


def _ack_ensure_directories(root):
    from . import custody
    state = root / "q06-gui-state"
    for directory in (state, state / "ack"):
        if _ack_absent(directory):
            custody.create_directory(directory)
    return state / "ack"


def _ack_write(root, name, payload):
    directory = _ack_ensure_directories(root)
    stage = ".ack-" + secrets.token_hex(16) + ".tmp"
    if sys.platform == "win32":
        # NOT EXECUTED on Windows in this remediation. Win32 rename reopens
        # the target directory, which conflicts with the guard's share mode,
        # so the guard validates before and after an exclusive stage+replace.
        from .windows_private_storage import validate_directory
        validate_directory(directory)
        target = directory / name
        try:
            existing = os.lstat(target)
        except FileNotFoundError:
            existing = None
        if existing is not None and (getattr(existing, "st_file_attributes", 0) & 0x400
                                     or not _ack_file_ok(existing)):
            raise Q06ReadOnlyError(_ACK_DENIED)
        fd = os.open(directory / stage, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                     | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOINHERIT", 0), 0o600)
        try:
            try:
                offset = 0
                while offset < len(payload):
                    count = os.write(fd, payload[offset:])
                    if count <= 0:
                        raise Q06ReadOnlyError(_ACK_DENIED)
                    offset += count
                os.fsync(fd)
            finally:
                os.close(fd)
            os.replace(directory / stage, target)
        except BaseException:
            try:
                os.unlink(directory / stage)
            except OSError:
                pass
            raise
        validate_directory(directory)
        return
    dfd = _ack_posix_directory(directory)
    fd = None
    staged = False
    try:
        try:
            existing = os.stat(name, dir_fd=dfd, follow_symlinks=False)
        except FileNotFoundError:
            existing = None
        if existing is not None and not _ack_file_ok(existing):
            raise Q06ReadOnlyError(_ACK_DENIED)
        fd = os.open(stage, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                     | os.O_CLOEXEC, 0o600, dir_fd=dfd)
        staged = True
        os.fchmod(fd, 0o600)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid():
            raise Q06ReadOnlyError(_ACK_DENIED)
        offset = 0
        while offset < len(payload):
            count = os.write(fd, payload[offset:])
            if count <= 0:
                raise Q06ReadOnlyError(_ACK_DENIED)
            offset += count
        os.fsync(fd)
        os.close(fd)
        fd = None
        os.rename(stage, name, src_dir_fd=dfd, dst_dir_fd=dfd)
        staged = False
        os.fsync(dfd)
    finally:
        if fd is not None:
            os.close(fd)
        try:
            if staged:
                os.unlink(stage, dir_fd=dfd)
        except OSError:
            pass
        finally:
            os.close(dfd)



class Bip39ReadOnlyBackend(ManagedWalletBackend):
    """All owned-Core and native-keychain calls execute on WalletExecutor thread."""

    def __init__(self, root, core, source, *, keychain=None, _anchor_factory=None, shared_profile=None):
        super().__init__(root, core, source, keychain=keychain,
                         _anchor_factory=_anchor_factory, shared_profile=shared_profile)
        self._seed_folder = None
        self._secret = None
        self._public = None
        self._spend_session = None
        self._resume_spend = False
        self._backup_challenge = None
        self._backup_epoch = 0

    def _invalidate_backup_challenge(self):
        self._backup_challenge = None
        self._backup_epoch += 1

    def _new_backup_challenge(self):
        # Serialized owner-session memory only. No mnemonic/answers persisted.
        self._backup_challenge = None
        if self._secret is None or self._seed_folder is None:
            raise Q06ReadOnlyError('Q06_GUI_BACKUP_VERIFY_LOCKED')
        positions = tuple(sorted(secrets.SystemRandom().sample(range(1, 13), 3)))
        identifier = secrets.token_hex(32)
        self._backup_challenge = (identifier, positions, self._seed_folder,
                                  self._backup_epoch, time.monotonic() + 120)
        return {'challenge_id': identifier, 'positions': positions,
                'expires_in_seconds': 120}

    def public_state(self):
        # Executor.state is the GUI's safety authority. Never conceal a
        # failed native spend session behind the unrelated control latch.
        s = self._spend_session
        p = self.owner.process if self.owner is not None else None
        bad = (self._control_fault
               or s is not None and (s.faulted or s._q06_uncertain))
        return {
            "locked": self._secret is None or s is not None and s.locked,
            "faulted": bool(bad),
            "reauthentication_required": bool(
                s is not None and getattr(s, "_core_reauthentication_required", False)),
            "core_alive": p is not None and p.poll() is None,
        }

    def _lock_q06(self):
        self._invalidate_backup_challenge()
        try:
            if self._spend_session is not None:
                session = self._spend_session
                self._resume_spend = False
                session.lock()  # uncertain runtime/session remains for review
                self._spend_session = None
                self._resume_spend = True
        finally:
            if self._secret is not None:
                self._secret[:] = bytes(len(self._secret))
                self._secret = None
            self._public = None
            self._seed_folder = None

    # Durable per-profile backup acknowledgement is stored in a NEW GUI-only
    # sidecar directory, never inside the encrypted seed vault or any existing
    # protected storage format.  A missing sidecar is treated as "unknown" so
    # pre-existing profiles (e.g. Q06 owner-probe fixtures, older test data)
    # continue to open normally; only an explicit `acknowledged=False` record
    # written by the GUI refusal path blocks reopen.
    def _q06_ack_dir(self):
        return self.root / "q06-gui-state" / "ack"

    def _q06_ack_path(self, folder):
        return self._q06_ack_dir() / _ack_name(folder)

    def _q06_read_ack(self, folder, secret=None):
        """Return (acknowledged, deferred, integrity).

        - (None, None, True) when no sidecar exists.
        - (False, True, True) for a legitimate deferred marker.
        - (True, False, True) for a verified acknowledged marker.
        - integrity=False for malformed, tampered or replaced sidecars.

        If `secret` is supplied and the sidecar claims acknowledgement, the
        stored MAC is verified; a bad MAC yields integrity=False.
        """
        try:
            raw = _ack_read(self._q06_ack_dir(), _ack_name(folder))
            if raw is None:
                return None, None, True
            data = json.loads(raw.decode("utf-8"))
            if (type(data) is not dict or not _ACK_REQUIRED <= set(data)
                    or not set(data) <= _ACK_REQUIRED | {"mac"}
                    or type(data["version"]) is not int or data["version"] != 1
                    or data["seed_id"] != folder.name
                    or type(data["acknowledged"]) is not bool
                    or type(data["deferred"]) is not bool
                    or data["acknowledged"] and data["deferred"]):
                return False, True, False
            acknowledged, deferred = data["acknowledged"], data["deferred"]
            mac = data.get("mac")
            if mac is not None and (not acknowledged or type(mac) is not str
                                    or re.fullmatch("[0-9a-f]{64}", mac) is None):
                return False, True, False
            if acknowledged and secret is not None:
                expected = hmac.new(secret, f"{folder.name}:acknowledged".encode(),
                                    "sha256").hexdigest()
                if mac is None or not hmac.compare_digest(mac, expected):
                    return False, True, False
            return acknowledged, deferred, True
        except Exception:
            return False, True, False

    def _q06_write_ack(self, folder, acknowledged, deferred=False, secret=None):
        name = _ack_name(folder)
        data = {"version": 1, "acknowledged": bool(acknowledged),
                "deferred": bool(deferred), "seed_id": folder.name}
        if acknowledged and secret is not None:
            data["mac"] = hmac.new(secret, f"{folder.name}:acknowledged".encode(),
                                   "sha256").hexdigest()
        try:
            _ack_write(self.root, name, json.dumps(data, separators=(',', ':')).encode())
        except Exception:
            # Not recorded: the caller fails closed and onboarding asks again.
            raise Q06ReadOnlyError(_ACK_DENIED) from None

    def _only_seed(self, owner):
        from .bip39_seed_vault import _folder
        if (owner.directory / "wallet-vault").exists() or (owner.root / "supervisor.wallet").exists():
            raise Q06ReadOnlyError("Q06_GUI_Q05_PROFILE_CONFLICT")
        matches = [p for p in owner.directory.iterdir()
                   if p.name.startswith("bip39-12-") and
                   not p.name.startswith("bip39-12-scan-")]
        if len(matches) != 1 or not matches[0].is_dir() or matches[0].is_symlink():
            raise Q06ReadOnlyError("Q06_GUI_SEED_PROFILE_AMBIGUOUS")
        _folder(matches[0])
        return matches[0]

    def _open_q06(self, password, mode, phrase=""):
        self._invalidate_backup_challenge()
        if (type(password) is not bytes or not 12 <= len(password) <= 1024
                or mode not in ("create", "restore", "reopen")
                or type(phrase) is not str):
            raise Q06ReadOnlyError("Q06_GUI_INPUT_DENIED")
        if self._secret is not None:
            raise Q06ReadOnlyError("Q06_GUI_ALREADY_OPEN")
        owner = self._core()
        # The ORIGINAL CoreSupervisor must initialize its fresh owner-only
        # namespace before the disposable macOS Keychain file is created.
        # Q05 uses the same deferred native-anchor boundary; precreating
        # the keychain in root makes CoreSupervisor reject a nonempty root.
        if self._anchor_factory is not None and not self._anchor_ready:
            self.keychain = self._anchor_factory(self.root)
            self._anchor_ready = True
        from .bip39_seed_vault import create_owned_seed_container, open_owned_seed_container
        from .bip39_12 import generate_phrase
        reveal = ""
        if mode in ("create", "restore"):
            if any(p.name.startswith("bip39-12-") for p in owner.directory.iterdir()):
                raise Q06ReadOnlyError("Q06_GUI_PROFILE_ALREADY_EXISTS")
            if mode == "create":
                if phrase:
                    raise Q06ReadOnlyError("Q06_GUI_PHRASE_NOT_EXPECTED")
                phrase = generate_phrase(authorized_disposable=True)
                reveal = phrase
                backup_status = "required"
            else:
                backup_status = "verified"
            folder, public = create_owned_seed_container(
                owner, self.source, password, phrase,
                authorized=True, keychain=self.keychain)
            # Generation-2 profiles require a durable acknowledgement sidecar
            # from birth.  Write a deferred marker now so a missing sidecar on
            # reopen is always detectable as tampering/incomplete onboarding,
            # while the GUI still treats the first session as "required" and
            # shows the 12-word grid.
            self._q06_write_ack(folder, False, deferred=True)
        else:
            if phrase:
                raise Q06ReadOnlyError("Q06_GUI_PHRASE_NOT_EXPECTED")
            # In-session unlock of the SAME original owned profile: the exact
            # authenticated reopen/acknowledge boundary used after a restart.
            return self._reopen_q06(password)
        self._secret = bytearray(password)
        self._seed_folder = folder
        self._public = public
        return {
            "profile": public["profile"], "account_id": public["account_id"],
            "receive_code": public["receive_code"],
            "status": "Q06_REGTEST_READ_ONLY_OWNER_OPENED",
            "mnemonic_once": reveal,
            "seed_folder": str(folder),
            "backup_status": backup_status,
            "checkpoint_present": (owner.directory / (
                'bip39-12-scan-' + folder.name.removeprefix('bip39-12-'))).exists(),
            "signer_allowed": False, "broadcast_allowed": False, "mainnet_allowed": False,
        }

    def _reopen_q06(self, password):
        """Authenticated in-session unlock of the SAME original REGTEST profile.

        Reuses the exact original owner/Keychain/acknowledge boundary as a
        restart reopen, so no mnemonic regeneration and no new profile is ever
        involved. Fail-closed on missing/tampered/deferred acknowledgement and
        clears partial in-memory custody on refusal.
        """
        self._invalidate_backup_challenge()
        owner = self._core()
        from .bip39_seed_vault import open_owned_seed_container
        folder = self._only_seed(owner)
        acknowledged, deferred, integrity = self._q06_read_ack(folder)
        if acknowledged is False and not deferred:
            raise Q06ReadOnlyError("Q06_GUI_BACKUP_ACK_REFUSED")
        with open_owned_seed_container(owner, folder, self.source, password,
                                       authorized=True, keychain=self.keychain) as keys:
            public = keys.public_metadata()
            secret = keys.backup_ack_key()
            generation = getattr(keys, "_q06_generation", 1)
        if generation >= 2:
            # New onboarding profiles require a trustworthy acknowledgement
            # record.  A missing or corrupt sidecar is treated as
            # tampering/incomplete onboarding and fails closed.
            if not integrity:
                self._lock_q06()
                raise Q06ReadOnlyError("Q06_GUI_BACKUP_ACK_TAMPERED")
            if acknowledged is None:
                self._lock_q06()
                raise Q06ReadOnlyError("Q06_GUI_BACKUP_ACK_REQUIRED")
            if acknowledged is True:
                re_ack, _, re_integrity = self._q06_read_ack(folder, secret)
                if not re_ack or not re_integrity:
                    self._lock_q06()
                    raise Q06ReadOnlyError("Q06_GUI_BACKUP_ACK_TAMPERED")
        if acknowledged is True:
            backup_status = "verified"
        elif acknowledged is False and deferred:
            backup_status = "deferred"
        else:
            # Legacy generation-1 profiles or pre-existing unversioned
            # profiles are grandfathered.
            backup_status = "verified"
        self._secret = bytearray(password)
        self._seed_folder = folder
        self._public = public
        return {
            "profile": public["profile"], "account_id": public["account_id"],
            "receive_code": public["receive_code"],
            "status": "Q06_REGTEST_READ_ONLY_OWNER_OPENED",
            "mnemonic_once": "",
            "seed_folder": str(folder),
            "backup_status": backup_status,
            "checkpoint_present": (owner.directory / (
                'bip39-12-scan-' + folder.name.removeprefix('bip39-12-'))).exists(),
            "signer_allowed": False, "broadcast_allowed": False, "mainnet_allowed": False,
        }

    def _fund_q06(self):
        """Explicit once-only signed-Core REGTEST receive fixture.

        Reuse Q05's *existing* public-transaction fixture to pay THIS
        BIP39-derived silent receive code; NEVER use Q05 Keyring or signer.
        This is not a generic mining RPC command or a product Send feature.
        """
        if self._secret is None or self._public is None or self._seed_folder is None:
            raise Q06ReadOnlyError("Q06_GUI_LOCKED")
        from .managed_wallet_checkpoint import _owned
        from .wallet_session import WalletCoreCli
        from .wsp_live import public_regtest_mining_address
        from .regtest_funding import fund_checkpoint_fixture
        owner=self._core()
        _owned(owner)
        seed_id=self._seed_folder.name.removeprefix("bip39-12-")
        if (owner.directory / ("bip39-12-scan-" + seed_id)).exists():
            raise Q06ReadOnlyError("Q06_GUI_ANCHORED_SCANNER_REQUIRES_RECONCILIATION")
        rpc=WalletCoreCli(owner.cli,owner.directory)
        fixture_record={}
        funding_phase="PREFLIGHT"
        try:
            rpc.attest()  # exact signed Core v0.1.13, chain and zero peers
            if rpc.call("getblockcount") != 0:
                raise Q06ReadOnlyError("Q06_GUI_TEST_FUNDING_FRESH_CHAIN_ONLY")
            address=public_regtest_mining_address(self.source)
            funding_phase="FIXTURE"
            txid, atoms, height = fund_checkpoint_fixture(
                rpc, self._public["receive_code"], address, fixture_record)
            funding_phase="POSTCHECK_OWNER"
            _owned(owner)
            funding_phase="POSTCHECK_RESULT"
            if (type(txid) is not str or not re.fullmatch("[0-9a-f]{64}",txid)
                    or type(atoms) is not int or atoms<=0
                    or type(height) is not int or height<102):
                raise Q06ReadOnlyError("Q06_GUI_TEST_FUNDING_UNVERIFIED")
            funding_phase="POSTCHECK_HEIGHT"
            # The fixture closes its WalletCoreCli HTTP transport after funding.
            # Reusing that terminal session would reject a valid confirmed payment.
            # The original CoreSupervisor read transport was just re-attested by _owned.
            if owner.read.call("getblockcount")!=height:
                raise Q06ReadOnlyError("Q06_GUI_TEST_FUNDING_UNVERIFIED")
            return {"status":"Q06_REGTEST_PUBLIC_BIP39_RECEIVE_FUNDED",
                    "txid":txid,"atoms":atoms,"height":height,
                    "signer_allowed":False,"broadcast_allowed":False,
                    "mainnet_allowed":False}
        except Q06ReadOnlyError:
            raise
        except Exception:
            # Only fixed, non-secret stage categories are emitted. A Core write
            # may have completed: preserve the original fail-closed no-retry rule.
            if funding_phase=="FIXTURE":
                detail=fixture_record.get("fixture_funding_failure")
                observed=detail.get("stage") if type(detail) is dict else None
                failure_stage={"attestation":"FIXTURE_ATTESTATION",
                               "generation":"GENERATION",
                               "payment":"PAYMENT"}.get(observed,"FIXTURE_UNCLASSIFIED")
            else:
                failure_stage=funding_phase if funding_phase in (
                    "PREFLIGHT","POSTCHECK_OWNER","POSTCHECK_RESULT","POSTCHECK_HEIGHT") else "UNCLASSIFIED"
            if sys.platform=="darwin":
                print("MACOS_Q06_FUNDING_FAILURE_STAGE="+failure_stage,flush=True)
            raise Q06ReadOnlyError("Q06_GUI_TEST_FUNDING_UNCERTAIN") from None
        finally:
            if getattr(rpc,"_transport",None) is not None:rpc._transport.close()


    def _activate_q06(self):
        """Explicit full REGTEST session: verify native checkpoint before Send."""
        if self._spend_session is not None:
            raise Q06ReadOnlyError("Q06_GUI_ALREADY_ACTIVATED")
        if self._secret is None or self._seed_folder is None:
            raise Q06ReadOnlyError("Q06_GUI_LOCKED")
        from .bip39_spend_session import open_owned_spend_session
        session = open_owned_spend_session(
            self._core(), self._seed_folder, self.source,
            bytes(self._secret), authorized=True, keychain=self.keychain)
        try:
            if (sys.platform == 'darwin' and os.environ.get('GITHUB_ACTIONS') == 'true'
                    and os.environ.get('WAM_Q06_CI_SPEND_QUALIFY') == '1'):
                print('MACOS_Q06_SPEND_OPEN_SESSION_PASS', flush=True)
            state = session.snapshot()
            if (state.signer_allowed is not True
                    or state.broadcast_allowed is not True
                    or state.mainnet_allowed is not False
                    or state.receive_code != self._public["receive_code"]):
                raise Q06ReadOnlyError("Q06_GUI_SPEND_SCOPE_DENIED")
        except Exception:
            # If a snapshot became uncertain, preserve its runtime and anchors;
            # the failed session is not silently replaced by read-only scanning.
            try:
                session.lock()
            except Exception:
                pass
            raise Q06ReadOnlyError("Q06_GUI_SPEND_ACTIVATION_DENIED") from None
        self._spend_session = session
        if (sys.platform == 'darwin' and os.environ.get('GITHUB_ACTIONS') == 'true'
                and os.environ.get('WAM_Q06_CI_SPEND_QUALIFY') == '1'):
            print('MACOS_Q06_SPEND_INITIAL_SNAPSHOT_PASS', flush=True)
        return self._session_snapshot()

    def _session_snapshot(self, history_offset=0):
        if self._spend_session is None:
            raise Q06ReadOnlyError("Q06_GUI_SPEND_NOT_ACTIVE")
        from wam_sp.wallet import Wallet
        session = self._spend_session
        item = session.snapshot() if history_offset == 0 else session.snapshot(history_offset=history_offset)
        available = Wallet(session.scanner).balance()["available_atoms"]
        return {
            "status": "Q06_REGTEST_BIP39_OWNED_SPEND_VERIFIED",
            "profile": self._public["profile"],
            "account_id": self._public["account_id"],
            "receive_code": item.receive_code,
            "height": item.height, "tip": item.tip,
            "confirmed_atoms": item.confirmed_atoms,
            "available_atoms": available,
            "history_count_shown": len(item.history),
            "history": tuple({
                "txid": h.txid, "height": h.block_height,
                "atoms": h.credit_atoms - h.debit_atoms
            } for h in item.history),
            "reservation_count": item.reservation_count,
            "payment_review": session._review,
            "payment_signed": session._signed is not None,
            "recovered_unsigned_cancel_available": session.recovered_unsigned_cancel_available(),
            "pending_confirm_txid": session._q06_pending_confirm,
            # Same verified WalletReadSnapshot consumed by existing Fusion UI.
            # No duplicate scanner, signer or new custody/session authority.
            "fusion_snapshot": item,
            "signer_allowed": True, "broadcast_allowed": True,
            "mainnet_allowed": False,
        }

    def _confirm_spend_ci(self):
        """One explicit test-only block on the original owned REGTEST Core."""
        if (sys.platform != "darwin"
                or os.environ.get("GITHUB_ACTIONS") != "true"
                or os.environ.get("WAM_Q06_CI_SPEND_QUALIFY") != "1"
                or self._spend_session is None):
            raise Q06ReadOnlyError("Q06_GUI_CONFIRM_CI_SCOPE_DENIED")
        from .managed_wallet_checkpoint import _owned
        from .wallet_session import WalletCoreCli
        from .wsp_live import public_regtest_mining_address
        owner = self._core()
        _owned(owner)
        cli = WalletCoreCli(owner.cli, owner.directory)
        try:
            cli.attest()
            before = cli.call("getblockcount")
            cli._call("generatetoaddress", ["1", public_regtest_mining_address(self.source)])
            _owned(owner)
            after = owner.read.call("getblockcount")
            if after != before + 1:
                raise Q06ReadOnlyError("Q06_GUI_CONFIRM_CI_HEIGHT_DENIED")
            return {"status": "Q06_REGTEST_CI_BLOCK_CONFIRMED", "height": after}
        except Q06ReadOnlyError:
            raise
        except Exception:
            raise Q06ReadOnlyError("Q06_GUI_CONFIRM_CI_UNCERTAIN") from None
        finally:
            if getattr(cli, "_transport", None) is not None:
                cli._transport.close()

    def _scan_q06(self, history_offset=0):
        if self._spend_session is not None:
            return self._session_snapshot() if history_offset == 0 else self._session_snapshot(history_offset)
        if self._seed_folder is None or self._secret is None:
            raise Q06ReadOnlyError("Q06_GUI_LOCKED")
        from .managed_wallet_checkpoint import _owned
        from .bip39_seed_vault import open_owned_seed_container
        from .wallet_session import WalletCoreCli
        from . import custody
        from .managed_wallet_session import RuntimeGuard
        from wam_sp.scanner import Scanner
        from wam_sp.wallet import Wallet
        owner = self._core()
        _owned(owner)
        wallet_id = self._seed_folder.name.removeprefix("bip39-12-")
        # Never ignore a protected scanner snapshot (which might carry
        # irreversible signed/uncertain reservations) to obtain a false balance.
        if (owner.directory / ("bip39-12-scan-" + wallet_id)).exists():
            raise Q06ReadOnlyError("Q06_GUI_ANCHORED_SCANNER_REQUIRES_RECONCILIATION")
        runtime_dir = owner.directory / ("q06-view-" + secrets.token_hex(16))
        custody.create_directory(runtime_dir)
        db_path = runtime_dir / "wallet-runtime.sqlite"
        scanner = guard = rpc = keys = None
        verified = False
        try:
            keys = open_owned_seed_container(owner, self._seed_folder, self.source,
                                             bytes(self._secret), authorized=True,
                                             keychain=self.keychain)
            # Windows SQLite must be created with native owner-only ACLs
            # BEFORE Scanner opens it, exactly as in the Q06 spend path.
            # Do not relax RuntimeGuard's Windows security verification.
            if sys.platform == "win32":
                from .windows_private_storage import create_managed_runtime
                create_managed_runtime(db_path)
            scanner = Scanner(db_path, keys.accounts())
            guard = RuntimeGuard(db_path)
            rpc = WalletCoreCli(owner.cli, owner.directory)
            rpc.attest()
            scanner.sync(rpc)
            scanner.assert_current()
            tip = scanner.store.tip()
            if (rpc.call("getblockcount"), rpc.call("getbestblockhash")) != tip:
                raise Q06ReadOnlyError("Q06_GUI_CORE_TIP_CHANGED")
            wallet = Wallet(scanner)
            balance = wallet.balance()
            history = wallet.history(limit=10)
            from .wallet_read import WalletReadSnapshot, HistoryRow
            from .history_pages import GUI_HISTORY_LIMIT
            with scanner.store.transaction():
                total = scanner.store.db.execute(
                    "SELECT count(*) FROM history").fetchone()[0]
                receives = scanner.store.db.execute(
                    "SELECT count(*) FROM history WHERE credit>0").fetchone()[0]
                verified_rows = scanner.store.db.execute(
                    "SELECT txid,height,credit,debit FROM history "
                    "ORDER BY height DESC,txid DESC LIMIT ? OFFSET ?", (GUI_HISTORY_LIMIT, history_offset)
                ).fetchall()
            if (type(total) is not int or total<0
                    or type(receives) is not int or not 0<=receives<=total
                    or len(verified_rows)>total):
                raise Q06ReadOnlyError("Q06_GUI_HISTORY_UNVERIFIED")
            structured = []
            for txid,block,credit,debit in verified_rows:
                if (type(txid) is not str or re.fullmatch(r"[0-9a-f]{64}",txid) is None
                        or type(block) is not int or not 1<=block<=tip[0]
                        or type(credit) is not int or credit<0
                        or type(debit) is not int or debit<0):
                    raise Q06ReadOnlyError("Q06_GUI_HISTORY_UNVERIFIED")
                structured.append(HistoryRow(txid,block,tip[0]-block+1,credit,debit))
            fusion = WalletReadSnapshot(
                chain="regtest", height=tip[0], tip=tip[1],
                receive_code=self._public["receive_code"],
                confirmed_atoms=balance["confirmed_atoms"],
                confirmed_utxos=len(scanner.coins()),
                history=tuple(structured),
                core_sha256=owner.receipt["wamd_sha256"],
                history_count=total, receive_count=receives,
                history_complete=history_offset == 0 and total<=GUI_HISTORY_LIMIT,
                history_offset=history_offset,
            )
            _owned(owner)
            guard.check()
            result = {
                "status": "Q06_REGTEST_REAL_CORE_READ_ONLY_VERIFIED",
                "profile": self._public["profile"],
                "account_id": self._public["account_id"],
                "receive_code": self._public["receive_code"],
                "height": tip[0], "tip": tip[1],
                "confirmed_atoms": balance["confirmed_atoms"],
                "available_atoms": balance["available_atoms"],
                "history_count_shown": len(history),
                "history": tuple({"txid":h.get("txid"), "height":h.get("height"),
                                  "atoms":h.get("atoms")} for h in history),
                "fusion_snapshot": fusion,
                "signer_allowed": False, "broadcast_allowed": False,
                "mainnet_allowed": False,
            }
            verified = True
            return result
        except Exception:
            raise Q06ReadOnlyError("Q06_GUI_READ_ONLY_SYNC_DENIED") from None
        finally:
            if scanner is not None:scanner.close()
            if rpc is not None and getattr(rpc, "_transport", None) is not None:
                rpc._transport.close()
            if keys is not None:keys.close()
            if guard is not None:
                try:
                    if verified:
                        # Pinned WSP scanner lock is persistent by design. Remove
                        # only our own known lease file after worker/SQLite exit.
                        lock = db_path.with_name(db_path.name + ".scan.lock")
                        if lock.exists() or lock.is_symlink():
                            info = lock.lstat()
                            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                                    or lock.is_symlink()
                                    or (sys.platform != "win32" and
                                        (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600))):
                                raise Q06ReadOnlyError("Q06_GUI_SCANNER_LOCK_UNCERTAIN")
                            lock.unlink()
                        guard.remove_owned()
                        runtime_dir.rmdir()
                    else:
                        guard.close()
                except (OSError, ValueError, RuntimeError):
                    # On cleanup uncertainty, preserve file and fail closed.
                    guard.close()
                    raise Q06ReadOnlyError("Q06_GUI_RUNTIME_PRESERVED") from None

    def execute(self, action, args, kwargs):
        result = self._execute_q06(action,args,kwargs)
        if self.shared_profile is not None and type(result) is dict and action in ('snapshot','activate','unlock'):
            from .shared_regtest import peer_status
            result['shared_network'] = peer_status(self._core().directory)
        return result

    def _execute_q06(self, action, args, kwargs):
        if action == 'reconcile_reorg':
            if (self.shared_profile is None or kwargs or len(args)!=1 or type(args[0]) is not bytes):
                raise Q06ReadOnlyError('Q06_SHARED_RECONCILIATION_DENIED')
            from .bip39_seed_vault import open_owned_seed_container
            from .bip39_reconciliation import reconcile_shared
            owner=self._core();folder=self._only_seed(owner);password=args[0]
            # Authenticate backup/profile BEFORE closing any current custody.
            with open_owned_seed_container(owner,folder,self.source,password,
                    authorized=True,keychain=self.keychain) as keys:
                acknowledged,_,integrity=self._q06_read_ack(folder,keys.backup_ack_key())
                if acknowledged is not True or not integrity:
                    raise Q06ReadOnlyError('Q06_GUI_BACKUP_ACK_REQUIRED')
            previous=self._spend_session
            if previous is not None:
                if not previous.faulted:
                    raise Q06ReadOnlyError('Q06_RECONCILIATION_NOT_NEEDED')
                try:previous.lock()
                except ValueError as error:
                    if error.args!=('Q06_SPEND_RUNTIME_PRESERVED',) or not previous.locked:raise
            try:
                proof=reconcile_shared(owner,folder,self.source,password,authorized=True,keychain=self.keychain)
                self._spend_session=None
                self._resume_spend=False
                if self._secret is not None:self._secret[:]=bytes(len(self._secret))
                self._secret=self._public=self._seed_folder=None
                opened=self._reopen_q06(password)
                return dict(opened,reconciliation=proof)
            except Exception:
                self._spend_session=previous
                if self._secret is not None:self._secret[:]=bytes(len(self._secret))
                self._secret=self._public=self._seed_folder=None
                raise Q06ReadOnlyError('Q06_SHARED_RECONCILIATION_DENIED') from None
        if action in ('network_status', 'network_active', 'core_start', 'core_status'):
            return super().execute(action, args, kwargs)
        if self.shared_profile is not None and action in ('prepare','sign','broadcast','mine','confirm','ci_confirm'):
            from .shared_regtest import peer_status
            if action in ('mine','confirm','ci_confirm') and not self.shared_profile.coordinator:
                raise Q06ReadOnlyError('SHARED_SINGLE_COORDINATOR_REQUIRED')
            peer_status(self._core().directory, require_connected=True)
        if action == "ci_confirm":
            if args or kwargs:
                raise Q06ReadOnlyError("Q06_GUI_CONFIRM_CI_ARGUMENTS_DENIED")
            return self._confirm_spend_ci()
        if action == "activate":
            if args or kwargs:
                raise Q06ReadOnlyError("Q06_GUI_ACTIVATE_ARGUMENTS_DENIED")
            return self._activate_q06()
        if action == "confirm":
            if kwargs or len(args) != 1 or self._spend_session is None:
                raise Q06ReadOnlyError("Q06_GUI_CONFIRM_ARGUMENTS_DENIED")
            return self._spend_session.confirm_pending(args[0])
        if action == "recovery_verify":
            if (kwargs or len(args) != 1 or self._secret is None
                    or self._spend_session is None):
                raise Q06ReadOnlyError("Q06_GUI_RECOVERY_PROOF_ARGS_DENIED")
            from .bip39_recovery_proof import verify_mnemonic_on_original_chain
            baseline = self._spend_session.snapshot()
            return verify_mnemonic_on_original_chain(
                self._core(), self.source, args[0], baseline)
        if action == "inspect_confirmed":
            # Post-reopen observation only. NO replay, mining, signature,
            # reservation clearing or inference from an absent txid.
            if (kwargs or len(args) != 1 or type(args[0]) is not str
                    or re.fullmatch(r"[0-9a-f]{64}", args[0]) is None
                    or self._spend_session is None
                    or self.public_state()["faulted"]):
                raise Q06ReadOnlyError("Q06_GUI_INSPECT_ARGUMENTS_DENIED")
            return self._spend_session.inspect_confirmed(args[0])
        if action in ("prepare", "sign", "broadcast", "cancel"):
            if kwargs or self._spend_session is None:
                raise Q06ReadOnlyError("Q06_GUI_SPEND_NOT_ACTIVE")
            expected = {"prepare": 3, "sign": 1, "broadcast": 1, "cancel": 0}
            if len(args) != expected[action]:
                raise Q06ReadOnlyError("Q06_GUI_SPEND_ARGUMENTS_DENIED")
            session = self._spend_session
            return getattr(session, action)(*args)
        if action == "unlock":
            # In-session Lock -> Unlock of the SAME original owned REGTEST
            # profile. Requires an explicit (non-recovery) authenticated
            # password; the reopen revalidates owner identity, native Keychain,
            # anchored checkpoint and backup acknowledgement on the live Core.
            if kwargs or len(args) != 2 or args[1] is not False:
                raise Q06ReadOnlyError("Q06_GUI_UNLOCK_ARGUMENTS_DENIED")
            if self._secret is not None:
                raise Q06ReadOnlyError("Q06_GUI_ALREADY_UNLOCKED")
            opened = self._reopen_q06(args[0])
            if self._resume_spend and opened['backup_status'] == 'verified':
                try:
                    verified = self._activate_q06()
                    return dict(opened, **verified)
                except Exception:
                    self._resume_spend = False
                    self._lock_q06()
                    raise Q06ReadOnlyError('Q06_GUI_UNLOCK_RECONCILIATION_DENIED') from None
            return opened
        if action == "open":
            if kwargs or len(args) != 3:
                raise Q06ReadOnlyError("Q06_GUI_OPEN_ARGUMENTS_DENIED")
            return self._open_q06(*args)
        if action == "acknowledge_create_pending":
            # GUI is about to show the phrase. Write a deferred marker so a
            # crash before the user completes backup cannot be mistaken for an
            # acceptance, while still allowing later completion on reopen.
            if kwargs or len(args) != 1:
                raise Q06ReadOnlyError("Q06_GUI_ACK_PENDING_ARGUMENTS_DENIED")
            folder = Path(args[0])
            if folder != self._seed_folder:
                raise Q06ReadOnlyError("Q06_GUI_ACK_FOLDER_MISMATCH")
            self._q06_write_ack(folder, False, deferred=True)
            return None
        if action == "backup_defer":
            if args or kwargs:
                raise Q06ReadOnlyError("Q06_GUI_BACKUP_DEFER_ARGS_DENIED")
            if self._seed_folder is None:
                raise Q06ReadOnlyError("Q06_GUI_BACKUP_DEFER_NO_SEED")
            self._q06_write_ack(self._seed_folder, False, deferred=True)
            self._lock_q06()
            return None
        if action == 'backup_challenge_cancel':
            self._invalidate_backup_challenge()
            if args or kwargs:
                raise Q06ReadOnlyError('Q06_GUI_BACKUP_CHALLENGE_ARGS_DENIED')
            return None
        if action == 'backup_challenge':
            self._backup_challenge = None
            if args or kwargs:
                raise Q06ReadOnlyError('Q06_GUI_BACKUP_CHALLENGE_ARGS_DENIED')
            return self._new_backup_challenge()
        if action == "backup_verify":
            # Consume BEFORE validation/decryption/ack write: wrong answers,
            # exceptions and concurrent/replayed submissions cannot reuse it.
            challenge, self._backup_challenge = self._backup_challenge, None
            if kwargs or len(args) != 2:
                raise Q06ReadOnlyError("Q06_GUI_BACKUP_VERIFY_ARGS_DENIED")
            identifier, answers = args
            if (type(identifier) is not str or not re.fullmatch('[0-9a-f]{64}', identifier)
                    or type(answers) not in (tuple, list) or len(answers) != 3
                    or not all(type(a) is str and 1 <= len(a) <= 32 and a.strip() for a in answers)):
                raise Q06ReadOnlyError("Q06_GUI_BACKUP_VERIFY_INPUT_DENIED")
            if self._seed_folder is None or self._secret is None:
                raise Q06ReadOnlyError("Q06_GUI_BACKUP_VERIFY_LOCKED")
            if (challenge is None or not hmac.compare_digest(identifier, challenge[0])
                    or challenge[2] != self._seed_folder or challenge[3] != self._backup_epoch
                    or time.monotonic() >= challenge[4]):
                raise Q06ReadOnlyError('Q06_GUI_BACKUP_CHALLENGE_DENIED')
            positions = challenge[1]
            from .bip39_seed_vault import (
                _owner_binding, open_owned_seed_container, read_seed_phrase)
            owner = self._core()
            decoded_password = bytes(self._secret).decode("utf-8")
            phrase = read_seed_phrase(
                self._seed_folder, self.source, decoded_password,
                keychain=self.keychain, owner_binding=_owner_binding(owner))
            words = phrase.split()
            phrase = None
            try:
                if len(words) != 12:
                    raise Q06ReadOnlyError("Q06_GUI_BACKUP_VERIFY_PHRASE_DENIED")
                normalized = [a.strip().lower() for a in answers]
                if any(normalized[i] != words[positions[i] - 1].lower()
                       for i in range(len(positions))):
                    return False
                with open_owned_seed_container(
                        owner, self._seed_folder, self.source,
                        bytes(self._secret), authorized=True,
                        keychain=self.keychain) as keys:
                    secret = keys.backup_ack_key()
                if time.monotonic() >= challenge[4]:
                    raise Q06ReadOnlyError('Q06_GUI_BACKUP_CHALLENGE_DENIED')
                self._q06_write_ack(self._seed_folder, True, secret=secret)
                return True
            except Exception:
                raise Q06ReadOnlyError("Q06_GUI_BACKUP_VERIFY_DENIED") from None
        if action == "snapshot":
            from .history_pages import HISTORY_OFFSET_MAX
            if (kwargs or len(args) > 1 or args and
                    (type(args[0]) is not int or not 0 <= args[0] <= HISTORY_OFFSET_MAX)):
                raise Q06ReadOnlyError("Q06_GUI_SYNC_ARGUMENTS_DENIED")
            return self._scan_q06(args[0]) if args else self._scan_q06()
        if action == "mine":
            if args or kwargs:raise Q06ReadOnlyError("Q06_GUI_FUND_ARGUMENTS_DENIED")
            return self._fund_q06()
        if action == "lock":
            if args or kwargs:raise Q06ReadOnlyError("Q06_GUI_LOCK_ARGUMENTS_DENIED")
            self._lock_q06();return None
        if action == "quit":
            self._lock_q06()
            return super().execute(action, args, kwargs)
        if action == "control":
            self._lock_q06() if args and args[0] != "status" else None
            return super().execute(action, args, kwargs)
        raise Q06ReadOnlyError("Q06_GUI_SPENDING_NOT_IMPLEMENTED")
