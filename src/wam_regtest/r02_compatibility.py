"""R-02: versioned REGTEST Core compatibility gate (non-activating).

A correctly signed release is NOT an approved WAM Fusion runtime. New upstream
tags cannot extend the v0.1.11 RPC compatibility profile by themselves.
All release classification results are preflight-only; no signer, loader,
wallet, node, process or executable is authorized by this module.
"""
from __future__ import annotations

import re

from .release import ARCHIVES, CLI_SHA256, FINGERPRINT
from .windows_release_preflight import BINARY_SHA256 as WINDOWS_BINARIES

# Independently measured on genuine official v0.1.11 Core.
# Changes require explicit R-02 compatibility approval and real 3-OS E2E,
# NEVER just a changed signed release or parsed version number.
COMPATIBLE_RPC_V011 = (111, "/WAM:0.1.11/", 70016)
SUPPORTED_REGTEST_CORE = "v0.1.11"
SIGNER_FINGERPRINT = FINGERPRINT

# Native developer Linux Core is not an official-signed runtime. It retains
# its separate linux_runtime approval path; never auto-map that build here.
V011_OFFICIAL_MEMBER_PINS = {
    "macos-arm64": {
        "wamd": ARCHIVES["macos-arm64"][1],
        "wam_cli": CLI_SHA256["macos-arm64"],
    },
    "windows-x64": {
        "wamd": WINDOWS_BINARIES["wamd.exe"],
        "wam_cli": WINDOWS_BINARIES["wam-cli.exe"],
    },
}
HEX64 = re.compile(r"[0-9a-f]{64}")
RECOGNIZED_PLATFORMS = ("macos-arm64", "windows-x64", "linux-x64")
RECOGNIZED_TAGS = ("v0.1.11", "v0.1.12")


class R02CompatibilityError(ValueError):
    """Stable redacted refusal: never include untrusted input in an error."""


def matches_v011_native_rpc(info: object) -> bool:
    """Re-check actual Core RPC version; no signed-version fallback."""
    return (
        type(info) is dict
        and type(info.get("version")) is int
        and type(info.get("subversion")) is str
        and type(info.get("protocolversion")) is int
        and (info["version"], info["subversion"], info["protocolversion"])
            == COMPATIBLE_RPC_V011
    )


def classify_release_candidate(*, platform: str, version: str, network: str,
                               wamd_sha256: str, wam_cli_sha256: str,
                               signer_fingerprint: str,
                               signed_archive_verified: bool) -> dict:
    """Conservative, pure preflight from public claimed observations.

    CAUTION: caller fields can be forged. They are NEVER authority to run
    software, reuse an authenticated release, replace any Core binary or unlock
    funds. R-01 must verify actual input bytes separately, and R-02 needs
    independent E2E/review receipts before any future version becomes allowed.
    """
    if (type(platform) is not str or type(version) is not str
            or type(network) is not str
            or type(wamd_sha256) is not str or type(wam_cli_sha256) is not str
            or type(signer_fingerprint) is not str
            or type(signed_archive_verified) is not bool):
        raise R02CompatibilityError("R02_PROFILE_INPUT_DENIED")
    if (not HEX64.fullmatch(wamd_sha256)
            or not HEX64.fullmatch(wam_cli_sha256)
            or len(signer_fingerprint) != 40
            or not re.fullmatch(r"[0-9A-F]{40}", signer_fingerprint)):
        raise R02CompatibilityError("R02_PROFILE_FORMAT_DENIED")

    status = "R02_UNAPPROVED_RELEASE_REFUSED"
    member_identity = False
    if network != "regtest":
        status = "R02_NON_REGTEST_DENIED"
    elif platform not in RECOGNIZED_PLATFORMS or version not in RECOGNIZED_TAGS:
        status = "R02_UNKNOWN_PROFILE_DENIED"
    elif (signed_archive_verified is not True
          or signer_fingerprint != SIGNER_FINGERPRINT):
        status = "R02_UNTRUSTED_RELEASE_DENIED"
    elif version != SUPPORTED_REGTEST_CORE:
        # v0.1.12 pre-release is NOT compatible merely because signed.
        status = "R02_NEW_VERSION_REQUALIFICATION_PENDING"
    elif platform == "linux-x64":
        status = "R02_LINUX_NATIVE_PROVENANCE_AND_CLI_PENDING"
    else:
        expected = V011_OFFICIAL_MEMBER_PINS[platform]
        member_identity = (wamd_sha256 == expected["wamd"]
                           and wam_cli_sha256 == expected["wam_cli"])
        status = ("R02_V011_PUBLIC_MEMBER_PINS_MATCH_ONLY" if member_identity
                  else "R02_OFFICIAL_MEMBER_HASH_DENIED")
    return {
        "schema": "wam-fusion-r02-public-compat-preflight/v1",
        "status": status,
        "platform": platform if platform in RECOGNIZED_PLATFORMS else "unrecognized",
        "version": version if version in RECOGNIZED_TAGS else "unrecognized",
        "network": network if network == "regtest" else "denied",
        "public_member_pins_matched": member_identity,
        "observed_release_is_genuinely_authenticated_here": False,
        "runtime_process_and_core_attested_here": False,
        "cross_platform_core_e2e_qualified": False,
        "wsp_and_signer_e2e_qualified": False,
        "descriptor_import_and_recovery_qualified": False,
        "frozen_gui_and_os_custody_qualified": False,
        "r02_full_p0_qualified": False,
        "core_activation_allowed": False,
        "wallet_signing_or_broadcast_allowed": False,
        "mainnet_allowed": False,
    }
