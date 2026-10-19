"""K-10 clean-host handoff: authenticated, read-only evidence composition.

Combines original mnemonic, encrypted v4 WSP backup, a destination namespace,
optional actual Core-native SQLite backup bytes and optional real REGTEST
read-only scanner IPC. This never performs or authorizes Core restore,
new OS anchor creation, transaction replay, wallet bootstrap or spending.
An original wallet's historical/uncertain reservations remain unresolved.
"""
from __future__ import annotations

from pathlib import Path

from .k10_portability import (
    K10PortabilityError, HEX64, probe_original_bip39_identity,
    inspect_original_core_sqlite, compare_core_sqlite_bytes,
)
from .k10_encrypted_portability import inspect_portable_k03_backup
from .k10_clean_host import review_clean_host_target
from .wsp_live import REGTEST_GENESIS


def _attest_core(rpc):
    """Read isolated real REGTEST tip through the existing restricted IPC."""
    from .managed_scan_client import ManagedScanRpc

    if type(rpc) is not ManagedScanRpc:
        raise K10PortabilityError("K10_ORIGINAL_CORE_IPC_REQUIRED")
    try:
        before=rpc.attest()
        height=before.get("blocks")
        hash_now=before.get("bestblockhash")
        if (before.get("chain")!="regtest"
                or type(height) is not int or not 0<=height<=1_000_000
                or type(hash_now) is not str or HEX64.fullmatch(hash_now) is None
                or rpc.call("getblockhash",[0])!=REGTEST_GENESIS
                or rpc.call("getblockhash",[height])!=hash_now
                or rpc.call("getbestblockhash")!=hash_now):
            raise ValueError
        after=rpc.attest()
        if (after.get("blocks")!=height
                or after.get("bestblockhash")!=hash_now):
            raise ValueError
    except Exception:
        raise K10PortabilityError("K10_CORE_TIP_UNVERIFIED") from None
    return height


def inspect_locked_clean_host_handoff(
        *, phrase, passphrase, encrypted_backup, backup_password, account,
        prior_trusted_public, wsp_source, target_root, authorized=False,
        original_core_sqlite=None, transported_core_sqlite=None,
        readonly_core_rpc=None, authorized_core_observation=False):
    """Compose real cryptographic evidence WITHOUT changing host state.

    Prior trusted public metadata must have been independently authenticated
    on the original owner device; a caller-invented prior receipt remains
    untrusted. No public digest is an authorization to sign or to discard
    earlier signed/uncertain reservations.
    """
    if authorized is not True:
        raise K10PortabilityError("K10_HANDOFF_OPERATOR_CONSENT_REQUIRED")
    if type(authorized_core_observation) is not bool:
        raise K10PortabilityError("K10_HANDOFF_CORE_CONSENT_SCOPE_DENIED")
    if ((original_core_sqlite is None)!=(transported_core_sqlite is None)
            or (original_core_sqlite is not None and
                (type(original_core_sqlite) is not type(Path())
                 or type(transported_core_sqlite) is not type(Path())))
            or (readonly_core_rpc is None)!=
               (authorized_core_observation is False)):
        raise K10PortabilityError("K10_HANDOFF_EVIDENCE_SCOPE_DENIED")
    # Derive from actual pinned WSP; verify exact prior owner public evidence.
    try:
        mnemonic=probe_original_bip39_identity(
            phrase,passphrase=passphrase,account=account,
            prior_trusted_public=prior_trusted_public,wsp_source=wsp_source,
            authorized=True)
        sealed=inspect_portable_k03_backup(
            encrypted_backup,backup_password,account=account,
            prior_trusted_public=prior_trusted_public,authorized=True)
        if mnemonic["public_identity_sha256"]!=sealed["public_identity_sha256"]:
            raise K10PortabilityError("K10_HANDOFF_KEY_IDENTITY_MISMATCH")
        start=review_clean_host_target(
            mnemonic,target_root,authorized=True)
        # This is byte-equivalence only, NEVER permission for Core restore.
        core_bytes_checked=False
        if original_core_sqlite is not None:
            source=inspect_original_core_sqlite(
                original_core_sqlite,authorized=True)
            destination=inspect_original_core_sqlite(
                transported_core_sqlite,authorized=True)
            comparison=compare_core_sqlite_bytes(
                source,destination,authorized=True)
            if comparison["byte_content_identical"] is not True:
                raise ValueError
            core_bytes_checked=True
        height=None
        if readonly_core_rpc is not None:
            height=_attest_core(readonly_core_rpc)
        # Re-examine the target after potentially lengthy scrypt and
        # source/chain inspections. No later mutation is authorized by this
        # time-of-check evidence.
        end=review_clean_host_target(
            mnemonic,target_root,authorized=True)
        if start!=end:
            raise K10PortabilityError("K10_HANDOFF_NAMESPACE_CHANGED")
        if original_core_sqlite is not None:
            if (inspect_original_core_sqlite(
                    original_core_sqlite,authorized=True)!=source
                    or inspect_original_core_sqlite(
                        transported_core_sqlite,authorized=True)!=destination):
                raise K10PortabilityError("K10_HANDOFF_SQLITE_CHANGED")
        return {
            "status":"K10_LOCKED_CLEAN_HOST_HANDOFF_INSPECTED",
            "chain":"regtest",
            "genesis":REGTEST_GENESIS,
            "native_platform_observed":mnemonic["native_platform_observed"],
            "account_index":account,
            "public_identity_sha256":mnemonic["public_identity_sha256"],
            "mnemonic_and_encrypted_v4_backup_identity_equal":True,
            "original_public_identity_matched":True,
            "clean_target_namespace_no_known_collision":True,
            "core_sqlite_source_copy_byte_equal":core_bytes_checked,
            "core_readonly_regtest_tip_observed":height is not None,
            "core_regtest_height_observed":height,
            "new_native_anchor_created":False,
            "source_anchor_transplanted":False,
            "core_sqlite_wallet_restored":False,
            "fusion_scanner_checkpoint_restored":False,
            "old_signed_uncertain_reservations_reconciled":False,
            "historical_chain_rescan_complete":False,
            "mempool_reorg_resolved":False,
            "frozen_gui_recovery_verified":False,
            "clean_os_physical_acceptance":False,
            "safe_to_create_wallet":False,
            "safe_to_unlock":False,
            "signer_allowed":False,
            "broadcast_allowed":False,
            "mainnet_allowed":False,
        }
    except K10PortabilityError:
        raise
    except Exception:
        raise K10PortabilityError("K10_HANDOFF_UNVERIFIED") from None
