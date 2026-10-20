"""R-03: versioned, conservative evidence invalidation for WAM Fusion REGTEST.

This module operates on public attestations only. Caller MUST independently
authenticate source, runner, artifact hashes and review receipts before setting
receipt_verified=True. Untrusted JSON is NEVER a release/permission oracle.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import re

SCHEMA = "wam-fusion-r03-evidence-lifecycle/v1"
KINDS = ("SOURCE", "CORE_E2E", "FROZEN", "PHYSICAL", "DEV_REVIEWED")
PLATFORMS = (("macos", "arm64"), ("windows", "x64"), ("linux", "x86_64"))
HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")
VERSION = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+")
IDENTITY_KEYS = (
    "code_sha",
    "os",
    "architecture",
    "core_version",
    "core_network",
    "core_genesis_sha256",
    "wamd_sha256",
    "wam_cli_sha256",
    "wsp_commit",
    "signer_source_sha256",
    "custody_source_sha256",
    "gui_source_sha256",
    "dependency_lock_sha256",
    "packaging_manifest_sha256",
    "test_environment_sha256",
)
HASH40_FIELDS = ("code_sha", "wsp_commit")
HASH64_FIELDS = (
    "core_genesis_sha256", "wamd_sha256", "wam_cli_sha256",
    "signer_source_sha256", "custody_source_sha256",
    "gui_source_sha256", "dependency_lock_sha256",
    "packaging_manifest_sha256", "test_environment_sha256",
)


def _identity_valid(identity: object, *, allow_artifact: bool = False) -> bool:
    if type(identity) is not dict:
        return False
    keys = set(identity)
    base = set(IDENTITY_KEYS)
    # An exact candidate may additionally identify its frozen binary. This
    # extension is NEVER part of the historical source identity.
    if keys != base and not (allow_artifact and keys == base | {"artifact_sha256"}):
        return False
    if "artifact_sha256" in identity and (
            type(identity["artifact_sha256"]) is not str
            or HEX64.fullmatch(identity["artifact_sha256"]) is None):
        return False
    if any(type(identity[k]) is not str or HEX40.fullmatch(identity[k]) is None
           for k in HASH40_FIELDS):
        return False
    if any(type(identity[k]) is not str or HEX64.fullmatch(identity[k]) is None
           for k in HASH64_FIELDS):
        return False
    return (
        (identity["os"], identity["architecture"]) in PLATFORMS
        and VERSION.fullmatch(identity["core_version"]) is not None
        and identity["core_network"] == "regtest"
    )


def _utc_valid(value: object) -> bool:
    if type(value) is not str or not value or len(value) > 50:
        return False
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return when.utcoffset() == timedelta(0)
    except (ValueError, TypeError, OverflowError):
        return False


def r03_effective_status(record: object, candidate: object,
                         *, receipt_verified: bool = False) -> str:
    """Return PASS/FAIL/PENDING/STALE, never invent a previously unproved PASS.

    A changed exact-code/native Core/WSP/signer/custody/GUI/dependency/package
    identity turns an old verified PASS (or FAIL) into STALE. Missing, skipped,
    unsupported and unauthenticated evidence remains PENDING.

    `receipt_verified` must be set ONLY after separately verifying the actual
    signed/runner/physical evidence; the record itself cannot prove that.
    No returned state permits wallet operations or Core activation.
    """
    if type(record) is not dict or type(candidate) is not dict:
        return "PENDING"
    if record.get("schema") != SCHEMA:
        return "PENDING"
    state = record.get("status")
    if state == "STALE":
        return "STALE"
    if state not in ("PASS", "FAIL"):
        return "PENDING"
    if record.get("kind") not in KINDS:
        return "PENDING"
    old = record.get("identity")
    if not _identity_valid(old) or not _identity_valid(candidate, allow_artifact=True):
        return "PENDING"
    if any(old[k] != candidate[k] for k in IDENTITY_KEYS):
        return "STALE"
    if receipt_verified is not True:
        return "PENDING"
    if not _utc_valid(record.get("tested_utc")):
        return "PENDING"
    if (type(record.get("test_ref")) is not str
            or not 1 <= len(record["test_ref"]) <= 512):
        return "PENDING"
    if (type(record.get("receipt_sha256")) is not str
            or HEX64.fullmatch(record["receipt_sha256"]) is None):
        return "PENDING"
    kind = record["kind"]
    if kind in ("CORE_E2E", "FROZEN") and record.get("genuine_core") is not True:
        return "PENDING"
    if kind == "FROZEN" and record.get("final_entrypoint") is not True:
        return "PENDING"
    # Source equivalence is insufficient when the frozen/native release
    # executable changed. The caller must bind the exact artifact bytes.
    if kind in ("FROZEN", "PHYSICAL", "DEV_REVIEWED"):
        artifact = record.get("artifact_sha256")
        actual_artifact = candidate.get("artifact_sha256")
        if (type(artifact) is not str or HEX64.fullmatch(artifact) is None
                or type(actual_artifact) is not str
                or HEX64.fullmatch(actual_artifact) is None):
            return "PENDING"
        if artifact != actual_artifact:
            return "STALE"
    if kind in ("PHYSICAL", "DEV_REVIEWED"):
        if (record.get("authorized_operator_receipt_verified") is not True
                or type(record.get("authorized_operator_ref")) is not str
                or not record["authorized_operator_ref"]):
            return "PENDING"
    return state


def r03_invalidation_reasons(old: object, candidate: object) -> tuple[str, ...]:
    """Public key names only: never emit private receipt values or file paths."""
    if not _identity_valid(old) or not _identity_valid(candidate, allow_artifact=True):
        return ("R03_IDENTITY_INCOMPLETE",)
    return tuple(k for k in IDENTITY_KEYS if old[k] != candidate[k])
