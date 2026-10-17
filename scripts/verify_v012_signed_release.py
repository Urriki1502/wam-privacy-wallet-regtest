"""Authenticate official WAM Core v0.1.12 archives without executing binaries.

Explicit network intake on disposable CI host only. Checks GPG-pinned signature,
signed SHA256SUMS, full downloaded archive SHA, and platform member inventory.
The result never authorizes Core activation, wallet signing or mainnet.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib import error, parse, request

from wam_regtest.core_release_preflight import ASSETS, review_offline, IntakeError
from wam_regtest.release import FINGERPRINT

RELEASE = "https://github.com/wamcoin-core-dev/wam-coin/releases/download/v0.1.12/"
KEY = "https://raw.githubusercontent.com/wamcoin-core-dev/wam-coin/v0.1.12/SIGNING-KEY.asc"
ALLOWED_HOSTS = frozenset({
    "github.com", "release-assets.githubusercontent.com",
    "objects.githubusercontent.com", "raw.githubusercontent.com",
})
LIMITS = {
    "SIGNING-KEY.asc": 32768, "SHA256SUMS": 131072, "SHA256SUMS.asc": 16384,
    **{asset: 320 * 1024 * 1024 for asset in ASSETS.values()},
}


class AuditDenied(ValueError):
    """A static code, never a host path or untrusted network response."""


def _deny(code: str) -> None:
    raise AuditDenied(code)


def _allowed(url: str) -> bool:
    try:
        u = parse.urlsplit(url)
        return (u.scheme == "https" and u.hostname in ALLOWED_HOSTS
                and u.username is None and u.password is None
                and u.port in (None, 443) and not u.fragment)
    except ValueError:
        return False


class _RestrictedRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if code not in (301, 302, 303, 307, 308) or not _allowed(newurl):
            _deny("V012_RELEASE_REDIRECT_DENIED")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _download(opener, url: str, dest: Path, maximum: int) -> None:
    if not _allowed(url) or not 0 < maximum <= 320 * 1024 * 1024:
        _deny("V012_RELEASE_DOWNLOAD_SCOPE_DENIED")
    req = request.Request(url, headers={
        "Accept-Encoding": "identity", "User-Agent": "WAM-Signed-Intake-CI/0.1"})
    try:
        with opener.open(req, timeout=65) as stream, dest.open("xb") as output:
            if (stream.status != 200 or not _allowed(stream.url)
                    or stream.headers.get("Content-Encoding") not in (None, "identity")):
                _deny("V012_RELEASE_HTTP_DENIED")
            total = 0
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > maximum:
                    _deny("V012_RELEASE_SIZE_DENIED")
                output.write(chunk)
            if not total:
                _deny("V012_RELEASE_EMPTY_DENIED")
            output.flush()
            os.fsync(output.fileno())
    except AuditDenied:
        raise
    except (OSError, ValueError, TimeoutError, error.URLError):
        _deny("V012_RELEASE_DOWNLOAD_DENIED")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as src:
        for b in iter(lambda: src.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def verify_release() -> dict:
    opener = request.build_opener(request.ProxyHandler({}), _RestrictedRedirect())
    with tempfile.TemporaryDirectory(prefix="wam-v012-signed-review-") as tmp:
        root = Path(tmp)
        root.chmod(0o700)
        key, sums, signature = (root / s for s in (
            "SIGNING-KEY.asc", "SHA256SUMS", "SHA256SUMS.asc"))
        for dest, url in ((key, KEY), (sums, RELEASE + sums.name),
                          (signature, RELEASE + signature.name)):
            _download(opener, url, dest, LIMITS[dest.name])
        platforms = {}
        for platform, asset in sorted(ASSETS.items()):
            archive = root / asset
            _download(opener, RELEASE + asset, archive, LIMITS[asset])
            proof = review_offline(
                archive, key, sums, signature, platform,
                installed="v0.1.11", minimum="v0.1.11")
            if (proof["signer_fingerprint"] != FINGERPRINT
                    or proof["archive_sha256"] != _sha256(archive)
                    or not proof["signed_archive_verified"]
                    or any(proof[flag] for flag in (
                        "wallet_signing_authorized", "installation_authorized",
                        "native_core_e2e_qualified", "core_version_profile_qualified",
                        "mainnet_allowed", "release_notes_authenticated"))):
                _deny("V012_RELEASE_UNEXPECTED_AUTHORITY_DENIED")
            platforms[platform] = {
                "archive_sha256": proof["archive_sha256"],
                "binary_member_names": sorted(proof["expected_members"]),
                "signed_manifest_verified": True,
                "native_binary_executed": False,
                "runtime_approved": False,
            }
        return {
            "schema": "wam-v012-official-signed-archive-proof/v1",
            "status": "OFFICIAL_V012_SIGNED_ARCHIVES_VALIDATED_RUNTIME_PENDING",
            "observed_utc": datetime.now(timezone.utc).isoformat(),
            "checkout_head": os.environ.get("WAM_SOURCE_HEAD", "UNSET"),
            "core_version": "v0.1.12",
            "signer_fingerprint": FINGERPRINT,
            "signed_sums_sha256": _sha256(sums),
            "signature_sha256": _sha256(signature),
            "platforms": platforms,
            "native_core_e2e_qualified": False,
            "wallet_signing_authorized": False,
            "installation_authorized": False,
            "mainnet_allowed": False,
        }


def main() -> int:
    try:
        print(json.dumps(verify_release(), sort_keys=True, separators=(",", ":")))
        return 0
    except (AuditDenied, IntakeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (OSError, ValueError, RuntimeError):
        print("V012_RELEASE_INTAKE_DENIED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
