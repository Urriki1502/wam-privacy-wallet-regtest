"""K-05 fail-closed classification of wallet backup *envelopes*, REGTEST only.

An old Berkeley DB wallet.dat is deprecated, never converted or auto-loaded.
Only a 32-byte header is examined BEFORE K-04 custody checks, for rejection
classification only; no BDB parser, private descriptor, secret or BIP39 words are read.
A recognized BDB page magic is a *candidate*, not provenance/network proof.
All source files remain unchanged. No Core RPC/write/signing capability.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat

from .core_sqlite_import import (
    CoreSqliteImportError, inspect_sqlite_backup, MIN_SQLITE, MAX_SQLITE,
    MAX_QUARANTINE_NAME,
)

# Berkeley DB Btree/Hash metadata page magics (also accept either byte order).
# This is a rejection heuristic ONLY, not approval of a BDB conversion.
_BDB_PAGE_MAGIC=frozenset((0x00053162,0x00061561))
_ALLOWED_NAMES=frozenset((".dat",".enc",".txt"))


def _looks_like_bdb(source):
    """Read max 32 header bytes for refusal; never trust/copy or parse keys."""
    if (type(source) is not type(Path()) or not source.is_absolute()
            or source.suffix.lower()!=".dat"
            or not 1<=len(source.name)<=MAX_QUARANTINE_NAME
            or source.is_symlink()):
        raise CoreSqliteImportError("K05_SOURCE_UNTRUSTED")
    for ext in ("-wal","-shm","-journal"):
        other=source.with_name(source.name+ext)
        if other.exists() or other.is_symlink():
            raise CoreSqliteImportError("K05_LIVE_WALLET_DENIED")
    fd=None
    try:
        flags=(os.O_RDONLY | getattr(os,"O_BINARY",0)
               | getattr(os,"O_NOFOLLOW",0)
               | getattr(os,"O_CLOEXEC",0))
        fd=os.open(source,flags)
        before=os.fstat(fd)
        # Only non-authoritative FORMAT classification. Many legitimate old
        # backups come from ZIP/USB with mode 0644 or a different POSIX UID.
        # K-04 MUST still enforce native owner-only custody BEFORE any copy,
        # quarantine or Core restore. Never weaken that acceptance gate.
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink!=1
                or not MIN_SQLITE<=before.st_size<=MAX_SQLITE):
            raise CoreSqliteImportError("K05_SOURCE_UNTRUSTED")
        header=os.read(fd,32)
        after=os.fstat(fd)
        if (len(header)!=32 or
                (before.st_dev,before.st_ino,before.st_size,
                 before.st_mtime_ns,before.st_ctime_ns)
                !=(after.st_dev,after.st_ino,after.st_size,
                   after.st_mtime_ns,after.st_ctime_ns)):
            raise CoreSqliteImportError("K05_SOURCE_CHANGED")
        # BDB DBMETA magic lives at bytes 12..15. Wrong/missing magic
        # stays UNKNOWN, not 'safe SQLite' or 'approved migration'.
        magic=header[12:16]
        return (int.from_bytes(magic,"little") in _BDB_PAGE_MAGIC
                or int.from_bytes(magic,"big") in _BDB_PAGE_MAGIC)
    except CoreSqliteImportError:
        raise
    except (OSError,ValueError):
        raise CoreSqliteImportError("K05_SOURCE_UNTRUSTED") from None
    finally:
        if fd is not None:
            os.close(fd)


def inspect_backup_format(source):
    """Return K-04 verified SQLite receipt OR one safe, typed refusal.

    Extension classification is performed BEFORE touching any .enc or text
    backup. Never open, inspect or log user-provided mnemonic text.
    """
    if type(source) is not type(Path()) or not source.is_absolute():
        raise CoreSqliteImportError("K05_BACKUP_SELECTION_DENIED")
    ext=source.suffix.lower()
    if ext==".enc":
        raise CoreSqliteImportError("K05_FUSION_ENCRYPTED_BACKUP_SEPARATE")
    if ext==".txt":
        raise CoreSqliteImportError("K05_MNEMONIC_TEXT_NOT_WALLET_DAT")
    if ext!=".dat":
        raise CoreSqliteImportError("K05_UNKNOWN_BACKUP_TYPE_DENIED")
    # DEV WAM review: K-04 insists on mode 0600/owner UID before looking
    # at the header, which made K-05's user-facing BDB explanation unreachable
    # for a normal ZIP/USB export (0644). A HEADER READ is not a migration.
    # Classification-first grants no new positive path and reads max 32 bytes.
    if _looks_like_bdb(source):
        raise CoreSqliteImportError("K05_BDB_DEPRECATED_UNSUPPORTED")
    try:
        # All actual SQLite acceptance / file copying still goes through
        # the UNCHANGED K-04 native custody + full-file identity checks.
        return inspect_sqlite_backup(source)
    except CoreSqliteImportError as error:
        if error.args==("K04_NOT_SQLITE_CORE_BACKUP",):
            raise CoreSqliteImportError("K05_UNKNOWN_CORE_DAT_DENIED") from None
        if error.args==("K04_SQLITE_SOURCE_CUSTODY_DENIED",):
            raise CoreSqliteImportError("K05_SQLITE_PRIVATE_CUSTODY_REQUIRED") from None
        raise
