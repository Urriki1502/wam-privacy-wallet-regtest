"""Managed, authenticated loopback REGTEST reads; no CLI per request.

Typed owned scanner reads with no attach/cookie/write/lifecycle authority.
Operational snapshots borrow this owned capability; hardened loader qualification
and explicit external-Core attachment remain open.
"""
import base64
from hashlib import sha256
from decimal import Decimal
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
from .network_policy import parse_local_config
from .wsp_live import REGTEST_GENESIS

MAX_REPLY=1024*1024
MAX_BLOCK_REPLY=32*1024*1024
# Measured on genuine independently pinned v0.1.11, not inferred from Bitcoin.
# Signed newer binaries require a separate compatibility qualification.
SUPPORTED_RPC=(111, '/WAM:0.1.11/', 70016)


class RpcError(ValueError):
    pass


def _private_config(directory):
    if sys.platform=='win32':
        from .windows_core_transport import read_private
        return read_private(directory,'wam.conf')
    if sys.platform=='darwin':
        from .private_directory import open_macos_private_directory as open_dir, _require_absent_acl as no_acl
    elif sys.platform=='linux':
        from .linux_private_storage import open_linux_private_directory as open_dir, _no_acl as no_acl
    else:raise RpcError('RPC_NATIVE_CUSTODY_REQUIRED')
    dfd=open_dir(directory);fd=None
    try:
        fd=os.open('wam.conf',os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,dir_fd=dfd)
        before=os.fstat(fd);no_acl(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid!=os.geteuid()
                or stat.S_IMODE(before.st_mode)!=0o600 or before.st_nlink!=1 or not 1<=before.st_size<=4096):
            raise RpcError('RPC_CONFIG_CUSTODY_DENIED')
        raw=os.read(fd,4097);after=os.fstat(fd)
        if any(getattr(before,k)!=getattr(after,k) for k in ('st_dev','st_ino','st_mode','st_uid','st_nlink','st_size','st_mtime_ns','st_ctime_ns')) or len(raw)!=before.st_size:
            raise RpcError('RPC_CONFIG_CHANGED')
        return raw
    finally:
        if fd is not None:os.close(fd)
        os.close(dfd)


def _unique(pairs):
    result={}
    for k,v in pairs:
        if k in result:raise RpcError('RPC_REPLY_INVALID')
        result[k]=v
    return result


def _params(method,params):
    if type(method) is not str or method not in ('getblockchaininfo','getblockcount','getblockhash','getnetworkinfo','getbestblockhash','getblock','getconnectioncount') or type(params) is not list:
        raise RpcError('RPC_READ_SCOPE_DENIED')
    if method=='getblockhash':
        if len(params)!=1 or type(params[0]) is not int or not 0<=params[0]<=1_000_000:
            raise RpcError('RPC_PARAMS_DENIED')
    elif method=='getblock':
        if (len(params)!=2 or type(params[0]) is not str or not re.fullmatch('[0-9a-f]{64}',params[0])
                or type(params[1]) is not int or params[1]!=3):raise RpcError('RPC_PARAMS_DENIED')
    elif params:raise RpcError('RPC_PARAMS_DENIED')


def _result(method,value):
    if method in ('getblockhash','getbestblockhash'):valid=type(value) is str and re.fullmatch('[0-9a-f]{64}',value)
    elif method=='getblockcount':valid=type(value) is int and 0<=value<=1_000_000
    elif method=='getconnectioncount':valid=type(value) is int and 0<=value<=1000
    elif method=='getblock':
        valid=(type(value) is dict and type(value.get('hash')) is str and re.fullmatch('[0-9a-f]{64}',value['hash'])
               and type(value.get('height')) is int and 0<=value['height']<=1_000_000
               and type(value.get('tx')) is list and 1<=len(value['tx'])<=100_000)
    elif method=='getnetworkinfo':
        valid=(type(value) is dict and type(value.get('version')) is int
               and type(value.get('protocolversion')) is int and type(value.get('subversion')) is str
               and (value['version'],value['subversion'],value['protocolversion'])==SUPPORTED_RPC)
        if not valid:raise RpcError('RPC_VERSION_CAPABILITY_DENIED')
    else:valid=(type(value) is dict and value.get('chain')=='regtest' and type(value.get('blocks')) is int and 0<=value['blocks']<=1_000_000)
    if not valid:raise RpcError('RPC_RESULT_OR_NETWORK_DENIED')
    return value


