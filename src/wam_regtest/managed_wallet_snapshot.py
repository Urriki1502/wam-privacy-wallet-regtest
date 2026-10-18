"""Q05 original-wallet WSP snapshot over authenticated supervisor-owned REGTEST Core.

The original encrypted WSP Keyring/Scanner is restored only inside this GUI-side
call; it never crosses IPC. Core data comes solely from the strict scan-only
ManagedScanRpc. There is NO signer, broadcast, mining or Core wallet RPC path.

Read-only by default: persisting a newly synced checkpoint requires a separate,
explicit local-storage consent. Never silently discard an existing plaintext
runtime database, reset reservations, rotate accounts or generate a seed.
"""
from __future__ import annotations

from pathlib import Path

from .wallet_read import HistoryRow,WalletReadSnapshot
from .managed_wallet_binding import verify_locked_wallet
from .managed_wallet_reopen import read as read_locator,make as make_locator


class ManagedWalletSnapshotError(ValueError):
    pass


def read_managed_wallet_snapshot(root,core_dir,wsp_source,password,*,
                                 authorized_readonly=False,
                                 authorized_persist_checkpoint=False,keychain=None):
    """Return chain-verified receive/balance/history, with NO spending authority.

    The OS-native anchor lease excludes competing wallet writers throughout
    restore/sync and optional checkpoint save. A stale or unknown SQLite path
    is never deleted, adopted or overwritten. On crash the native custody
    boundary may leave plaintext runtime: its presence blocks the next restore.
    This method does NOT claim crash cleanup or complete frozen Q05 acceptance.
    """
    if authorized_readonly is not True:
        raise ManagedWalletSnapshotError("MANAGED_WALLET_READ_CONSENT_REQUIRED")
    if type(authorized_persist_checkpoint) is not bool:
        raise ManagedWalletSnapshotError("MANAGED_WALLET_PERSIST_CONSENT_DENIED")
    if (type(root) is not type(Path()) or not root.is_absolute()
            or type(core_dir) is not type(Path()) or not core_dir.is_absolute()
            or type(wsp_source) is not type(Path()) or not wsp_source.is_absolute()
            or type(password) is not bytes or not 12<=len(password)<=1024):
        raise ManagedWalletSnapshotError("MANAGED_WALLET_READ_INPUT_DENIED")
    ring=scanner=rpc=None
    # The one established native wallet-runtime path is create-only on restore.
    # Do not use arbitrary supplied paths, temporary fallbacks or user data.
    runtime=root/"chain"/"wallet-runtime.sqlite"
    restored=False
    try:
        from . import custody
        from .core import verified_core_paths
        from .supervisor_client import control
        from .vault import CheckpointVault
        from .managed_scan_client import ManagedScanRpc
        from wam_sp.wallet import Wallet

        attested=verify_locked_wallet(
            root,core_dir,wsp_source,password,authorized=True,keychain=keychain)
        if (type(attested) is not dict or
                attested.get("status")!="MANAGED_WALLET_ORIGINAL_CHECKPOINT_VERIFIED_LOCKED"
                or attested.get("supervisor_authenticated") is not True
                or attested.get("supervisor_core_identity_verified") is not True
                or attested.get("wallet_locked") is not True
                or attested.get("signer_allowed") is not False
                or attested.get("broadcast_allowed") is not False):
            raise ManagedWalletSnapshotError("MANAGED_WALLET_PREFLIGHT_UNVERIFIED")
        before=control(root,"status",timeout=3)
        if (before["state"]!="ready" or before["core_process_owned"] is not True
                or type(before["height"]) is not int):
            raise ManagedWalletSnapshotError("MANAGED_WALLET_SUPERVISOR_NOT_READY")
        _,_,receipt=verified_core_paths(core_dir)
        data_dir=root/"chain"
        folder=data_dir/"wallet-vault"
        storage=custody.storage()
        storage.validate_directory(data_dir)
        storage.validate_directory(folder)
        profile=read_locator(folder,password)
        if profile!=make_locator(profile["wallet_id"],receipt):
            raise ManagedWalletSnapshotError("MANAGED_WALLET_PROFILE_MISMATCH")
        anchor=custody.anchor(profile["wallet_id"],keychain)
        vault=CheckpointVault(folder,anchor,wsp_source)
        with anchor.lease():
            record=anchor.read()
            if record is None or record!=vault._expected:
                raise ManagedWalletSnapshotError("MANAGED_WALLET_ANCHOR_STALE")
            rpc=ManagedScanRpc(root,authorized_readonly=True)
            info=rpc.attest()
            if info["chain"]!="regtest" or info["blocks"]!=before["height"]:
                raise ManagedWalletSnapshotError("MANAGED_WALLET_LIVE_CORE_CHANGED")
            ring,scanner=vault.restore(runtime,password)
            restored=True
            if ring.accounts()!=scanner.accounts or not ring.accounts():
                raise ManagedWalletSnapshotError("MANAGED_WALLET_ACCOUNTS_CHANGED")
            from .account_isolation import require_native_wsp_accounts
            # A read-only snapshot must not accidentally present mining/Core
            # descriptor balances as the original WSP/BIP352 account.
            require_native_wsp_accounts(ring,scanner,profile["wallet_id"])
            metrics=scanner.sync(rpc)
            scanner.assert_current()
            height,tip=scanner.store.tip()
            if (height!=info["blocks"] or
                    height!=rpc.call("getblockcount") or
                    tip!=rpc.call("getbestblockhash") or
                    tip!=rpc.call("getblockhash",[height]) or
                    anchor.read()!=record):
                raise ManagedWalletSnapshotError("MANAGED_WALLET_SCAN_NOT_CURRENT")
            wallet=Wallet(scanner)
            balance=wallet.balance()
            history=tuple(
                HistoryRow(item["txid"],item["height"],item["confirmations"],
                           item["credit"],item["debit"])
                for item in reversed(wallet.history())
            )
            snapshot=WalletReadSnapshot(
                chain="regtest",height=height,tip=tip,
                receive_code=ring.accounts()[-1].payment_code(),
                confirmed_atoms=balance["confirmed_atoms"],
                confirmed_utxos=len(scanner.coins()),history=history,
                core_sha256=receipt["wamd_sha256"],
                synthetic_rpc=False,demo_account_only=False,
                signer_allowed=False,broadcast_allowed=False,
                mainnet_allowed=False,
            )
            after=control(root,"status",timeout=3)
            if (after!=before or
                    rpc.call("getbestblockhash")!=tip or
                    anchor.read()!=record):
                raise ManagedWalletSnapshotError("MANAGED_WALLET_CHAIN_OR_OWNER_CHANGED")
            # Local encrypted checkpoint update is NOT a Core RPC write.
            # Still opt-in independently; never auto-authorize after a read.
            if authorized_persist_checkpoint and (metrics.blocks or metrics.rollback):
                vault.save(ring,scanner,password)
                if anchor.read()!=vault._expected:
                    raise ManagedWalletSnapshotError("MANAGED_WALLET_CHECKPOINT_SAVE_UNCERTAIN")
            return snapshot
    except ManagedWalletSnapshotError:
        raise
    except Exception:
        # No private paths, secrets, wallet identifiers or OS stack in UI.
        raise ManagedWalletSnapshotError("MANAGED_WALLET_SNAPSHOT_UNVERIFIED") from None
    finally:
        if scanner is not None:
            scanner.close()
        if ring is not None:
            ring.close()
        if rpc is not None:
            rpc.close()
        # Delete only the runtime which THIS invocation successfully
        # restored. An unexplained pre-existing file is NEVER touched.
        if restored:
            runtime.unlink(missing_ok=True)
