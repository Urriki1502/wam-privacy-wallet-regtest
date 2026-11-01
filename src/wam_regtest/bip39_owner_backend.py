"""Q06 isolated REGTEST 12-word read-only owner-thread trial.

Human trial surface for mnemonic create/reopen/fresh restore, native custody,
real BIP352 receive identity and genuine owned-Core balance/history scanning.

No send/sign/prepare/broadcast, no migration from Q05, no checkpoint
promotion or G6/G7 acceptance. A fresh full rescan is intentionally read-only;
the absence of native scanner checkpoint forbids use as spend authority.
"""
import os
from pathlib import Path
import re
import secrets
import stat
import sys

from .wallet_executor import ManagedWalletBackend, WalletExecutorError


class Q06ReadOnlyError(ValueError):
    pass


class Bip39ReadOnlyBackend(ManagedWalletBackend):
    """All owned-Core and native-keychain calls execute on WalletExecutor thread."""

    def __init__(self, root, core, source, *, keychain=None, _anchor_factory=None):
        super().__init__(root, core, source, keychain=keychain,
                         _anchor_factory=_anchor_factory)
        self._seed_folder = None
        self._secret = None
        self._public = None
        self._spend_session = None

    def public_state(self):
        p = self.owner.process if self.owner is not None else None
        return {
            "locked": self._secret is None,
            "faulted": self._control_fault,
            "reauthentication_required": False,
            "core_alive": p is not None and p.poll() is None,
        }

    def _lock_q06(self):
        if self._spend_session is not None:
            session = self._spend_session
            session.lock()  # fail-closed: uncertain runtime remains for review
            self._spend_session = None
        if self._secret is not None:
            self._secret[:] = bytes(len(self._secret))
            self._secret = None
        self._public = None
        self._seed_folder = None

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
            folder, public = create_owned_seed_container(
                owner, self.source, password, phrase,
                authorized=True, keychain=self.keychain)
        else:
            if phrase:
                raise Q06ReadOnlyError("Q06_GUI_PHRASE_NOT_EXPECTED")
            folder = self._only_seed(owner)
            with open_owned_seed_container(owner, folder, self.source, password,
                                           authorized=True, keychain=self.keychain) as keys:
                public = keys.public_metadata()
        self._secret = bytearray(password)
        self._seed_folder = folder
        self._public = public
        return {
            "profile": public["profile"], "account_id": public["account_id"],
            "receive_code": public["receive_code"],
            "status": "Q06_REGTEST_READ_ONLY_OWNER_OPENED",
            "mnemonic_once": reveal,
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
        from .q05_checkpoint_scenario import fund_checkpoint_fixture
        owner=self._core()
        _owned(owner)
        seed_id=self._seed_folder.name.removeprefix("bip39-12-")
        if (owner.directory / ("bip39-12-scan-" + seed_id)).exists():
            raise Q06ReadOnlyError("Q06_GUI_ANCHORED_SCANNER_REQUIRES_RECONCILIATION")
        rpc=WalletCoreCli(owner.cli,owner.directory)
        fixture_record={}
        funding_phase="PREFLIGHT"
        try:
            rpc.attest()  # exact signed Core v0.1.11, chain and zero peers
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
        return self._session_snapshot()

    def _session_snapshot(self):
        if self._spend_session is None:
            raise Q06ReadOnlyError("Q06_GUI_SPEND_NOT_ACTIVE")
        from wam_sp.wallet import Wallet
        session = self._spend_session
        item = session.snapshot()
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

    def _scan_q06(self):
        if self._spend_session is not None:
            return self._session_snapshot()
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
        db_path = runtime_dir / "wallet.sqlite"
        scanner = guard = rpc = keys = None
        verified = False
        try:
            keys = open_owned_seed_container(owner, self._seed_folder, self.source,
                                             bytes(self._secret), authorized=True,
                                             keychain=self.keychain)
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
        if action == "ci_confirm":
            if args or kwargs:
                raise Q06ReadOnlyError("Q06_GUI_CONFIRM_CI_ARGUMENTS_DENIED")
            return self._confirm_spend_ci()
        if action == "activate":
            if args or kwargs:
                raise Q06ReadOnlyError("Q06_GUI_ACTIVATE_ARGUMENTS_DENIED")
            return self._activate_q06()
        if action in ("prepare", "sign", "broadcast", "cancel"):
            if kwargs or self._spend_session is None:
                raise Q06ReadOnlyError("Q06_GUI_SPEND_NOT_ACTIVE")
            expected = {"prepare": 3, "sign": 1, "broadcast": 1, "cancel": 0}
            if len(args) != expected[action]:
                raise Q06ReadOnlyError("Q06_GUI_SPEND_ARGUMENTS_DENIED")
            session = self._spend_session
            return getattr(session, action)(*args)
        if action == "open":
            if kwargs or len(args) != 3:
                raise Q06ReadOnlyError("Q06_GUI_OPEN_ARGUMENTS_DENIED")
            return self._open_q06(*args)
        if action == "snapshot":
            if args or kwargs:raise Q06ReadOnlyError("Q06_GUI_SYNC_ARGUMENTS_DENIED")
            return self._scan_q06()
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
