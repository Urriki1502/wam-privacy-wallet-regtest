"""Fetch and verify OFFICIAL signed WAM Core v0.1.13 release binaries.

Fixed WAM HTTPS endpoints and independently pinned GPG signer. Only the
wamd/wam-cli binary members are extracted. Does NOT start or authorize Core.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import urllib.error

FINGERPRINT = "4BD4A8D3AFD43F5CBCB500E23798462FE00ADBA4"
VERSION = "v0.1.13"
RELEASE_URL = "https://wamcoin.org"
MEMBER_ROOT = "wam-coin-v0.1.13/bin/"
ARCHIVES = {
    "macos-arm64": (
        "wam-coin-v0.1.13-arm64-apple-darwin.tar.gz",
        "fe04a61f17eb8047f1d2a537ebcb61b45cbde14c491bc332d2a2ab7ee18237ba",
    ),
    "linux-x64": (
        "wam-coin-v0.1.13-x86_64-linux-gnu.tar.gz",
        "a3e3bf810e74824e3739fd4cbd1a45037cae997056b8c978c4dc1a61d674f0c7",
    ),
}
# Independently pinned exact macOS CLI member from the same GPG-verified
# official v0.1.13 archive; a mutable receipt cannot authorize another CLI.
CLI_SHA256 = {
    "linux-x64": "d99fc90e3aa4233979056d9981a388360e5d7ff77090d00b9bc37191a2425300",
    "macos-arm64": "2b19fdac692cbed5810b6fa9663ac89f25ab8f346da84c5fd13bf2b8535e3e19",
}
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
MAX_ARCHIVE = 320 * 1024 * 1024
MAX_MEMBER = 128 * 1024 * 1024


class ReleaseError(ValueError):
    """Redacted error codes; never include untrusted response bytes."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ReleaseError("RELEASE_REDIRECT_DENIED")


def _download_exact(relative: str, maximum: int, dest: Path) -> None:
    if not relative.startswith("/") or ".." in relative:
        raise ReleaseError("RELEASE_URI_DENIED")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    request = urllib.request.Request(
        RELEASE_URL + relative,
        headers={"Accept-Encoding": "identity", "User-Agent": "WAM-REGTEST-Release-Review/0.1"},
    )
    count = 0
    try:
        with opener.open(request, timeout=90) as response, dest.open("xb") as out:
            if response.status != 200 or response.getheader("Content-Encoding") not in (None, "identity"):
                raise ReleaseError("RELEASE_HTTP_DENIED")
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                count += len(chunk)
                if count > maximum:
                    raise ReleaseError("RELEASE_SIZE_DENIED")
                out.write(chunk)
        if count == 0:
            raise ReleaseError("RELEASE_SIZE_DENIED")
    except ReleaseError:
        raise
    except (OSError, ValueError, TimeoutError, urllib.error.URLError):
        raise ReleaseError("RELEASE_DOWNLOAD_DENIED") from None


def _sha(path: Path) -> str:
    dig = hashlib.sha256()
    with path.open("rb") as inp:
        while True:
            chunk = inp.read(1024 * 1024)
            if not chunk:
                break
            dig.update(chunk)
    return dig.hexdigest()


