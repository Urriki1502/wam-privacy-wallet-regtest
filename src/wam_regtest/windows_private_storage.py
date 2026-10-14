"""Native Win64 owner-only NTFS custody and create-only ciphertext publication.

No chmod/UID emulation, no junction traversal, no overwrite or ACL repair.
Flush data before an atomic same-directory handle rename. Power-loss durability
and protection against an elevated/compromised OS are separate qualifications.
"""
from contextlib import contextmanager
from pathlib import Path
import platform
import re
import secrets
import sys

MAX_ENVELOPE=32*1024*1024+52

class WindowsCustodyError(ValueError): pass

if sys.platform=='win32':
    import ctypes as c
    from ctypes import wintypes as w
    K=c.WinDLL('kernel32',use_last_error=True)
    A=c.WinDLL('advapi32',use_last_error=True)
    def api(lib,name,args,result):
        f=getattr(lib,name);f.argtypes=args;f.restype=result;return f
    close=api(K,'CloseHandle',[w.HANDLE],w.BOOL)
    free=api(K,'LocalFree',[c.c_void_p],c.c_void_p)
    current=api(K,'GetCurrentProcess',[],w.HANDLE)
    token_open=api(A,'OpenProcessToken',[w.HANDLE,w.DWORD,c.POINTER(w.HANDLE)],w.BOOL)
    token_info=api(A,'GetTokenInformation',[w.HANDLE,c.c_int,c.c_void_p,w.DWORD,c.POINTER(w.DWORD)],w.BOOL)
    sid_string=api(A,'ConvertSidToStringSidW',[c.c_void_p,c.POINTER(w.LPWSTR)],w.BOOL)
    sddl=api(A,'ConvertStringSecurityDescriptorToSecurityDescriptorW',[w.LPCWSTR,w.DWORD,c.POINTER(c.c_void_p),c.POINTER(w.DWORD)],w.BOOL)
    security=api(A,'GetSecurityInfo',[w.HANDLE,c.c_int,w.DWORD,c.POINTER(c.c_void_p),c.POINTER(c.c_void_p),c.POINTER(c.c_void_p),c.POINTER(c.c_void_p),c.POINTER(c.c_void_p)],w.DWORD)
    control=api(A,'GetSecurityDescriptorControl',[c.c_void_p,c.POINTER(w.WORD),c.POINTER(w.DWORD)],w.BOOL)
    acl_info=api(A,'GetAclInformation',[c.c_void_p,c.c_void_p,w.DWORD,c.c_int],w.BOOL)
    get_ace=api(A,'GetAce',[c.c_void_p,w.DWORD,c.POINTER(c.c_void_p)],w.BOOL)
    mkdir=api(K,'CreateDirectoryW',[w.LPCWSTR,c.c_void_p],w.BOOL)
    create=api(K,'CreateFileW',[w.LPCWSTR,w.DWORD,w.DWORD,c.c_void_p,w.DWORD,w.DWORD,w.HANDLE],w.HANDLE)
    ftype=api(K,'GetFileType',[w.HANDLE],w.DWORD)
    fex=api(K,'GetFileInformationByHandleEx',[w.HANDLE,c.c_int,c.c_void_p,w.DWORD],w.BOOL)
    finfo=api(K,'GetFileInformationByHandle',[w.HANDLE,c.c_void_p],w.BOOL)
    write=api(K,'WriteFile',[w.HANDLE,c.c_void_p,w.DWORD,c.POINTER(w.DWORD),c.c_void_p],w.BOOL)
    readfile=api(K,'ReadFile',[w.HANDLE,c.c_void_p,w.DWORD,c.POINTER(w.DWORD),c.c_void_p],w.BOOL)
    flush=api(K,'FlushFileBuffers',[w.HANDLE],w.BOOL)
    setinfo=api(K,'SetFileInformationByHandle',[w.HANDLE,c.c_int,c.c_void_p,w.DWORD],w.BOOL)
    delete=api(K,'DeleteFileW',[w.LPCWSTR],w.BOOL)
    volume=api(K,'GetVolumeInformationByHandleW',[w.HANDLE,w.LPWSTR,w.DWORD,c.POINTER(w.DWORD),c.POINTER(w.DWORD),c.POINTER(w.DWORD),w.LPWSTR,w.DWORD],w.BOOL)
    class SA(c.Structure):
        _fields_=[('length',w.DWORD),('descriptor',c.c_void_p),('inherit',w.BOOL)]
    class TAG(c.Structure):
        _fields_=[('attributes',w.DWORD),('tag',w.DWORD)]
    class INFO(c.Structure):
        _fields_=[('attributes',w.DWORD),('created',w.FILETIME),('accessed',w.FILETIME),
          ('written',w.FILETIME),('volume',w.DWORD),('size_hi',w.DWORD),('size_lo',w.DWORD),
          ('links',w.DWORD),('index_hi',w.DWORD),('index_lo',w.DWORD)]
    class ACLINFO(c.Structure):
        _fields_=[('count',w.DWORD),('used',w.DWORD),('free',w.DWORD)]
    class ACE(c.Structure):
        _fields_=[('kind',c.c_ubyte),('flags',c.c_ubyte),('size',w.WORD),('mask',w.DWORD)]
    class RENAME(c.Structure):
        _fields_=[('flags',w.DWORD),('root',w.HANDLE),('length',w.DWORD),('name',w.WCHAR*1)]
    INVALID=c.c_void_p(-1).value


