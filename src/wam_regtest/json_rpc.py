"""Shared, authenticated, loopback-only HTTP JSON-RPC transport for owned WAM Core.

No per-call CLI spawn, no repeated full-binary hashing, no remote endpoint, no
wallet-facing listener, no automatic retry of writes. This module covers only
read-only scanner sync; write paths remain on the existing signed CLI boundary.
"""
from __future__ import annotations

import base64
from decimal import Decimal
import hashlib
import http.client
import json
import os
import re
import stat
import sys
import threading
import time
import random

from .core_process import OwnedCoreBinding, CoreBindingError
from .rpc_credentials import CredentialSource, CredentialError, private_bytes
from .telemetry import increment
from .wsp_live import REGTEST_GENESIS


MAX_REPLY = 1024 * 1024
MAX_BLOCK_REPLY = 32 * 1024 * 1024
MAX_IDLE_REUSE_SECONDS = 5
MAX_TRUST_CACHE_SECONDS = 5
SUPPORTED_RPC = (111, '/WAM:0.1.11/', 70016)

_HTTP_READS = frozenset((
    'getblockchaininfo', 'getblockcount', 'getbestblockhash', 'getblockhash',
    'getblock', 'getconnectioncount', 'getnetworkinfo',
))

_HASH = re.compile(r'[0-9a-f]{64}\Z')


class RpcError(ValueError):
    """Fixed non-secret failure status; never include node output or paths."""


def _private_config(directory):
    """Read the protected wam.conf using the existing native credential boundary."""
    if sys.platform == 'win32':
        from .windows_core_transport import read_private
        return read_private(directory, 'wam.conf')
    if sys.platform == 'darwin':
        from .private_directory import open_macos_private_directory as open_dir, _require_absent_acl as no_acl
    elif sys.platform == 'linux':
        from .linux_private_storage import open_linux_private_directory as open_dir, _no_acl as no_acl
    else:
        raise RpcError('RPC_NATIVE_CUSTODY_REQUIRED')
    dfd = open_dir(directory)
    fd = None
    try:
        fd = os.open('wam.conf', os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=dfd)
        before = os.fstat(fd)
        no_acl(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid()
                or stat.S_IMODE(before.st_mode) != 0o600 or before.st_nlink != 1
                or not 1 <= before.st_size <= 4096):
            raise RpcError('RPC_CONFIG_CUSTODY_DENIED')
        raw = os.read(fd, 4097)
        after = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        if any(getattr(before, k) != getattr(after, k) for k in fields) or len(raw) != before.st_size:
            raise RpcError('RPC_CONFIG_CHANGED')
        return raw
    finally:
        if fd is not None:
            os.close(fd)
        os.close(dfd)


