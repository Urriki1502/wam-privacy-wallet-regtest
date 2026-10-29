"""Owner-local live sessions; no passwords or signing on supervisor IPC."""
import os
import stat
import threading
import sys
from contextlib import ExitStack

from . import custody
from .managed_wallet_checkpoint import (
    _inputs,_owned,_runtime,_read_reference,_publish_reference,_snapshot,
)
from .supervisor_identity import directory_identity
from .wallet_recovery import active_location,has_recovery_records,require_anchor_floor


class RuntimeGuard:
    """Pin the fresh runtime inode for this session; refuse changed paths.

    Private-directory/native custody is still required. This is not protection
    against a compromised same-user process/OS racing pathname operations.
    """
    def __init__(self,path):
        self.path=path;self.fd=None
        try:
            custody.storage().validate_directory(path.parent)
            self.parent=directory_identity(path.parent)
            self.fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_CLOEXEC',0))
            self.check()
        except Exception:
            self.close();raise

    def check(self):
        if self.fd is None:raise ValueError('WALLET_MANAGED_RUNTIME_CLOSED')
        held=os.fstat(self.fd);current=self.path.lstat()
        if (not stat.S_ISREG(held.st_mode) or not stat.S_ISREG(current.st_mode)
                or held.st_nlink!=1 or current.st_nlink!=1
                or (held.st_dev,held.st_ino)!=(current.st_dev,current.st_ino)
                or directory_identity(self.path.parent)!=self.parent):
            raise ValueError('WALLET_MANAGED_RUNTIME_CHANGED')
        if sys.platform=='win32':
            import msvcrt
            from . import windows_private_storage as native
            handle=msvcrt.get_osfhandle(self.fd)
            native._metadata(handle);native.verify_security(handle)
        elif held.st_uid!=os.geteuid() or stat.S_IMODE(held.st_mode)!=0o600:
            raise ValueError('WALLET_MANAGED_RUNTIME_CUSTODY_DENIED')

    def remove_owned(self):
        self.check()
        if any(self.path.with_name(self.path.name+s).exists()
               or self.path.with_name(self.path.name+s).is_symlink()
               for s in ('-journal','-wal','-shm')):
            raise ValueError('WALLET_MANAGED_RUNTIME_SIDECAR_UNCERTAIN')
        # Windows CRT pins can prevent unlink; close only after identity check
        # and recheck the path before removing this exact fresh session file.
        before=self.path.lstat();self.close();after=self.path.lstat()
        if (before.st_dev,before.st_ino)!=(after.st_dev,after.st_ino) or not stat.S_ISREG(after.st_mode):
            raise ValueError('WALLET_MANAGED_RUNTIME_CHANGED')
        self.path.unlink()

    def close(self):
        if self.fd is not None:os.close(self.fd);self.fd=None


def check_session(session):
    from .wallet_session import WalletSessionError
    try:
        if threading.get_ident()!=session._managed_thread or session._managed_lease is None:
            raise ValueError('WALLET_MANAGED_OWNER_THREAD_REQUIRED')
        _owned(session._managed_owner)
        if session._managed_owner.process is not session._managed_process:
            raise ValueError('WALLET_MANAGED_CORE_INSTANCE_CHANGED')
        session._managed_runtime_guard.check()
        if directory_identity(session.vault.directory)!=session._managed_target_identity:
            raise ValueError('WALLET_MANAGED_CONTAINER_CHANGED')
        if not session._managed_opening:
            wallet_id=_read_reference(session._managed_owner)
            folder,name,floor=active_location(session._managed_owner,wallet_id)
            if (wallet_id!=session.vault.anchor.wallet_id or folder!=session.vault.directory
                    or session.runtime!=session.datadir/name):
                raise ValueError('WALLET_MANAGED_REFERENCE_CHANGED')
            require_anchor_floor(session.vault.anchor.read(),floor)
    except (OSError,ValueError,RuntimeError):
        session.faulted=True
        raise WalletSessionError('WALLET_MANAGED_OWNER_UNVERIFIED') from None


