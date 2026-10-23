"""Explicit, exact-checkpoint recovery of a leased managed REGTEST runtime.

Never open residue using WSP Store.__init__: that constructor can migrate it.
Only a native-custodied byte image is inspected, in RAM, with SQLite read-only
queries and the pinned WSP validator. Any sidecar or logical divergence blocks
recovery. Retain the entire original image encrypted before removing plaintext.
"""
import base64
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import sys

from . import custody

MARKER = 'managed-runtime-owner.enc'
LIMIT = 32 * 1024 * 1024


class RuntimeRecoveryError(ValueError):
    pass


def _lease_root():
    # Stable per-user native namespace; TEMP/TMPDIR differences must not split
    # wallet ownership across launches/sessions. No environment-selected root.
    if sys.platform=='win32':
        import ctypes as c
        from ctypes import wintypes as w
        from uuid import UUID
        shell=c.WinDLL('shell32'); ole=c.WinDLL('ole32')
        get=shell.SHGetKnownFolderPath
        get.argtypes=(c.c_void_p,w.DWORD,w.HANDLE,c.POINTER(w.LPWSTR)); get.restype=c.c_long
        free=ole.CoTaskMemFree; free.argtypes=(c.c_void_p,); free.restype=None
        folder=(c.c_ubyte*16).from_buffer_copy(UUID('F1B32785-6FBA-4FCF-9D55-7B8E7F157091').bytes_le)
        value=w.LPWSTR()
        try:
            if get(c.byref(folder),0,None,c.byref(value))!=0 or not value:
                raise RuntimeRecoveryError('RUNTIME_NATIVE_USER_PATH_DENIED')
            return Path(value.value)/'wam-regtest-runtime-leases'
        finally:
            if value: free(c.cast(value,c.c_void_p))
    if sys.platform not in ('darwin','linux'):
        raise RuntimeRecoveryError('RUNTIME_NATIVE_PLATFORM_REQUIRED')
    return Path('/tmp').resolve(strict=True)/('wam-regtest-runtime-leases-'+str(os.geteuid()))


class RuntimeLease:
    """Descriptor ownership is process-wide, transferable across Qt threads.

    A distinct per-wallet namespace excludes copies in separate directories.
    Unlike a named Windows mutex, this handle has no thread-affinity/recursion.
    Existing native anchor CAS leases remain independent and unchanged.
    """
    def __init__(self, wallet_id):
        import re
        if type(wallet_id) is not str or not re.fullmatch('[0-9a-f]{32}', wallet_id):
            raise RuntimeRecoveryError('RUNTIME_WALLET_ID_DENIED')
        root = _lease_root()
        if not root.exists():
            try: custody.create_directory(root)
            except FileExistsError: pass
        custody.storage().validate_directory(root)
        self._handle = None
        self._windows = sys.platform == 'win32'
        name = wallet_id+'.lock'
        if self._windows:
            from . import windows_private_storage as n
            with n.directory_guard(root), n.security_attributes() as attributes:
                handle = n.create(str(root/name), 0xc0000000, 0, attributes, 4, 0x200080, None)
                if handle in (None, n.INVALID):
                    raise RuntimeRecoveryError('RUNTIME_SESSION_BUSY')
                try:
                    if n._metadata(handle)[3] != 0: raise ValueError
                    n.verify_security(handle)
                except BaseException:
                    n.close(handle); raise
                self._handle = handle
        else:
            import fcntl
            from .supervisor_store import _posix_dir, _posix_file
            with _posix_dir(root) as dfd:
                try: fd = _posix_file(dfd, name, create=True)
                except FileExistsError: fd = _posix_file(dfd, name)
                try:
                    if os.fstat(fd).st_size != 0: raise ValueError
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    named = os.stat(name, dir_fd=dfd, follow_symlinks=False)
                    if (named.st_dev, named.st_ino) != (os.fstat(fd).st_dev, os.fstat(fd).st_ino):
                        raise ValueError
                    self._handle = fd
                except BaseException:
                    os.close(fd)
                    raise RuntimeRecoveryError('RUNTIME_SESSION_BUSY') from None

    def close(self):
        handle, self._handle = self._handle, None
        if handle is not None:
            if self._windows:
                from .windows_private_storage import close
                close(handle)
            else: os.close(handle)


