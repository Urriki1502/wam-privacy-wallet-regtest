"""Native official-byte/loader/RPC observation. Fresh isolated REGTEST only."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from wam_regtest.official_core_v013 import stage_tar, MEMBERS, SOURCE, VERSION
from wam_regtest.core import _port, _write_private_config


def main():
    p=argparse.ArgumentParser();p.add_argument('--destination',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    host={'Linux':'linux-x86_64','Darwin':'macos-arm64'}.get(platform.system())
    assert host and platform.machine() in ('x86_64','arm64')
    d=a.destination.absolute();r=stage_tar(host,d)
    out={'schema':'wam-official-v013-native-intake/v1','source_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
         'upstream_source':SOURCE,'platform':host,'release':r,'native_versions':{},'files':{},'synthetic_rpc':False,'mainnet_allowed':False}
    for name in MEMBERS[host]:
        if host=='linux-x86_64':
            from wam_regtest.linux_developer_core import inspect_elf,library_identity,_system_file
            elf=inspect_elf((d/name).read_bytes())
            out['files'][name]={'sha256':sha256((d/name).read_bytes()).hexdigest(),'elf':elf,'loader':_system_file(elf['interpreter']),'libraries':library_identity(d/name)}
        out['native_versions'][name]=subprocess.check_output([str(d/name),'-version'],text=True,timeout=15).splitlines()[0]
        assert 'v0.1.13' in out['native_versions'][name]
    with tempfile.TemporaryDirectory(prefix='wam-v013-native-regtest-') as t:
        root=Path(t).resolve();root.chmod(0o700);rpc,p2p=_port(),_port()
        while p2p==rpc:p2p=_port()
        _write_private_config(root,rpc,p2p)
        env={'PATH':'/usr/bin:/bin','HOME':str(root),'LC_ALL':'C'}
        def call(*args):
            res=subprocess.run([str(d/'wam-cli'),'-regtest','-datadir='+str(root),'-rpcconnect=127.0.0.1','-rpcport='+str(rpc),*args],capture_output=True,text=True,env=env,timeout=120)
            if res.returncode:raise ValueError('V013_RPC_NOT_READY')
            try:return json.loads(res.stdout)
            except json.JSONDecodeError:return res.stdout.strip()
        with (root/'node.log').open('xb') as log:
            owner=subprocess.Popen([str(d/'wamd'),'-regtest','-datadir='+str(root),'-daemon=0'],stdout=log,stderr=log,stdin=subprocess.DEVNULL,env=env)
            try:
                deadline=time.monotonic()+90
                while True:
                    assert owner.poll() is None,'V013_CORE_EARLY_EXIT'
                    try:chain=call('getblockchaininfo');break
                    except ValueError:
                        if time.monotonic()>deadline:raise
                        time.sleep(.25)
                genesis=call('getblockhash','0');assert chain['chain']=='regtest' and genesis=='b88f3d262f285e38e184f50bf3eea1c8e615486ae67d3d9eaf0976fbd6d3d30d'
                info=call('getnetworkinfo');out['networkinfo']={k:info[k] for k in ('version','subversion','protocolversion','connections')}
                assert info['connections']==0
                call('createwallet','disposable-v013');addr=call('-rpcwallet=disposable-v013','getnewaddress')
                assert len(call('generatetoaddress','101',addr))==101
                out.update(genesis=genesis,height=call('getblockcount'),zero_peers=call('getconnectioncount')==0,status='NATIVE_OFFICIAL_CORE_INTAKE_101_BLOCKS_PASS')
            finally:
                if owner.poll() is None:
                    try:call('stop')
                    except ValueError:pass
                    try:owner.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        owner.terminate();owner.wait(timeout=20)
                out['original_popen_stopped']=owner.poll() is not None
    with a.report.open('x') as f:json.dump(out,f,indent=2,sort_keys=True);f.write('\n')
    print(out['status']);print(json.dumps(out['networkinfo']))
if __name__=='__main__':main()