def open_owned(cls,owner,source,password,*,authorized=False,keychain=None,create=False,mining_address=None):
    from .vault import CheckpointVault
    from .wallet_session import WalletCoreCli,WalletSessionError
    import secrets
    ring=scanner=rpc=lease=guard=None
    try:
        _inputs(owner,source,password,authorized)
        if type(create) is not bool:raise ValueError('WALLET_MANAGED_MODE_DENIED')
        floor=None
        if create:
            folder=owner.directory/'wallet-vault';runtime=_runtime(owner)
            if (folder.exists() or folder.is_symlink() or has_recovery_records(owner)
                    or (owner.root/'supervisor.wallet').exists() or (owner.root/'supervisor.wallet').is_symlink()):
                raise ValueError('WALLET_MANAGED_EXISTS_OR_UNCERTAIN')
            wallet_id=secrets.token_hex(16)
        else:
            wallet_id=_read_reference(owner)
            folder,name,floor=active_location(owner,wallet_id);runtime=_runtime(owner,name)
        anchor=custody.anchor(wallet_id,keychain)
        context=anchor.lease();context.__enter__();lease=context
        require_anchor_floor(anchor.read(),floor);_owned(owner)
        if create:
            if anchor.read() is not None:raise ValueError('WALLET_MANAGED_ANCHOR_EXISTS')
            custody.create_directory(folder)
        vault=CheckpointVault(folder,anchor,source)
        rpc=WalletCoreCli(owner.cli,owner.directory);rpc.attest()
        from wam_sp.keystore import Keyring
        from wam_sp.scanner import Scanner
        if create:
            ring=Keyring();ring.backup(password)
            if sys.platform=='win32':
                from .windows_private_storage import create_managed_runtime
                create_managed_runtime(runtime)
            scanner=Scanner(runtime,ring.accounts())
        else:
            ring,scanner=vault.restore(runtime,password,private_windows_runtime=sys.platform=='win32')
        _snapshot(ring,scanner,rpc,vault)
        guard=RuntimeGuard(runtime)
        session=cls(owner.core,owner.directory,source,ring,scanner,vault,password,mining_address,
                    core_cli=owner.cli,core_receipt=owner.receipt)
        session._managed_owner=owner;session._managed_process=owner.process
        session._managed_thread=threading.get_ident()
        session._managed_lease=lease;session._managed_runtime_guard=guard
        session._managed_target_identity=directory_identity(folder);session._managed_opening=True
        session._save()
        if create:_publish_reference(owner,wallet_id)
        session._managed_opening=False;check_session(session)
        # Transfer custody only after every check succeeds. Failure preserves
        # runtime evidence and closes keys/lease; never repairs or sweeps files.
        ring=scanner=lease=guard=None
        return session
    except (OSError,ValueError,RuntimeError):
        raise WalletSessionError('WALLET_MANAGED_OPEN_DENIED') from None
    finally:
        with ExitStack() as closing:
            if rpc is not None and getattr(rpc,'_transport',None) is not None:closing.callback(rpc._transport.close)
            if lease is not None:closing.callback(lease.__exit__,None,None,None)
            if guard is not None:closing.callback(guard.close)
            if ring is not None:closing.callback(ring.close)
            if scanner is not None:closing.callback(scanner.close)


def close_session(session):
    from .wallet_session import WalletSessionError
    if threading.get_ident()!=session._managed_thread:
        raise WalletSessionError('WALLET_MANAGED_OWNER_THREAD_REQUIRED')
    if session.locked:return
    try:
        with ExitStack() as keys:
            keys.callback(session.ring.close)
            keys.callback(session.scanner.close)
            keys.callback(session._close_rpc)
            if session._disclosure_gate is not None:keys.callback(session._disclosure_gate.close)
        session._managed_runtime_guard.remove_owned()
    except (OSError,ValueError,RuntimeError):
        raise WalletSessionError('WALLET_MANAGED_RUNTIME_PRESERVED') from None
    finally:
        session.scanner=session.ring=None;session._password=None
        session._prepared=session._signed=session._review=session._tip=None
        session._disclosure_gate=None
        try:session._managed_runtime_guard.close()
        finally:
            if session._managed_lease is not None:
                session._managed_lease.__exit__(None,None,None);session._managed_lease=None
