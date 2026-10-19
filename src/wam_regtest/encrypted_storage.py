"""Create-only encrypted envelopes using macOS no-follow descriptor custody.

Publication/fsync pattern adapted from the MIT legacy encrypted_scan_backup
at acfdb18d079617e0899c7cdf6a870b6598e4096f. Ciphertext only; no crypto here.
"""
import os
from pathlib import Path
import re
import secrets
import stat
from .private_directory import open_macos_private_directory

MAX_ENVELOPE = 32 * 1024 * 1024 + 52


class EncryptedStorageError(ValueError):
    pass


def _name(name):
    if type(name) is not str or not re.fullmatch(r"[a-z0-9-]{1,80}\.enc", name):
        raise EncryptedStorageError("ENCRYPTED_STORAGE_NAME_DENIED")


def publish(directory: Path, name: str, ciphertext: bytes):
    _name(name)
    if (type(ciphertext) is not bytes or not 52 <= len(ciphertext) <= MAX_ENVELOPE
            or not ciphertext.startswith(b"WAMSP02\x00")):
        raise EncryptedStorageError("ENCRYPTED_STORAGE_FORMAT_DENIED")
    dfd = open_macos_private_directory(directory)
    temporary = ".stage-" + secrets.token_hex(16)
    fd = None
    staged = False
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                     | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=dfd)
        staged = True
        os.fchmod(fd, 0o600)
        offset = 0
        while offset < len(ciphertext):
            count = os.write(fd, ciphertext[offset:])
            if count <= 0:
                raise OSError
            offset += count
        os.fsync(fd)
        os.close(fd)
        fd = None
        os.link(temporary, name, src_dir_fd=dfd, dst_dir_fd=dfd,
                follow_symlinks=False)
        os.unlink(temporary, dir_fd=dfd)
        staged = False
        os.fsync(dfd)
    except (OSError, ValueError):
        raise EncryptedStorageError("ENCRYPTED_STORAGE_PUBLISH_DENIED") from None
    finally:
        if fd is not None:
            os.close(fd)
        if staged:
            os.unlink(temporary, dir_fd=dfd)
        os.close(dfd)


def read(directory: Path, name: str) -> bytes:
    _name(name)
    dfd = open_macos_private_directory(directory)
    fd = None
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
                     | os.O_NONBLOCK, dir_fd=dfd)
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or stat.S_IMODE(before.st_mode) != 0o600
                or before.st_uid != os.geteuid() or before.st_nlink != 1
                or not 52 <= before.st_size <= MAX_ENVELOPE):
            raise EncryptedStorageError("ENCRYPTED_STORAGE_FILE_DENIED")
        parts, remaining = [], before.st_size
        while remaining:
            part = os.read(fd, min(remaining, 65536))
            if not part:
                raise EncryptedStorageError("ENCRYPTED_STORAGE_READ_DENIED")
            parts.append(part)
            remaining -= len(part)
        after = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_mode", "st_uid", "st_nlink",
                  "st_size", "st_mtime_ns", "st_ctime_ns")
        if any(getattr(before, f) != getattr(after, f) for f in fields):
            raise EncryptedStorageError("ENCRYPTED_STORAGE_CHANGED")
        return b"".join(parts)
    except (OSError, ValueError):
        raise EncryptedStorageError("ENCRYPTED_STORAGE_READ_DENIED") from None
    finally:
        if fd is not None:
            os.close(fd)
        os.close(dfd)


def validate_directory(directory):
    fd = open_macos_private_directory(directory)
    os.close(fd)


def read_crash_residue(directory: Path, name: str) -> bytes:
    """K-09 read-only descriptor evidence, not a general encrypted file reader.

    A POSIX interrupted link/unlink can leave exactly two hard links; ordinary
    vault restore still requires one. No stage file is moved or removed here.
    """
    from .private_directory import _require_absent_acl
    if (type(name) is not str or not (
            re.fullmatch(r"\.stage-[0-9a-f]{32}", name)
            or re.fullmatch(r"snapshot-[0-9]{9}\.enc", name))):
        raise EncryptedStorageError("K09_MAC_RESIDUE_NAME_DENIED")
    dfd = open_macos_private_directory(directory)
    fd = None
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
                     | os.O_NONBLOCK, dir_fd=dfd)
        before = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid",
                  "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
        if (not stat.S_ISREG(before.st_mode)
                or stat.S_IMODE(before.st_mode) != 0o600
                or before.st_uid != os.geteuid()
                or before.st_nlink not in (1, 2)
                or os.get_inheritable(fd)
                or not 52 <= before.st_size <= MAX_ENVELOPE):
            raise EncryptedStorageError("K09_MAC_RESIDUE_METADATA_DENIED")
        _require_absent_acl(fd)
        parts, remaining = [], before.st_size
        while remaining:
            chunk = os.read(fd, min(remaining, 65536))
            if not chunk:
                raise EncryptedStorageError("K09_MAC_RESIDUE_SHORT_READ")
            parts.append(chunk)
            remaining -= len(chunk)
        _require_absent_acl(fd)
        after = os.fstat(fd)
        if any(getattr(before, field) != getattr(after, field)
               for field in fields):
            raise EncryptedStorageError("K09_MAC_RESIDUE_CHANGED")
        # A held descriptor protects bytes, not the stability of the name.
        # Reopen only metadata with no-follow relative to the held directory.
        named = os.stat(name, dir_fd=dfd, follow_symlinks=False)
        if any(getattr(before, field) != getattr(named, field)
               for field in fields):
            raise EncryptedStorageError("K09_MAC_RESIDUE_CHANGED")
        raw = b"".join(parts)
        if not raw.startswith(b"WAMSP02\x00"):
            raise EncryptedStorageError("K09_MAC_RESIDUE_FORMAT_DENIED")
        return raw
    except (OSError, ValueError):
        raise EncryptedStorageError("K09_MAC_RESIDUE_READ_DENIED") from None
    finally:
        if fd is not None:
            os.close(fd)
        os.close(dfd)
