"""K-04: refuse unsafe Core wallet files and quarantine genuine SQLite backups.

This is an INPUT + disposable REGTEST Core-owned restore probe, NOT a
WSP seed import, private-descriptor decoder, Core-wallet signer or blanket
mainnet wallet importer. The original source is always opened read-only and
must remain identical before and after copying. No transfer into the user's
persistent managed Core or double-loading a miner wallet is authorized here.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import re
import secrets
import stat

SQLITE_MAGIC=b"SQLite format 3\x00"
MIN_SQLITE=4096
MAX_SQLITE=128*1024*1024
MAX_QUARANTINE_NAME=60


class CoreSqliteImportError(ValueError):
    pass


@dataclass(frozen=True,repr=False)
class CoreSqliteReceipt:
    file_sha256: str
    byte_count: int
    format: str = "sqlite"
    network: str = "UNVERIFIED"  # Header does not encode WAM chain provenance.

    def __repr__(self):
        return "<CoreSqliteReceipt public-only network-unverified>"


def _native_source_open(source):
    if (type(source) is not type(Path()) or not source.is_absolute()
            or source.suffix.lower()!=".dat"
            or not 1<=len(source.name)<=MAX_QUARANTINE_NAME
            or source.name.count("/") or "\x00" in str(source)
            or source.is_symlink()):
        raise CoreSqliteImportError("K04_SQLITE_SOURCE_PATH_DENIED")
    for extension in ("-wal","-shm","-journal"):
        entry=source.with_name(source.name+extension)
        if entry.exists() or entry.is_symlink():
            # A live SQLite wallet may have uncheckpointed transactions.
            raise CoreSqliteImportError("K04_SQLITE_LIVE_OR_PARTIAL_BACKUP_DENIED")
    flags=os.O_RDONLY | getattr(os,"O_NOFOLLOW",0)
    if hasattr(os,"O_CLOEXEC"):flags|=os.O_CLOEXEC
    if hasattr(os,"O_NONBLOCK"):flags|=os.O_NONBLOCK
    try:
        fd=os.open(source,flags)
        identity=os.fstat(fd)
        if (not stat.S_ISREG(identity.st_mode)
                or identity.st_nlink!=1
                or not MIN_SQLITE<=identity.st_size<=MAX_SQLITE):
            raise CoreSqliteImportError("K04_SQLITE_SOURCE_SIZE_OR_TYPE_DENIED")
        if os.name!="nt" and (identity.st_uid!=os.geteuid()
                               or (identity.st_mode&0o077)!=0):
            raise CoreSqliteImportError("K04_SQLITE_SOURCE_CUSTODY_DENIED")
        # No SQLite connection or descriptor parsing: bytes are only
        # passed to independently qualified Core's supported restore RPC.
        header=os.read(fd,100)
        if (len(header)!=100 or not header.startswith(SQLITE_MAGIC)
                or header[18] not in (1,2) or header[19] not in (1,2)
                or header[21:24]!=b"\x40\x20\x20"
                or int.from_bytes(header[16:18],"big") not in
                    (512,1024,2048,4096,8192,16384,32768,1)):
            raise CoreSqliteImportError("K04_NOT_SQLITE_CORE_BACKUP")
        os.lseek(fd,0,os.SEEK_SET)
        return fd,identity
    except CoreSqliteImportError:
        if "fd" in locals():os.close(fd)
        raise
    except (OSError,ValueError):
        if "fd" in locals():os.close(fd)
        raise CoreSqliteImportError("K04_SQLITE_SOURCE_UNVERIFIED") from None


def inspect_sqlite_backup(source):
    """Read-only validation, no copies, Core RPC, private keys, logs or paths."""
    fd,identity=_native_source_open(source)
    try:
        digest=sha256()
        amount=0
        while True:
            block=os.read(fd,65536)
            if not block:break
            amount+=len(block)
            if amount>MAX_SQLITE:
                raise CoreSqliteImportError("K04_SQLITE_SIZE_CHANGED")
            digest.update(block)
        after=os.fstat(fd)
        if (amount!=identity.st_size
                or (identity.st_dev,identity.st_ino,identity.st_size,
                    identity.st_mtime_ns,identity.st_ctime_ns)
                !=(after.st_dev,after.st_ino,after.st_size,
                   after.st_mtime_ns,after.st_ctime_ns)):
            raise CoreSqliteImportError("K04_SQLITE_SOURCE_CHANGED")
        return CoreSqliteReceipt(digest.hexdigest(),amount)
    except CoreSqliteImportError:raise
    except OSError:
        raise CoreSqliteImportError("K04_SQLITE_SOURCE_READ_DENIED") from None
    finally:os.close(fd)


def stage_verified_backup(source, staging, *, authorized=False):
    """Exclusive create-only copy in native private disposable REGTEST staging.

    Caller MUST hold a staging-owner/chain lease. Never auto-replace a
    foreign file, remove an unknown file, or copy a live miner's WAL.
    This creates a new staging file only; it never loads a wallet.
    """
    if authorized is not True:
        raise CoreSqliteImportError("K04_EXPLICIT_DISPOSABLE_CONSENT_REQUIRED")
    from .custody import storage
    if (type(staging) is not type(Path()) or not staging.is_absolute()
            or source.parent==staging or staging.is_symlink()):
        raise CoreSqliteImportError("K04_STAGING_SCOPE_DENIED")
    try:
        storage().validate_directory(staging)
    except Exception:
        raise CoreSqliteImportError("K04_STAGING_PRIVATE_CUSTODY_DENIED") from None
    before=inspect_sqlite_backup(source)
    reader,identity=_native_source_open(source)
    name="wallet-"+secrets.token_hex(16)+".dat"
    destination=staging/name
    fd=None
    try:
        if len(name)>MAX_QUARANTINE_NAME:
            raise CoreSqliteImportError("K04_STAGE_NAME_DENIED")
        fd=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL
                   |getattr(os,"O_NOFOLLOW",0),0o600)
        digest=sha256()
        total=0
        while True:
            block=os.read(reader,65536)
            if not block:break
            total+=len(block)
            if total>MAX_SQLITE:
                raise CoreSqliteImportError("K04_COPY_EXCEEDED_LIMIT")
            digest.update(block)
            view=memoryview(block)
            while view:
                written=os.write(fd,view)
                if written<=0:raise OSError("short write")
                view=view[written:]
        os.fsync(fd)
        current=os.fstat(reader)
        if ((current.st_dev,current.st_ino,current.st_size,
             current.st_mtime_ns,current.st_ctime_ns)
            !=(identity.st_dev,identity.st_ino,identity.st_size,
               identity.st_mtime_ns,identity.st_ctime_ns)
            or digest.hexdigest()!=before.file_sha256
            or total!=before.byte_count
            or inspect_sqlite_backup(source)!=before):
            raise CoreSqliteImportError("K04_SOURCE_CHANGED_DURING_COPY")
        return destination,before
    except Exception:
        # A partially published file may represent ambiguous handling.
        # Never auto-adopt or delete it; owner must inspect/reconcile.
        raise CoreSqliteImportError("K04_STAGING_UNVERIFIED") from None
    finally:
        os.close(reader)
        if fd is not None:os.close(fd)


def verify_restored_core_wallet(*, chain, genesis, wallet_info,
                                descriptor_listing):
    """Only genuine Core-provided public descriptor data; no DB decoding."""
    from .v1_contracts import (
        require_regtest,core_descriptor_identity,WalletContractError,
    )
    try:
        require_regtest(chain,genesis)
        if (type(wallet_info) is not dict or wallet_info.get("format")!="sqlite"
                or wallet_info.get("descriptors") is not True
                or type(wallet_info.get("private_keys_enabled")) is not bool
                or wallet_info.get("scanning") not in (False,None)):
            raise ValueError
        identity=core_descriptor_identity(descriptor_listing)
        if type(identity) is not str or not re.fullmatch("[0-9a-f]{64}",identity):
            raise ValueError
        return {"status":"K04_CORE_SQLITE_REGTEST_RESTORE_VERIFIED",
                "format":"sqlite","chain":"regtest",
                "descriptor_identity_sha256":identity,
                "private_keys_enabled":wallet_info["private_keys_enabled"],
                "source_unmodified":True,"synthetic_core":False,
                "wallet_spend_authorized":False,"mainnet_allowed":False}
    except (ValueError,KeyError,TypeError,WalletContractError):
        raise CoreSqliteImportError("K04_CORE_WALLET_UNVERIFIED") from None


def _public_descriptor_set(response):
    """Public descriptor comparison via official Core listdescriptors(false).

    Never examine SQLite wallet table content or retrieve private descriptors.
    Refuse unexpected scalar key material rather than producing diagnostics.
    """
    try:
        entries=response["descriptors"]
        if type(entries) is not list or not 1<=len(entries)<=1000:
            raise ValueError
        distinct=set()
        for item in entries:
            if (type(item) is not dict or
                    type(item.get("desc")) is not str or
                    not 1<=len(item["desc"])<=10000 or
                    type(item.get("internal")) is not bool):
                raise ValueError
            desc=item["desc"]
            if any(marker in desc.lower() for marker in (
                    "xprv","tprv","prv","private_key","wif")):
                raise ValueError
            key=(desc,item["internal"])
            if key in distinct:raise ValueError
            distinct.add(key)
        return frozenset(distinct)
    except (KeyError,TypeError,ValueError):
        raise CoreSqliteImportError("K04_PUBLIC_DESCRIPTOR_SHAPE_DENIED") from None


def require_distinct_descriptors(existing,imported):
    """Refuse any exact duplicate OR partially overlapping Core identities."""
    a=_public_descriptor_set(existing)
    b=_public_descriptor_set(imported)
    if a & b:
        raise CoreSqliteImportError("K04_CORE_ACCOUNT_OVERLAP_DENIED")
    return True
