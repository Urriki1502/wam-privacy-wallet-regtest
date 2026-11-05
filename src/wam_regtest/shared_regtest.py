"""Explicit manual Core-to-Core REGTEST policy; never remote wallet RPC.

An immutable policy belongs to a NEW owned supervisor profile. Isolated
profiles are never reinterpreted or migrated. No discovery or P2P protocol is
implemented here: signed WAM Core owns TCP, handshake, relay and consensus.
"""
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import ipaddress
import os
import secrets
import socket
import stat
import sys

MAGIC = bytes.fromhex('57414d52')
P2P_PORT = 29555
RPC_PORT = 29554
PROFILE_SCHEMA = 'wam-fusion-owned-shared-regtest-profile/v1'


class SharedRegtestError(ValueError):
    pass


def private_host(value):
    if type(value) is not str or not 1 <= len(value) <= 64 or '%' in value:
        raise SharedRegtestError('SHARED_PRIVATE_IP_REQUIRED')
    try:
        address = ipaddress.ip_address(value)
        if (not address.is_private or address.is_unspecified or address.is_multicast
                or address.is_link_local):
            raise ValueError
        return str(address)
    except ValueError:
        raise SharedRegtestError('SHARED_PRIVATE_IP_REQUIRED') from None


def endpoint(host, port):
    host = private_host(host)
    if type(port) is not int or not 1024 <= port <= 65535:
        raise SharedRegtestError('SHARED_PORT_DENIED')
    return f'[{host}]:{port}' if ':' in host else f'{host}:{port}'


@dataclass(frozen=True)
class SharedRegtestProfile:
    peer_host: str
    bind_host: str = '127.0.0.1'
    coordinator: bool = False
    rpc_port: int = RPC_PORT
    p2p_port: int = P2P_PORT
    peer_port: int = P2P_PORT

    def __post_init__(self):
        if type(self.coordinator) is not bool:
            raise SharedRegtestError('SHARED_ROLE_DENIED')
        object.__setattr__(self, 'peer_host', private_host(self.peer_host))
        object.__setattr__(self, 'bind_host', private_host(self.bind_host))
        endpoint(self.bind_host, self.p2p_port)
        endpoint(self.peer_host, self.peer_port)
        endpoint('127.0.0.1', self.rpc_port)
        if self.rpc_port == self.p2p_port:
            raise SharedRegtestError('SHARED_PORT_COLLISION')
        if self.bind_host == self.peer_host and self.p2p_port == self.peer_port:
            raise SharedRegtestError('SHARED_SELF_PEER_DENIED')

    def record(self):
        return asdict(self)

    @classmethod
    def from_record(cls, value):
        if type(value) is not dict or set(value) != set(cls.__dataclass_fields__):
            raise SharedRegtestError('SHARED_PROFILE_DENIED')
        return cls(**value)

    def settings(self):
        from .network_policy import _FIXED
        values = dict(_FIXED)
        values.update(listen='1', port=str(self.p2p_port), rpcport=str(self.rpc_port),
                      bind=endpoint(self.bind_host, self.p2p_port),
                      addnode=endpoint(self.peer_host, self.peer_port),
                      # Core reserves outbound slots even with discovery off;
                      # leave two inbound slots for the one manual counterpart.
                      dns='0', listenonion='0', maxconnections='12',
                      **{'# fusion_shared_role':'coordinator' if self.coordinator else 'participant'})
        return values


@contextmanager
def reserve_ports(profile):
    if type(profile) is not SharedRegtestProfile:
        raise SharedRegtestError('SHARED_EXPLICIT_PROFILE_REQUIRED')
    sockets = []
    try:
        for host, port in (('127.0.0.1', profile.rpc_port), (profile.bind_host, profile.p2p_port)):
            sock = socket.socket(socket.AF_INET6 if ':' in host else socket.AF_INET, socket.SOCK_STREAM)
            sockets.append(sock)
            if sys.platform == 'win32':
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            sock.bind((host, port))
        yield
    finally:
        for sock in sockets:
            sock.close()


