"""In-process owned WalletSession START→RESTORE on signed macOS REGTEST Core.

GUI-equivalent path: CoreSupervisor.start, WalletSession.open_owned(create),
snapshot, lock (Core stays up), shutdown, reopen owner, open_owned restore.
No fixture funding. Never adopts a PID or shuts Core from wallet lock.
"""
import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess
import sys

from wam_regtest.core import verified_core_paths
from wam_regtest.core_supervisor import CoreSupervisor
from wam_regtest.custody import create_directory
from wam_regtest.wallet_session import WalletSession
from wam_regtest.wsp_live import PINNED_WSP_COMMIT,_pinned_source


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--core-dir',required=True,type=Path)
    parser.add_argument('--wsp-source',required=True,type=Path)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--receipt',required=True,type=Path)
    parser.add_argument('--confirm-disposable-regtest',action='store_true')
    a=parser.parse_args()
    source=Path(__file__).resolve().parents[1]
    if (not a.confirm_disposable_regtest or platform.system()!='Darwin'
            or platform.machine()!='arm64' or a.root.exists() or a.root.is_symlink()
            or a.receipt.exists()
            or subprocess.check_output(['git','status','--porcelain'],cwd=source)):
        raise SystemExit('Q05_OWNED_SESSION_PROBE_SCOPE_DENIED')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
    node,cli,intake=verified_core_paths(a.core_dir);_pinned_source(a.wsp_source)
    record={'schema':'q05-owned-session-native/v1','status':'FAIL',
        'source_sha':head,'checkout_sha':head,'platform':'macos-arm64','frozen':False,
        'core_trust':'official-signed-v0.1.11','core_sha256':{
            p.name:sha256(p.read_bytes()).hexdigest() for p in (node,cli)},
        'wsp_source_commit':PINNED_WSP_COMMIT,'synthetic_rpc':False,
        'fixture_funding':False,'mainnet_allowed':False,'observations':[]}
    owner=session=None;stage='KEYCHAIN'
    try:
        create_directory(a.root)
        owner=CoreSupervisor(a.root,a.core_dir,authorized=True)
        owner.start(timeout=30)
        keychain=a.root/'q05-disposable.keychain-db'
        result=subprocess.run(['/usr/bin/security','create-keychain','-p',
            'public-test-only',str(keychain)],capture_output=True,timeout=15)
        if result.returncode:raise ValueError('Q05_DISPOSABLE_KEYCHAIN_DENIED')
        password=b'public-disposable-q05-native-only'
        stage='CREATE_OWNED_SESSION'
        session=WalletSession.open_owned(owner,a.wsp_source,password,authorized=True,
                                         create=True,keychain=keychain)
        snap=session.snapshot()
        if (snap.chain!='regtest' or snap.mainnet_allowed or not snap.signer_allowed
                or type(snap.receive_count) is not int or snap.receive_count!=0
                or snap.history_count!=0):raise ValueError('Q05_EMPTY_OWNED_SNAPSHOT_DENIED')
        code=snap.receive_code;digest=snap.core_sha256
        record['observations'].append({'created_empty_owned_session':True,
            'height':snap.height,'history_count':0,'receive_count':0})
        stage='LOCK_WITHOUT_CORE_SHUTDOWN'
        pid=owner.process.pid
        session.lock();session=None
        if owner.process is None or owner.process.poll() is not None or owner.process.pid!=pid:
            raise ValueError('Q05_WALLET_LOCK_STOPPED_CORE')
        record['observations'].append({'wallet_lock_left_core_running':True,'core_pid':pid})
        stage='CORE_REOPEN'
        owner.shutdown();owner.close()
        owner=CoreSupervisor(a.root,a.core_dir,authorized=True);owner.start(timeout=30)
        stage='RESTORE_OWNED_SESSION'
        session=WalletSession.open_owned(owner,a.wsp_source,password,authorized=True,
                                         create=False,keychain=keychain)
        restored=session.snapshot()
        if (restored.receive_code!=code or restored.core_sha256!=digest
                or restored.history_count!=0 or restored.receive_count!=0):
            raise ValueError('Q05_OWNED_RESTORE_CONTINUITY_DENIED')
        session.lock();session=None
        owner.shutdown();owner.close();owner=None
        record['observations'].append({'restored_same_payment_code':True})
        record['status']='PASS'
    except Exception as error:
        record['failure_stage']=stage;record['failure_type']=type(error).__name__
        if session is not None:
            try:session.lock()
            except (OSError,ValueError,RuntimeError):record['wallet_lock_blocked']=True
        if owner is not None and owner.process is not None and owner.process.poll() is None:
            try:owner.recover_stop()
            except (OSError,ValueError,RuntimeError):record['owned_release_blocked']=True
    finally:
        if owner is not None:
            try:owner.close()
            except (OSError,ValueError,RuntimeError):record['owner_close_blocked']=True
        record['timestamp_utc']=datetime.now(timezone.utc).isoformat()
        with a.receipt.open('x') as out:json.dump(record,out,indent=2);out.write('\n')
    print(json.dumps({'status':record['status'],'source_sha':head,
                      'observations':len(record['observations'])}))
    if record['status']!='PASS':raise SystemExit(2)


if __name__=='__main__':
    raise SystemExit(main())
