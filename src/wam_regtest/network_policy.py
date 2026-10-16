"""Strict local REGTEST profile, adapted from reviewed WAM network policy.

No networking or anonymity implementation. Local scan/broadcast intentionally
share one private node; all remote routes, proxies, includes and fallback deny.
"""
import os
from pathlib import Path
import re
import stat
from .private_directory import open_macos_private_directory


class NetworkPolicyError(ValueError):
    pass


_FIXED = {'port':None,'rpcport':None,'rpcuser':None,'rpcpassword':None,
    'rpcbind':'127.0.0.1','rpcallowip':'127.0.0.1','listen':'0','connect':'0',
    'dnsseed':'0','discover':'0','upnp':'0','txindex':'1','blockfilterindex':'1',
    'coinstatsindex':'1','fallbackfee':'0.0001'}


def local_rpc_port(datadir):
    """Read bounded private config; return only the local port, never secrets."""
    import sys
    if sys.platform=="win32":
        from .windows_core_transport import local_rpc_port as windows_port
        return windows_port(datadir)
    fd=dfd=None
    try:
        if sys.platform=='linux':
            from .linux_private_storage import open_linux_private_directory
            dfd=open_linux_private_directory(datadir)
        else:dfd=open_macos_private_directory(datadir)
        fd=os.open('wam.conf',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,dir_fd=dfd)
        info=os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid()
                or stat.S_IMODE(info.st_mode)!=0o600 or info.st_nlink!=1
                or not 1<=info.st_size<=4096):
            raise NetworkPolicyError('LOCAL_RPC_CONFIG_CUSTODY_DENIED')
        raw=os.read(fd,4097)
        after=os.fstat(fd)
        if any(getattr(info,k)!=getattr(after,k) for k in
               ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink')):
            raise NetworkPolicyError('LOCAL_RPC_CONFIG_CHANGED')
        return parse_local_config(raw)
    except NetworkPolicyError:
        raise
    except (OSError,ValueError,UnicodeError):
        raise NetworkPolicyError('LOCAL_RPC_CONFIG_DENIED') from None
    finally:
        if fd is not None: os.close(fd)
        if dfd is not None: os.close(dfd)



def parse_local_config(raw):
    try:
        lines=raw.decode('ascii').splitlines()
        if lines[:3]!=['regtest=1','server=1','[regtest]']:
            raise NetworkPolicyError('LOCAL_RPC_SCOPE_DENIED')
        config={}
        for line in lines[3:]:
            key,value=line.split('=',1)
            if key in config or key not in _FIXED:
                raise NetworkPolicyError('LOCAL_RPC_OPTION_DENIED')
            config[key]=value
        if set(config)!=set(_FIXED) or any(config[k]!=v for k,v in _FIXED.items() if v is not None):
            raise NetworkPolicyError('LOCAL_RPC_PROFILE_DENIED')
        ports=[]
        for key in ('port','rpcport'):
            value=config[key]
            if not re.fullmatch(r'[1-9][0-9]{0,4}',value) or not 1<=int(value)<=65535:
                raise NetworkPolicyError('LOCAL_RPC_PORT_DENIED')
            ports.append(int(value))
        if ports[0]==ports[1] or not re.fullmatch(r'disposable_[0-9a-f]{16}',config['rpcuser']) or not re.fullmatch(r'[0-9a-f]{64}',config['rpcpassword']):
            raise NetworkPolicyError('LOCAL_RPC_AUTH_PROFILE_DENIED')
        return ports[1]
    except NetworkPolicyError:
        raise
    except (ValueError,UnicodeError,TypeError):
        raise NetworkPolicyError('LOCAL_RPC_CONFIG_DENIED') from None


def diagnostics(rpc):
    rpc.attest()
    from .json_rpc import ManagedReadRpc
    info=rpc.call('getnetworkinfo',[]) if type(rpc) is ManagedReadRpc else rpc._call('getnetworkinfo',[])
    if (type(info) is not dict or type(info.get('connections')) is not int or info.get('connections')!=0
            or type(info.get('networks')) is not list
            or any(type(n) is not dict or n.get('proxy')!='' for n in info['networks'])):
        raise NetworkPolicyError('LOCAL_NODE_NETWORK_DIAGNOSTICS_DENIED')
    return {'status':'LOCAL_REGTEST_NETWORK_POLICY_PASS','chain':'regtest',
        'scan_route':'local','broadcast_route':'local','zero_peers':True,
        'role_separation':'shared_private_local_node','remote_routes_allowed':False,
        'proxy_routes_qualified':False,'clearnet_fallback_allowed':False,
        'anonymity_qualified':False,'synthetic_rpc':False}
