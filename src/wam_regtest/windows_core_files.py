"""Owner-correct creation and bounded reads of public managed-Core block data.

No existing owner/ACL repair. Private vault/config APIs stay protected-DACL only.
Default owner is scoped to the Popen creation interval and restored afterward;
no privilege is enabled and the only permitted new owner is TokenUser itself.
"""
from contextlib import contextmanager
import sys
import threading
from . import windows_private_storage as store

_spawn_guard = threading.RLock()


def _token_buffer(token, kind):
    c,w=store.c,store.w
    needed=w.DWORD()
    store.token_info(token,kind,None,0,c.byref(needed))
    if not 1<=needed.value<=65536:
        raise ValueError('WIN_CORE_OWNER_TOKEN_QUERY_DENIED')
    buffer=c.create_string_buffer(needed.value)
    if not store.token_info(token,kind,buffer,needed.value,c.byref(needed)):
        raise ValueError('WIN_CORE_OWNER_TOKEN_QUERY_DENIED')
    return buffer


@contextmanager
def child_user_owner():
    """Keep the actual subprocess.Popen and original process identity intact."""
    store.require_native()
    c,w=store.c,store.w
    set_token=store.api(store.A,'SetTokenInformation',
        [w.HANDLE,c.c_int,c.c_void_p,w.DWORD],w.BOOL)
    with _spawn_guard:
        token=w.HANDLE()
        if not store.token_open(store.current(),0x0088,c.byref(token)):
            raise ValueError('WIN_CORE_OWNER_TOKEN_OPEN_DENIED')
        changed=False
        try:
            user=_token_buffer(token,1)
            original=_token_buffer(token,4)
            user_sid=c.cast(user,c.POINTER(c.c_void_p))[0]
            owner_sid=c.cast(original,c.POINTER(c.c_void_p))[0]
            original_text=store._sid_text(owner_sid)
            if store._sid_text(user_sid)!=original_text:
                selected=c.c_void_p(user_sid)
                if not set_token(token,4,c.byref(selected),c.sizeof(selected)):
                    raise ValueError('WIN_CORE_USER_DEFAULT_OWNER_DENIED')
                changed=True
            current=_token_buffer(token,4)
            if store._sid_text(c.cast(current,c.POINTER(c.c_void_p))[0])!=store.owner_sid():
                raise ValueError('WIN_CORE_USER_DEFAULT_OWNER_UNVERIFIED')
            yield
        finally:
            try:
                if changed:
                    if not set_token(token,4,original,c.sizeof(c.c_void_p)):
                        raise ValueError('WIN_CORE_DEFAULT_OWNER_RESTORE_DENIED')
                    restored=_token_buffer(token,4)
                    if store._sid_text(c.cast(restored,c.POINTER(c.c_void_p))[0])!=original_text:
                        raise ValueError('WIN_CORE_DEFAULT_OWNER_RESTORE_UNVERIFIED')
            finally:store.close(token)


def public_block_prefix(directory, name, count):
    """Read ONLY public block framing under an original owned Core scope.

    Core-created files may inherit the single user ACE from the protected
    blocks directory. Verify that exact DACL and user owner; never accept an
    Administrators/foreign owner or weaken private encrypted-file readers.
    """
    store.require_native()
    if (name,count) not in (('xor.dat',8),('blk00000.dat',4)):
        raise ValueError('WIN_CORE_PUBLIC_PREFIX_SCOPE_DENIED')
    from .rpc_scope import identity
    scope=identity(directory)
    if scope is None or scope.faulted or scope.binding.directory!=directory:
        raise ValueError('WIN_CORE_PUBLIC_PREFIX_OWNER_REQUIRED')
    scope.binding._assert_image()
    c,w=store.c,store.w
    blocks=directory/'regtest'/'blocks'
    with store.directory_guard(blocks):
        # Read+write sharing permits the owned daemon to append block data;
        # delete sharing stays denied so the held file cannot be replaced.
        handle=store.create(str(blocks/name),0x80020000,3,None,3,0x00200080,None)
        if handle in (None,store.INVALID):
            raise ValueError('WIN_CORE_PUBLIC_PREFIX_OPEN_DENIED')
        try:
            before=store._metadata(handle)
            store.verify_security(handle,protected=False)
            if before[3]<count or name=='xor.dat' and before[3]!=8:
                raise ValueError('WIN_CORE_PUBLIC_PREFIX_SIZE_DENIED')
            buffer=c.create_string_buffer(count);read=w.DWORD()
            if not store.readfile(handle,buffer,count,c.byref(read),None) or read.value!=count:
                raise ValueError('WIN_CORE_PUBLIC_PREFIX_READ_DENIED')
            after=store._metadata(handle)
            store.verify_security(handle,protected=False)
            if before[:3]!=after[:3] or before[6]!=after[6]:
                raise ValueError('WIN_CORE_PUBLIC_PREFIX_CHANGED')
            scope.binding._assert_image()
            return buffer.raw
        finally:store.close(handle)
