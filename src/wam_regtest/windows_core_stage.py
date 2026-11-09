"""Stage bundled, independently pinned Windows Core into a new private directory.

Shared by the qualification entry (windows_package_entry) and the production
entry (windows_production_entry). Body moved verbatim; no custody change.
"""
from hashlib import sha256


def _stage_original_core(source,destination):
    from wam_regtest import windows_private_storage as store
    from wam_regtest.windows_core_transport import write_new,verified_core_paths
    from wam_regtest.windows_release_preflight import BINARY_SHA256
    store.create_private_directory(destination)
    with store.directory_guard(source,private=False):
        if set(p.name for p in source.iterdir())!={'wamd.exe','wam-cli.exe','receipt.json'}:
            raise ValueError('WIN_BUNDLE_CORE_MEMBERS_DENIED')
        for name in ('wamd.exe','wam-cli.exe','receipt.json'):
            # Distribution ACLs are not runtime custody. Only independently
            # pinned original bytes enter the newly protected executable stage.
            handle=store.create(str(source/name),0x80000000,1,None,3,0x200080,None)
            if handle in (None,store.INVALID):raise ValueError('WIN_BUNDLE_CORE_READ_DENIED')
            try:
                before=store._metadata(handle)
                limit=4096 if name=='receipt.json' else 128*1024*1024
                if not 1<=before[3]<=limit:raise ValueError('WIN_BUNDLE_CORE_SIZE_DENIED')
                import ctypes
                remaining=before[3];parts=[]
                while remaining:
                    size=min(remaining,65536);buf=ctypes.create_string_buffer(size);count=store.w.DWORD()
                    if not store.readfile(handle,buf,size,ctypes.byref(count),None) or not count.value:
                        raise ValueError('WIN_BUNDLE_CORE_READ_DENIED')
                    parts.append(buf.raw[:count.value]);remaining-=count.value
                if before!=store._metadata(handle):raise ValueError('WIN_BUNDLE_CORE_CHANGED_DENIED')
                payload=b''.join(parts)
                if name in BINARY_SHA256 and sha256(payload).hexdigest()!=BINARY_SHA256[name]:
                    raise ValueError('WIN_BUNDLE_CORE_PIN_DENIED')
                write_new(destination,name,payload)
            finally:store.close(handle)
    verified_core_paths(destination)
