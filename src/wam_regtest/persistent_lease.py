"""T05 candidate: cooperative single-writer lease for a private REGTEST profile.

No Core execution, process attach, wallet state or signer authority is granted.
The lease detects a competing cooperating process; it is NOT a defense against
a hostile same-UID process, filesystem rollback, or Windows ACL bypass.
"""
from contextlib import contextmanager
import os
import stat

from .persistent_profile import (
    PersistentProfileError, _root, inspect_profile,
)


@contextmanager
def hold_profile(root, *, expected_genesis, expected_node_sha256,
                 expected_cli_sha256):
    """Hold a descriptor-bound OS lock over a *previously validated* profile."""
    receipt=inspect_profile(root,expected_genesis=expected_genesis,
                            expected_node_sha256=expected_node_sha256,
                            expected_cli_sha256=expected_cli_sha256)
    # Import only on POSIX after inspect_profile has denied Windows.
    import fcntl
    directory=lock=None
    try:
        directory,_=_root(root)
        lock=os.open('session.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC,
                     0o600,dir_fd=directory)
        info=os.fstat(lock)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid()
                or info.st_nlink!=1 or stat.S_IMODE(info.st_mode)!=0o600
                or info.st_size!=0):
            raise PersistentProfileError('PROFILE_LEASE_FILE_DENIED')
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise PersistentProfileError('PROFILE_SINGLE_WRITER_BUSY') from None
        os.fsync(directory)
        current=os.stat('session.lock',dir_fd=directory,follow_symlinks=False)
        if (info.st_ino,info.st_dev)!=(current.st_ino,current.st_dev):
            raise PersistentProfileError('PROFILE_LEASE_INODE_CHANGED')
        try:
            yield receipt
        finally:
            # Never accept a pathname swap while an older inode remains locked.
            # A malicious same-UID attacker still falls outside this contract.
            try:
                current=os.stat('session.lock',dir_fd=directory,follow_symlinks=False)
                if (info.st_ino,info.st_dev)!=(current.st_ino,current.st_dev):
                    raise PersistentProfileError('PROFILE_LEASE_INODE_CHANGED')
            finally:
                fcntl.flock(lock,fcntl.LOCK_UN)
    except PersistentProfileError:
        raise
    except OSError:
        raise PersistentProfileError('PROFILE_LEASE_UNVERIFIED') from None
    finally:
        if lock is not None:os.close(lock)
        if directory is not None:os.close(directory)