def enroll(directory, wallet_id, password):
    """Create-only protocol record while caller owns the wallet lifetime lease.

    Never enroll an unknown existing runtime. The marker is retained across
    normal close, crash and recovery; it grants no anchor/signing authority.
    """
    from wam_sp.keystore import seal, unseal
    from .wsp_live import REGTEST_GENESIS
    expected = {'schema':'wam-managed-runtime-lease/v1', 'wallet_id':wallet_id,
                'genesis':REGTEST_GENESIS}
    store = custody.storage()
    if not (directory/MARKER).exists() and not (directory/MARKER).is_symlink():
        if any((directory/('wallet-runtime.sqlite'+suffix)).exists()
               or (directory/('wallet-runtime.sqlite'+suffix)).is_symlink()
               for suffix in ('', '-journal', '-wal', '-shm')):
            raise RuntimeRecoveryError('RUNTIME_UNKNOWN_OWNER_REVIEW_REQUIRED')
        store.publish(directory, MARKER, seal(json.dumps(expected,sort_keys=True).encode(), password, b'recovery'))
    if json.loads(unseal(store.read(directory, MARKER), password, b'recovery')) != expected:
        raise RuntimeRecoveryError('RUNTIME_OWNER_PROTOCOL_DENIED')


def _no_sidecars(path):
    if any(path.with_name(path.name+s).exists() or path.with_name(path.name+s).is_symlink()
           for s in ('-journal','-wal','-shm')):
        raise RuntimeRecoveryError('RUNTIME_SIDECAR_REVIEW_REQUIRED')


