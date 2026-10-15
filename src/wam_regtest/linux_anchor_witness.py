"""Experimental root-owned Linux monotonic witness, no keys or cryptography.

Optional administrative service; NEVER auto-installed by the wallet. Client
requires root SO_PEERCRED and protected pathname ancestors. Server authorizes
one non-root UID and retains immutable generation/digest records. Root/whole
OS rollback, power-loss durability and hardened process binding are unqualified.
Not yet connected to custody.py or spending; native acceptance is mandatory.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import platform
import re
import secrets
import socket
import stat
import struct
import sys
import threading

PROTOCOL='wam-regtest-root-witness/v1'
LIMIT=512


class LinuxWitnessError(ValueError):pass


def _native():
    if sys.platform!='linux' or platform.machine()!='x86_64' or not hasattr(socket,'SO_PEERCRED'):
        raise LinuxWitnessError('ROOT_WITNESS_NATIVE_LINUX_REQUIRED')


def _record(value):
    if value is None:return None
    if (type(value) not in (list,tuple) or len(value)!=2 or type(value[0]) is not int
            or not 1<=value[0]<=10000 or type(value[1]) is not str
            or not re.fullmatch('[0-9a-f]{64}',value[1])):
        raise LinuxWitnessError('ROOT_WITNESS_RECORD_DENIED')
    return tuple(value)


def _root_directory(path,private=False):
    if type(path) is not type(Path()) or path.anchor!='/' or '..' in path.parts or len(path.parts)<2:
        raise LinuxWitnessError('ROOT_WITNESS_PATH_DENIED')
    held=[]
    try:
        held.append(os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC))
        for name in path.parts[1:]:
            held.append(os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=held[-1]))
            info=os.fstat(held[-1])
            if info.st_uid!=0 or (info.st_mode&0o022 and not info.st_mode&stat.S_ISVTX):
                raise LinuxWitnessError('ROOT_WITNESS_DIRECTORY_OWNER_DENIED')
            if set(os.listxattr(held[-1]))&{'system.posix_acl_access','system.posix_acl_default'}:
                raise LinuxWitnessError('ROOT_WITNESS_DIRECTORY_ACL_DENIED')
        if private and stat.S_IMODE(os.fstat(held[-1]).st_mode)!=0o700:
            raise LinuxWitnessError('ROOT_WITNESS_DIRECTORY_MODE_DENIED')
        return held.pop()
    finally:
        for fd in reversed(held):os.close(fd)


def _peer(connection):
    return struct.unpack('3i',connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,struct.calcsize('3i')))


def _send(connection,value):
    raw=json.dumps(value,separators=(',',':')).encode('ascii')+b'\n'
    if len(raw)>LIMIT:raise LinuxWitnessError('ROOT_WITNESS_MESSAGE_LIMIT')
    connection.sendall(raw)


def _receive(connection):
    raw=bytearray()
    while len(raw)<LIMIT:
        part=connection.recv(1)
        if not part:raise LinuxWitnessError('ROOT_WITNESS_CONNECTION_LOST')
        if part==b'\n':
            value=json.loads(raw)
            if type(value) is not dict:raise LinuxWitnessError('ROOT_WITNESS_MESSAGE_DENIED')
            return value
        raw.extend(part)
    raise LinuxWitnessError('ROOT_WITNESS_MESSAGE_LIMIT')


class LinuxRootWitnessAnchor:
    def __init__(self,wallet_id,endpoint):
        _native()
        if type(wallet_id) is not str or not re.fullmatch('[0-9a-f]{32}',wallet_id):
            raise LinuxWitnessError('ROOT_WITNESS_WALLET_ID_DENIED')
        if type(endpoint) is not type(Path()) or len(os.fsencode(endpoint))>103:
            raise LinuxWitnessError('ROOT_WITNESS_ENDPOINT_DENIED')
        self.wallet_id,self.endpoint=wallet_id,endpoint
        self._local=threading.local()
    @contextmanager
    def lease(self):
        if getattr(self._local,'pid',None)==os.getpid():
            yield;return
        fd=_root_directory(self.endpoint.parent);connection=None
        try:
            if stat.S_IMODE(os.fstat(fd).st_mode)!=0o755:
                raise LinuxWitnessError('ROOT_WITNESS_ENDPOINT_PARENT_MODE_DENIED')
            info=os.stat(self.endpoint.name,dir_fd=fd,follow_symlinks=False)
            if (not stat.S_ISSOCK(info.st_mode) or info.st_uid!=os.geteuid()
                    or stat.S_IMODE(info.st_mode)!=0o600 or info.st_nlink!=1):
                raise LinuxWitnessError('ROOT_WITNESS_SOCKET_CUSTODY_DENIED')
            connection=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
            connection.settimeout(30);connection.connect(str(self.endpoint))
            if _peer(connection)[1]!=0:raise LinuxWitnessError('ROOT_WITNESS_ROOT_PEER_REQUIRED')
            _send(connection,{'op':'lease','wallet_id':self.wallet_id})
            reply=_receive(connection)
            if reply!={'ok':True,'protocol':PROTOCOL}:
                raise LinuxWitnessError('ROOT_WITNESS_SESSION_BUSY_OR_DENIED')
            self._local.pid=os.getpid();self._local.connection=connection
            try:
                yield
                # Prove the root-held lease survived through the sensitive body.
                if self._request({'op':'ping'}) is not True:
                    raise LinuxWitnessError('ROOT_WITNESS_LEASE_LOST')
            finally:
                try:
                    if self._request({'op':'release'}) is not True:
                        raise LinuxWitnessError('ROOT_WITNESS_RELEASE_DENIED')
                finally:self._local.pid=None;self._local.connection=None
        except LinuxWitnessError:raise
        except (OSError,ValueError):raise LinuxWitnessError('ROOT_WITNESS_UNAVAILABLE_OR_DENIED') from None
        finally:
            if connection is not None:connection.close()
            os.close(fd)
    def _request(self,message):
        if getattr(self._local,'pid',None)!=os.getpid():
            raise LinuxWitnessError('ROOT_WITNESS_LEASE_REQUIRED')
        try:
            _send(self._local.connection,message);reply=_receive(self._local.connection)
            if set(reply)!={'ok','value'} or reply['ok'] is not True:
                raise LinuxWitnessError('ROOT_WITNESS_OPERATION_DENIED')
            return reply['value']
        except LinuxWitnessError:raise
        except (OSError,ValueError):raise LinuxWitnessError('ROOT_WITNESS_CONNECTION_LOST') from None
    def read(self):
        with self.lease():return _record(self._request({'op':'read'}))
    def advance(self,previous,current):
        with self.lease():self._advance_unlocked(previous,current)
    def _advance_unlocked(self,previous,current):
        previous,current=_record(previous),_record(current)
        if current is None or current[0]!=(1 if previous is None else previous[0]+1):
            raise LinuxWitnessError('ROOT_WITNESS_SEQUENCE_DENIED')
        if self._request({'op':'advance','previous':previous,'current':current}) is not True:
            raise LinuxWitnessError('ROOT_WITNESS_CAS_DENIED')


def _root_file(fd,limit=LIMIT):
    info=os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_nlink!=1
            or stat.S_IMODE(info.st_mode)!=0o600 or not 0<=info.st_size<=limit
            or set(os.listxattr(fd))&{'system.posix_acl_access','system.posix_acl_default'}):
        raise LinuxWitnessError('ROOT_WITNESS_STATE_CUSTODY_DENIED')


class _Journal:
    def __init__(self,root):self.root=root
    def read(self):
        fd=_root_directory(self.root,private=True)
        try:
            names=[n for n in os.listdir(fd) if not n.startswith('.stage-')]
            if len(names)>10000 or any(not re.fullmatch(r'[0-9]{5}\.anchor',n) for n in names):
                raise LinuxWitnessError('ROOT_WITNESS_JOURNAL_SHAPE_DENIED')
            if not names:return None
            generation=max(int(n[:5]) for n in names)
            if set(names)!={f'{i:05d}.anchor' for i in range(1,generation+1)}:
                raise LinuxWitnessError('ROOT_WITNESS_JOURNAL_GAP_DENIED')
            member=os.open(f'{generation:05d}.anchor',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,dir_fd=fd)
            try:
                _root_file(member);value=_record(json.loads(os.read(member,LIMIT+1)))
                if value is None or value[0]!=generation:raise LinuxWitnessError('ROOT_WITNESS_JOURNAL_RECORD_DENIED')
                return value
            finally:os.close(member)
        finally:os.close(fd)
    def advance(self,previous,current):
        if self.read()!=previous or current[0]!=(1 if previous is None else previous[0]+1):
            raise LinuxWitnessError('ROOT_WITNESS_STALE_WRITER_DENIED')
        fd=_root_directory(self.root,private=True);member=None;stage='.stage-'+secrets.token_hex(16);created=False
        try:
            member=os.open(stage,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=fd);created=True
            _root_file(member);raw=json.dumps(current).encode('ascii')
            offset=0
            while offset<len(raw):
                count=os.write(member,raw[offset:])
                if count<=0:raise LinuxWitnessError('ROOT_WITNESS_STATE_WRITE_DENIED')
                offset+=count
            os.fsync(member);os.close(member);member=None
            os.link(stage,f'{current[0]:05d}.anchor',src_dir_fd=fd,dst_dir_fd=fd,follow_symlinks=False)
            os.unlink(stage,dir_fd=fd);created=False;os.fsync(fd)
            if self.read()!=current:raise LinuxWitnessError('ROOT_WITNESS_STATE_VERIFY_DENIED')
        finally:
            if member is not None:os.close(member)
            try:
                if created:os.unlink(stage,dir_fd=fd)
            finally:os.close(fd)


def serve(root,uid,*,provision=False):
    """Administrative entry: install reviewed file root-owned first, then opt in."""
    _native()
    import fcntl
    if os.geteuid()!=0 or type(uid) is not int or not 1<=uid<2**31:
        raise LinuxWitnessError('ROOT_WITNESS_ADMIN_REQUIRED')
    source=Path(__file__).resolve();info=source.stat()
    if info.st_uid!=0 or info.st_mode&0o022:
        raise LinuxWitnessError('ROOT_WITNESS_SERVICE_INSTALL_REQUIRED')
    endpoint=root/'anchor.sock'
    if len(os.fsencode(endpoint))>103:raise LinuxWitnessError('ROOT_WITNESS_ENDPOINT_DENIED')
    if provision:
        parent=_root_directory(root.parent)
        try:os.mkdir(root.name,0o755,dir_fd=parent);os.fsync(parent)
        finally:os.close(parent)
        (root/'records').mkdir(mode=0o700);(root/'locks').mkdir(mode=0o700)
        with (root/'identity.json').open('xb') as out:
            os.chmod(root/'identity.json',0o600);out.write(json.dumps({'protocol':PROTOCOL,'uid':uid}).encode());out.flush();os.fsync(out.fileno())
    rfd=_root_directory(root)
    server_lock=listener=None
    try:
        if stat.S_IMODE(os.fstat(rfd).st_mode)!=0o755:
            raise LinuxWitnessError('ROOT_WITNESS_ENDPOINT_PARENT_MODE_DENIED')
        meta=os.open('identity.json',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,dir_fd=rfd)
        try:
            _root_file(meta)
            if json.loads(os.read(meta,LIMIT+1))!={'protocol':PROTOCOL,'uid':uid}:
                raise LinuxWitnessError('ROOT_WITNESS_IDENTITY_DENIED')
        finally:os.close(meta)
        for name in ('records','locks'):
            checked=_root_directory(root/name,private=True)
            try:os.fsync(checked)
            finally:os.close(checked)
        server_lock=os.open('server.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=rfd)
        _root_file(server_lock,0);fcntl.flock(server_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if endpoint.exists():
            existing=endpoint.lstat()
            if not stat.S_ISSOCK(existing.st_mode):raise LinuxWitnessError('ROOT_WITNESS_STALE_SOCKET_DENIED')
            endpoint.unlink()
        listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);listener.bind(str(endpoint))
        os.chown(endpoint,uid,-1);os.chmod(endpoint,0o600);os.fsync(rfd)
        listener.listen(16);slots=threading.BoundedSemaphore(16)
        def handle(connection):
            lockfd=lockdir=None
            try:
                connection.settimeout(300)
                if _peer(connection)[1]!=uid:raise LinuxWitnessError('ROOT_WITNESS_CLIENT_UID_DENIED')
                hello=_receive(connection)
                if (set(hello)!={'op','wallet_id'} or hello['op']!='lease' or type(hello['wallet_id']) is not str
                        or not re.fullmatch('[0-9a-f]{32}',hello['wallet_id'])):
                    raise LinuxWitnessError('ROOT_WITNESS_HELLO_DENIED')
                wallet=hello['wallet_id'];lockdir=_root_directory(root/'locks',private=True)
                lockfd=os.open(wallet+'.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=lockdir)
                _root_file(lockfd,0);fcntl.flock(lockfd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                directory=root/'records'/wallet
                parentfd=_root_directory(root/'records',private=True)
                try:
                    try:
                        os.mkdir(wallet,0o700,dir_fd=parentfd);os.fsync(parentfd)
                    except FileExistsError:pass
                finally:os.close(parentfd)
                journal=_Journal(directory);journal.read()
                _send(connection,{'ok':True,'protocol':PROTOCOL})
                while True:
                    message=_receive(connection)
                    if message=={'op':'read'}:value=journal.read()
                    elif message=={'op':'ping'}:value=True
                    elif message=={'op':'release'}:
                        os.close(lockfd);lockfd=None
                        _send(connection,{'ok':True,'value':True});break
                    elif set(message)=={'op','previous','current'} and message['op']=='advance':
                        previous,current=_record(message['previous']),_record(message['current'])
                        if current is None:raise LinuxWitnessError('ROOT_WITNESS_RECORD_DENIED')
                        journal.advance(previous,current);value=True
                    else:raise LinuxWitnessError('ROOT_WITNESS_OPERATION_DENIED')
                    _send(connection,{'ok':True,'value':value})
            except Exception:
                if lockfd is not None:os.close(lockfd);lockfd=None
                try:_send(connection,{'ok':False,'code':'ROOT_WITNESS_DENIED'})
                except (OSError,ValueError):pass
            finally:
                if lockfd is not None:os.close(lockfd)
                if lockdir is not None:os.close(lockdir)
                connection.close();slots.release()
        print('ROOT_WITNESS_READY '+str(os.getpid()),flush=True)
        while True:
            connection,_=listener.accept()
            if not slots.acquire(blocking=False):connection.close();continue
            threading.Thread(target=handle,args=(connection,),daemon=True).start()
    finally:
        if listener is not None:listener.close();endpoint.unlink(missing_ok=True)
        if server_lock is not None:os.close(server_lock)
        os.close(rfd)


def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--state-root',type=Path,required=True)
    parser.add_argument('--uid',type=int,required=True);parser.add_argument('--provision',action='store_true')
    args=parser.parse_args()
    try:serve(args.state_root,args.uid,provision=args.provision)
    except Exception:print('ROOT_WITNESS_START_DENIED',file=sys.stderr);return 2
    return 0


if __name__=='__main__':raise SystemExit(main())
