"""Q06 REGTEST BIP39 spend-session integration with the existing Q05 engine.

Reuse WalletSession's intent/UTXO verified Prepare->Sign->Broadcast engine.
Only native authenticated scanner generations are authoritative. No mainnet,
no seed migration and no automatic uncertain-reservation repair.

This module is not a release/owner-acceptance grant. Activation requires an
explicit owned-Core caller and must be separately tested on frozen macOS.
"""
import os
from pathlib import Path
import secrets
import stat
import sys

from . import custody
from .managed_wallet_checkpoint import _owned, _runtime
from .managed_wallet_session import RuntimeGuard
from .wallet_session import WalletSession, WalletSessionError, WalletCoreCli
from .bip39_seed_vault import (
    _owned_password, _owner_binding, open_owned_seed_container,
)
from .bip39_native_checkpoint import (
    _directory, _native, _scanner_anchor_record, _require_confirmed_descendant,
    advance_owned_candidate, publish_owned_candidate, read_owned_candidate,
)
from .bip39_scanner_checkpoint import (
    decode_candidate, require_irreversible_preserved,
)
from wam_sp.scanner import Scanner


class Q06SpendSessionError(ValueError):
    """Public bounded error. Never interpolate secrets, paths or RPC details."""


def _reservation_map(scanner):
    rows = scanner.store.db.execute(
        "SELECT txid,vout,token,state,created FROM reservations").fetchall()
    if len(rows) != len({(v[0], v[1]) for v in rows}):
        raise Q06SpendSessionError("Q06_SPEND_RESERVATION_DUPLICATE")
    return {(v[0], v[1]): (v[2], v[3], v[4]) for v in rows}


def _remove_known_scanner_lock(path):
    lock = path.with_name(path.name + ".scan.lock")
    if lock.exists() or lock.is_symlink():
        info = lock.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or lock.is_symlink()
                or (sys.platform != "win32"
                    and (info.st_uid != os.geteuid()
                         or stat.S_IMODE(info.st_mode) != 0o600))):
            raise Q06SpendSessionError("Q06_SPEND_SCAN_LOCK_UNCERTAIN")
        lock.unlink()


class _Q06NativeScannerVault:
    """Persist only BIP39 scanner state, never Q05's 32-byte Keyring format."""

    def __init__(self, owner, seed_folder, source, password, keychain):
        seed_id, folder = _directory(owner, seed_folder)
        _, self.anchor = _native(folder, seed_id, source, keychain)
        self.directory = folder
        self._expected = _scanner_anchor_record(self.anchor.read())
        self.owner, self.seed_folder, self.source = owner, seed_folder, source
        self.password, self.keychain = password, keychain

    def save(self, keys, scanner, password):
        if (password != self.password
                or keys.accounts() != scanner.accounts
                or self.anchor.read() != self._expected):
            raise Q06SpendSessionError("Q06_SPEND_STALE_ANCHOR_OR_ACCOUNT")
        receipt = advance_owned_candidate(
            self.owner, self.seed_folder, scanner, self.source, password,
            authorized=True, keychain=self.keychain,
            anchor_override=self.anchor)
        updated = _scanner_anchor_record(self.anchor.read())
        if (updated[0] != self._expected[0] + 1
                or receipt["generation"] != updated[0]
                or receipt["signer_allowed"] is not False):
            raise Q06SpendSessionError("Q06_SPEND_CHECKPOINT_AUTHORITY_DENIED")
        self._expected = updated


class Q06OwnedSpendSession(WalletSession):
    """Use Q05's transaction methods but Q06's independent native checkpoint."""

    def __init__(self, owner, source, keys, scanner, guard, vault, password):
        super().__init__(
            owner.core, owner.directory, source, keys, scanner, vault, password,
            mining_address=None, core_cli=owner.cli, core_receipt=owner.receipt)
        self._q06_owner = owner
        self._q06_guard = guard
        self._q06_uncertain = False

    def _rpc(self):
        if self._q06_uncertain:
            raise WalletSessionError("Q06_SPEND_UNCERTAIN_LOCK_RETAINED")
        _owned(self._q06_owner)
        self._q06_guard.check()
        return super()._rpc()

    def _save(self):
        try:
            _owned(self._q06_owner)
            self._q06_guard.check()
            self.vault.save(self.ring, self.scanner, self._password)
        except Exception:
            # An irreversible action may precede the failed publication.
            # Never discard this SQLite, recreate the Core, or unlock drafts.
            self._q06_uncertain = self.faulted = True
            raise WalletSessionError("Q06_SPEND_ANCHORED_SAVE_DENIED") from None

    def lock(self):
        if self.locked:
            return
        try:
            self._close_rpc()
            self.scanner.close()
            self.ring.close()
            if (self._q06_uncertain or self.faulted
                    or self.vault.anchor.read() != self.vault._expected):
                raise Q06SpendSessionError("Q06_SPEND_RUNTIME_UNCERTAIN")
            self._q06_guard.check()
            _remove_known_scanner_lock(self.runtime)
            self._q06_guard.remove_owned()
        except Exception:
            self._q06_uncertain = True
            raise Q06SpendSessionError("Q06_SPEND_RUNTIME_PRESERVED") from None
        finally:
            # Secrets close even if the guarded SQLite must remain for review.
            self._q06_guard.close()
            self.ring = self.scanner = self._password = None
            self._prepared = self._signed = self._review = self._tip = None

    def backup(self, *args, **kwargs):
        raise Q06SpendSessionError("Q06_SPEND_Q05_BACKUP_FORMAT_DENIED")

    def recover_backup(self, *args, **kwargs):
        raise Q06SpendSessionError("Q06_SPEND_Q05_BACKUP_FORMAT_DENIED")

    def unlock(self, *args, **kwargs):
        raise Q06SpendSessionError("Q06_SPEND_EXPLICIT_OWNED_REOPEN_REQUIRED")


