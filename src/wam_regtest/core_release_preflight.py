"""Offline *intake only* for WAM Core v0.1.12; never install or authorize execution.

Release body/asset listing are untrusted advisory metadata. The independently
pinned WAM OpenPGP key authenticates SHA256SUMS.asc -> SHA256SUMS -> archive.
Even a valid signature does not qualify a new Core for Fusion REGTEST.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import sys
import tarfile
import tempfile
import zipfile

from .release import FINGERPRINT, MAX_ARCHIVE, MAX_MEMBER, ReleaseError

CANDIDATE = "v0.1.12"
CURRENT_APPROVED = "v0.1.11"  # Candidate preflight floor, NOT approval of v0.1.12.
ASSETS = {
    "macos-arm64": "wam-coin-v0.1.12-arm64-apple-darwin.tar.gz",
    "windows-x64": "wam-coin-v0.1.12-x86_64-w64-mingw32.zip",
    "linux-x64": "wam-coin-v0.1.12-x86_64-linux-gnu.tar.gz",
}
ROOT = "wam-coin-v0.1.12"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
VERSION = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")
MAX_TOTAL_UNCOMPRESSED = 512 * 1024 * 1024
MAX_ENTRIES = 256


class IntakeError(ValueError):
    """Only static public error codes; never expose local paths or GPG output."""


def _deny(code: str):
    raise IntakeError(code)


def _version(value: str) -> tuple[int, int, int]:
    if type(value) is not str or not (m := VERSION.fullmatch(value)):
        _deny("CORE_RELEASE_VERSION_DENIED")
    return tuple(map(int, m.groups()))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _input_file(path: Path, maximum: int) -> None:
    if (type(path) is not type(Path()) or not path.is_absolute()
            or path.is_symlink() or not path.is_file()
            or not 0 < path.stat().st_size <= maximum):
        _deny("CORE_RELEASE_FILE_DENIED")


def _signed_digest(gpg: str, files: Path, asset_name: str) -> str:
    # Reuse the existing isolated-GNUPGHOME verifier, including its exact
    # hard-coded primary fingerprint and VALIDSIG checks. No new key source.
    from .release import _validate_signed_sums
    return _validate_signed_sums(gpg, files, asset_name)


def _validate_entry(name: str, seen: set[str]) -> str:
    clean = name.rstrip("/")
    parts = clean.split("/")
    if (not clean or len(clean) > 512 or "\\" in clean or ":" in clean
            or parts[0] != ROOT or any(p in ("", ".", "..") for p in parts)
            or clean.casefold() in seen):
        _deny("CORE_RELEASE_MEMBER_DENIED")
    seen.add(clean.casefold())
    return clean


def _archive_shape(path: Path, platform: str) -> dict[str, int]:
    suffix = ".exe" if platform == "windows-x64" else ""
    required = {f"{ROOT}/bin/wamd{suffix}", f"{ROOT}/bin/wam-cli{suffix}"}
    seen: set[str] = set()
    found: dict[str, int] = {}
    total = 0
    try:
        if platform == "windows-x64":
            with zipfile.ZipFile(path) as archive:
                members = archive.infolist()
                if not 2 <= len(members) <= MAX_ENTRIES:
                    _deny("CORE_RELEASE_COUNT_DENIED")
                for m in members:
                    if getattr(m, "orig_filename", None) != m.filename:
                        _deny("CORE_RELEASE_MEMBER_DENIED")
                    name = _validate_entry(m.filename, seen)
                    kind = (m.external_attr >> 16) & 0o170000
                    if ((m.flag_bits & 1) or kind == stat.S_IFLNK
                            or m.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                        _deny("CORE_RELEASE_MEMBER_DENIED")
                    if m.is_dir():
                        if m.file_size: _deny("CORE_RELEASE_MEMBER_DENIED")
                        continue
                    if not 0 <= m.file_size <= MAX_MEMBER: _deny("CORE_RELEASE_SIZE_DENIED")
                    total += m.file_size
                    if total > MAX_TOTAL_UNCOMPRESSED: _deny("CORE_RELEASE_SIZE_DENIED")
                    if name in required:
                        if not m.file_size: _deny("CORE_RELEASE_MEMBER_DENIED")
                        found[name] = m.file_size
        else:
            with tarfile.open(path, "r:gz") as archive:
                members = archive.getmembers()
                if not 2 <= len(members) <= MAX_ENTRIES:
                    _deny("CORE_RELEASE_COUNT_DENIED")
                for m in members:
                    name = _validate_entry(m.name, seen)
                    if not (m.isfile() or m.isdir()) or m.issym() or m.islnk():
                        _deny("CORE_RELEASE_MEMBER_DENIED")
                    if not 0 <= m.size <= MAX_MEMBER: _deny("CORE_RELEASE_SIZE_DENIED")
                    if m.isfile():
                        total += m.size
                        if total > MAX_TOTAL_UNCOMPRESSED: _deny("CORE_RELEASE_SIZE_DENIED")
                        if name in required:
                            if not m.size: _deny("CORE_RELEASE_MEMBER_DENIED")
                            found[name] = m.size
    except IntakeError:
        raise
    except (OSError, ValueError, EOFError, RuntimeError, tarfile.TarError, zipfile.BadZipFile, zipfile.LargeZipFile):
        _deny("CORE_RELEASE_ARCHIVE_DENIED")
    if set(found) != required:
        _deny("CORE_RELEASE_BINARY_MEMBERS_DENIED")
    return {name.rsplit("/", 1)[-1]: size for name, size in sorted(found.items())}


def update_signal(untrusted_release_body: str | None) -> str:
    """Advisory only: never call untrusted release text an authenticated priority."""
    if untrusted_release_body is None:
        return "UNKNOWN"
    if type(untrusted_release_body) is not str or len(untrusted_release_body) > 65536:
        _deny("CORE_RELEASE_NOTES_DENIED")
    first = next((line.strip() for line in untrusted_release_body.splitlines() if line.strip()), "")
    if not first: return "UNKNOWN"
    if first.startswith("MANDATORY:"):
        return "UNVERIFIED_MANDATORY_CLAIM" if first[len("MANDATORY:"):].strip() else "UNKNOWN"
    return "UNVERIFIED_NORMAL_CLAIM"


def review_offline(archive: Path, signing_key: Path, sums: Path, signature: Path,
                   platform: str, *, installed: str = CURRENT_APPROVED,
                   minimum: str = CURRENT_APPROVED, release_body: str | None = None,
                   gpg: str = "gpg") -> dict:
    """Pure offline signed intake; does not install, execute, or approve Core."""
    if type(platform) is not str or platform not in ASSETS:
        _deny("CORE_RELEASE_PLATFORM_DENIED")
    # Caller-provided installed/minimum arguments cannot lower the invariant
    # independently pinned v0.1.11 floor. A real update manager must read its
    # highest-accepted version from protected OS custody, not CLI arguments.
    if (_version(installed) < _version(CURRENT_APPROVED)
            or _version(minimum) < _version(CURRENT_APPROVED)
            or _version(CANDIDATE) <= _version(installed)
            or _version(CANDIDATE) < _version(minimum)
            or _version(installed) < _version(minimum)):
        _deny("CORE_RELEASE_ROLLBACK_DENIED")
    if type(gpg) is not str or not gpg or len(gpg) > 512:
        _deny("CORE_RELEASE_GPG_DENIED")
    _input_file(archive, MAX_ARCHIVE)
    if archive.name != ASSETS[platform]:
        _deny("CORE_RELEASE_ASSET_DENIED")
    for path, limit in ((signing_key, 32768), (sums, 131072), (signature, 16384)):
        _input_file(path, limit)
    priority = update_signal(release_body)
    with tempfile.TemporaryDirectory(prefix="wam-v012-intake-") as temp:
        workspace = Path(temp)
        workspace.chmod(0o700)
        for src, dst in ((signing_key, "SIGNING-KEY.asc"), (sums, "SHA256SUMS"),
                         (signature, "SHA256SUMS.asc")):
            shutil.copyfile(src, workspace / dst)
        try:
            signed_sha = _signed_digest(gpg, workspace, archive.name)
        except (ReleaseError, OSError, UnicodeError):
            _deny("CORE_RELEASE_SIGNATURE_DENIED")
        if type(signed_sha) is not str or not HEX64.fullmatch(signed_sha):
            _deny("CORE_RELEASE_SIGNED_DIGEST_DENIED")
    if _sha256(archive) != signed_sha:
        _deny("CORE_RELEASE_ARCHIVE_DIGEST_DENIED")
    members = _archive_shape(archive, platform)
    return {
        "status": "SIGNED_CORE_V012_INTAKE_ONLY_COMPATIBILITY_PENDING",
        "version": CANDIDATE, "platform": platform,
        "archive_sha256": signed_sha,
        "signer_fingerprint": FINGERPRINT,
        "expected_members": members,
        "advisory_release_signal": priority,
        "release_notes_authenticated": False,
        "signed_archive_verified": True,
        "core_version_profile_qualified": False,
        "native_core_e2e_qualified": False,
        "wallet_signing_authorized": False,
        "installation_authorized": False,
        "mainnet_allowed": False,
    }


def main() -> int:
    cli = argparse.ArgumentParser(description="OFFLINE v0.1.12 intake ONLY; NEVER EXEC / INSTALL")
    cli.add_argument("--platform", choices=sorted(ASSETS), required=True)
    for name in ("archive", "signing-key", "sums", "signature"):
        cli.add_argument("--" + name, required=True, type=Path)
    cli.add_argument("--installed", default=CURRENT_APPROVED)
    cli.add_argument("--minimum", default=CURRENT_APPROVED)
    cli.add_argument("--release-body", type=Path, help="UNAUTHENTICATED advisory only")
    cli.add_argument("--gpg", default="gpg")
    args = cli.parse_args()
    try:
        body = None
        if args.release_body is not None:
            _input_file(args.release_body, 65536)
            body = args.release_body.read_text(encoding="utf-8")
        result = review_offline(args.archive, args.signing_key, args.sums, args.signature,
                                args.platform, installed=args.installed, minimum=args.minimum,
                                release_body=body, gpg=args.gpg)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (IntakeError, OSError, UnicodeError) as exc:
        print(str(exc) if isinstance(exc, IntakeError) else "CORE_RELEASE_INPUT_DENIED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
