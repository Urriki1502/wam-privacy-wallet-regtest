"""R-06: non-authorizing public release / rollback preflight (REGTEST only).

Only reads release-candidate manifest-shaped PUBLIC metadata, never actual
wallet, backup, Core process or OS custody. No automatic install/migration.
"""
from __future__ import annotations
import re
from .release import ARCHIVES, CLI_SHA256
from .windows_release_preflight import BINARY_SHA256

SHA40 = re.compile(r"[0-9a-f]{40}")
SHA64 = re.compile(r"[0-9a-f]{64}")
SCHEMA = "wam-regtest-release-candidate/v1"
WSP_PIN = "ac55f13423620252bdbf848c7e8a280c3b84721e"
# Linux developer Core remains separate from officially signed release inputs.
_LINUX = {"wamd": "ccc9f0f1d299a1e98a49ff83859aa03e994e83e6ea4b7cd60c327eb1e0e8e4d6",
          "wam-cli": "ada9dabd56d0859b9d64c0b20a05c33cb039b2573f75088443b45c35d5379652"}
PINS = {
    "macos-arm64": {"wamd": ARCHIVES["macos-arm64"][1],
                    "wam-cli": CLI_SHA256["macos-arm64"]},
    "windows-x64": dict(BINARY_SHA256),
    "linux-x86_64-desktop": _LINUX,
    "linux-x86_64-headless": _LINUX,
}
PROVENANCE = {platform: ("reviewed-developer-source-build" if platform.startswith("linux")
                         else "official-signed-v0.1.11") for platform in PINS}


class ReleaseTransitionError(ValueError):
    """Fixed redacted reason codes; never serialize untrusted private inputs."""


def _valid(m: object) -> bool:
    if type(m) is not dict or m.get("schema") != SCHEMA:
        return False
    platform = m.get("platform")
    if type(platform) is not str or platform not in PINS:
        return False
    if (m.get("candidate_id") != "WAM-Fusion-REGTEST-RC1"
            or m.get("network") != "regtest"
            or m.get("mainnet_allowed") is not False
            or m.get("production_qualified") is not False
            or m.get("official_final_release") is not False
            or m.get("dev_wam_reviewed") is not False
            or m.get("native_final_executable_e2e_pass") is not True
            or m.get("core_provenance") != PROVENANCE[platform]
            or m.get("core_sha256") != PINS[platform]
            or m.get("wsp_source_commit") != WSP_PIN
            or type(m.get("single_commit_build")) is not bool):
        return False
    for field in ("source_head_sha", "checkout_sha"):
        value = m.get(field)
        if type(value) is not str or SHA40.fullmatch(value) is None:
            return False
    dependencies = m.get("dependencies")
    if (type(dependencies) is not dict or len(dependencies) > 80
            or any(type(k) is not str or not 1 <= len(k) <= 100
                   or type(v) is not str or not 1 <= len(v) <= 80
                   for k, v in dependencies.items())):
        return False
    files = m.get("files_sha256")
    if (type(files) is not dict or not 1 <= len(files) <= 8192
            or any(type(k) is not str or not 1 <= len(k) <= 512
                   or type(v) is not str or SHA64.fullmatch(v) is None
                   for k, v in files.items())):
        return False
    return True


def review_transition(previous: object, candidate: object,
                      *, previous_provenance_verified: bool = False,
                      candidate_provenance_verified: bool = False) -> dict:
    """Conservative operator decision aid. No release authority granted.

    Proof flags are EXTERNAL statements about independent validation of real
    bytes and runner origin. JSON cannot verify itself; booleans alone are
    never permission to replace Core, anchors, backups or live wallet state.
    """
    if (type(previous_provenance_verified) is not bool
            or type(candidate_provenance_verified) is not bool):
        raise ReleaseTransitionError("R06_TRUST_INPUT_DENIED")
    if not _valid(candidate) or previous is not None and not _valid(previous):
        raise ReleaseTransitionError("R06_PUBLIC_MANIFEST_DENIED")
    status = "R06_MANUAL_STATE_REVIEW_REQUIRED"
    if (not candidate["single_commit_build"]
            or candidate["checkout_sha"] != candidate["source_head_sha"]):
        status = "R06_SYNTHETIC_MERGE_BUILD_DENIED"
    elif previous is None:
        status = "R06_NEW_REGTEST_INSTALL_REVIEW_REQUIRED"
    elif previous["platform"] != candidate["platform"]:
        status = "R06_OS_CHANGE_MIGRATION_REVIEW_REQUIRED"
    elif previous["core_provenance"] != candidate["core_provenance"] or previous["core_sha256"] != candidate["core_sha256"]:
        status = "R06_CORE_PROFILE_CHANGE_REVIEW_REQUIRED"
    elif previous["wsp_source_commit"] != candidate["wsp_source_commit"]:
        status = "R06_WSP_MIGRATION_REVIEW_REQUIRED"
    elif previous["dependencies"] != candidate["dependencies"]:
        status = "R06_DEPENDENCY_CHANGE_REQUALIFICATION_REQUIRED"
    elif previous["source_head_sha"] == candidate["source_head_sha"]:
        status = ("R06_SAME_SOURCE_ARTIFACT_DRIFT_REVIEW_REQUIRED"
                  if previous["files_sha256"] != candidate["files_sha256"]
                  else "R06_SAME_RELEASE_NO_AUTOMATIC_REINSTALL")
    if (status == "R06_MANUAL_STATE_REVIEW_REQUIRED"
            and (not candidate_provenance_verified
                 or previous is not None and not previous_provenance_verified)):
        status = "R06_INDEPENDENT_PROVENANCE_PENDING"

    return {
        "schema": "wam-fusion-r06-public-transition-review/v1",
        "status": status,
        "network": "regtest",
        "platform": candidate["platform"],
        "candidate_source_sha": candidate["source_head_sha"],
        "previous_source_sha": previous["source_head_sha"] if previous is not None else None,
        "previous_provenance_claimed_verified": previous_provenance_verified if previous is not None else False,
        "candidate_provenance_claimed_verified": candidate_provenance_verified,
        "core_or_os_auto_upgrade_allowed": False,
        "wallet_or_anchor_reset_allowed": False,
        "old_signed_or_uncertain_reservations_cleared": False,
        "rollback_executable_approved": False,
        "install_approved_by_this_review": False,
        "cross_platform_migration_qualified": False,
        "physical_operator_accepted": False,
        "external_dev_reviewed": False,
        "r06_full_p0_qualified": False,
        "mainnet_allowed": False,
    }
