"""Owner-only native Windows Core staging/config and strictly local RPC custody.

Original official bytes only. Not a process-handle loader attestation or a
protection against same-user malware/administrators controlling the OS.
"""
import ctypes
from hashlib import sha256
import json
from pathlib import Path
from . import windows_private_storage as store
from .windows_release_preflight import ARCHIVE_SHA256, BINARY_SHA256


class WindowsCoreTransportError(ValueError):
    pass


_LIMITS={'wamd.exe':128*1024*1024,'wam-cli.exe':128*1024*1024,'wam.conf':4096,'receipt.json':4096}


def write_new(directory,name,data):
    store.require_native()
    if name not in _LIMITS or type(data) is not bytes or not 1<=len(data)<=_LIMITS[name]:
        raise WindowsCoreTransportError('WIN_CORE_PRIVATE_FILE_DENIED')
    with store.directory_guard(directory):
        with store.security_attributes() as sa:
            handle=store.create(str(directory/name),0xc0030000,1,sa,1,0x80200080,None)
        if handle in (None,store.INVALID):
            raise WindowsCoreTransportError('WIN_CORE_PRIVATE_CREATE_DENIED')
        complete=False
        try:
            store._metadata(handle);store.verify_security(handle)
            offset=0
            while offset<len(data):
                part=data[offset:offset+65536];buffer=ctypes.create_string_buffer(part);count=store.w.DWORD()
                if not store.write(handle,buffer,len(part),ctypes.byref(count),None) or not count.value:
                    raise WindowsCoreTransportError('WIN_CORE_PRIVATE_WRITE_DENIED')
                offset+=count.value
            if not store.flush(handle):raise WindowsCoreTransportError('WIN_CORE_PRIVATE_FLUSH_DENIED')
            store._metadata(handle);store.verify_security(handle);complete=True
        finally:
            try:
                if not complete:
                    disposition=store.DISPOSITION(True)
                    if not store.setinfo(handle,4,ctypes.byref(disposition),ctypes.sizeof(disposition)):
                        raise WindowsCoreTransportError('WIN_CORE_PRIVATE_CLEANUP_DENIED')
            finally:store.close(handle)


def read_private(directory,name):
    store.require_native()
    if name not in _LIMITS:raise WindowsCoreTransportError('WIN_CORE_PRIVATE_FILE_DENIED')
    with store.directory_guard(directory):
        handle=store.create(str(directory/name),0x80020000,1,None,3,0x200080,None)
        if handle in (None,store.INVALID):raise WindowsCoreTransportError('WIN_CORE_PRIVATE_READ_DENIED')
        try:
            before=store._metadata(handle);store.verify_security(handle)
            if not 1<=before[3]<=_LIMITS[name]:raise WindowsCoreTransportError('WIN_CORE_PRIVATE_SIZE_DENIED')
            remaining=before[3];parts=[]
            while remaining:
                size=min(remaining,65536);buffer=ctypes.create_string_buffer(size);count=store.w.DWORD()
                if not store.readfile(handle,buffer,size,ctypes.byref(count),None) or not count.value:
                    raise WindowsCoreTransportError('WIN_CORE_PRIVATE_READ_DENIED')
                parts.append(buffer.raw[:count.value]);remaining-=count.value
            if before!=store._metadata(handle):raise WindowsCoreTransportError('WIN_CORE_PRIVATE_CHANGED_DENIED')
            store.verify_security(handle);return b''.join(parts)
        finally:store.close(handle)


def verified_core_paths(directory):
    try:
        receipt=json.loads(read_private(directory,'receipt.json'))
        if (receipt['platform']!='windows-x64' or receipt['signed_archive_verified'] is not True
                or receipt['archive_sha256']!=ARCHIVE_SHA256 or receipt['member_sha256']!=BINARY_SHA256
                or receipt['mainnet_allowed'] is not False or receipt['loader_process_binding_qualified'] is not False):
            raise ValueError
        for name,digest in BINARY_SHA256.items():
            if sha256(read_private(directory,name)).hexdigest()!=digest:raise ValueError
        return directory/'wamd.exe',directory/'wam-cli.exe',{
            **receipt,'wamd_sha256':BINARY_SHA256['wamd.exe'],'wam_cli_sha256':BINARY_SHA256['wam-cli.exe']}
    except Exception:
        raise WindowsCoreTransportError('WIN_CORE_PRIVATE_IDENTITY_DENIED') from None


def local_rpc_port(directory):
    from .network_policy import parse_local_config
    return parse_local_config(read_private(directory,'wam.conf'))


def read_cli(cmd,timeout=15):
    from .windows_core_regtest_smoke import _rpc, _host_env
    store.require_native()
    if (type(cmd) is not list or len(cmd)<3 or any(type(x) is not str for x in cmd)
            or not cmd[1].startswith('-datadir=')):
        raise WindowsCoreTransportError('WIN_CORE_LOCAL_COMMAND_DENIED')
    args=cmd[2:]
    if args[0]=='-rpcwallet=test':args=args[1:]
    permitted={'getblockchaininfo','getblockcount','getbestblockhash','getblockhash','getblock',
        'getconnectioncount','getnetworkinfo','getrawmempool','gettxout','testmempoolaccept',
        'sendrawtransaction','generatetoaddress','invalidateblock','reconsiderblock',
        'createwallet','getnewaddress','stop'}
    if not args or args[0] not in permitted or any(a.startswith('-') for a in args):
        raise WindowsCoreTransportError('WIN_CORE_LOCAL_METHOD_DENIED')
    directory=Path(cmd[1][9:]);binary=Path(cmd[0])
    # Every CLI invocation authenticates exact bytes and native file custody.
    if binary.name!='wam-cli.exe' or sha256(read_private(binary.parent,binary.name)).hexdigest()!=BINARY_SHA256['wam-cli.exe']:
        raise WindowsCoreTransportError('WIN_CORE_CLI_IDENTITY_DENIED')
    port=local_rpc_port(directory)
    return _rpc(binary,directory,port,_host_env(directory),*cmd[2:],timeout=timeout)
