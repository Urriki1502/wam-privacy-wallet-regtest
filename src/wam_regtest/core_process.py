"""Owned Core process/established-socket binding BEFORE HTTP auth is sent.

Kernel endpoint ownership and mapped image path are evidence, not hardened
fd-to-loader attestation or protection against same-user/OS compromise.
"""
import ctypes
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import time
from .core import verified_core_paths


class CoreBindingError(ValueError):
    pass


def _metadata(path):
    s=path.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1:
        raise CoreBindingError('RPC_EXECUTABLE_METADATA_DENIED')
    if os.name=='posix' and (s.st_uid not in (0,os.geteuid()) or s.st_mode&0o022):
        raise CoreBindingError('RPC_EXECUTABLE_CUSTODY_DENIED')
    return tuple(getattr(s,k) for k in ('st_dev','st_ino','st_size','st_mode','st_uid','st_nlink','st_mtime_ns','st_ctime_ns'))


def _image(pid,directory):
    if sys.platform=='linux':return os.readlink(f'/proc/{pid}/exe')
    if sys.platform=='darwin':
        lib=ctypes.CDLL('/usr/lib/libproc.dylib',use_errno=True)
        lib.proc_pidpath.argtypes=[ctypes.c_int,ctypes.c_void_p,ctypes.c_uint32];lib.proc_pidpath.restype=ctypes.c_int
        buf=ctypes.create_string_buffer(4096);n=lib.proc_pidpath(pid,buf,len(buf))
        if not 0<n<len(buf):raise CoreBindingError('RPC_PROCESS_IMAGE_DENIED')
        return buf.value.decode('utf8')
    if sys.platform=='win32':
        from ctypes import wintypes as w
        lib=ctypes.WinDLL('kernel32',use_last_error=True)
        lib.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];lib.OpenProcess.restype=w.HANDLE
        lib.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,ctypes.POINTER(w.DWORD)];lib.QueryFullProcessImageNameW.restype=w.BOOL
        lib.CloseHandle.argtypes=[w.HANDLE];lib.CloseHandle.restype=w.BOOL
        h=lib.OpenProcess(0x1000,False,pid)
        if not h:raise CoreBindingError('RPC_PROCESS_IMAGE_DENIED')
        try:
            buf=ctypes.create_unicode_buffer(32768);size=w.DWORD(len(buf))
            if not lib.QueryFullProcessImageNameW(h,0,buf,ctypes.byref(size)) or not 0<size.value<len(buf):
                raise CoreBindingError('RPC_PROCESS_IMAGE_DENIED')
            return buf.value
        finally:lib.CloseHandle(h)
    raise CoreBindingError('RPC_NATIVE_PROCESS_PROOF_REQUIRED')


def _linux_socket(pid,server_port,client_port):
    root=Path(f'/proc/{pid}');inodes=set()
    for fd in (root/'fd').iterdir():
        try:target=os.readlink(fd)
        except OSError:continue
        m=re.fullmatch(r'socket:\[([0-9]+)\]',target)
        if m:inodes.add(m[1])
    local=f'0100007F:{server_port:04X}';remote=f'0100007F:{client_port:04X}'
    for line in (root/'net/tcp').read_text().splitlines()[1:]:
        fields=line.split()
        if len(fields)>=10 and fields[1]==local and fields[2]==remote and fields[3]=='01' and fields[9] in inodes:return True
    return False


def _lsof_match(raw,pid,server_port,client_port):
    expected=f'127.0.0.1:{server_port}->127.0.0.1:{client_port}'
    current_pid=None;name=None;state=None;found=False
    for line in [*raw.splitlines(),'fEND']:
        if line.startswith(('f','p')):
            if current_pid==str(pid) and name==expected and state=='ESTABLISHED':found=True
            name=state=None
        if line.startswith('p'):current_pid=line[1:]
        elif line.startswith('n'):name=line[1:]
        elif line.startswith('TST='):state=line[4:]
    return found