def require_native():
    if sys.platform!='win32' or platform.machine().lower() not in ('amd64','x86_64'):
        raise WindowsCustodyError('WIN_CUSTODY_NATIVE_X64_REQUIRED')


def _deny(code): raise WindowsCustodyError(code)

def _sid_text(pointer):
    result=w.LPWSTR()
    if not sid_string(pointer,c.byref(result)): _deny('WIN_CUSTODY_SID_DENIED')
    try: return result.value
    finally: free(c.cast(result,c.c_void_p))


def owner_sid():
    require_native();token=w.HANDLE();needed=w.DWORD()
    if not token_open(current(),8,c.byref(token)): _deny('WIN_CUSTODY_TOKEN_DENIED')
    try:
        token_info(token,1,None,0,c.byref(needed))
        if not 1<=needed.value<=65536: _deny('WIN_CUSTODY_TOKEN_DENIED')
        buffer=c.create_string_buffer(needed.value)
        if not token_info(token,1,buffer,needed.value,c.byref(needed)): _deny('WIN_CUSTODY_TOKEN_DENIED')
        return _sid_text(c.cast(buffer,c.POINTER(c.c_void_p))[0])
    finally: close(token)


@contextmanager
def security_attributes(*,directory=False,kernel=False,descriptor=None):
    require_native();sd=c.c_void_p()
    sid=owner_sid()
    text=descriptor or ('O:'+sid+'D:P(A;'+('OICI' if directory else '')+';'+('GA' if kernel else 'FA')+';;;'+sid+')')
    if not sddl(text,1,c.byref(sd),None): _deny('WIN_CUSTODY_DESCRIPTOR_DENIED')
    try:
        attributes=SA(c.sizeof(SA),sd,False)
        yield c.byref(attributes)
    finally: free(sd)


def verify_security(handle,*,kernel=False,protected=True):
    require_native();owner=c.c_void_p();dacl=c.c_void_p();sd=c.c_void_p()
    if security(handle,6 if kernel else 1,5,c.byref(owner),None,c.byref(dacl),None,c.byref(sd)):
        _deny('WIN_CUSTODY_SECURITY_QUERY_DENIED')
    try:
        sid=owner_sid()
        if not owner.value or _sid_text(owner)!=sid: _deny('WIN_CUSTODY_OWNER_DENIED')
        flags=w.WORD();revision=w.DWORD()
        if not control(sd,c.byref(flags),c.byref(revision)) or not dacl.value or protected and not flags.value&0x1000:
            _deny('WIN_CUSTODY_DACL_DENIED')
        info=ACLINFO()
        if not acl_info(dacl,c.byref(info),c.sizeof(info),2) or info.count!=1:
            _deny('WIN_CUSTODY_DACL_DENIED')
        ace=c.c_void_p()
        if not get_ace(dacl,0,c.byref(ace)) or not ace.value: _deny('WIN_CUSTODY_DACL_DENIED')
        header=c.cast(ace,c.POINTER(ACE)).contents
        allowed=(0x1f0001,0x10000000) if kernel else (0x1f01ff,)
        if (header.kind!=0 or header.flags&8 or header.mask not in allowed
                or header.size<12 or _sid_text(c.c_void_p(ace.value+8))!=sid):
            _deny('WIN_CUSTODY_DACL_DENIED')
    finally: free(sd)


def _path(path):
    require_native()
    if (type(path) is not type(Path()) or not path.is_absolute() or not re.fullmatch(r'[A-Za-z]:',path.drive)
            or len(str(path))>240 or any(p in ('.','..') or p.endswith((' ','.')) or ':' in p
              or re.fullmatch(r'(?i)(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\..*)?',p)
              for p in path.parts[1:])):
        _deny('WIN_CUSTODY_PATH_DENIED')
    return path


def _metadata(handle,*,directory=False):
    tag=TAG();info=INFO()
    if (ftype(handle)!=1 or not fex(handle,9,c.byref(tag),c.sizeof(tag))
            or tag.attributes&0x400 or bool(tag.attributes&0x10)!=directory
            or not finfo(handle,c.byref(info)) or not directory and info.links!=1):
        _deny('WIN_CUSTODY_REPARSE_OR_LINK_DENIED')
    return (info.volume,info.index_hi,info.index_lo,info.size_hi<<32|info.size_lo,
            info.written.dwHighDateTime,info.written.dwLowDateTime,info.links)


