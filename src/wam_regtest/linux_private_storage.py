"""Linux no-follow ciphertext custody primitives, not a rollback anchor.

Reuses the existing create-only/fsync publication design. No cipher, keyring,
GUI, shell helper, permission repair or wallet-signing authorization lives here.
"""
import errno
import os
from pathlib import Path
import platform
import re
import secrets
import stat
import sys

MAX_ENVELOPE = 32*1024*1024+52


class LinuxStorageError(ValueError):
    pass


def require_native():
    if (sys.platform!='linux' or platform.machine().lower()!='x86_64'
            or os.open not in os.supports_dir_fd
            or not all(hasattr(os,n) for n in ('O_NOFOLLOW','O_CLOEXEC','O_DIRECTORY','listxattr'))):
        raise LinuxStorageError('LINUX_PRIVATE_NATIVE_CAPABILITY_DENIED')


def _identity(info):
    return tuple(getattr(info,k) for k in ('st_dev','st_ino','st_mode','st_uid','st_gid',
        'st_nlink','st_size','st_mtime_ns','st_ctime_ns'))


def _no_acl(fd):
    # Deny both access and inheritable POSIX ACLs. Inspection errors are never
    # interpreted as absent ACLs, including unsupported filesystems.
    try:
        if set(os.listxattr(fd)) & {'system.posix_acl_access','system.posix_acl_default'}:
            raise LinuxStorageError('LINUX_PRIVATE_ACL_DENIED')
    except OSError:
        raise LinuxStorageError('LINUX_PRIVATE_ACL_INSPECTION_DENIED') from None


def _validate_directory_fd(fd):
    before=os.fstat(fd)
    if (not stat.S_ISDIR(before.st_mode) or before.st_uid!=os.geteuid()
            or stat.S_IMODE(before.st_mode)!=0o700 or before.st_nlink<1
            or os.get_inheritable(fd)):
        raise LinuxStorageError('LINUX_PRIVATE_DIRECTORY_METADATA_DENIED')
    _no_acl(fd)
    if _identity(before)!=_identity(os.fstat(fd)):
        raise LinuxStorageError('LINUX_PRIVATE_DIRECTORY_CHANGED')


def _walk(directory, *, private=True):
    require_native()
    if (type(directory) is not type(Path()) or directory.anchor!='/'
            or '..' in directory.parts or not 2<=len(directory.parts)<=256):
        raise LinuxStorageError('LINUX_PRIVATE_PATH_DENIED')
    owned=[]
    try:
        owned.append(os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC))
        for name in directory.parts[1:]:
            owned.append(os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=owned[-1]))
            info=os.fstat(owned[-1])
            # Shared root-owned sticky /tmp is allowed; arbitrary writable
            # ancestors or directories owned by another user are not.
            if (info.st_uid not in (0,os.geteuid()) or
                    (info.st_mode&0o022 and not (info.st_uid==0 and info.st_mode&stat.S_ISVTX))):
                raise LinuxStorageError('LINUX_PRIVATE_ANCESTOR_DENIED')
        if private:_validate_directory_fd(owned[-1])
        else:_no_acl(owned[-1])
        result=owned.pop()
        return result
    except LinuxStorageError:raise
    except OSError:raise LinuxStorageError('LINUX_PRIVATE_DIRECTORY_OPEN_DENIED') from None
    finally:
        for fd in reversed(owned):os.close(fd)


def open_linux_private_directory(directory):return _walk(directory)


def validate_directory(directory):
    fd=_walk(directory)
    os.close(fd)


def create_private_directory(directory):
    require_native()
    if type(directory) is not type(Path()) or directory.name in ('','..','.'):
        raise LinuxStorageError('LINUX_PRIVATE_PATH_DENIED')
    parent=_walk(directory.parent,private=False)
    child=None
    try:
        os.mkdir(directory.name,mode=0o700,dir_fd=parent)
        child=os.open(directory.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent)
        _validate_directory_fd(child)
        os.fsync(child);os.fsync(parent)
    except (OSError,ValueError):
        # Do not repair permissions, replace directories or erase ambiguous
        # newly-created state on an unqualified filesystem.
        raise LinuxStorageError('LINUX_PRIVATE_DIRECTORY_CREATE_DENIED') from None
    finally:
        if child is not None:os.close(child)
        os.close(parent)


def _name(name):
    if type(name) is not str or not re.fullmatch(r'[a-z0-9-]{1,80}\.enc',name):
        raise LinuxStorageError('LINUX_ENVELOPE_NAME_DENIED')