def _reply(raw,identifier,method):
    try:
        if type(raw) is not bytes or not 1<=len(raw)<=(MAX_BLOCK_REPLY if method=='getblock' else MAX_REPLY):raise ValueError
        data=json.loads(raw.decode('utf8'),object_pairs_hook=_unique,parse_float=Decimal,
                        parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if (type(data) is not dict or set(data)!={'result','error','id'}
                or type(data['id']) is not int or data['id']!=identifier):raise ValueError
        if data['error'] is not None:raise RpcError('RPC_CORE_READ_REFUSED')
        return _result(method,data['result'])
    except RpcError:raise
    except (ValueError,UnicodeError,TypeError,KeyError,RecursionError):
        raise RpcError('RPC_REPLY_INVALID') from None


class _BoundConnection(http.client.HTTPConnection):
    def __init__(self,port,timeout,binding):
        self._binding=binding
        super().__init__('127.0.0.1',port,timeout=timeout)

    def request(self, *args, **kwargs):
        # Recheck live owned process and cheap file identity even on a reused
        # connection. Full binary hashes are checked only at binding creation.
        try:
            self._binding._assert_image()
        except CoreBindingError as error:
            self.close();raise RpcError(error.args[0]) from None
        except Exception:
            self.close();raise RpcError('RPC_NATIVE_PROCESS_PROOF_DENIED') from None
        return super().request(*args, **kwargs)

    def connect(self):
        # HTTPConnection invokes this BEFORE sending buffered headers, including
        # Basic auth. Each new TCP connection requires fresh kernel ownership.
        try:
            self._binding._assert_image()
            super().connect()
            self._binding.assert_socket(self.sock)
        except CoreBindingError as error:
            self.close();raise RpcError(error.args[0]) from None
        except Exception:
            self.close();raise RpcError('RPC_NATIVE_ENDPOINT_PROOF_DENIED') from None


class ManagedReadRpc:
    """No endpoint override, proxy, redirect, wallet selector or write method."""
    def __init__(self,core,directory,*,authorized_readonly=False,timeout=5,binding=None):
        if authorized_readonly is not True:raise RpcError('RPC_EXPLICIT_READ_CONSENT_REQUIRED')
        if type(timeout) not in (int,float) or not 0.1<=timeout<=30:raise RpcError('RPC_TIMEOUT_DENIED')
        if type(binding) is not OwnedCoreBinding or binding.core!=core or binding.directory!=directory:
            raise RpcError('RPC_MANAGED_PROCESS_REQUIRED')
        self._connection=None;self._auth=None;self._closed=False;self._lock=threading.RLock();self._identifier=0
        try:
            raw=_private_config(directory);port=parse_local_config(raw)
            self._config_directory=directory;self._config_digest=sha256(raw).digest()
            values=dict(line.split('=',1) for line in raw.decode('ascii').splitlines()[3:])
            self._auth='Basic '+base64.b64encode((values['rpcuser']+':'+values['rpcpassword']).encode('ascii')).decode('ascii')
            self._connection=_BoundConnection(port,timeout,binding)
            self._connection.set_debuglevel(0)
            self.attest()
        except RpcError:
            self.close();raise
        except Exception:
            self.close();raise RpcError('RPC_MANAGED_OPEN_DENIED') from None

    def __repr__(self):return '<ManagedReadRpc redacted>'

    def receipt_for(self,core,directory):
        with self._lock:
            if self._closed:raise RpcError('RPC_SESSION_CLOSED')
            binding=self._connection._binding
            if binding.core!=core or binding.directory!=directory:raise RpcError('RPC_SESSION_SCOPE_DENIED')
            self._assert_config()
            try:binding._assert_image()
            except Exception:
                self.close();raise RpcError('RPC_MANAGED_PROCESS_CHANGED') from None
            return dict(binding.receipt)

    def _assert_config(self):
        # Preserve the original per-operation native custody/config gate.
        # Hash only this bounded 4KiB private config, never the Core binaries.
        # No credentials or port are adopted from a changed configuration.
        if sha256(_private_config(self._config_directory)).digest()!=self._config_digest:
            raise RpcError('RPC_CONFIG_CHANGED')

    def _request(self,method,params):
        _params(method,params)  # All write methods denied before retry logic.
        for attempt in range(3):
            try:return self._request_once(method,params)
            except RpcError as error:
                if error.args!=('RPC_NODE_BUSY',) or attempt==2:raise
                # Only a positively rejected idempotent read is replayed.
                # Connection/auth uncertainty and all writes are never retried.
                time.sleep(random.SystemRandom().uniform(.05,.15)*(2**attempt))

    def _request_once(self,method,params):
        if self._closed:raise RpcError('RPC_SESSION_CLOSED')
        _params(method,params)
        # Deny before sending any HTTP bytes. A subsequent explicit read may
        # proceed only if the EXACT protected original config is restored;
        # this never retries an operation or changes the running node config.
        self._assert_config()
        self._identifier+=1
        try:
            body=json.dumps({'jsonrpc':'1.0','id':self._identifier,'method':method,'params':params},separators=(',',':')).encode('ascii')
            self._connection.request('POST','/',body,{'Authorization':self._auth,'Content-Type':'application/json','Connection':'keep-alive'})
            response=self._connection.getresponse()
            raw=response.read((MAX_BLOCK_REPLY if method=='getblock' else MAX_REPLY)+1)
            if response.status==401:raise RpcError('RPC_AUTHENTICATION_DENIED')
            if response.status==503:raise RpcError('RPC_NODE_BUSY')
            if response.status!=200 or response.getheader('Content-Type','').split(';')[0].strip()!='application/json':
                raise RpcError('RPC_HTTP_DENIED')
            result=_reply(raw,self._identifier,method)
            if method=='getblock' and result['hash']!=params[0]:raise RpcError('RPC_BLOCK_HASH_DENIED')
            return result
        except RpcError as error:
            if error.args==('RPC_NODE_BUSY',):
                # Core may close the rejected connection. New TCP connections
                # still require the native process/socket proof before auth.
                self._connection.close()
            else:self.close()
            raise
        except (OSError,http.client.HTTPException,ValueError):
            self.close();raise RpcError('RPC_CONNECTION_UNCERTAIN_READ_FAILED') from None

    def attest(self):
        with self._lock:
            info=self._request('getblockchaininfo',[])
            if self._request('getblockhash',[0])!=REGTEST_GENESIS:
                self.close();raise RpcError('RPC_GENESIS_DENIED')
            self._request('getnetworkinfo',[])
            if self._request('getconnectioncount',[])!=0:
                self.close();raise RpcError('RPC_EXTERNAL_PEERS_DENIED')
            return info

    def call(self,method,params=None):
        args=[] if params is None else params
        _params(method,args)  # Refuse writes/unknown params before any socket activity.
        with self._lock:
            info=self.attest()  # Reattest chain/genesis, not files or subprocesses.
            return info if method=='getblockchaininfo' else self._request(method,args)

    def close(self):
        # Serialize teardown with reads; concurrent close must not erase the
        # authentication header halfway through a request. RLock permits a
        # fail-closed request/attest path to quarantine its own connection.
        with self._lock:
            self._closed=True;self._auth=None
            if self._connection is not None:self._connection.close()

    def __enter__(self):return self
    def __exit__(self,*_):self.close()