@contextmanager
def directory_guard(path,*,private=True):
    path=_path(path);handles=[]
    try:
        cursor=Path(path.anchor)
        for part in (None,*path.parts[1:]):
            if part is not None: cursor=cursor/part
            handle=create(str(cursor),0x20000|0x80|1,1,None,3,0x2200000,None)
            if handle in (None,INVALID): _deny('WIN_CUSTODY_DIRECTORY_OPEN_DENIED')
            handles.append(handle);_metadata(handle,directory=True)
        if private:
            verify_security(handles[-1])
            filesystem=c.create_unicode_buffer(32)
            if not volume(handles[-1],None,0,None,None,None,filesystem,len(filesystem)) or filesystem.value!="NTFS":
                _deny("WIN_CUSTODY_NTFS_REQUIRED")
        yield handles[-1]
    finally:
        for handle in reversed(handles): close(handle)


def validate_directory(path):
    with directory_guard(path): pass


def create_private_directory(path):
    path=_path(path)
    with directory_guard(path.parent,private=False),security_attributes(directory=True) as attributes:
        if not mkdir(str(path),attributes): _deny('WIN_CUSTODY_CREATE_DIRECTORY_DENIED')
        validate_directory(path)


def _name(name):
    if (type(name) is not str or not re.fullmatch(r'[a-z0-9-]{1,80}\.enc',name)
            or re.fullmatch(r'(con|prn|aux|nul|com[0-9]|lpt[0-9])\.enc',name)):
        _deny('WIN_CUSTODY_NAME_DENIED')


def publish(directory,name,ciphertext):
    _name(name);require_native()
    if type(ciphertext) is not bytes or not 52<=len(ciphertext)<=MAX_ENVELOPE or not ciphertext.startswith(b'WAMSP02\x00'):
        _deny('WIN_CUSTODY_ENVELOPE_DENIED')
    temporary='.stage-'+secrets.token_hex(16);handle=None;renamed=False
    with directory_guard(directory) as root:
        try:
            with security_attributes() as attributes:
                handle=create(str(directory/temporary),0x80000000|0x40000000|0x10000|0x20000,1,attributes,1,0x80200080,None)
            if handle in (None,INVALID): handle=None;_deny('WIN_CUSTODY_STAGE_DENIED')
            _metadata(handle);verify_security(handle)
            offset=0
            while offset<len(ciphertext):
                chunk=ciphertext[offset:offset+65536];count=w.DWORD();buffer=c.create_string_buffer(chunk)
                if not write(handle,buffer,len(chunk),c.byref(count),None) or not count.value:
                    _deny('WIN_CUSTODY_WRITE_DENIED')
                offset+=count.value
            if not flush(handle): _deny('WIN_CUSTODY_FLUSH_DENIED')
            # Handle-based same-directory rename; flags=0 NEVER replaces.
            text=name.encode('utf-16-le');buffer=c.create_string_buffer(RENAME.name.offset+len(text)+2)
            rename=RENAME.from_buffer(buffer);rename.flags=0;rename.root=root;rename.length=len(text)
            c.memmove(c.addressof(buffer)+RENAME.name.offset,text,len(text))
            if not setinfo(handle,3,buffer,len(buffer)): _deny('WIN_CUSTODY_PUBLISH_DENIED')
            renamed=True;_metadata(handle);verify_security(handle)
        finally:
            if handle is not None: close(handle)
            if not renamed and (directory/temporary).exists():
                if not delete(str(directory/temporary)): _deny('WIN_CUSTODY_STAGE_CLEANUP_DENIED')


def read(directory,name):
    _name(name);require_native();handle=None
    with directory_guard(directory):
        try:
            handle=create(str(directory/name),0x80000000|0x20000,1,None,3,0x200080,None)
            if handle in (None,INVALID): handle=None;_deny('WIN_CUSTODY_READ_OPEN_DENIED')
            before=_metadata(handle);verify_security(handle)
            if not 52<=before[3]<=MAX_ENVELOPE: _deny('WIN_CUSTODY_SIZE_DENIED')
            parts=[];remaining=before[3]
            while remaining:
                size=min(remaining,65536);buffer=c.create_string_buffer(size);count=w.DWORD()
                if not readfile(handle,buffer,size,c.byref(count),None) or not count.value:
                    _deny('WIN_CUSTODY_READ_DENIED')
                parts.append(buffer.raw[:count.value]);remaining-=count.value
            if before!=_metadata(handle): _deny('WIN_CUSTODY_CHANGED_DENIED')
            verify_security(handle);return b''.join(parts)
        finally:
            if handle is not None: close(handle)
