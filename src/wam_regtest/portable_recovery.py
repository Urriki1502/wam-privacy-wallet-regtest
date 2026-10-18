"""K-08 portable wallet recovery PRE-FLIGHT, not automatic wallet restoration.

A mnemonic can deterministically recover BIP352 spend/scan keys, but cannot
reconstruct a Core descriptor .dat, encrypted Fusion checkpoint, transaction
reservation ledger, native OS anchor or necessarily the full prior history.
No recovery mode may silently create a second signer or release uncertain
transactions. The actual clean-device creation/scan/reconciliation remains a
separately authorized, audited acceptance step after this preflight.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .v1_contracts import BIP39_PROFILE, CORE_PROFILE, RC1_PROFILE
from .wsp_live import REGTEST_GENESIS

MODES=frozenset(("bip39-mnemonic","core-sqlite-dat",
                 "fusion-encrypted-enc","os-native-anchor"))


class PortableRecoveryError(ValueError):
    """Only constant non-secret refusal reasons."""


@dataclass(frozen=True,repr=False)
class PortableRecoveryPlan:
    schema: str
    mode: str
    chain: str
    genesis: str
    native_owner_proof_required: bool
    cross_os_anchor_copy_allowed: bool
    source_mutation_allowed: bool
    signer_allowed: bool
    balance_claim_allowed: bool
    history_restored: bool
    pending_reconciliation: bool
    expected_profile: str | None

    def __repr__(self):
        return "<PortableRecoveryPlan REGTEST locked; redacted>"


def recovery_plan(mode,*,authorized=False):
    """Distinguish four recovery *authorities* before touching any input."""
    if authorized is not True:
        raise PortableRecoveryError("K08_OPERATOR_CONSENT_REQUIRED")
    if type(mode) is not str or mode not in MODES:
        raise PortableRecoveryError("K08_RECOVERY_MODE_DENIED")
    profile={
        "bip39-mnemonic":BIP39_PROFILE,
        "core-sqlite-dat":CORE_PROFILE,
        "fusion-encrypted-enc":None,
        "os-native-anchor":None,
    }[mode]
    return PortableRecoveryPlan(
        schema="wam-fusion-k08-portable-recovery-preflight/v1",
        mode=mode,chain="regtest",genesis=REGTEST_GENESIS,
        native_owner_proof_required=True,
        cross_os_anchor_copy_allowed=False,
        source_mutation_allowed=False,
        signer_allowed=False,balance_claim_allowed=False,
        history_restored=False,pending_reconciliation=True,
        expected_profile=profile,
    )


def verify_bip39_owner_for_clean_device(
        phrase, *, passphrase, account, expected_public, wsp_source,
        authorized=False):
    """Owner-facing preflight: prove *exact same* BIP39 WSP public identity.

    Verify all 64 seed bytes through the pinned native WSP derivation, never
    compare only a shortened fingerprint. expected_public must be an exact
    previously trusted public receipt; matching an attacker-provided new
    receipt alone is NOT proof of ownership or native custody. This routine
    creates no filesystem files, Core wallets, OS anchors, credentials,
    transaction reservations or spending permissions. It must run before any
    clean-device bootstrap and historical reconciliation.
    """
    if authorized is not True:
        raise PortableRecoveryError("K08_OWNER_AUTHORIZATION_REQUIRED")
    if (type(account) is not int or not 0<=account<16
            or type(phrase) is not str or type(passphrase) is not str
            or type(wsp_source) is not type(Path())
            or not wsp_source.is_absolute()
            or type(expected_public) is not dict):
        raise PortableRecoveryError("K08_OWNER_RECOVERY_INPUT_DENIED")
    try:
        from .bip39_wallet import Bip39RegtestKeys
        with Bip39RegtestKeys(
                phrase,source=wsp_source,passphrase=passphrase,
                authorized_disposable=True) as keys:
            # Compares the REGTEST chain, exact K-02 derivation profile,
            # account index, 64-byte-seed-derived account_id/receive_code.
            verified=keys.require_public_metadata(expected_public,account)
            if (verified["profile"]!=BIP39_PROFILE
                    or verified["chain"]!="regtest"
                    or verified["genesis"]!=REGTEST_GENESIS
                    or verified["mainnet_allowed"] is not False):
                raise ValueError
    except Exception:
        raise PortableRecoveryError("K08_BIP39_ORIGINAL_IDENTITY_DENIED") from None
    return {
        "status":"K08_BIP39_ORIGINAL_PUBLIC_IDENTITY_VERIFIED_LOCKED",
        "schema":"wam-fusion-k08-portable-recovery-preflight/v1",
        "network":"regtest","profile":BIP39_PROFILE,
        "account_index":account,
        "identity_matched_prior_trusted_receipt":True,
        "native_new_device_anchor_created":False,
        "original_os_anchor_transplanted":False,
        "original_core_dat_restored":False,
        "original_fusion_enc_restored":False,
        "historical_spend_reservations_reconciled":False,
        "history_verified":False,
        "balance_verified":False,
        "signer_allowed":False,
        "broadcast_allowed":False,
        "mainnet_allowed":False,
    }


def require_safe_bootstrap_prerequisites(receipt,*,target_root,
                                         approved_regtest_core=False,
                                         owner_native_auth=False,
                                         original_state_reconciled=False):
    """Additional fail-closed authorization for an eventual clean-device UI.

    This remains a *gate only*, never calls Core, creates anchors or imports
    databases. A freshly derived mnemonic must NOT silently clear pending
    signed/uncertain payments merely because it can derive the correct key.
    """
    if (type(receipt) is not dict
            or receipt.get("status")!="K08_BIP39_ORIGINAL_PUBLIC_IDENTITY_VERIFIED_LOCKED"
            or receipt.get("identity_matched_prior_trusted_receipt") is not True
            or receipt.get("signer_allowed") is not False
            or receipt.get("broadcast_allowed") is not False
            or receipt.get("historical_spend_reservations_reconciled") is not False
            or receipt.get("mainnet_allowed") is not False):
        raise PortableRecoveryError("K08_IDENTITY_RECEIPT_DENIED")
    if (type(target_root) is not type(Path()) or not target_root.is_absolute()
            or target_root.is_symlink()):
        raise PortableRecoveryError("K08_TARGET_ROOT_DENIED")
    # We refuse both an existing native vault and leftover runtime data:
    # neither may be deleted/adopted to overwrite an original wallet.
    chain=target_root/"chain"
    for target in (chain/"wallet-vault",chain/"wallet-runtime.sqlite",
                   chain/"wallet-runtime.sqlite-wal",
                   chain/"wallet-runtime.sqlite-shm",
                   chain/"wallet-runtime.sqlite-journal"):
        if target.exists() or target.is_symlink():
            raise PortableRecoveryError("K08_EXISTING_WALLET_OR_CRASH_RESIDUE_DENIED")
    if (approved_regtest_core is not True or owner_native_auth is not True
            or original_state_reconciled is not True):
        raise PortableRecoveryError("K08_CLEAN_DEVICE_OR_RECONCILIATION_PENDING")
    # This is not an authorization to transact or a wallet restore. Real
    # native startup, clean host bootstrap and explicit signing controls
    # must independently enforce their own policies.
    return {
        "status":"K08_CLEAN_DEVICE_PREREQUISITES_REVIEWED_ONLY",
        "wallet_created":False,"native_anchor_created":False,
        "signer_allowed":False,"broadcast_allowed":False,
        "history_verified":False,"mainnet_allowed":False,
    }