def _validate_file(fd, size_min=52, size_max=MAX_ENVELOPE):
    info=os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid()
            or stat.S_IMODE(info.st_mode)!=0o600 or info.st_nlink!=1
            or not size_min<=info.st_size<=size_max or os.get_inheritable(fd)):
        raise LinuxStorageError('LINUX_ENVELOPE_FILE_DENIED')
    _no_acl(fd)
    return info


def read(directory,name):
    _name(name);dfd=_walk(directory);fd=None
    try:
        fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,dir_fd=dfd)
        before=_validate_file(fd);parts=[];remaining=before.st_size
        while remaining:
            part=os.read(fd,min(remaining,65536))
            if not part:raise LinuxStorageError('LINUX_ENVELOPE_SHORT_READ_DENIED')
            parts.append(part);remaining-=len(part)
        if _identity(before)!=_identity(_validate_file(fd)):
            raise LinuxStorageError('LINUX_ENVELOPE_CHANGED')
        raw=b''.join(parts)
        if not raw.startswith(b'WAMSP02\0'):raise LinuxStorageError('LINUX_ENVELOPE_FORMAT_DENIED')
        return raw
    except LinuxStorageError:raise
    except OSError:raise LinuxStorageError('LINUX_ENVELOPE_READ_DENIED') from None
    finally:
        if fd is not None:os.close(fd)
        os.close(dfd)


def publish(directory,name,ciphertext):
    _name(name)
    if (type(ciphertext) is not bytes or not 52<=len(ciphertext)<=MAX_ENVELOPE
            or not ciphertext.startswith(b'WAMSP02\0')):
        raise LinuxStorageError('LINUX_ENVELOPE_FORMAT_DENIED')
    dfd=_walk(directory);fd=None;stage='.stage-'+secrets.token_hex(16);created=False
    try:
        fd=os.open(stage,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=dfd)
        created=True
        _validate_file(fd,0,MAX_ENVELOPE)
        offset=0
        while offset<len(ciphertext):
            count=os.write(fd,ciphertext[offset:])
            if count<=0:raise LinuxStorageError('LINUX_ENVELOPE_WRITE_DENIED')
            offset+=count
        _validate_file(fd);os.fsync(fd);os.close(fd);fd=None
        os.link(stage,name,src_dir_fd=dfd,dst_dir_fd=dfd,follow_symlinks=False)
        os.unlink(stage,dir_fd=dfd);created=False
        os.fsync(dfd)
        _validate_directory_fd(dfd)
    except LinuxStorageError:raise
    except OSError:raise LinuxStorageError('LINUX_ENVELOPE_PUBLICATION_DENIED') from None
    finally:
        if fd is not None:os.close(fd)
        try:
            if created:
                try:os.unlink(stage,dir_fd=dfd)
                except OSError:raise LinuxStorageError('LINUX_ENVELOPE_STAGE_CLEANUP_DENIED') from None
        finally:os.close(dfd)


class LinuxWalletLease:
    """Same-wallet OS lock across vault directories; not freshness evidence."""
    def __init__(self,root,wallet_id):
        if type(wallet_id) is not str or not re.fullmatch('[0-9a-f]{32}',wallet_id):
            raise LinuxStorageError('LINUX_WALLET_LEASE_ID_DENIED')
        import threading
        self.root,self.wallet_id=root,wallet_id
        self._local=threading.local()
    def hold(self):
        from contextlib import contextmanager
        return contextmanager(self._hold)()
    def _hold(self):
        import fcntl
        if getattr(self._local,'pid',None)==os.getpid():
            yield;return
        dfd=_walk(self.root);fd=None
        try:
            fd=os.open(self.wallet_id+'.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,0o600,dir_fd=dfd)
            _validate_file(fd,0,0)
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError:raise LinuxStorageError('LINUX_WALLET_SESSION_BUSY') from None
            self._local.pid=os.getpid()
            try:yield
            finally:self._local.pid=None;fcntl.flock(fd,fcntl.LOCK_UN)
        finally:
            if fd is not None:os.close(fd)
            os.close(dfd)


def require_trusted_anchor_for_spending():
    # Passphrase encryption, a colocated journal or a lease cannot establish
    # independent monotonic freshness. Never silently use them as an anchor.
    raise LinuxStorageError('LINUX_TRUSTED_ANTI_ROLLBACK_ANCHOR_UNQUALIFIED')
