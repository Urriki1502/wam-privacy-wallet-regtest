"""Native owner-only persistent control state for T05, separate from wallet custody.

Do not use the chain datadir for IPC secrets. No chmod/ACL repair, symlink
following, deletion on failure, or pre-existing user wallet adoption.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import re
import stat
import sys

MAX_CONTROL_FILE=4096
CONTROL_NAMES=frozenset({"supervisor.token","supervisor.scan.token",
                         "supervisor.spend.token","supervisor.profile","supervisor.lock"})


class SupervisorStorageError(ValueError):pass


def _name(name):
    if type(name) is not str or name not in CONTROL_NAMES:
        raise SupervisorStorageError("SUPERVISOR_STORAGE_NAME_DENIED")


def _root(root):
    if (type(root) is not type(Path()) or not root.is_absolute()
            or ".." in root.parts or not re.fullmatch(
                r"wam-fusion-core-[0-9a-f]{16}",root.name)):
        raise SupervisorStorageError("SUPERVISOR_STORAGE_ROOT_DENIED")
    return root


@contextmanager
def _posix_dir(root):
    if sys.platform=="darwin":
        from .private_directory import open_macos_private_directory as private
    elif sys.platform=="linux":
        from .linux_private_storage import open_linux_private_directory as private
    else:raise SupervisorStorageError("SUPERVISOR_NATIVE_STORE_REQUIRED")
    try:fd=private(root)
    except (OSError,ValueError):
        raise SupervisorStorageError("SUPERVISOR_STORAGE_ROOT_UNTRUSTED") from None
    try:yield fd
    finally:os.close(fd)


def _posix_file(fd,name,*,create=False):
    flags=os.O_RDWR if create else os.O_RDONLY
    flags|=os.O_NOFOLLOW|os.O_CLOEXEC
    if create:flags|=os.O_CREAT|os.O_EXCL
    descriptor=os.open(name,flags,0o600,dir_fd=fd)
    try:
        info=os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid()
                or info.st_nlink!=1 or stat.S_IMODE(info.st_mode)!=0o600):
            raise SupervisorStorageError("SUPERVISOR_STORAGE_FILE_UNTRUSTED")
        if sys.platform=="darwin":
            from .private_directory import _require_absent_acl
            _require_absent_acl(descriptor)
        else:
            from .linux_private_storage import _no_acl
            _no_acl(descriptor)
    except BaseException:
        os.close(descriptor);raise
    return descriptor


def _win_open(root,name,*,create=False,exclusive=False):
    from . import windows_private_storage as native
    native.require_native()
    context=native.directory_guard(root)
    context.__enter__()
    handle=None
    try:
        if create:
            with native.security_attributes() as sa:
                handle=native.create(str(root/name),0xc0000000,0,sa,1,0x200080,None)
        else:
            handle=native.create(str(root/name),0xc0000000 if exclusive else 0x80000000,
                                 0 if exclusive else 1,None,3,0x200080,None)
        if handle in (None,native.INVALID):
            raise SupervisorStorageError("SUPERVISOR_STORAGE_FILE_BUSY_OR_DENIED")
        native._metadata(handle)
        native.verify_security(handle)
        return native,handle,context
    except BaseException:
        if handle not in (None,native.INVALID):native.close(handle)
        context.__exit__(None,None,None)
        raise


def _win_read(native,handle,limit):
    import ctypes
    before=native._metadata(handle)
    if not 1<=before[3]<=limit:
        raise SupervisorStorageError("SUPERVISOR_STORAGE_SIZE_DENIED")
    chunks=[];left=before[3]
    while left:
        size=min(65536,left)
        buf=ctypes.create_string_buffer(size);got=native.w.DWORD()
        if not native.readfile(handle,buf,size,ctypes.byref(got),None) or not got.value:
            raise SupervisorStorageError("SUPERVISOR_STORAGE_READ_DENIED")
        chunks.append(buf.raw[:got.value]);left-=got.value
    if native._metadata(handle)!=before:
        raise SupervisorStorageError("SUPERVISOR_STORAGE_CHANGED")
    native.verify_security(handle)
    return b"".join(chunks)


def create_once(root,name,data):
    root=_root(root);_name(name)
    if name=="supervisor.lock" or type(data) is not bytes or not 1<=len(data)<=MAX_CONTROL_FILE:
        raise SupervisorStorageError("SUPERVISOR_STORAGE_CREATE_DENIED")
    try:
        if sys.platform=="win32":
            native,handle,guard=_win_open(root,name,create=True)
            try:
                import ctypes
                offset=0
                while offset<len(data):
                    segment=data[offset:offset+65536]
                    buf=ctypes.create_string_buffer(segment);n=native.w.DWORD()
                    if not native.write(handle,buf,len(segment),ctypes.byref(n),None) or n.value!=len(segment):
                        raise SupervisorStorageError("SUPERVISOR_STORAGE_WRITE_DENIED")
                    offset+=n.value
                if not native.flush(handle):
                    raise SupervisorStorageError("SUPERVISOR_STORAGE_FSYNC_DENIED")
            finally:native.close(handle);guard.__exit__(None,None,None)
        else:
            with _posix_dir(root) as directory:
                handle=_posix_file(directory,name,create=True)
                try:
                    offset=0
                    while offset<len(data):
                        n=os.write(handle,data[offset:])
                        if n<=0:raise SupervisorStorageError("SUPERVISOR_STORAGE_WRITE_DENIED")
                        offset+=n
                    os.fsync(handle)
                finally:os.close(handle)
                os.fsync(directory)
    except SupervisorStorageError:raise
    except (OSError,ValueError):
        raise SupervisorStorageError("SUPERVISOR_STORAGE_CREATE_UNVERIFIED") from None


def read_exact(root,name,*,length=None):
    root=_root(root);_name(name)
    if name=="supervisor.lock":raise SupervisorStorageError("SUPERVISOR_STORAGE_READ_DENIED")
    try:
        if sys.platform=="win32":
            native,handle,guard=_win_open(root,name)
            try:raw=_win_read(native,handle,MAX_CONTROL_FILE)
            finally:native.close(handle);guard.__exit__(None,None,None)
        else:
            with _posix_dir(root) as directory:
                handle=_posix_file(directory,name)
                try:
                    before=os.fstat(handle)
                    if not 1<=before.st_size<=MAX_CONTROL_FILE:
                        raise SupervisorStorageError("SUPERVISOR_STORAGE_SIZE_DENIED")
                    raw=os.read(handle,MAX_CONTROL_FILE+1);after=os.fstat(handle)
                    fields=("st_dev","st_ino","st_mode","st_uid","st_nlink","st_size","st_mtime_ns","st_ctime_ns")
                    if len(raw)!=before.st_size or any(getattr(before,k)!=getattr(after,k) for k in fields):
                        raise SupervisorStorageError("SUPERVISOR_STORAGE_CHANGED")
                finally:os.close(handle)
        if length is not None and (type(length) is not int or len(raw)!=length):
            raise SupervisorStorageError("SUPERVISOR_STORAGE_LENGTH_DENIED")
        return raw
    except SupervisorStorageError:raise
    except (OSError,ValueError):
        raise SupervisorStorageError("SUPERVISOR_STORAGE_READ_UNVERIFIED") from None


@contextmanager
def exclusive_lease(root):
    """One native descriptor-held lock; never remove or steal stale lock paths."""
    root=_root(root)
    if sys.platform=="win32":
        from . import windows_private_storage as native
        with native.directory_guard(root):
            # OPEN_ALWAYS, no sharing: crash closes kernel handle.
            with native.security_attributes() as sa:
                handle=native.create(str(root/"supervisor.lock"),0xc0000000,0,sa,4,0x200080,None)
            if handle in (None,native.INVALID):
                raise SupervisorStorageError("SUPERVISOR_STORAGE_LEASE_BUSY")
            try:
                info=native._metadata(handle);native.verify_security(handle)
                if info[3]!=0:raise SupervisorStorageError("SUPERVISOR_STORAGE_LEASE_INVALID")
                yield
            finally:native.close(handle)
    else:
        import fcntl
        with _posix_dir(root) as directory:
            try:handle=_posix_file(directory,"supervisor.lock",create=True)
            except FileExistsError:handle=_posix_file(directory,"supervisor.lock")
            try:
                info=os.fstat(handle)
                if info.st_size!=0:raise SupervisorStorageError("SUPERVISOR_STORAGE_LEASE_INVALID")
                try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:
                    raise SupervisorStorageError("SUPERVISOR_STORAGE_LEASE_BUSY") from None
                after=os.stat("supervisor.lock",dir_fd=directory,follow_symlinks=False)
                if after.st_ino!=info.st_ino or after.st_dev!=info.st_dev:
                    raise SupervisorStorageError("SUPERVISOR_STORAGE_LEASE_CHANGED")
                try:yield
                finally:
                    after=os.stat("supervisor.lock",dir_fd=directory,follow_symlinks=False)
                    try:
                        if after.st_ino!=info.st_ino or after.st_dev!=info.st_dev:
                            raise SupervisorStorageError("SUPERVISOR_STORAGE_LEASE_CHANGED")
                    finally:fcntl.flock(handle,fcntl.LOCK_UN)
            finally:os.close(handle)
