"""Native persistent directory identity, without transient mount device numbers.

No migration/rebinding, PID authority or independent full-OS rollback witness.
All components come from the same native guarded directory descriptor/handle.
"""
import ctypes
import os
import struct
import sys


class DirectoryIdentityError(ValueError):pass


def _mac(fd):
    class Attrlist(ctypes.Structure):
        _fields_=[('count',ctypes.c_uint16),('reserved',ctypes.c_uint16),
                  ('common',ctypes.c_uint32),('volume',ctypes.c_uint32),
                  ('directory',ctypes.c_uint32),('file',ctypes.c_uint32),
                  ('fork',ctypes.c_uint32)]
    lib=ctypes.CDLL('/usr/lib/libSystem.B.dylib',use_errno=True)
    call=lib.fgetattrlist
    call.argtypes=[ctypes.c_int,ctypes.POINTER(Attrlist),ctypes.c_void_p,
                   ctypes.c_size_t,ctypes.c_ulong];call.restype=ctypes.c_int
    def attributes(common,volume,size):
        request=Attrlist(5,0,common,volume,0,0,0)
        buffer=ctypes.create_string_buffer(size)
        if (call(fd,ctypes.byref(request),buffer,size,0)!=0
                or struct.unpack_from('=I',buffer.raw)[0]!=size):
            raise DirectoryIdentityError('MANAGED_DIRECTORY_NATIVE_ID_DENIED')
        return buffer.raw[4:]
    # Darwin sys/attr.h: volume and common groups require separate requests.
    volume=attributes(0,0x80000000|0x00040000,20)  # VOL_INFO | VOL_UUID
    born,ns,file_id=struct.unpack('=qqQ',attributes(0x00000200|0x02000000,0,28))
    if (not any(volume) or file_id!=os.fstat(fd).st_ino or file_id<=0
            or born<=0 or not 0<=ns<10**9):
        raise DirectoryIdentityError('MANAGED_DIRECTORY_NATIVE_ID_DENIED')
    return {'kind':'macos-volume-uuid-fileid-birth/v1','volume':volume.hex(),
            'file_id':file_id,'birth_ns':born*10**9+ns}


def _linux(fd):
    # Linux UAPI struct statx is a fixed 256-byte ABI. statx_timestamp uses
    # s64 seconds/u32 nanoseconds/u32 reserved, independent of libc time_t.
    lib=ctypes.CDLL(None,use_errno=True)
    call=lib.statx
    call.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_uint,ctypes.c_void_p]
    call.restype=ctypes.c_int
    buffer=ctypes.create_string_buffer(256);wanted=0x100|0x800  # INO | BTIME
    if call(fd,b'',0x1000|0x100,wanted,buffer)!=0:  # EMPTY_PATH | SYMLINK_NOFOLLOW
        raise DirectoryIdentityError('MANAGED_DIRECTORY_NATIVE_ID_DENIED')
    mask=struct.unpack_from('=I',buffer.raw)[0]
    file_id=struct.unpack_from('=Q',buffer.raw,32)[0]
    born,ns=struct.unpack_from('=qI',buffer.raw,80)
    fsid=os.fstatvfs(fd).f_fsid
    if (mask&wanted!=wanted or file_id!=os.fstat(fd).st_ino or file_id<=0
            or type(fsid) is not int or not 0<fsid<2**64
            or born<=0 or not 0<=ns<10**9):
        raise DirectoryIdentityError('MANAGED_DIRECTORY_NATIVE_ID_DENIED')
    return {'kind':'linux-fsid-inode-birth/v1','volume':fsid,
            'file_id':file_id,'birth_ns':born*10**9+ns}


def directory_identity(directory):
    """Refuse unavailable native identity; never fall back to st_dev/path."""
    try:
        if sys.platform=='win32':
            from . import windows_private_storage as store
            with store.directory_guard(directory) as handle:
                metadata=store._metadata(handle,directory=True);info=store.INFO()
                if not store.finfo(handle,ctypes.byref(info)):
                    raise DirectoryIdentityError('MANAGED_DIRECTORY_NATIVE_ID_DENIED')
                born=info.created.dwHighDateTime<<32|info.created.dwLowDateTime
                file_id=metadata[1]<<32|metadata[2]
                if not metadata[0] or not file_id or not born:
                    raise DirectoryIdentityError('MANAGED_DIRECTORY_NATIVE_ID_DENIED')
                return {'kind':'windows-volume-fileid-birth/v1','volume':metadata[0],
                        'file_id':file_id,'birth_100ns':born}
        if sys.platform=='darwin':
            from .private_directory import open_macos_private_directory as private
            identify=_mac
        elif sys.platform=='linux':
            from .linux_private_storage import open_linux_private_directory as private
            identify=_linux
        else:
            raise DirectoryIdentityError('MANAGED_DIRECTORY_NATIVE_ID_DENIED')
        fd=private(directory)
        try:return identify(fd)
        finally:os.close(fd)
    except DirectoryIdentityError:raise
    except (OSError,ValueError,AttributeError,TypeError,struct.error):
        raise DirectoryIdentityError('MANAGED_DIRECTORY_NATIVE_ID_DENIED') from None