def _gpg(exe: str, home: Path, *args: str) -> tuple[int, str]:
    # The Git-for-Windows MSYS GnuPG bundled on hosted Windows runners expects
    # /c/... POSIX paths, NOT C:\\... Win32 paths. Without conversion it tries
    # to open <working-directory>/C:\\.../pubring.kbx and fails before parsing.
    # Retain exact official fingerprint and detached signature verification.
    if os.name == "nt":
        import shutil
        resolved = shutil.which(exe) or ""
        normalized = resolved.replace("\\", "/").lower()
        if not normalized.endswith("/git/usr/bin/gpg.exe"):
            raise ReleaseError("RELEASE_WINDOWS_GPG_RUNTIME_DENIED")
        def native_to_msys(value: str) -> str:
            if re.match(r"^[A-Za-z]:[\\/]", value):
                return "/" + value[0].lower() + "/" + value[3:].replace("\\", "/")
            return value
        gpg_home = native_to_msys(str(home))
        gpg_args = tuple(native_to_msys(arg) for arg in args)
    else:
        gpg_home, gpg_args = str(home), args
    # Windows GnuPG requires the OS system directory for its native runtime.
    # Keep the isolated GNUPGHOME and strict public-key/signature checks;
    # do not import user keyrings or process arbitrary GPG configuration.
    env = {"GNUPGHOME": gpg_home, "HOME": gpg_home, "LC_ALL": "C",
           "PATH": os.environ.get("PATH", "")}
    if os.name == "nt":
        root = os.environ.get("SystemRoot") or os.environ.get("SYSTEMROOT")
        if not root or not os.path.isabs(root):
            raise ReleaseError("RELEASE_WINDOWS_SYSTEMROOT_DENIED")
        env["SystemRoot"] = root
    try:
        p = subprocess.run(
            [exe, "--homedir", gpg_home, "--batch", "--no-tty", "--no-autostart",
             "--no-auto-key-retrieve", *gpg_args],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, timeout=30, check=False,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ReleaseError("RELEASE_GPG_UNAVAILABLE") from None
    return p.returncode, p.stdout.decode("utf-8", "replace")


def _validate_signed_sums(gpg_path: str, tmp: Path, archive_name: str) -> str:
    key = tmp / "SIGNING-KEY.asc"
    sums = tmp / "SHA256SUMS"
    sig = tmp / "SHA256SUMS.asc"
    home = tmp / "gnupg"
    home.mkdir(mode=0o700)
    rc, key_data = _gpg(gpg_path, home, "--with-colons", "--import-options", "show-only", "--import", str(key))
    primaries = []
    state = ""
    for line in key_data.splitlines():
        bits = line.split(":")
        if bits[0] == "pub":
            state = "pub"
        elif bits[0] == "sub":
            state = "sub"
        elif bits[0] == "fpr" and len(bits) > 9 and state == "pub":
            primaries.append(bits[9])
    if rc != 0 or primaries != [FINGERPRINT]:
        raise ReleaseError("RELEASE_SIGNER_DENIED")
    ring = tmp / "public-release.gpg"
    rc, _ = _gpg(gpg_path, home, "--dearmor", "--output", str(ring), str(key))
    if rc != 0:
        raise ReleaseError("RELEASE_SIGNER_DENIED")
    rc, checks = _gpg(gpg_path, home, "--no-default-keyring", "--keyring", str(ring),
                      "--status-fd", "1", "--verify", str(sig), str(sums))
    valids = [line.split() for line in checks.splitlines() if line.startswith("[GNUPG:] VALIDSIG ")]
    denied_status = {'BADSIG', 'ERRSIG', 'EXPSIG', 'EXPKEYSIG', 'REVKEYSIG',
                     'KEYREVOKED', 'KEYEXPIRED', 'SIGEXPIRED', 'FAILURE', 'ERROR'}
    bad = any(len(line.split()) > 1 and line.split()[0] == '[GNUPG:]'
              and line.split()[1] in denied_status for line in checks.splitlines())
    if rc != 0 or bad or len(valids) != 1 or valids[0][2] != FINGERPRINT:
        raise ReleaseError("RELEASE_SIGNATURE_DENIED")
    try:
        lines = sums.read_text(encoding="ascii").splitlines()
    except UnicodeError:
        raise ReleaseError("RELEASE_SUMS_DENIED") from None
    found = {}
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64}) [ *]([A-Za-z0-9._-]+)", line)
        if match is None or match.group(2) in found:
            raise ReleaseError("RELEASE_SUMS_DENIED")
        found[match.group(2)] = match.group(1)
    if archive_name not in found:
        raise ReleaseError("RELEASE_ASSET_NOT_SIGNED")
    return found[archive_name]


def _write_exact_binary(tar: tarfile.TarFile, member: tarfile.TarInfo, target: Path) -> str:
    if not member.isfile() or not 0 < member.size <= MAX_MEMBER:
        raise ReleaseError("RELEASE_MEMBER_DENIED")
    dig = hashlib.sha256()
    fileobj = tar.extractfile(member)
    if fileobj is None:
        raise ReleaseError("RELEASE_MEMBER_DENIED")
    with fileobj, target.open("xb") as output:
        os.chmod(target, 0o700)
        remaining = member.size
        while remaining:
            chunk = fileobj.read(min(1024 * 1024, remaining))
            if not chunk:
                raise ReleaseError("RELEASE_MEMBER_TRUNCATED")
            dig.update(chunk)
            output.write(chunk)
            remaining -= len(chunk)
        if fileobj.read(1):
            raise ReleaseError("RELEASE_MEMBER_DENIED")
        output.flush()
        os.fsync(output.fileno())
    return dig.hexdigest()


def _verify_executable_shape(target: Path, os_arch: str) -> None:
    with target.open("rb") as f:
        hdr = f.read(32)
    if os_arch == "macos-arm64":
        if len(hdr) != 32 or struct.unpack("<IiiI", hdr[:16])[:2] != (0xFEEDFACF, 0x0100000C) or struct.unpack("<I", hdr[12:16])[0] != 2:
            raise ReleaseError("RELEASE_MACHO_ARM64_DENIED")
    elif not (hdr[:4] == b"\x7fELF" and len(hdr) == 32 and hdr[4] == 2 and hdr[18:20] == b"\x3e\x00"):
        raise ReleaseError("RELEASE_ELF_AMD64_DENIED")


def review_and_stage(os_arch: str, destination: Path, gpg_exe: str = "gpg") -> dict:
    if os_arch not in ARCHIVES:
        raise ReleaseError("RELEASE_SCOPE_DENIED")
    from .official_core_v013 import stage_tar
    return stage_tar('linux-x86_64' if os_arch == 'linux-x64' else os_arch,
                     destination, gpg_exe)


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage signed official WAM v0.1.13 Core (NO EXEC)")
    ap.add_argument("--platform", choices=sorted(ARCHIVES), required=True)
    ap.add_argument("--destination", type=Path, required=True)
    ap.add_argument("--gpg", default="gpg")
    args = ap.parse_args()
    try:
        result = review_and_stage(args.platform, args.destination.expanduser().absolute(), args.gpg)
        print(json.dumps({"status": "SIGNED_CORE_STAGE_PASS", "platform": result["platform"], "wamd_sha256": result["wamd_sha256"]}, sort_keys=True))
        return 0
    except ReleaseError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