def write_config(directory, profile):
    from . import custody
    custody.storage().validate_directory(directory)
    values = profile.settings()
    values.update(rpcuser='disposable_'+secrets.token_hex(8), rpcpassword=secrets.token_hex(32))
    raw = ('regtest=1\nserver=1\n[regtest]\n' +
           ''.join(f'{key}={value}\n' for key,value in values.items())).encode('ascii')
    if sys.platform == 'win32':
        from .windows_core_transport import write_new
        write_new(directory, 'wam.conf', raw)
    else:
        fd = os.open(directory/'wam.conf', os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())


def validate_peers(rows, profile, *, require_connected=False):
    if type(profile) is not SharedRegtestProfile or type(rows) is not list or len(rows) > 2:
        raise SharedRegtestError('SHARED_PEER_SET_DENIED')
    for row in rows:
        if type(row) is not dict or type(row.get('addr')) is not str:
            raise SharedRegtestError('SHARED_PEER_REPLY_DENIED')
        address = row['addr']
        try:
            host, port = address.rsplit(':', 1)
            host = private_host(host.strip('[]'))
            port = int(port)
        except (ValueError, TypeError):
            raise SharedRegtestError('SHARED_PEER_ENDPOINT_DENIED') from None
        if (host != profile.peer_host or not 1 <= port <= 65535
                or type(row.get('inbound')) is not bool
                or not row['inbound'] and port != profile.peer_port
                or type(row.get('version')) is not int or row.get('version') not in (0,70016)
                or row.get('subver') not in ('','/WAM:0.1.13/')):
            raise SharedRegtestError('SHARED_UNEXPECTED_PEER_DENIED')
    ready = [r for r in rows if r.get('version') == 70016 and r.get('subver') == '/WAM:0.1.13/']
    if require_connected and not ready:
        raise SharedRegtestError('SHARED_CONFIRMED_PEER_REQUIRED')
    return {'connected': bool(ready), 'peer_count':len(ready),
            'coordinator':profile.coordinator, 'manual_only':True,
            'rpc_loopback_only':True, 'mainnet_allowed':False,
            'peers':tuple({k:r.get(k) for k in ('addr','version','subver','inbound','connection_type')}
                          for r in rows)}


def peer_status(directory, *, require_connected=False):
    from .rpc_scope import identity, route
    context = identity(directory)
    profile = getattr(context, 'shared_profile', None)
    if context is None or context.faulted or type(profile) is not SharedRegtestProfile:
        raise SharedRegtestError('SHARED_OWNED_SCOPE_REQUIRED')
    rows = route(context.binding.cli, directory, ['getpeerinfo'])
    try:
        return validate_peers(rows, profile, require_connected=require_connected)
    except SharedRegtestError as error:
        if error.args != ('SHARED_CONFIRMED_PEER_REQUIRED',):
            context.faulted = True
        raise


def block_magic(directory):
    """Read only the public first record marker of this owned Core's blocks.

    Core v0.1.13 defaults to XOR-obfuscated block files. The local mask is
    never returned or logged. This checks disk framing, not a wire capture.
    """
    from .custody import storage
    blocks = directory/'regtest'/'blocks'
    storage().validate_directory(blocks)
    def read(name,count):
        fd = os.open(blocks/name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_uid!=os.geteuid():
                raise SharedRegtestError('SHARED_MAGIC_FILE_DENIED')
            raw = os.read(fd,count)
            if len(raw)!=count:raise SharedRegtestError('SHARED_MAGIC_MISSING')
            return raw
        finally:os.close(fd)
    mask = read('xor.dat',8)
    raw = read('blk00000.dat',4)
    marker = bytes(v^mask[i] for i,v in enumerate(raw))
    if marker!=MAGIC:raise SharedRegtestError('SHARED_NETWORK_MAGIC_DENIED')
    return marker.hex()
