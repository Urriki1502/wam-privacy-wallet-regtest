"""K-10 deterministic REGTEST portability and cross-host evidence contracts.

This layer verifies real pinned native WSP/BIP39 public key derivation and
Core-native SQLite BACKUP BYTES in memory. It NEVER migrates native OS anchors,
imports Core wallet databases, unlocks a signer, clears reservations or
claims clean-OS/frozen-app acceptance.

Owner-origin attestations and physical-host evidence must be supplied and
independently qualified by a separate end-to-end run (Codex/DEV).
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import platform
import re
import sys

from .v1_contracts import BIP39_PROFILE, REGTEST_ACCOUNT_LIMIT
from .wsp_live import REGTEST_GENESIS

SCHEMA="wam-fusion-k10-public-portability/v1"
PLATFORMS=frozenset(("macos-arm64","windows-x64","linux-x86_64"))
HEX64=re.compile(r"[0-9a-f]{64}\Z")


class K10PortabilityError(ValueError):
    """Fixed, non-secret reason code only."""


def native_platform():
    """Detect local platform, NEVER accept a caller-supplied OS identity."""
    machine=platform.machine().lower()
    if sys.platform=="darwin" and machine in ("arm64","aarch64"):
        return "macos-arm64"
    if sys.platform=="win32" and machine in ("amd64","x86_64"):
        return "windows-x64"
    if sys.platform=="linux" and machine=="x86_64":
        return "linux-x86_64"
    raise K10PortabilityError("K10_UNQUALIFIED_PLATFORM_DENIED")


def _sha_public(metadata):
    """Hash *public* WSP metadata, not a mnemonic, seed or backup ciphertext."""
    try:
        canonical=json.dumps(metadata,sort_keys=True,separators=(",",":"),
                             ensure_ascii=True,allow_nan=False).encode("ascii")
        return sha256(canonical).hexdigest()
    except (TypeError,UnicodeError,ValueError):
        raise K10PortabilityError("K10_PUBLIC_METADATA_UNVERIFIED") from None


def probe_original_bip39_identity(phrase, *, passphrase, account,
                                 prior_trusted_public, wsp_source,
                                 authorized=False):
    """Derive the exact same public account through independent K02/K03 APIs.

    No wallet creation, Core RPC, filesystem write, source-OS anchor copy or
    private key serialization. The *caller* must obtain the previous trusted
    public receipt from an independently verified original wallet. Repeating
    an attacker-chosen receipt on a fresh OS is not proof of legitimate owner.
    """
    if authorized is not True:
        raise K10PortabilityError("K10_OWNER_CONSENT_REQUIRED")
    if (type(phrase) is not str or type(passphrase) is not str
            or type(account) is not int or not 0<=account<REGTEST_ACCOUNT_LIMIT
            or type(prior_trusted_public) is not dict
            or type(wsp_source) is not type(Path())
            or not wsp_source.is_absolute()):
        raise K10PortabilityError("K10_PUBLIC_OWNER_INPUT_DENIED")
    try:
        from .bip39_wallet import Bip39RegtestKeys
        from .bip39_durable import Bip39DurableKeyring
        from .portable_recovery import verify_bip39_owner_for_clean_device

        os_name=native_platform()
        prior=verify_bip39_owner_for_clean_device(
            phrase,passphrase=passphrase,account=account,
            expected_public=prior_trusted_public,wsp_source=wsp_source,
            authorized=True)
        if prior.get("signer_allowed") is not False:
            raise ValueError
        with Bip39RegtestKeys(
                phrase,source=wsp_source,passphrase=passphrase,
                authorized_disposable=True) as ephemeral:
            observed=ephemeral.require_public_metadata(
                prior_trusted_public,account)
        with Bip39DurableKeyring.from_phrase(
                phrase,source=wsp_source,passphrase=passphrase,
                account=account,authorized=True) as durable:
            account_native=durable.accounts()[0]
            if (account_native.account_id!=observed["account_id"]
                    or account_native.payment_code()!=observed["receive_code"]):
                raise ValueError
        if (observed["profile"]!=BIP39_PROFILE
                or observed["chain"]!="regtest"
                or observed["genesis"]!=REGTEST_GENESIS):
            raise ValueError
        return {
            "schema":SCHEMA,
            "native_platform_observed":os_name,
            "chain":"regtest",
            "genesis":REGTEST_GENESIS,
            "profile":BIP39_PROFILE,
            "account_index":account,
            "public_identity_sha256":_sha_public(observed),
            "original_public_identity_matched":True,
            "ephemeral_and_durable_wsp_identity_matched":True,
            "portable_restore_created":False,
            "history_reconciled":False,
            "signed_uncertain_reservations_reconciled":False,
            "native_anchor_transplanted":False,
            "signer_allowed":False,
            "broadcast_allowed":False,
            "mainnet_allowed":False,
            "physical_os_qualified":False,
            "frozen_gui_qualified":False,
        }
    except K10PortabilityError:
        raise
    except Exception:
        raise K10PortabilityError("K10_PUBLIC_IDENTITY_UNVERIFIED") from None


def compare_public_os_evidence(receipts):
    """Check an exactly matched public derivation across 3 reported hosts.

    Receipts are UNTRUSTED without individual exact-HEAD signed runner logs
    and physical provenance. Do not expose a cross-OS PASS even if all labels
    and fingerprints match: any process can invent an OS field.
    """
    if type(receipts) not in (tuple,list) or len(receipts)!=3:
        raise K10PortabilityError("K10_PLATFORM_RECEIPT_SET_DENIED")
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
    fields=set(expected)|{
        "native_platform_observed","account_index","public_identity_sha256"}
    platforms=set()
    identities=set()
    accounts=set()
    for entry in receipts:
        if (type(entry) is not dict or set(entry)!=fields
                or any(type(entry.get(k)) is not type(v) or entry[k]!=v
                       for k,v in expected.items())
                or type(entry.get("native_platform_observed")) is not str
                or entry["native_platform_observed"] not in PLATFORMS
                or type(entry.get("account_index")) is not int
                or not 0<=entry["account_index"]<REGTEST_ACCOUNT_LIMIT
                or type(entry.get("public_identity_sha256")) is not str
                or HEX64.fullmatch(entry["public_identity_sha256"]) is None):
            raise K10PortabilityError("K10_PLATFORM_RECEIPT_UNVERIFIED")
        platforms.add(entry["native_platform_observed"])
        identities.add(entry["public_identity_sha256"])
        accounts.add(entry["account_index"])
    if platforms!=PLATFORMS or len(identities)!=1 or len(accounts)!=1:
        raise K10PortabilityError("K10_OS_PUBLIC_IDENTITY_MISMATCH")
    return {
        "status":"K10_THREE_DECLARED_OS_PUBLIC_IDENTITIES_AGREE_ONLY",
        "public_identity_consistent":True,
        "signed_os_runner_provenance_verified":False,
        "real_regtest_signed_payment_on_all_os":False,
        "core_sqlite_cross_os_restored":False,
        "frozen_gui_recovery_verified":False,
        "physical_os_qualified":False,
        "safe_to_unlock":False,
        "signer_allowed":False,
        "broadcast_allowed":False,
    }


@dataclass(frozen=True,repr=False)
class CoreSqliteByteEvidence:
    """Comparison-only original Core SQLite digest; NEVER chain attestation."""
    checksum: str
    size: int

    def __repr__(self):
        return "<K10CoreSqliteByteEvidence private digest redacted>"


def inspect_original_core_sqlite(source, *, authorized=False):
    """Reuse K-04 actual native no-follow read-only SQLite inspection."""
    if authorized is not True:
        raise K10PortabilityError("K10_CORE_SOURCE_CONSENT_REQUIRED")
    try:
        from .core_sqlite_import import inspect_sqlite_backup
        receipt=inspect_sqlite_backup(source)
        if (receipt.format!="sqlite" or receipt.network!="UNVERIFIED"
                or type(receipt.file_sha256) is not str
                or HEX64.fullmatch(receipt.file_sha256) is None
                or type(receipt.byte_count) is not int
                or not 4096<=receipt.byte_count<=128*1024*1024):
            raise ValueError
        return CoreSqliteByteEvidence(receipt.file_sha256,receipt.byte_count)
    except Exception:
        raise K10PortabilityError("K10_CORE_SQLITE_BYTES_UNVERIFIED") from None


def compare_core_sqlite_bytes(original, restored_copy, *, authorized=False):
    """Same bytes != genuine Core wallet restore, descriptor parity or safety."""
    if authorized is not True:
        raise K10PortabilityError("K10_CORE_COMPARE_CONSENT_REQUIRED")
    if (type(original) is not CoreSqliteByteEvidence
            or type(restored_copy) is not CoreSqliteByteEvidence
            or type(original.checksum) is not str
            or HEX64.fullmatch(original.checksum) is None
            or type(restored_copy.checksum) is not str
            or HEX64.fullmatch(restored_copy.checksum) is None
            or type(original.size) is not int or type(restored_copy.size) is not int
            or not 4096<=original.size<=128*1024*1024
            or not 4096<=restored_copy.size<=128*1024*1024):
        raise K10PortabilityError("K10_CORE_BYTES_EVIDENCE_UNVERIFIED")
    if original!=restored_copy:
        raise K10PortabilityError("K10_CORE_BYTES_CHANGED_ON_TRANSFER")
    return {
        "status":"K10_SQLITE_ORIGINAL_AND_TARGET_BYTES_EQUAL_ONLY",
        "byte_content_identical":True,
        "core_native_descriptor_identity_qualified":False,
        "regtest_chain_attested_by_core":False,
        "cross_os_core_restore_qualified":False,
        "history_reconciled":False,
        "signed_uncertain_reservations_reconciled":False,
        "signer_allowed":False,"broadcast_allowed":False,
    }