@contextmanager
def _image(directory):
    """Held no-follow, owner-only, single-link image; no disk SQLite connection."""
    path = directory/'wallet-runtime.sqlite'
    _no_sidecars(path)
    if sys.platform == 'win32':
        import ctypes
        from . import windows_private_storage as n
        with n.directory_guard(directory):
            h = n.create(str(path), 0x80000000|0x20000|0x10000, 0, None, 3, 0x200080, None)
            if h in (None,n.INVALID): raise RuntimeRecoveryError('RUNTIME_IMAGE_BUSY_OR_DENIED')
            try:
                before=n._metadata(h); n.verify_security(h)
                if not 512<=before[3]<=LIMIT: raise ValueError
                parts=[]; left=before[3]
                while left:
                    size=min(65536,left); buf=ctypes.create_string_buffer(size); got=n.w.DWORD()
                    if not n.readfile(h,buf,size,ctypes.byref(got),None) or not got.value: raise ValueError
                    parts.append(buf.raw[:got.value]); left-=got.value
                def remove_verified():
                    _no_sidecars(path)
                    if n._metadata(h)!=before: raise ValueError
                    n.verify_security(h)
                    disposition=n.DISPOSITION(True)
                    if not n.setinfo(h,4,ctypes.byref(disposition),ctypes.sizeof(disposition)): raise ValueError
                if n._metadata(h)!=before: raise ValueError
                yield b''.join(parts), remove_verified
            finally: n.close(h)
    else:
        from .supervisor_store import _posix_dir, _posix_file
        with _posix_dir(directory) as dfd:
            fd=_posix_file(dfd,path.name)
            try:
                before=os.fstat(fd)
                if not 512<=before.st_size<=LIMIT: raise ValueError
                fields=('st_dev','st_ino','st_mode','st_uid','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
                identity=lambda value: tuple(getattr(value,k) for k in fields)
                parts=[]; left=before.st_size
                while left:
                    part=os.read(fd,min(left,65536))
                    if not part: raise ValueError
                    parts.append(part); left-=len(part)
                def remove_verified():
                    _no_sidecars(path)
                    if (identity(os.fstat(fd))!=identity(before)
                            or identity(os.stat(path.name,dir_fd=dfd,follow_symlinks=False))!=identity(before)):
                        raise ValueError
                    os.unlink(path.name,dir_fd=dfd); os.fsync(dfd)
                if identity(os.fstat(fd))!=identity(before): raise ValueError
                yield b''.join(parts), remove_verified
            finally: os.close(fd)


def verify_image(raw, payload, password):
    """Compare every typed WSP row, schema and original key-derived identity."""
    from wam_sp.keystore import unseal
    from wam_sp.state import decode_checkpoint
    from wam_sp.store import Store, SCHEMA, TABLES
    from wam_sp.watcher import GENESIS
    from .bip39_durable import restore_keyring
    ring=None; db=expected=None
    try:
        ring=restore_keyring(base64.b64decode(payload['keys'],validate=True), password)
        identity=json.dumps({'version':2,'network':GENESIS,'accounts':[a.identity() for a in ring.accounts()]},
                            sort_keys=True,separators=(',',':'))
        checkpoint=decode_checkpoint(unseal(base64.b64decode(payload['checkpoint'],validate=True),password,b'checkpoint'),identity)
        if checkpoint.get('schema')!=3: raise ValueError
        db=sqlite3.connect(':memory:'); db.deserialize(raw)
        db.execute('PRAGMA trusted_schema=OFF'); db.execute('PRAGMA query_only=ON')
        db.row_factory=sqlite3.Row
        if [tuple(r) for r in db.execute('PRAGMA integrity_check')]!=[('ok',)]: raise ValueError
        if db.execute('PRAGMA user_version').fetchone()[0]!=3: raise ValueError
        expected=sqlite3.connect(':memory:'); expected.executescript(SCHEMA)
        schema=lambda c: sorted(tuple(r) for r in c.execute('SELECT type,name,tbl_name,sql FROM sqlite_master'))
        if schema(db)!=schema(expected): raise ValueError
        if dict(db.execute('SELECT key,value FROM meta'))!={'identity':identity,'profile':'WSP-1'}: raise ValueError
        # Invoke the actual pinned row/curve/chain validator on the RAM image,
        # bypassing only Store's WRITE/MIGRATION constructor, never validation.
        view=Store.__new__(Store); view.db=db; view.identity=identity
        view.validate()
        canonical=lambda rows: sorted(json.dumps(list(r),separators=(',',':'),ensure_ascii=True) for r in rows)
        for table in TABLES:
            if canonical(db.execute('SELECT * FROM '+table))!=canonical(checkpoint['tables'][table]):
                raise RuntimeRecoveryError('RUNTIME_CHECKPOINT_DIVERGED_REVIEW_REQUIRED')
        return True
    finally:
        if db is not None: db.close()
        if expected is not None: expected.close()
        if ring is not None: ring.close()


def _retain_image(directory, raw, password):
    from wam_sp.keystore import seal, unseal
    name='runtime-residue-'+sha256(raw).hexdigest()[:32]+'.enc'
    store=custody.storage()
    if not (directory/name).exists() and not (directory/name).is_symlink():
        store.publish(directory,name,seal(raw,password,b'checkpoint'))
    if unseal(store.read(directory,name),password,b'checkpoint')!=raw:
        raise RuntimeRecoveryError('RUNTIME_RETAINED_IMAGE_CHANGED')
    return name


def recover_managed_runtime(root, core, source, password, *, authorized=False):
    """Stay LOCKED after explicit archive/recovery. Unlock is a separate action."""
    if authorized is not True:
        raise RuntimeRecoveryError('RUNTIME_RECOVERY_EXPLICIT_CONSENT_REQUIRED')
    from .managed_wallet_binding import verify_locked_wallet
    from .managed_wallet_reopen import read
    from .supervisor_client import control
    from .vault import CheckpointVault
    from wam_sp.file_lock import exclusive_file_lock
    lease=None
    try:
        verify_locked_wallet(root,core,source,password,authorized=True)
        before=control(root,'status',timeout=3)
        directory=root/'chain'; folder=directory/'wallet-vault'
        identity=read(folder,password); anchor=custody.anchor(identity['wallet_id'])
        lease=RuntimeLease(identity['wallet_id'])
        # An unknown/legacy runtime cannot be retroactively declared leased.
        if not (directory/MARKER).exists():
            raise RuntimeRecoveryError('RUNTIME_UNKNOWN_OWNER_REVIEW_REQUIRED')
        enroll(directory,identity['wallet_id'],password)
        vault=CheckpointVault(folder,anchor,source)
        with anchor.lease(), exclusive_file_lock(folder/'.vault.lock'), exclusive_file_lock(directory/'wallet-runtime.sqlite.scan.lock'):
            record=anchor.read()
            if record is None or record!=vault._expected: raise ValueError
            payload=vault._load_payload(password,record)
            with _image(directory) as (raw,remove_verified):
                verify_image(raw,payload,password)
                if control(root,'status',timeout=3)!=before or anchor.read()!=record: raise ValueError
                # Create-only and retryable after interruption: the retained
                # encrypted image must decrypt to EVERY original byte.
                _retain_image(directory,raw,password)
                if anchor.read()!=record or control(root,'status',timeout=3)!=before: raise ValueError
                remove_verified()
            if anchor.read()!=record: raise ValueError
        return {'status':'MANAGED_RUNTIME_EXACT_CHECKPOINT_RECOVERED_LOCKED',
                'original_image_retained_encrypted':True,'all_wsp_rows_match_anchor':True,
                'anchor_unchanged':True,'signer_allowed':False,'broadcast_allowed':False}
    except RuntimeRecoveryError: raise
    except Exception:
        raise RuntimeRecoveryError('RUNTIME_RECOVERY_UNPROVEN_REVIEW_REQUIRED') from None
    finally:
        if lease is not None: lease.close()
