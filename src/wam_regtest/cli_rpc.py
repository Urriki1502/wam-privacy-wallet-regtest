"""Bounded signed-CLI RPC boundary; no persistent HTTP transport or retries.

The existing coordinator owns write authorization. This layer only narrows its
finite disposable-REGTEST method/parameter surface and validates CLI output.
"""
import json
import re
import subprocess
import threading
import time


class CliRpcError(ValueError):
    pass


READS=frozenset(('getblockchaininfo','getblockcount','getbestblockhash',
    'getblockhash','getblock','getconnectioncount','getnetworkinfo',
    'getrawmempool','gettxout','listwallets','waitfornewblock'))
WRITES=frozenset(('testmempoolaccept','sendrawtransaction','generatetoaddress',
    'invalidateblock','reconsiderblock','createwallet','getnewaddress','stop'))
HASH=re.compile(r'[0-9a-f]{64}\Z')
LIMIT=8*1024*1024


def _uint(value,maximum):
    return bool(re.fullmatch(r'0|[1-9][0-9]{0,9}',value)) and int(value)<=maximum


def _raw(value):
    return 2<=len(value)<=800000 and len(value)%2==0 and bool(re.fullmatch('[0-9a-f]+',value))


def validate(args):
    if type(args) is not list or not args or any(type(v) is not str for v in args):
        raise CliRpcError('CORE_LOCAL_RPC_COMMAND_DENIED')
    wallet=args[0]=='-rpcwallet=test'
    if wallet:args=args[1:]
    if (not args or args[0] not in READS|WRITES or any(v.startswith('-') for v in args)
            or any('\x00' in v or '\r' in v or '\n' in v for v in args)):
        raise CliRpcError('CORE_LOCAL_RPC_METHOD_DENIED')
    method,*params=args
    valid=False
    if method in ('getblockchaininfo','getblockcount','getbestblockhash','getconnectioncount',
                  'getnetworkinfo','getrawmempool','listwallets','stop','getnewaddress'):
        valid=not params
    elif method=='createwallet':valid=params==['test']
    elif method in ('getblockhash','waitfornewblock'):
        valid=len(params)==1 and _uint(params[0],1000000 if method=='getblockhash' else 30000)
    elif method=='getblock':
        valid=len(params)==2 and bool(HASH.fullmatch(params[0])) and params[1] in ('2','3')
    elif method=='generatetoaddress':
        valid=(len(params)==2 and _uint(params[0],101) and int(params[0])>=1
               and 20<=len(params[1])<=120 and bool(re.fullmatch('wamrt1[023456789acdefghjklmnpqrstuvwxyz]+',params[1])))
    elif method in ('invalidateblock','reconsiderblock'):valid=len(params)==1 and bool(HASH.fullmatch(params[0]))
    elif method=='gettxout':
        valid=len(params)==3 and bool(HASH.fullmatch(params[0])) and _uint(params[1],2**32-1) and params[2]=='true'
    elif method=='sendrawtransaction':valid=len(params)==1 and _raw(params[0])
    elif method=='testmempoolaccept' and len(params)==1 and len(params[0])<=800010:
        try:
            txs=json.loads(params[0])
            valid=type(txs) is list and len(txs)==1 and type(txs[0]) is str and _raw(txs[0])
        except ValueError:pass
    if not valid or wallet!=(method=='getnewaddress'):
        raise CliRpcError('CORE_LOCAL_RPC_PARAMS_DENIED')
    return method,params


def _pairs(pairs):
    obj={}
    for key,value in pairs:
        if key in obj:raise ValueError
        obj[key]=value
    return obj


