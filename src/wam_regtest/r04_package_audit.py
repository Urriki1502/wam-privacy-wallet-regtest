"""R-04 public release-candidate package inventory audit (no execution).

Checks final published *output directory* against its self-contained manifest
and SHA256SUMS, after native/frozen E2E and before CI publication. A matching
untrusted manifest is NOT a publisher signature, trusted Core, reproducible
toolchain, physical approval or permission to install/activate anything.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

SCHEMA = "wam-regtest-release-candidate/v1"
SHA64 = re.compile(r"[0-9a-f]{64}")
SHA40 = re.compile(r"[0-9a-f]{40}")
ALLOWED_PLATFORMS = (
    "macos-arm64", "windows-x64", "linux-x86_64-headless",
    "linux-x86_64-desktop",
)
SUMS = "SHA256SUMS.txt"
MANIFEST = "RELEASE_CANDIDATE_MANIFEST.json"
MAX_FILES = 8192
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
MAX_SUMS_BYTES = 1024 * 1024


class PackageAuditError(ValueError):
    """Fixed public refusal without filesystem paths or contents."""


def _unique_pairs(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise PackageAuditError("R04_DUPLICATE_MANIFEST_KEY_DENIED")
        result[name] = value
    return result


def _digest(path: Path) -> str:
    before = path.lstat()
    if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
            or before.st_size < 0
            or getattr(before, "st_file_attributes", 0) & 0x400):
        raise PackageAuditError("R04_MEMBER_TYPE_DENIED")
    h = sha256()
    with path.open("rb") as inp:
        opened = os.fstat(inp.fileno())
        # Windows CRT fstat/lstat can present different cached timestamps
        # for the same file handle. Compare each native view to itself across
        # hashing, and the common size across views; do not bypass change checks.
        if (before.st_size != opened.st_size
                or os.name != "nt" and not _same(before, opened)):
            raise PackageAuditError("R04_MEMBER_CHANGED")
        while True:
            part = inp.read(1024 * 1024)
            if not part:
                break
            h.update(part)
        if not _same(opened, os.fstat(inp.fileno())):
            raise PackageAuditError("R04_MEMBER_CHANGED")
    if not _same(before, path.lstat()):
        raise PackageAuditError("R04_MEMBER_CHANGED")
    return h.hexdigest()


def _same(a, b):
    return all(getattr(a, k) == getattr(b, k) for k in (
        "st_dev", "st_ino", "st_size", "st_mode", "st_mtime_ns", "st_ctime_ns",
        "st_nlink",
    ))


def _safe_name(name: object, *, top_level: bool = False) -> bool:
    if (type(name) is not str or not 1 <= len(name) <= 512
            or any(ord(c) < 32 or ord(c) == 127 for c in name)
            or "\\" in name or name.startswith("/") or "\x00" in name):
        return False
    parts = PurePosixPath(name).parts
    return (parts and name == "/".join(parts)
            and all(p not in ("", ".", "..") for p in parts)
            and (len(parts) == 1 if top_level else True))


def _regular_tree(output: Path) -> dict[str, Path]:
    try:
        root = output.lstat()
        if not stat.S_ISDIR(root.st_mode) or output.is_symlink():
            raise PackageAuditError("R04_ROOT_DENIED")
        items = list(output.rglob("*"))
        if not 2 <= len(items) <= MAX_FILES:
            raise PackageAuditError("R04_MEMBER_COUNT_DENIED")
        files = {}
        folds = set()
        for path in items:
            rel = path.relative_to(output).as_posix()
            if not _safe_name(rel) or rel.casefold() in folds:
                raise PackageAuditError("R04_MEMBER_PATH_DENIED")
            folds.add(rel.casefold())
            native = path.lstat()
            if path.is_symlink() or getattr(native, "st_file_attributes", 0) & 0x400:
                raise PackageAuditError("R04_MEMBER_TYPE_DENIED")
            if stat.S_ISDIR(native.st_mode):
                continue
            if not stat.S_ISREG(native.st_mode) or native.st_nlink != 1:
                raise PackageAuditError("R04_MEMBER_TYPE_DENIED")
            files[rel] = path
        if MANIFEST not in files or SUMS not in files:
            raise PackageAuditError("R04_INVENTORY_MISSING")
        return files
    except PackageAuditError:
        raise
    except (OSError, ValueError):
        raise PackageAuditError("R04_TREE_READ_DENIED") from None


def _read_small(path: Path, bound: int) -> bytes:
    if path.lstat().st_size > bound:
        raise PackageAuditError("R04_METADATA_OVERSIZE_DENIED")
    try:
        raw = path.read_bytes()
        if not 1 <= len(raw) <= bound:
            raise PackageAuditError("R04_METADATA_SIZE_DENIED")
        return raw
    except OSError:
        raise PackageAuditError("R04_METADATA_READ_DENIED") from None


def audit_candidate_output(output: Path, *, expected_platform: str | None = None) -> dict:
    """Verify exact file set and checksums; never trust manifest as approval.

    The audit must run under an independently authenticated clean build runner.
    A malicious party able to rewrite files AND manifest can still forge it.
    """
    if (not isinstance(output, Path) or
            expected_platform is not None and expected_platform not in ALLOWED_PLATFORMS):
        raise PackageAuditError("R04_AUDIT_INPUT_DENIED")
    files = _regular_tree(output)
    try:
        record = json.loads(_read_small(files[MANIFEST], MAX_MANIFEST_BYTES),
                            object_pairs_hook=_unique_pairs,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except PackageAuditError:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise PackageAuditError("R04_MANIFEST_FORMAT_DENIED") from None

    if (type(record) is not dict or record.get("schema") != SCHEMA
            or record.get("candidate_id") != "WAM-Fusion-REGTEST-RC1"
            or record.get("network") != "regtest"
            or record.get("platform") not in ALLOWED_PLATFORMS
            or expected_platform is not None and record["platform"] != expected_platform
            or record.get("mainnet_allowed") is not False
            or record.get("production_qualified") is not False
            or record.get("official_final_release") is not False
            or record.get("dev_wam_reviewed") is not False
            or record.get("native_final_executable_e2e_pass") is not True
            or type(record.get("source_head_sha")) is not str
            or SHA40.fullmatch(record["source_head_sha"]) is None
            or type(record.get("checkout_sha")) is not str
            or SHA40.fullmatch(record["checkout_sha"]) is None
            or type(record.get("wsp_source_commit")) is not str
            or SHA40.fullmatch(record["wsp_source_commit"]) is None):
        raise PackageAuditError("R04_MANIFEST_PROFILE_DENIED")
    core = record.get("core_sha256")
    core_names = ({"wamd.exe", "wam-cli.exe"} if record["platform"] == "windows-x64"
                  else {"wamd", "wam-cli"})
    if (type(core) is not dict or set(core) != core_names
            or any(type(v) is not str or SHA64.fullmatch(v) is None
                   for v in core.values())):
        raise PackageAuditError("R04_CORE_PROFILE_DENIED")
    declared = record.get("files_sha256")
    if (type(declared) is not dict or len(declared) != len(files) - 2
            or set(declared) != set(files) - {MANIFEST, SUMS}):
        raise PackageAuditError("R04_MANIFEST_FILE_SET_DENIED")
    for rel, expected in declared.items():
        if (not _safe_name(rel) or type(expected) is not str
                or SHA64.fullmatch(expected) is None
                or _digest(files[rel]) != expected):
            raise PackageAuditError("R04_MANIFEST_FILE_HASH_DENIED")

    try:
        raw = _read_small(files[SUMS], MAX_SUMS_BYTES).decode("ascii")
    except UnicodeError:
        raise PackageAuditError("R04_SUMS_FORMAT_DENIED") from None
    # Accepted CRLF on Windows, but strict two-space sha256sum format.
    normalized = raw.replace("\r\n", "\n")
    if not normalized.endswith("\n") or "\r" in normalized:
        raise PackageAuditError("R04_SUMS_FORMAT_DENIED")
    values = {}
    for line in normalized[:-1].split("\n"):
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None or not _safe_name(match[2], top_level=True):
            raise PackageAuditError("R04_SUMS_FORMAT_DENIED")
        if match[2] in values:
            raise PackageAuditError("R04_SUMS_DUPLICATE_DENIED")
        values[match[2]] = match[1]
    top_files = {rel for rel in files if "/" not in rel and rel != SUMS}
    if set(values) != top_files or list(values) != sorted(values):
        raise PackageAuditError("R04_SUMS_FILE_SET_DENIED")
    for rel, expected in values.items():
        if _digest(files[rel]) != expected:
            raise PackageAuditError("R04_SUMS_HASH_DENIED")
    return {
        "schema": "wam-fusion-r04-final-package-audit/v1",
        "status": "R04_PUBLIC_OUTPUT_INVENTORY_MATCH_ONLY",
        "platform": record["platform"],
        "source_head_sha": record["source_head_sha"],
        "checkout_sha": record["checkout_sha"],
        "files_checked": len(files),
        "manifest_sha256": _digest(files[MANIFEST]),
        "sums_sha256": _digest(files[SUMS]),
        "native_execution_verified_by_this_audit": False,
        "publisher_signature_verified_by_this_audit": False,
        "byte_identical_cross_build_reproducibility_qualified": False,
        "physical_operator_accepted": False,
        "r04_full_p0_qualified": False,
        "mainnet_allowed": False,
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Read-only REGTEST candidate output integrity")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--platform", choices=ALLOWED_PLATFORMS, required=True)
    args = parser.parse_args()
    try:
        result = audit_candidate_output(args.output, expected_platform=args.platform)
    except PackageAuditError as exc:
        parser.exit(2, str(exc) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