def _unique(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise RpcError('RPC_REPLY_INVALID')
        result[k] = v
    return result


def _params(method, params):
    if (type(method) is not str or method not in _HTTP_READS
            or type(params) is not list):
        raise RpcError('RPC_READ_SCOPE_DENIED')
    if method in ('getblockcount', 'getbestblockhash', 'getconnectioncount', 'getnetworkinfo', 'getblockchaininfo'):
        if params:
            raise RpcError('RPC_PARAMS_DENIED')
    elif method == 'getblockhash':
        if (len(params) != 1 or type(params[0]) is not int
                or not 0 <= params[0] <= 1_000_000):
            raise RpcError('RPC_PARAMS_DENIED')
    elif method == 'getblock':
        if (len(params) != 2 or type(params[0]) is not str
                or not _HASH.fullmatch(params[0])
                or type(params[1]) is not int or params[1] not in (2, 3)):
            raise RpcError('RPC_PARAMS_DENIED')
    else:
        raise RpcError('RPC_READ_SCOPE_DENIED')


def _result(method, value):
    if method in ('getblockhash', 'getbestblockhash'):
        valid = type(value) is str and _HASH.fullmatch(value)
    elif method == 'getblockcount':
        valid = type(value) is int and 0 <= value <= 1_000_000
    elif method == 'getconnectioncount':
        valid = type(value) is int and 0 <= value <= 1000
    elif method == 'getblock':
        valid = (type(value) is dict and type(value.get('hash')) is str
                 and _HASH.fullmatch(value['hash'])
                 and type(value.get('height')) is int
                 and 0 <= value['height'] <= 1_000_000
                 and type(value.get('tx')) is list)
    elif method == 'getnetworkinfo':
        valid = (type(value) is dict and type(value.get('version')) is int
                 and type(value.get('protocolversion')) is int
                 and type(value.get('subversion')) is str
                 and (value['version'], value['subversion'], value['protocolversion']) == SUPPORTED_RPC)
        if not valid:
            raise RpcError('RPC_VERSION_CAPABILITY_DENIED')
    elif method == 'getblockchaininfo':
        valid = (type(value) is dict and value.get('chain') == 'regtest'
                 and type(value.get('blocks')) is int
                 and 0 <= value['blocks'] <= 1_000_000)
    else:
        valid = False
    if not valid:
        raise RpcError('RPC_RESULT_OR_NETWORK_DENIED')
    return value


def _reply(raw, identifier, method):
    try:
        if type(raw) is not bytes or not 1 <= len(raw) <= (MAX_BLOCK_REPLY if method == 'getblock' else MAX_REPLY):
            raise ValueError
        data = json.loads(raw.decode('utf8'), object_pairs_hook=_unique,
                          parse_float=Decimal,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if (type(data) is not dict or set(data) != {'result', 'error', 'id'}
                or type(data['id']) is not int or data['id'] != identifier):
            raise ValueError
        if data['error'] is not None:
            error = data['error']
            if (data['result'] is None and type(error) is dict
                    and set(error) == {'code', 'message'}
                    and type(error['code']) is int and error['code'] == -28
                    and type(error['message']) is str and len(error['message']) <= 4096):
                raise RpcError('RPC_CORE_WARMUP')
            raise RpcError('RPC_CORE_READ_REFUSED')
        return _result(method, data['result'])
    except RpcError:
        raise
    except (ValueError, UnicodeError, TypeError, KeyError, RecursionError):
        raise RpcError('RPC_REPLY_INVALID') from None


class _BoundConnection(http.client.HTTPConnection):
    def __init__(self, port, timeout, binding):
        self._binding = binding
        super().__init__('127.0.0.1', port, timeout=timeout)
        increment('http_connection_create')

    def connect(self):
        try:
            self._binding._assert_image()
            super().connect()
            self._binding.assert_socket(self.sock)
            increment('http_socket_connect')
        except CoreBindingError as error:
            self.close()
            raise RpcError(error.args[0]) from None
        except Exception:
            self.close()
            raise RpcError('RPC_NATIVE_ENDPOINT_PROOF_DENIED') from None

    def request(self, *args, **kwargs):
        # Cheap process-identity recheck even on reused connections.
        try:
            self._binding._assert_image()
        except CoreBindingError as error:
            self.close()
            raise RpcError(error.args[0]) from None
        except Exception:
            self.close()
            raise RpcError('RPC_NATIVE_PROCESS_PROOF_DENIED') from None
        return super().request(*args, **kwargs)


class ManagedReadRpc:
    """Bounded, authenticated, loopback-only HTTP JSON-RPC for owned Core reads.

    No endpoint override, proxy, redirect, wallet selector or write method.
    """

    def __init__(self, core, directory, *, authorized_readonly=False, timeout=5, binding=None):
        if authorized_readonly is not True:
            raise RpcError('RPC_EXPLICIT_READ_CONSENT_REQUIRED')
        if type(timeout) not in (int, float) or not 0.1 <= timeout <= 30:
            raise RpcError('RPC_TIMEOUT_DENIED')
        if type(binding) is not OwnedCoreBinding or binding.core != core or binding.directory != directory:
            raise RpcError('RPC_MANAGED_PROCESS_REQUIRED')
        self._connection = None
        self._auth = None
        self._closed = False
        self._lock = threading.RLock()
        self._identifier = 0
        self._last_completed = None
        self._last_attest = None
        self._config_directory = directory
        self._credentials = None
        try:
            credentials = CredentialSource(directory)
            self._credentials = credentials
            self._auth = self._build_auth(credentials)
            # The bytes used for the header must still belong to the pinned
            # credential snapshot before any authenticated connection opens.
            credentials.attest()
            self._connection = _BoundConnection(credentials.port, timeout, binding)
            self._connection.set_debuglevel(0)
            self.attest()
        except RpcError:
            self.close()
            raise
        except CredentialError as error:
            self.close()
            code = error.args[0] if len(error.args) == 1 and type(error.args[0]) is str else None
            mapped = {
                'RPC_AUTHENTICATION_DENIED': 'RPC_AUTHENTICATION_DENIED',
                'RPC_CONFIG_CHANGED': 'RPC_CONFIG_CHANGED',
                'RPC_COOKIE_CHANGED': 'RPC_CONFIG_CHANGED',
                'RPC_CREDENTIAL_CUSTODY_DENIED': 'RPC_CONFIG_CUSTODY_DENIED',
                'RPC_CREDENTIAL_CHANGED': 'RPC_CONFIG_CHANGED',
                'RPC_COOKIE_FORMAT_DENIED': 'RPC_AUTHENTICATION_DENIED',
                'RPC_CONFIG_PROFILE_DENIED': 'RPC_CONFIG_CHANGED',
            }
            raise RpcError(mapped.get(code, 'RPC_MANAGED_OPEN_DENIED')) from None
        except Exception:
            self.close()
            raise RpcError('RPC_MANAGED_OPEN_DENIED') from None

    def __repr__(self):
        return '<ManagedReadRpc redacted>'

    def _build_auth(self, credentials):
        if credentials.mode == 'config':
            raw = _private_config(self._config_directory)
            values = dict(line.split('=', 1) for line in raw.decode('ascii').splitlines()[3:])
            return 'Basic ' + base64.b64encode(
                (values['rpcuser'] + ':' + values['rpcpassword']).encode('ascii')).decode('ascii')
        # Cookie mode: read the Core-generated cookie under regtest/.cookie.
        raw, _ = private_bytes(self._config_directory / 'regtest', '.cookie', 256, core_cookie=True)
        return 'Basic ' + base64.b64encode(raw.strip()).decode('ascii')

    def _assert_config(self):
        try:
            self._credentials.attest()
        except CredentialError as error:
            code = error.args[0] if len(error.args) == 1 and type(error.args[0]) is str else None
            if code in ('RPC_COOKIE_CHANGED', 'RPC_CONFIG_CHANGED',
                        'RPC_CREDENTIAL_CHANGED', 'RPC_CONFIG_PROFILE_DENIED'):
                raise RpcError('RPC_CONFIG_CHANGED') from None
            raise RpcError('RPC_AUTHENTICATION_DENIED') from None

    def _discard_idle_connection(self):
        if (self._last_completed is not None
                and time.monotonic() - self._last_completed >= MAX_IDLE_REUSE_SECONDS):
            self._connection.close()
            self._last_completed = None

    def _current_auth(self):
        # Never adopt a freshly rotated cookie between attestation and send.
        # Config and cookie headers are pinned at construction; drift revokes.
        return self._auth

    def _request_once(self, method, params):
        if self._closed:
            raise RpcError('RPC_SESSION_CLOSED')
        _params(method, params)
        self._identifier += 1
        identifier = self._identifier
        try:
            self._assert_config()
            self._discard_idle_connection()
            increment('http_request')
            body = json.dumps({'jsonrpc': '1.0', 'id': identifier, 'method': method, 'params': params},
                              separators=(',', ':')).encode('ascii')
            self._connection.request('POST', '/', body,
                                     {'Authorization': self._current_auth(),
                                      'Content-Type': 'application/json',
                                      'Connection': 'keep-alive'})
            response = self._connection.getresponse()
            raw = response.read((MAX_BLOCK_REPLY if method == 'getblock' else MAX_REPLY) + 1)
            # Do not return a reply obtained while credentials changed.
            self._assert_config()
            if response.status == 401:
                raise RpcError('RPC_AUTHENTICATION_DENIED')
            if response.status == 503:
                raise RpcError('RPC_NODE_BUSY')
            if response.status != 200 or response.getheader('Content-Type', '').split(';')[0].strip() != 'application/json':
                raise RpcError('RPC_HTTP_DENIED')
            result = _reply(raw, identifier, method)
            if method == 'getblock' and result['hash'] != params[0]:
                raise RpcError('RPC_BLOCK_HASH_DENIED')
            self._last_completed = time.monotonic()
            return result
        except RpcError as error:
            if error.args == ('RPC_NODE_BUSY',):
                self._connection.close()
            else:
                self.close()
            raise
        except Exception:
            self.close()
            raise RpcError('RPC_CONNECTION_UNCERTAIN_READ_FAILED') from None

    def _request(self, method, params):
        for attempt in range(3):
            try:
                return self._request_once(method, params)
            except RpcError as error:
                if error.args != ('RPC_NODE_BUSY',) or attempt == 2:
                    self.close()
                    raise
                time.sleep(random.SystemRandom().uniform(.05, .15) * (2 ** attempt))

    def attest(self):
        with self._lock:
            increment('rpc_attest')
            info = self._request('getblockchaininfo', [])
            if self._request('getblockhash', [0]) != REGTEST_GENESIS:
                self.close()
                raise RpcError('RPC_GENESIS_DENIED')
            self._request('getnetworkinfo', [])
            if self._request('getconnectioncount', []) != 0:
                self.close()
                raise RpcError('RPC_EXTERNAL_PEERS_DENIED')
            self._last_attest = time.monotonic()
            return info

    def call(self, method, params=None):
        args = [] if params is None else params
        _params(method, args)
        with self._lock:
            if self._closed:
                raise RpcError('RPC_SESSION_CLOSED')
            if (self._connection is None or self._last_attest is None
                    or time.monotonic() - self._last_attest >= MAX_TRUST_CACHE_SECONDS):
                self.attest()
            if method == 'getblockchaininfo':
                return self._request('getblockchaininfo', [])
            return self._request(method, args)

    def close(self):
        with self._lock:
            self._closed = True
            self._auth = None
            if self._connection is not None:
                self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