def _mac_socket(pid,server_port,client_port):
    tool=Path('/usr/sbin/lsof');s=tool.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_uid!=0 or s.st_mode&0o022:raise CoreBindingError('RPC_SYSTEM_SOCKET_PROBE_DENIED')
    result=subprocess.run([str(tool),'-nP','-a','-p',str(pid),f'-iTCP:{server_port}','-sTCP:ESTABLISHED','-FpfnT'],
        stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=2,
        env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','LC_ALL':'C'},check=False)
    if len(result.stdout)>65536 or result.returncode not in (0,1):raise CoreBindingError('RPC_SOCKET_PROOF_DENIED')
    return _lsof_match(result.stdout.decode('ascii'),pid,server_port,client_port)


def _windows_socket(pid,server_port,client_port,directory):
    from ctypes import wintypes as w
    from .windows_core_regtest_smoke import _host_env
    lib=ctypes.WinDLL(str(Path(_host_env(directory)['SystemRoot'])/'System32/iphlpapi.dll'),use_last_error=True)
    get=lib.GetExtendedTcpTable;get.argtypes=[ctypes.c_void_p,ctypes.POINTER(w.DWORD),w.BOOL,w.ULONG,ctypes.c_int,w.ULONG];get.restype=w.DWORD
    class Row(ctypes.Structure):_fields_=[(n,w.DWORD) for n in ('state','local_addr','local_port','remote_addr','remote_port','pid')]
    size=w.DWORD(0)
    if get(None,ctypes.byref(size),False,2,5,0) not in (0,122) or not 4<=size.value<=8*1024*1024:
        raise CoreBindingError('RPC_SOCKET_TABLE_DENIED')
    for _ in range(2):
        buf=ctypes.create_string_buffer(size.value);rc=get(buf,ctypes.byref(size),False,2,5,0)
        if rc==122:
            if not 4<=size.value<=8*1024*1024:raise CoreBindingError('RPC_SOCKET_TABLE_DENIED')
            continue
        if rc:raise CoreBindingError('RPC_SOCKET_TABLE_DENIED')
        count=w.DWORD.from_buffer_copy(buf).value
        if count>100000 or 4+count*ctypes.sizeof(Row)>len(buf):raise CoreBindingError('RPC_SOCKET_TABLE_DENIED')
        loopback=int.from_bytes(socket.inet_aton('127.0.0.1'),'little')
        for i in range(count):
            row=Row.from_buffer_copy(buf,4+i*ctypes.sizeof(Row))
            if (row.pid==pid and row.state==5 and row.local_addr==loopback and row.remote_addr==loopback
                    and socket.ntohs(row.local_port&0xffff)==server_port and socket.ntohs(row.remote_port&0xffff)==client_port):return True
        return False
    raise CoreBindingError('RPC_SOCKET_TABLE_CHANGED')


class OwnedCoreBinding:
    def __init__(self,process,core,directory):
        if type(process) is not subprocess.Popen or type(core) is not type(Path()) or type(directory) is not type(Path()):
            raise CoreBindingError('RPC_OWNED_PROCESS_REQUIRED')
        self.process,self.core,self.directory=process,core,directory
        # T-04: pin BOTH executable file identities before the potentially
        # lengthy signed-byte verification, and demand the same identities
        # immediately after it. This closes the obvious replace-during-hash
        # window without ever rehashing Core/CLI for ordinary RPC requests.
        # This is NOT fd-to-loader attestation against compromised same-UID/OS.
        if (type(process.args) is not list or len(process.args)!=3
                or type(process.args[0]) is not str):
            raise CoreBindingError('RPC_OWNED_PROCESS_REQUIRED')
        requested=Path(process.args[0])
        if (requested.parent!=core or requested.name not in ('wamd','wamd.exe')
                or process.args!=[str(requested),f'-datadir={directory}','-daemon=0']
                or process.poll() is not None):
            raise CoreBindingError('RPC_OWNED_PROCESS_REQUIRED')
        expected_cli=core/('wam-cli.exe' if requested.name=='wamd.exe' else 'wam-cli')
        before=(_metadata(requested),_metadata(expected_cli))
        self.node,self.cli,self.receipt=verified_core_paths(core)
        if self.node!=requested or self.cli!=expected_cli:
            raise CoreBindingError('RPC_EXECUTABLE_PAIR_DENIED')
        after=(_metadata(self.node),_metadata(self.cli))
        if before!=after:
            raise CoreBindingError('RPC_EXECUTABLE_CHANGED_DURING_VERIFY')
        self._files=after
        self._image_path=str(self.node.resolve(strict=True))
        self._argv=[str(self.node),f'-datadir={directory}','-daemon=0']
        self._assert_image()

    def __repr__(self):return '<OwnedCoreBinding public-process-scope>'

    def _assert_image(self):
        if self.process.args!=self._argv or self.process.poll() is not None:
            raise CoreBindingError('RPC_OWNED_PROCESS_EXITED')
        try:
            image=_image(self.process.pid,self.directory)
        except OSError:
            # A child may exit between poll() and the native image lookup.
            # Never treat the missing image as ownership. Startup may classify
            # an actual exited bind collision; every other caller still denies.
            raise CoreBindingError('RPC_PROCESS_IMAGE_DENIED') from None
        # Windows may report the process launch's 8.3 alias while Path.resolve
        # returns its long name. Compare native file identity, not spelling;
        # the independently pinned metadata below must still be unchanged.
        same=(os.path.samefile(image,self.node) if sys.platform=='win32' else
              os.path.normcase(image)==os.path.normcase(self._image_path))
        if not same:raise CoreBindingError('RPC_PROCESS_IMAGE_DENIED')
        if self._files!=(_metadata(self.node),_metadata(self.cli)):
            raise CoreBindingError('RPC_EXECUTABLE_CHANGED')

    def assert_socket(self,sock):
        self._assert_image()
        local,remote=sock.getsockname(),sock.getpeername()
        if local[0]!='127.0.0.1' or remote[0]!='127.0.0.1':raise CoreBindingError('RPC_LOOPBACK_SOCKET_REQUIRED')
        deadline=time.monotonic()+1
        while True:
            self._assert_image()
            if sys.platform=='darwin':found=_mac_socket(self.process.pid,remote[1],local[1])
            elif sys.platform=='linux':found=_linux_socket(self.process.pid,remote[1],local[1])
            elif sys.platform=='win32':found=_windows_socket(self.process.pid,remote[1],local[1],self.directory)
            else:raise CoreBindingError('RPC_NATIVE_PROCESS_PROOF_REQUIRED')
            if found:
                self._assert_image();return
            if time.monotonic()>=deadline:raise CoreBindingError('RPC_ENDPOINT_OWNER_DENIED')
            time.sleep(.02)
