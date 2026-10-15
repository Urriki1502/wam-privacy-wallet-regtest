"""Genuine source-built Linux Core REGTEST lifecycle; no wallet E2E claim."""
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import time
from .linux_developer_core import verify,LinuxCoreError
from .core import _port,_write_private_config
from .network_policy import parse_local_config

GENESIS = 'b88f3d262f285e38e184f50bf3eea1c8e615486ae67d3d9eaf0976fbd6d3d30d'


def smoke(directory, manifest_sha256, *, authorized=False):
    node,cli,receipt=verify(directory,manifest_sha256,authorized=authorized)
    with tempfile.TemporaryDirectory(prefix='wam-linux-regtest-') as temporary:
        root=Path(temporary).resolve(strict=True);root.chmod(0o700)
        rpc,p2p=_port(),_port()
        while p2p==rpc:p2p=_port()
        _write_private_config(root,rpc,p2p)
        environment={'PATH':'/usr/bin:/bin','HOME':str(root),'LC_ALL':'C'}
        def call(*arguments,timeout=15):
            fd=os.open(root/'wam.conf',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
            try:
                info=os.fstat(fd)
                if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_uid!=os.geteuid()
                        or stat.S_IMODE(info.st_mode)!=0o600 or not 1<=info.st_size<=4096):
                    raise LinuxCoreError('LINUX_RPC_CONFIG_CUSTODY_DENIED')
                if parse_local_config(os.read(fd,4097))!=rpc:
                    raise LinuxCoreError('LINUX_RPC_LOCAL_PROFILE_DENIED')
            finally:os.close(fd)
            result=subprocess.run([str(cli),'-datadir='+str(root),'-regtest',
                '-rpcconnect=127.0.0.1','-rpcport='+str(rpc),*arguments],
                env=environment,capture_output=True,text=True,timeout=timeout)
            if result.returncode or len(result.stdout)>2*1024*1024:
                raise LinuxCoreError('LINUX_ACTUAL_RPC_DENIED')
            value=result.stdout.strip()
            try:return json.loads(value) if value else None
            except json.JSONDecodeError:return value
        with (root/'node-output.log').open('xb') as log:
            process=subprocess.Popen([str(node),'-datadir='+str(root),'-regtest',
                '-daemon=0','-printtoconsole=1'],env=environment,stdin=subprocess.DEVNULL,
                stdout=log,stderr=subprocess.STDOUT)
            try:
                deadline=time.monotonic()+120
                while True:
                    if process.poll() is not None:
                        raise LinuxCoreError('LINUX_CORE_EARLY_EXIT_DENIED')
                    try:info=call('getblockchaininfo');break
                    except (LinuxCoreError,subprocess.TimeoutExpired):
                        if time.monotonic()>=deadline:raise LinuxCoreError('LINUX_CORE_START_TIMEOUT') from None
                        time.sleep(.3)
                if info['chain']!='regtest' or call('getblockhash','0')!=GENESIS or call('getconnectioncount')!=0:
                    raise LinuxCoreError('LINUX_ACTUAL_REGTEST_IDENTITY_DENIED')
                call('createwallet','disposable')
                address=call('-rpcwallet=disposable','getnewaddress')
                hashes=call('generatetoaddress','101',address,timeout=120)
                if len(hashes)!=101 or call('getblockcount')!=101 or call('getconnectioncount')!=0:
                    raise LinuxCoreError('LINUX_ACTUAL_BLOCK_GENERATION_DENIED')
                report={'status':'REAL_LINUX_DEVELOPER_CORE_REGTEST_101_BLOCKS_PASS',
                    'source_manifest_sha256':manifest_sha256,'sources':receipt['sources'],
                    'core_sha256':{name:record['sha256'] for name,record in receipt['files'].items()},
                    'real_core_rpc':True,'synthetic_rpc':False,'chain':'regtest',
                    'height':101,'genesis':GENESIS,'zero_peers':True,
                    'official_signed_release':False,'mainnet_allowed':False,
                    'wallet_e2e_qualified':False}
            finally:
                if process.poll() is None:
                    try:call('stop')
                    except (ValueError,OSError,subprocess.SubprocessError):pass
                    try:process.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        process.terminate()
                        try:process.wait(timeout=10)
                        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=10)
                if process.poll() is None:raise LinuxCoreError('LINUX_OWNED_PROCESS_CLEANUP_DENIED')
        report['owned_process_stopped']=True
    report['temporary_datadir_removed']=not root.exists()
    return report


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--core-dir',type=Path,required=True)
    parser.add_argument('--manifest-sha256',required=True)
    parser.add_argument('--confirm-experimental-developer-regtest',action='store_true')
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    try:
        result=smoke(args.core_dir.absolute(),args.manifest_sha256,
            authorized=args.confirm_experimental_developer_regtest)
        with args.report.open('x') as output:json.dump(result,output,indent=2);output.write('\n')
        print(result['status'])
        return 0
    except Exception as error:
        # Never expose raw daemon, config, RPC errors or private paths.
        print(str(error) if type(error) is LinuxCoreError else 'LINUX_CORE_ACCEPTANCE_DENIED')
        return 2


if __name__=='__main__':raise SystemExit(main())