def open_owned_spend_session(owner, seed_folder, source, password, *,
                             authorized=False, keychain=None):
    """Authenticate owned Core + seed + anchored scanner before any signer.

    A new profile may publish its first checkpoint only when its native
    namespace has no scanner history. An existing checkpoint MUST be restored
    into a fresh protected runtime and resynced with the same-chain Core.
    """
    _owned_password(owner, source, password, authorized)
    _owned(owner)
    keys = scanner = guard = rpc = None
    transferred = False
    phase = 'SEED_AUTH'
    try:
        keys = open_owned_seed_container(
            owner, seed_folder, source, password,
            authorized=authorized, keychain=keychain)
        phase = 'RUNTIME_PREFLIGHT'
        # Any leftover prior native runtime is ambiguous after a crash.
        # Deny implicit replay/recovery rather than creating a parallel signer.
        import re
        if any(re.fullmatch(
                r"wallet-runtime-recovery-[0-9a-f]{16}\.sqlite"
                r"(?:-journal|-wal|-shm|\.scan\.lock)?", p.name)
               for p in owner.directory.iterdir()):
            raise Q06SpendSessionError("Q06_SPEND_PRIOR_RUNTIME_UNCERTAIN")
        name = "wallet-runtime-recovery-" + secrets.token_hex(8) + ".sqlite"
        target = _runtime(owner, name)
        if sys.platform == "win32":
            from .windows_private_storage import create_managed_runtime
            create_managed_runtime(target)
        phase = 'SCANNER_CREATE'
        scanner = Scanner(target, keys.accounts())
        phase = 'SCANNER_GUARD'
        guard = RuntimeGuard(target)
        phase = 'RPC_ATTEST'
        rpc = WalletCoreCli(owner.cli, owner.directory)
        rpc.attest()
        phase = 'CHECKPOINT_DIRECTORY'
        seed_id, folder = _directory(owner, seed_folder)
        if folder.exists() or folder.is_symlink():
            phase = 'CHECKPOINT_RESTORE'
            previous, receipt = read_owned_candidate(
                owner, seed_folder, source, password,
                authorized=authorized, keychain=keychain,
                allow_descendant=True)
            before = (receipt["height"], receipt["tip"])
            _require_confirmed_descendant(owner, before, (
                rpc.call("getblockcount"), rpc.call("getbestblockhash")))
            decoded = decode_candidate(
                keys, scanner, previous, password.decode("utf-8"),
                owner_binding=_owner_binding(owner))
            if ((decoded["claimed_height"], decoded["claimed_tip"]) != before
                    or decoded["account_id"] != keys.public_metadata()["account_id"]):
                raise Q06SpendSessionError("Q06_SPEND_RESTORE_PROFILE_DENIED")
            locked = _reservation_map(scanner)
            scanner.sync(rpc)
            scanner.assert_current()
            require_irreversible_preserved(locked, _reservation_map(scanner))
            _require_confirmed_descendant(owner, before, scanner.store.tip())
            if scanner.store.tip() != (
                    rpc.call("getblockcount"), rpc.call("getbestblockhash")):
                raise Q06SpendSessionError("Q06_SPEND_CORE_CHANGED")
            # Resync to descendant was never an authorization to drop locks.
            if scanner.store.tip() != before:
                advance_owned_candidate(
                    owner, seed_folder, scanner, source, password,
                    authorized=True, keychain=keychain)
        else:
            phase = 'INITIAL_SCANNER_SYNC'
            scanner.sync(rpc)
            scanner.assert_current()
            if scanner.store.tip() != (
                    rpc.call("getblockcount"), rpc.call("getbestblockhash")):
                raise Q06SpendSessionError("Q06_SPEND_CORE_CHANGED")
            phase = 'INITIAL_NATIVE_PUBLISH'
            publish_owned_candidate(
                owner, seed_folder, scanner, source, password,
                authorized=True, keychain=keychain)
        phase = 'NATIVE_VAULT_OPEN'
        vault = _Q06NativeScannerVault(
            owner, seed_folder, source, password, keychain)
        guard.check()
        _owned(owner)
        phase = 'SESSION_CONSTRUCTION'
        session = Q06OwnedSpendSession(
            owner, source, keys, scanner, guard, vault, password)
        # Require both the source and Q05 transaction engine to re-observe
        # the exact native checkpoint before passing this to any GUI.
        phase = 'OWNED_SESSION_RPC'
        session._rpc()
        transferred = True
        return session
    except Exception:
        # CI-only fixed whitelist: no exception payloads, keys or paths.
        if (sys.platform == 'darwin' and os.environ.get('GITHUB_ACTIONS') == 'true'
                and os.environ.get('WAM_Q06_CI_SPEND_QUALIFY') == '1'):
            print('MACOS_Q06_SPEND_OPEN_DENIED_STAGE=' + phase, flush=True)
        raise Q06SpendSessionError("Q06_SPEND_OPEN_DENIED") from None
    finally:
        if rpc is not None and getattr(rpc, "_transport", None) is not None:
            rpc._transport.close()
        if not transferred:
            if scanner is not None:
                scanner.close()
            if keys is not None:
                keys.close()
            if guard is not None:
                guard.close()
            # Uncertain runtime/anchor is intentionally never auto-removed.
