"""Q06 B2c: bounded, *read-only* original-Core scanner reconciliation.

No GUI, no signer, no broadcast, no mutable native checkpoint generation.
Only a one-shot authenticated candidate can be replayed into FRESH native
SQLite. On failed reconciliation leave uncertain evidence untouched.
"""
import secrets
import sys
from pathlib import Path

from . import custody
from .bip39_native_checkpoint import (
    SeededNativeCheckpointError, _owned_tip, read_owned_candidate,
)
from .bip39_seed_vault import _owned_password, open_owned_seed_container
from .bip39_scanner_checkpoint import decode_candidate
from .managed_wallet_checkpoint import _owned, reservation_fingerprint
from .managed_wallet_session import RuntimeGuard
from .wallet_session import WalletCoreCli


class SeededReconciliationError(ValueError):
    """Public fixed error code; never include mnemonic, path, or RPC payload."""


def _fresh_runtime(owner):
    custody.storage().validate_directory(owner.directory)
    target = owner.directory / ("q06-reconcile-" + secrets.token_hex(16) + ".sqlite")
    if any(target.with_name(target.name + suffix).exists()
           or target.with_name(target.name + suffix).is_symlink()
           for suffix in ("", "-wal", "-shm", "-journal", ".scan.lock")):
        raise SeededReconciliationError("Q06_RECONCILE_RUNTIME_EXISTS_OR_UNCERTAIN")
    return target


def _reservations(scanner):
    rows = scanner.store.db.execute(
        "SELECT txid,vout,token,state,created FROM reservations ORDER BY txid,vout"
    )
    return reservation_fingerprint(rows)


def reconcile_owned_readonly(owner, seed_folder, source, password, *,
                             authorized=False, keychain=None):
    """Attested Core + fresh native SQLite, then immediately lock and discard.

    This is a *qualification read*, not a persistent wallet reopen or a
    promotion of scanner checkpoint. Only exact anchored tip is permitted.
    No funds/keys/transactions are emitted, and signer is never constructed.
    """
    _owned_password(owner, source, password, authorized)
    _owned(owner)
    keys = scanner = guard = rpc = None
    try:
        encrypted, receipt = read_owned_candidate(
            owner, seed_folder, source, password,
            authorized=authorized, keychain=keychain,
        )
        if (type(receipt) is not dict
                or receipt.get("status") != "ENCRYPTED_CANDIDATE_NEEDS_FRESH_SQLITE_RESTORE"
                or receipt.get("signer_allowed") is not False
                or receipt.get("broadcast_allowed") is not False
                or receipt.get("mainnet_allowed") is not False
                or type(receipt.get("height")) is not int
                or type(receipt.get("tip")) is not str):
            raise SeededReconciliationError("Q06_RECONCILE_CANDIDATE_DENIED")
        before = (receipt["height"], receipt["tip"])
        if _owned_tip(owner) != before:
            raise SeededReconciliationError("Q06_RECONCILE_TIP_CHANGED")
        keys = open_owned_seed_container(
            owner, seed_folder, source, password,
            authorized=authorized, keychain=keychain,
        )
        if keys.public_metadata()["account_id"] != receipt["account_id"]:
            raise SeededReconciliationError("Q06_RECONCILE_IDENTITY_CHANGED")
        rpc = WalletCoreCli(owner.cli, owner.directory)
        rpc.attest()
        if (rpc.call("getblockcount"), rpc.call("getbestblockhash")) != before:
            raise SeededReconciliationError("Q06_RECONCILE_TIP_CHANGED")
        target = _fresh_runtime(owner)
        if sys.platform == "win32":
            from .windows_private_storage import create_managed_runtime
            create_managed_runtime(target)  # actual native DACL; not chmod
        from wam_sp.scanner import Scanner
        scanner = Scanner(target, keys.accounts())
        guard = RuntimeGuard(target)
        from .bip39_native_checkpoint import _owner_binding
        decoded = decode_candidate(
            keys, scanner, encrypted, password.decode("utf-8"),
            owner_binding=_owner_binding(owner),
        )
        if (decoded["claimed_height"], decoded["claimed_tip"]) != before:
            raise SeededReconciliationError("Q06_RECONCILE_CHECKPOINT_TIP_DENIED")
        prior_reservations = _reservations(scanner)
        scanner.sync(rpc)                 # authentic signed/reviewed Core RPC
        scanner.assert_current()
        after = (rpc.call("getblockcount"), rpc.call("getbestblockhash"))
        if (after != before or scanner.store.tip() != before
                or scanner.verified_tip != before
                or _reservations(scanner) != prior_reservations):
            raise SeededReconciliationError("Q06_RECONCILE_CHAIN_OR_RESERVATION_CHANGED")
        _owned(owner)
        # Verify the same anchored ciphertext still has authority after sync.
        second, matching = read_owned_candidate(
            owner, seed_folder, source, password,
            authorized=authorized, keychain=keychain,
        )
        if second != encrypted or matching != receipt or _owned_tip(owner) != before:
            raise SeededReconciliationError("Q06_RECONCILE_ANCHOR_OR_TIP_CHANGED")
        guard.check()
        scanner.close(); scanner = None
        # This session has never signed, broadcast or advanced the anchor.
        # Remove only the verified file WE created; uncertain residue is kept.
        guard.remove_owned(); guard = None
        return {
            "status": "Q06_RECONCILED_READ_ONLY_LOCKED",
            "profile": "fusion-bip39-12-bip32-bip352-regtest-v1",
            "account_id": decoded["account_id"],
            "height": before[0], "tip": before[1],
            "reservation_count": prior_reservations[0],
            "signer_allowed": False, "broadcast_allowed": False,
            "mainnet_allowed": False,
            "fresh_runtime_removed": True,
        }
    except Exception:
        # Never auto repair a crash/corrupt anchor or delete uncertain SQLite.
        raise SeededReconciliationError("Q06_RECONCILE_DENIED") from None
    finally:
        if scanner is not None:
            scanner.close()
        if guard is not None:
            guard.close()
        if keys is not None:
            keys.close()
        if rpc is not None and getattr(rpc, "_transport", None) is not None:
            rpc._transport.close()
