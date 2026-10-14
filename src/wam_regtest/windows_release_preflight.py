"""Non-executing Windows AMD64 Core intake. No wallet or launch authorization.

Authenticates the official SHA256SUMS signature using the existing macOS
release-verifier implementation, then inspects the ZIP without extraction.
This is a portability preflight, NOT native Windows qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import stat
import struct
import sys
import tempfile
import zipfile

ASSET = "wam-coin-v0.1.11-x86_64-w64-mingw32.zip"
ROOT = "wam-coin-v0.1.11"
# Independently authenticated official v0.1.11 bytes; never learned from a receipt.
ARCHIVE_SHA256 = "ece622fa7ec3072c4e8b0d32e2c3749397d66260f2b0cf22b3636346873d15c5"
BINARY_SHA256 = {
    "wamd.exe": "31717319535c5b784b2bed3b4d3c9a727f5c062e9534b4d27c59d2ffd04e95a1",
    "wam-cli.exe": "538a6d1b918b698ce76a949dda982fdda6776e33ba057efaac59b1af59e59d21",
}
MEMBERS = {f"{ROOT}/bin/{name}.exe" for name in ("wamd", "wam-cli")}
MAX_ARCHIVE_BYTES = 320 * 1024 * 1024
MAX_MEMBER_BYTES = 128 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024


class WindowsReleaseError(ValueError):
    """Error codes only; no host paths, secrets, or untrusted ZIP contents."""


def _fail(code: str):
    raise WindowsReleaseError(code)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _validate_amd64_pe(payload: bytes) -> None:
    """Only structural PE32+/AMD64 validation, NOT Authenticode or loader trust."""
    if type(payload) is not bytes or len(payload) < 128 or payload[:2] != b"MZ":
        _fail("WIN_PE_DOS_DENIED")
    offset = struct.unpack_from("<I", payload, 0x3C)[0]
    if offset < 64 or offset > 4096 or offset + 26 > len(payload):
        _fail("WIN_PE_OFFSET_DENIED")
    if payload[offset:offset + 4] != b"PE\x00\x00":
        _fail("WIN_PE_SIGNATURE_DENIED")
    machine, count, _timestamp, _sympos, _symbols, optional_size, flags = struct.unpack_from(
        "<HHIIIHH", payload, offset + 4)
    if (machine != 0x8664 or not 1 <= count <= 96
            or not 0x70 <= optional_size <= 4096
            or offset + 24 + optional_size > len(payload)
            or not flags & 0x0002 or flags & 0x2000):
        _fail("WIN_PE_AMD64_EXEC_DENIED")
    if payload[offset + 24:offset + 26] != b"\x0b\x02":
        _fail("WIN_PE32_PLUS_DENIED")


def inspect_signed_zip_shape(archive: Path, expected_sha256: str) -> dict:
    """Read-only ZIP inspection after independent signature verification.

    The caller supplies a digest from AUTHENTICATED SHA256SUMS. This method
    checks equality only; calling it directly does not authenticate a signer.
    """
    if (type(archive) is not type(Path()) or not archive.is_file()
            or type(expected_sha256) is not str or len(expected_sha256) != 64
            or any(c not in "0123456789abcdef" for c in expected_sha256)):
        _fail("WIN_RELEASE_INPUT_DENIED")
    size = archive.stat().st_size
    if not 0 < size <= MAX_ARCHIVE_BYTES or _sha256(archive) != expected_sha256:
        _fail("WIN_RELEASE_ARCHIVE_DIGEST_DENIED")
    found: dict[str, str] = {}
    seen: set[str] = set()
    total = 0
    try:
        with zipfile.ZipFile(archive) as bundle:
            entries = bundle.infolist()
            if not 2 <= len(entries) <= 128:
                _fail("WIN_RELEASE_ENTRY_COUNT_DENIED")
            for entry in entries:
                # On native Windows, Python ZipInfo normalizes raw backslash
                # separators to forward slashes before exposing .filename.
                # Verify the ORIGINAL archive entry name first: otherwise
                # a crafted noncanonical member can bypass path policy.
                raw_name = getattr(entry, "orig_filename", None)
                if type(raw_name) is not str or raw_name != entry.filename:
                    _fail("WIN_RELEASE_ZIP_ENTRY_DENIED")
                name = raw_name.rstrip("/")
                components = name.split("/")
                if (not name or len(name) > 512 or name.startswith("/")
                        or "\\" in name or ":" in name
                        or components[0] != ROOT
                        or any(c in ("", ".", "..") for c in components)
                        or name.casefold() in seen
                        or (entry.flag_bits & 1) != 0
                        or (entry.external_attr >> 16) & 0o170000 == stat.S_IFLNK
                        or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                    _fail("WIN_RELEASE_ZIP_ENTRY_DENIED")
                seen.add(name.casefold())
                if entry.is_dir():
                    if entry.file_size != 0:
                        _fail("WIN_RELEASE_ZIP_DIRECTORY_DENIED")
                    continue
                total += entry.file_size
                if (not 0 <= entry.file_size <= MAX_MEMBER_BYTES
                        or total > MAX_UNCOMPRESSED_BYTES):
                    _fail("WIN_RELEASE_ZIP_BOUNDS_DENIED")
                if name in MEMBERS:
                    with bundle.open(entry) as source:
                        payload = source.read(MAX_MEMBER_BYTES + 1)
                    if len(payload) != entry.file_size:
                        _fail("WIN_RELEASE_MEMBER_TRUNCATED")
                    _validate_amd64_pe(payload)
                    found[name] = hashlib.sha256(payload).hexdigest()
    except WindowsReleaseError:
        raise
    except (OSError, ValueError, RuntimeError, EOFError, zipfile.BadZipFile, zipfile.LargeZipFile):
        _fail("WIN_RELEASE_ZIP_READ_DENIED")
    if set(found) != MEMBERS:
        _fail("WIN_RELEASE_MEMBERS_MISSING")
    return {
        "status": "WIN_X64_OFFLINE_CORE_SHAPE_PASS_NOT_EXECUTABLE_AUTHORITY",
        "platform": "windows-x64",
        "release": "v0.1.11",
        "archive_sha256": expected_sha256,
        "member_sha256": {key.rsplit("/", 1)[-1]: found[key] for key in sorted(found)},
        "native_windows_tests_passed": False,
        "loader_process_binding_qualified": False,
        "real_core_e2e_qualified": False,
        "wsp_scanner_qualified": False,
        "wallet_signing_authorized": False,
        "mainnet_allowed": False,
    }


def verify_signed_windows_archive(archive: Path, signing_key: Path,
                                  sha256sums: Path, signature: Path,
                                  gpg_path: str = "gpg") -> dict:
    """Reuse pinned official GPG identity without adding another verifier."""
    from .release import _validate_signed_sums, ReleaseError
    if (not all(type(p) is type(Path()) and p.is_file()
                for p in (archive, signing_key, sha256sums, signature))
            or archive.name != ASSET):
        _fail("WIN_RELEASE_INPUT_DENIED")
    with tempfile.TemporaryDirectory(prefix="wam-win-review-") as d:
        tmp = Path(d)
        for source, name in ((signing_key, "SIGNING-KEY.asc"),
                             (sha256sums, "SHA256SUMS"),
                             (signature, "SHA256SUMS.asc")):
            shutil.copyfile(source, tmp / name)
        try:
            expected = _validate_signed_sums(gpg_path, tmp, ASSET)
        except ReleaseError:
            _fail("WIN_RELEASE_SIGNATURE_DENIED")
    result = inspect_signed_zip_shape(archive, expected)
    if result["archive_sha256"] != ARCHIVE_SHA256 or result["member_sha256"] != BINARY_SHA256:
        _fail("WIN_RELEASE_INDEPENDENT_PIN_DENIED")
    result["signed_archive_verified"] = True
    return result


def main() -> int:
    cli = argparse.ArgumentParser(description="OFFLINE Windows v0.1.11 Core ZIP review — NEVER EXEC")
    for opt in ("archive", "signing-key", "sha256sums", "signature"):
        cli.add_argument("--" + opt, required=True, type=Path)
    cli.add_argument("--gpg", default="gpg")
    args = cli.parse_args()
    try:
        proof = verify_signed_windows_archive(args.archive, args.signing_key,
                                             args.sha256sums, args.signature, args.gpg)
        print(json.dumps(proof, sort_keys=True, separators=(",", ":")))
        return 0
    except WindowsReleaseError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
