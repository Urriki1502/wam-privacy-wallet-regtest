"""K-10 clean host TARGET preflight: read-only and permanently non-authorizing.

K-08 verified mnemonic public ownership and current host directory shape
are necessary but insufficient. This module never creates or recovers wallets,
attests Keychain/Credential/OS-native anchors, calls Core or clears history.
It refuses pre-existing local original/partial wallet state rather than
repairing/deleting it. Actual clean OS owner bootstrap remains P0 PENDING.
"""
from __future__ import annotations

from pathlib import Path

from .k10_portability import (
    HEX64, SCHEMA, K10PortabilityError, native_platform,
)
from .v1_contracts import BIP39_PROFILE, REGTEST_ACCOUNT_LIMIT
from .wsp_live import REGTEST_GENESIS


RESIDUE_NAMES=(
    "wallet-vault","wallet-runtime.sqlite","wallet-runtime.sqlite-wal",
    "wallet-runtime.sqlite-shm","wallet-runtime.sqlite-journal",
)


def review_clean_host_target(identity_receipt, target_root, *, authorized=False):
    """Strict original-public identity and known-collision *read-only* check.

    A matching public digest or empty folder never proves the provenance of
    a signer, absence of old broadcasts, new OS native anchor authorization,
    a complete chain rescan, or Core-native descriptor ownership.
    """
    if authorized is not True:
        raise K10PortabilityError("K10_CLEAN_HOST_CONSENT_REQUIRED")
    expected={
        "schema":SCHEMA,"chain":"regtest","genesis":REGTEST_GENESIS,
        "profile":BIP39_PROFILE,"original_public_identity_matched":True,
        "ephemeral_and_durable_wsp_identity_matched":True,
        "portable_restore_created":False,"history_reconciled":False,
        "signed_uncertain_reservations_reconciled":False,
        "native_anchor_transplanted":False,"signer_allowed":False,
        "broadcast_allowed":False,"mainnet_allowed":False,
        "physical_os_qualified":False,"frozen_gui_qualified":False,
    }
    if (type(identity_receipt) is not dict
            or set(identity_receipt)!=set(expected)|{
                "native_platform_observed","account_index","public_identity_sha256"}
            or any(type(identity_receipt.get(k)) is not type(v)
                   or identity_receipt[k]!=v for k,v in expected.items())
            or type(identity_receipt.get("account_index")) is not int
            or not 0<=identity_receipt["account_index"]<REGTEST_ACCOUNT_LIMIT
            or type(identity_receipt.get("public_identity_sha256")) is not str
            or HEX64.fullmatch(identity_receipt["public_identity_sha256"]) is None
            or identity_receipt.get("native_platform_observed")!=native_platform()):
        raise K10PortabilityError("K10_CLEAN_HOST_IDENTITY_DENIED")
    if (type(target_root) is not type(Path())
            or not target_root.is_absolute()
            or ".." in target_root.parts
            or target_root.is_symlink() or not target_root.is_dir()):
        raise K10PortabilityError("K10_CLEAN_HOST_ROOT_DENIED")
    chain=target_root/"chain"
    if chain.is_symlink() or (chain.exists() and not chain.is_dir()):
        raise K10PortabilityError("K10_CLEAN_HOST_CHAIN_DENIED")
    for name in RESIDUE_NAMES:
        candidate=chain/name
        if candidate.exists() or candidate.is_symlink():
            raise K10PortabilityError("K10_CLEAN_HOST_OLD_STATE_DENIED")
    return {
        "status":"K10_CLEAN_HOST_NAMESPACE_INSPECTED_LOCKED_ONLY",
        "native_platform_observed":identity_receipt["native_platform_observed"],
        "known_vault_or_runtime_collision_found":False,
        "public_identity_verified_against_prior_receipt":True,
        "path_is_native_custody_attested":False,
        "native_new_host_owner_auth_attested":False,
        "old_os_anchor_absent_proven":False,
        "new_os_anchor_created":False,
        "core_sqlite_restored":False,
        "original_fusion_reservations_reconciled":False,
        "original_history_reconciled":False,
        "fresh_scanner_rescan_completed":False,
        "frozen_gui_restored":False,
        "safe_to_create_wallet":False,
        "safe_to_unlock_signer":False,
        "signer_allowed":False,
        "broadcast_allowed":False,
        "mainnet_allowed":False,
    }
