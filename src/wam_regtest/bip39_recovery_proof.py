"""Q06 same-chain mnemonic-only readback, without native checkpoint authority.

A fresh 12-word-derived WSP scanner independently reconstructs confirmed
history on the SAME attested, originally owned REGTEST blockchain. This
does not migrate encrypted reservations, reconstruct an absent chain, create
a new owner or authorize spending. No mnemonic, keys or raw history are logged.
"""
import secrets
from pathlib import Path

from . import custody
from .bip39_12 import Bip39Regtest12Keys
from .managed_wallet_checkpoint import _owned
from .managed_wallet_session import RuntimeGuard
from .wallet_session import WalletCoreCli
from .history_pages import GUI_HISTORY_LIMIT, complete_history
from .bip39_spend_session import _remove_known_scanner_lock


class Q06RecoveryProofError(ValueError):
    """Only fixed public denial categories."""


def verify_mnemonic_on_original_chain(owner, source, phrase, expected):
    """Independent read-only seed rescan; original checkpoint remains intact."""
    if (type(phrase) is not str or not 1 <= len(phrase) <= 1024
            or expected is None or expected.chain != "regtest"
            or expected.signer_allowed is not True
            or type(expected.history_count) is not int
            or type(expected.history_sha256) is not str):
        raise Q06RecoveryProofError("Q06_RECOVERY_INPUT_OR_BASELINE_DENIED")
    _owned(owner)
    keys = scanner = guard = rpc = None
    directory = None
    verified = False
    try:
        keys = Bip39Regtest12Keys(phrase, source=source, authorized_disposable=True)
        public = keys.public_metadata()
        if public["receive_code"] != expected.receive_code:
            raise Q06RecoveryProofError("Q06_RECOVERY_MNEMONIC_IDENTITY_DENIED")
        # An independent scanner must never copy or open the existing wallet
        # database or its irreversible native checkpoint.
        directory = owner.directory / ("q06-seed-proof-" + secrets.token_hex(16))
        custody.create_directory(directory)
        target = directory / "wallet-runtime.sqlite"
        from wam_sp.scanner import Scanner
        from wam_sp.wallet import Wallet
        # Consistent with Q06 owned-spend: Windows must create the private
        # SQLite runtime through native ACL custody before sqlite3 opens it.
        import sys
        if sys.platform == "win32":
            from .windows_private_storage import create_managed_runtime
            create_managed_runtime(target)
        scanner = Scanner(target, keys.accounts())
        guard = RuntimeGuard(target)
        rpc = WalletCoreCli(owner.cli, owner.directory)
        rpc.attest()
        if (rpc.call("getblockcount"), rpc.call("getbestblockhash")) != (
                expected.height, expected.tip):
            raise Q06RecoveryProofError("Q06_RECOVERY_ORIGINAL_CHAIN_CHANGED")
        scanner.sync(rpc)
        scanner.assert_current()
        tip = scanner.store.tip()
        if tip != (expected.height, expected.tip):
            raise Q06RecoveryProofError("Q06_RECOVERY_SCAN_TIP_DENIED")
        wallet = Wallet(scanner)
        with scanner.store.transaction():
            declared = wallet.db.execute("SELECT count(*) FROM history").fetchone()[0]
            def page(limit, offset):
                return wallet._history(limit, offset)
            count, digest, _ = complete_history(
                page, declared, tip[0], keep_tail=GUI_HISTORY_LIMIT,
                skip_newest=0, error=Q06RecoveryProofError)
            amount = wallet._balance(1)["confirmed_atoms"]
        if (count != expected.history_count
                or digest != expected.history_sha256
                or amount != expected.confirmed_atoms
                or keys.public_metadata()["receive_code"] != expected.receive_code):
            raise Q06RecoveryProofError("Q06_RECOVERY_HISTORY_OR_BALANCE_DENIED")
        _owned(owner)
        if (rpc.call("getblockcount"), rpc.call("getbestblockhash")) != tip:
            raise Q06RecoveryProofError("Q06_RECOVERY_ORIGINAL_CHAIN_CHANGED")
        guard.check()
        verified = True
        return {
            "status": "Q06_SAME_CHAIN_BIP39_HISTORY_RESCAN_PASS",
            "receive_code": expected.receive_code,
            "height": tip[0],
            "history_count": count,
            "history_sha256": digest,
            "confirmed_atoms": amount,
            "same_chain_only": True,
            "clean_device_recovery": False,
            "signed_reservations_restored": False,
            "signer_allowed": False,
            "broadcast_allowed": False,
            "mainnet_allowed": False,
        }
    except Q06RecoveryProofError:
        raise
    except Exception:
        raise Q06RecoveryProofError("Q06_RECOVERY_INDEPENDENT_RESCAN_DENIED") from None
    finally:
        if scanner is not None:
            scanner.close()
        if rpc is not None and getattr(rpc, "_transport", None) is not None:
            rpc._transport.close()
        if keys is not None:
            keys.close()
        if guard is not None:
            if verified:
                try:
                    _remove_known_scanner_lock(target)
                    guard.remove_owned()
                    directory.rmdir()
                except Exception:
                    guard.close()
                    raise Q06RecoveryProofError("Q06_RECOVERY_TEMP_RUNTIME_PRESERVED") from None
            else:
                # Never erase an ambiguous or partially written SQLite scan.
                guard.close()
