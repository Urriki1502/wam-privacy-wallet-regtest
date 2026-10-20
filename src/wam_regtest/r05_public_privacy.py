"""R-05 read-only privacy checks for public native release-candidate outputs.

Narrow, high-confidence publication boundary: detect secret-bearing paths and
unambiguous plaintext credential markers in public receipts/text artifacts.
This is NOT source auditing, binary/ZIP inspection, image analysis, telemetry
verification, a human security review or real-wallet operation authorization.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import stat

from .r04_package_audit import _regular_tree, PackageAuditError

TEXT_SUFFIXES = {".json", ".jsonl", ".txt", ".md", ".log", ".yaml",
                 ".yml", ".ini", ".cfg", ".conf", ".xml", ".csv"}
TEXT_LIMIT = 16 * 1024 * 1024
TOTAL_LIMIT = 64 * 1024 * 1024
HASH_SEAL = "wam-fusion-r05-public-output-privacy/v1"

# Named private files cannot enter the public release tree even if no known
# secret string happens to be present at the time of inspection.
DANGEROUS_BASENAMES = {
    "wam.conf", "wallet.dat", ".cookie", ".env", "debug.log",
    "credentials.json", "secrets.json", "id_rsa", "id_ed25519",
}
DANGEROUS_SUFFIXES = (
    ".sqlite", ".sqlite3", ".sqlite-wal", ".sqlite-shm",
    ".sqlite-journal", ".db", ".keychain-db", ".enc",
    ".pem", ".p12", ".pfx", ".seed", ".mnemonic",
    ".secret", ".secrets", ".bak",
)
# Require an explicit value marker; don't reject ordinary operator docs that
# *discuss* RPC credentials, recovery or sensitive data handling.
SECRET_PATTERNS = (
    re.compile(r"(?im)^\s*(?:rpcpassword|rpc_user_password|rpc_pass(?:word)?)\s*=\s*\S+"),
    re.compile(r'(?im)"(?:rpcpassword|rpc_password|seed_phrase|mnemonic|private_key|secret_key)"\s*:\s*"[^"]+"'),
    re.compile(r"-----BEGIN (?:[A-Z0-9 ]* )?PRIVATE KEY-----"),
    re.compile(r"-----BEGIN OPENSSH PRIVATE KEY-----"),
    re.compile(r"(?i)\bAuthorization\s*:\s*Basic\s+[A-Za-z0-9+/]{8,}={0,2}"),
    re.compile(r"\bxprv[1-9A-HJ-NP-Za-km-z]{30,}\b"),
)


class PrivacyAuditError(ValueError):
    """Only static reason codes; never print the path, value or source bytes."""


def _sensitive_name(relative: str) -> bool:
    for name in relative.lower().split("/"):
        if name in DANGEROUS_BASENAMES or name.startswith(".env."):
            return True
        if any(name.endswith(ext) for ext in DANGEROUS_SUFFIXES):
            return True
    return False


def _checked_text(path: Path) -> str:
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > TEXT_LIMIT:
        raise PrivacyAuditError("R05_PUBLIC_TEXT_TYPE_OR_SIZE_DENIED")
    try:
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            if opened.st_size != before.st_size:
                raise PrivacyAuditError("R05_PUBLIC_TEXT_CHANGED")
            raw = stream.read(TEXT_LIMIT + 1)
            after = os.fstat(stream.fileno())
        stable = (opened.st_size == after.st_size
                  and opened.st_mtime_ns == after.st_mtime_ns
                  and opened.st_ctime_ns == after.st_ctime_ns
                  and opened.st_ino == after.st_ino
                  and opened.st_dev == after.st_dev)
        end = path.lstat()
        if (not stable or len(raw) != before.st_size or
                (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                != (end.st_size, end.st_mtime_ns, end.st_ctime_ns)):
            raise PrivacyAuditError("R05_PUBLIC_TEXT_CHANGED")
        if b"\x00" in raw:
            raise PrivacyAuditError("R05_PUBLIC_TEXT_BINARY_DENIED")
        return raw.decode("utf-8", errors="strict")
    except PrivacyAuditError:
        raise
    except (OSError, UnicodeError, ValueError):
        raise PrivacyAuditError("R05_PUBLIC_TEXT_UNREADABLE") from None


def audit_public_output(output: Path) -> dict:
    """Fail closed on select plaintext/path leaks in an R-04 verified output.

    Run after R-04 and before uploading any native candidate artifact. Do not
    claim a PASS for binary archives, screenshots, OS logs or external review.
    """
    try:
        files = _regular_tree(output)
    except PackageAuditError:
        raise PrivacyAuditError("R05_PUBLIC_TREE_DENIED") from None
    examined = 0
    bytes_examined = 0
    for name, path in sorted(files.items()):
        if _sensitive_name(name):
            raise PrivacyAuditError("R05_PRIVATE_FILENAME_DENIED")
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        value = _checked_text(path)
        bytes_examined += len(value.encode("utf-8"))
        if bytes_examined > TOTAL_LIMIT:
            raise PrivacyAuditError("R05_PUBLIC_TEXT_TOTAL_LIMIT_DENIED")
        if any(pattern.search(value) for pattern in SECRET_PATTERNS):
            raise PrivacyAuditError("R05_PLAINTEXT_SECRET_MARKER_DENIED")
        examined += 1
    return {
        "schema": HASH_SEAL,
        "status": "R05_PUBLIC_TEXT_AND_PATH_AUDIT_PASS",
        "text_files_examined": examined,
        "public_files_scoped": len(files),
        "text_bytes_examined": bytes_examined,
        "binary_archive_payloads_scanned": False,
        "screenshot_pixels_reviewed": False,
        "runtime_dns_or_telemetry_audited": False,
        "external_security_reviewed": False,
        "production_qualified": False,
        "mainnet_allowed": False,
    }
