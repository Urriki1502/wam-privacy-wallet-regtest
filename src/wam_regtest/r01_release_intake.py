"""R-01 offline, non-executing WAM Core release authenticity intake.

No network access, node process, wallet, executable extraction or install.
All inputs must be explicit public release files selected by the operator.
Signature authenticity is checked by the pre-existing pinned-key verifier;
compatibility/activation remain separate, never inferred from valid GPG.
"""
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import re
import stat
import tempfile

from . import release


class CoreIntakeRefusal(ValueError):
    """Stable non-sensitive refusal code."""


PLATFORMS = {
    "macos-arm64": ("arm64-apple-darwin", ".tar.gz"),
    "linux-x64": ("x86_64-linux-gnu", ".tar.gz"),
    "windows-x64": ("x86_64-w64-mingw32", ".zip"),
}
# This is a recognition scope, NOT an approval allowlist for executing Core.
KNOWN_RELEASES = frozenset(("v0.1.11", "v0.1.12"))
MAX_BYTES = {"SIGNING-KEY.asc": 32768, "SHA256SUMS": 131072,
             "SHA256SUMS.asc": 16384, "archive": 320 * 1024 * 1024}
SHA_RE = re.compile(r"[0-9a-f]{64}\\Z")


def _copy_untrusted_file(source: Path, dest: Path, maximum: int) -> None:
    """Snapshot from one file descriptor; reject symlinks, hardlinks and drift."""
    if type(source) is not type(Path()) or not source.is_absolute():
        raise CoreIntakeRefusal("R01_INPUT_SCOPE_DENIED")
    try:
        before = os.lstat(source)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or before.st_size < 1 or before.st_size > maximum):
            raise CoreIntakeRefusal("R01_INPUT_TYPE_DENIED")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        with os.fdopen(os.open(source, flags), "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino, opened.st_size) != (before.st_dev, before.st_ino, before.st_size):
                raise CoreIntakeRefusal("R01_INPUT_CHANGED")
            size = 0
            with dest.open("xb") as output:
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > maximum:
                        raise CoreIntakeRefusal("R01_INPUT_SIZE_DENIED")
                    output.write(chunk)
            after = os.fstat(stream.fileno())
            current = os.lstat(source)
            if (size != before.st_size or
                    (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) !=
                    (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) or
                    (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) !=
                    (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)):
                raise CoreIntakeRefusal("R01_INPUT_CHANGED")
    except CoreIntakeRefusal:
        raise
    except (OSError, ValueError):
        raise CoreIntakeRefusal("R01_INPUT_UNAVAILABLE") from None


def verify_offline_core_intake(*, version: str, platform: str, archive: Path,
                               signing_key: Path, sha256sums: Path,
                               signature: Path, gpg_path: str = "gpg") -> dict:
    """Verify detached signature and matching archive SHA; never activate Core.

    The independently reviewed signer fingerprint is pinned in release.py.
    Source/operator provenance of the public key must ALSO be independently
    assessed before an owner trusts it; a matching key file is not provenance.
    """
    if (type(version) is not str or version not in KNOWN_RELEASES or
            type(platform) is not str or platform not in PLATFORMS or
            type(gpg_path) is not str or not gpg_path):
        raise CoreIntakeRefusal("R01_RELEASE_SCOPE_DENIED")
    suffix, ext = PLATFORMS[platform]
    expected_name = f"wam-coin-{version}-{suffix}{ext}"
    if type(archive) is not type(Path()) or archive.name != expected_name:
        raise CoreIntakeRefusal("R01_ASSET_PLATFORM_DENIED")
    inputs = ((signing_key, "SIGNING-KEY.asc"),
              (sha256sums, "SHA256SUMS"),
              (signature, "SHA256SUMS.asc"),
              (archive, "archive"))
    with tempfile.TemporaryDirectory(prefix="wam-r01-offline-") as tmpname:
        directory = Path(tmpname)
        os.chmod(directory, 0o700)
        for source, name in inputs:
            # Canonicalize ONLY our private output name, not the user's source.
            _copy_untrusted_file(source, directory / name, MAX_BYTES[name])
        (directory / "archive").rename(directory / expected_name)
        try:
            signed_digest = release._validate_signed_sums(gpg_path, directory, expected_name)
        except release.ReleaseError:
            raise CoreIntakeRefusal("R01_SIGNATURE_OR_SIGNER_DENIED") from None
        if type(signed_digest) is not str or SHA_RE.fullmatch(signed_digest) is None:
            raise CoreIntakeRefusal("R01_SIGNED_MANIFEST_DENIED")
        computed = sha256()
        with (directory / expected_name).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                computed.update(chunk)
        if computed.hexdigest() != signed_digest:
            raise CoreIntakeRefusal("R01_ARCHIVE_SHA_DENIED")
    return {
        "status": "R01_OFFLINE_SIGNATURE_AND_ARCHIVE_PASS_ONLY",
        "version": version, "platform": platform,
        "archive": expected_name, "archive_sha256": signed_digest,
        "pinned_signer_fingerprint": release.FINGERPRINT,
        "signed_manifest_and_archive_verified": True,
        "trusted_key_distribution_independently_attested": False,
        "core_compatibility_qualified": False,
        "native_binary_executed": False,
        "wallet_signing_or_broadcast_allowed": False,
        "core_install_or_activation_allowed": False,
        "mainnet_allowed": False,
    }