def decode(raw,method,params):
    """CLI prints bare hashes/addresses; never parse those as JSON numbers."""
    try:
        if type(raw) is not bytes or not 1<=len(raw)<=LIMIT:raise ValueError
        text=raw.decode('utf8').strip()
        if method in ('getblockhash','getbestblockhash','sendrawtransaction'):
            if not HASH.fullmatch(text):raise ValueError
            return text
        if method=='getnewaddress':
            if not 20<=len(text)<=120 or not re.fullmatch('wamrt1[023456789acdefghjklmnpqrstuvwxyz]+',text):raise ValueError
            return text
        if method=='stop':
            # The pinned signed v0.1.11 macOS binary returns WAM Coin stopping.
            # Keep the former literal for existing platform fixtures; never
            # accept arbitrary text, generic success or a prefix match.
            if text not in ('WAM Core stopping','WAM Coin stopping'):raise ValueError
            return text
        def nonfinite(_):raise ValueError
        value=json.loads(text,object_pairs_hook=_pairs,parse_constant=nonfinite)
        if method in ('getblockcount','getconnectioncount'):
            good=type(value) is int and 0<=value<=1000000
        elif method in ('getblockchaininfo','getnetworkinfo','createwallet','waitfornewblock'):
            good=type(value) is dict
        elif method=='gettxout':good=value is None or type(value) is dict
        elif method=='getblock':good=type(value) is dict and value.get('hash')==params[0] and type(value.get('tx')) is list
        elif method in ('getrawmempool','generatetoaddress'):
            good=type(value) is list and len(value)<=100000 and all(type(v) is str and HASH.fullmatch(v) for v in value)
            if method=='generatetoaddress':good=good and len(value)==int(params[0])
        elif method=='listwallets':good=type(value) is list and all(type(v) is str for v in value)
        elif method=='testmempoolaccept':
            good=type(value) is list and len(value)==1 and type(value[0]) is dict and type(value[0].get('allowed')) is bool
        else:good=value is None # invalidate/reconsider return CLI JSON null.
        if not good:raise ValueError
        return value
    except (ValueError,UnicodeError,TypeError,RecursionError):
        raise CliRpcError('CORE_RPC_REPLY_DENIED') from None


def execute(argv,method,params,*,directory,env,timeout,creationflags=0):
    if type(timeout) not in (int,float) or not .1<=timeout<=120:
        raise CliRpcError('CORE_RPC_TIMEOUT_SCOPE_DENIED')
    # Bound memory WHILE draining both pipes. Never capture unbounded output
    # then check its size, and never publish stderr/credentials/tracebacks.
    proc=None;threads=[];parts=[bytearray(),bytearray()];overflow=threading.Event()
    def drain(pipe,target,limit):
        try:
            while True:
                chunk=pipe.read1(65536)
                if not chunk:return
                if len(target)+len(chunk)>limit:
                    overflow.set();proc.kill();return
                target.extend(chunk)
        except OSError:overflow.set()
    try:
        deadline=time.monotonic()+timeout
        proc=subprocess.Popen(argv,cwd=directory,env=env,stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=creationflags)
        for pipe,target,limit in ((proc.stdout,parts[0],LIMIT),(proc.stderr,parts[1],4096)):
            thread=threading.Thread(target=drain,args=(pipe,target,limit),daemon=True)
            thread.start();threads.append(thread)
        proc.wait(timeout=max(.001,deadline-time.monotonic()))
        for thread in threads:thread.join(max(0,deadline-time.monotonic()))
        if any(t.is_alive() for t in threads):raise subprocess.TimeoutExpired('',timeout)
        if overflow.is_set():raise CliRpcError('CORE_RPC_REPLY_BOUNDS_DENIED')
        if proc.returncode:
            error=bytes(parts[1]).lower()
            if b'incorrect rpcuser or rpcpassword' in error or b'authorization failed' in error:
                raise CliRpcError('CORE_RPC_AUTHENTICATION_DENIED')
            if b'could not connect' in error:raise CliRpcError('CORE_RPC_UNAVAILABLE')
            if b'error code: -28' in error:raise CliRpcError('CORE_RPC_WARMUP')
            raise CliRpcError('CORE_RPC_DENIED')
        # For null-return RPCs wam-cli prints nothing; all other empty output
        # remains malformed, not a successful None fallback.
        raw=bytes(parts[0])
        if not raw.strip() and method in ('invalidateblock','reconsiderblock'):raw=b'null'
        return decode(raw,method,params)
    except subprocess.TimeoutExpired:raise CliRpcError('CORE_RPC_TIMEOUT_UNCERTAIN') from None
    except OSError:raise CliRpcError('CORE_RPC_PROCESS_DENIED') from None
    finally:
        if proc is not None:
            if proc.poll() is None:proc.kill()
            proc.wait()
            for thread in threads:thread.join(1)
            for pipe in (proc.stdout,proc.stderr):
                if pipe is not None:pipe.close()
