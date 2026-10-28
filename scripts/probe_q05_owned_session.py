"""In-process owned WalletSession START→RESTORE on signed macOS REGTEST Core.

GUI-equivalent path: CoreSupervisor.start, WalletSession.open_owned(create),
snapshot, lock (Core stays up), shutdown, reopen owner, open_owned restore.
Optional public-fixture funding is probe-only. Never adopts a PID or shuts
Core from wallet lock. Interpreter exit always stops a live original child.
"""
import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

from wam_regtest.core import verified_core_paths
from wam_regtest.core_supervisor import CoreSupervisor,ManagedCoreError
from wam_regtest.custody import create_directory
from wam_regtest.rpc_scope import identity
from wam_regtest.wallet_session import WalletSession
from wam_regtest.wsp_live import PINNED_WSP_COMMIT,_pinned_source


def _assert_live_original(owner):
    process=owner.process
    scope=identity(owner.directory)
    if (type(process) is not subprocess.Popen or process.poll() is not None
            or owner.binding is None or owner.binding.process is not process
            or owner._faulted or not owner._registered
            or scope is None or scope.binding.process is not process):
        raise ValueError('Q05_ORIGINAL_POPEN_DENIED')
    status=owner.status()
    if not status.get('core_process_owned') or status.get('state') not in ('ready','syncing'):
        raise ValueError('Q05_OWNED_CORE_NOT_READY')
    return process.pid


def _stop_owned(owner):
    if owner is None:
        return
    if owner.process is not None and owner.process.poll() is None:
        try:
            owner.shutdown()
        except (ManagedCoreError,OSError,ValueError,RuntimeError):
            try:
                owner.recover_stop()
            except (ManagedCoreError,OSError,ValueError,RuntimeError):
                pass
    try:
        owner.close()
    except (ManagedCoreError,OSError,ValueError,RuntimeError):
        pass


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--core-dir',required=True,type=Path)
    parser.add_argument('--wsp-source',required=True,type=Path)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--receipt',required=True,type=Path)
    parser.add_argument('--confirm-disposable-regtest',action='store_true')
    parser.add_argument('--fund-disposable-wallet',action='store_true')
    a=parser.parse_args()
    source=Path(__file__).resolve().parents[1]
    dirty=subprocess.check_output(
        ['git','status','--porcelain','--untracked-files=no'],cwd=source)
    if (not a.confirm_disposable_regtest or platform.system()!='Darwin'
            or platform.machine()!='arm64' or a.root.exists() or a.root.is_symlink()
            or a.receipt.exists() or dirty):
        raise SystemExit('Q05_OWNED_SESSION_PROBE_SCOPE_DENIED')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
    expected=os.environ.get('GITHUB_SHA')
    if expected and expected!=head:
        raise SystemExit('Q05_OWNED_SESSION_SOURCE_SHA_DENIED')
    node,cli,intake=verified_core_paths(a.core_dir.expanduser().resolve());_pinned_source(a.wsp_source)
    record={'schema':'q05-owned-session-native/v1','status':'FAIL',
        'source_sha':head,'checkout_sha':head,'platform':'macos-arm64','frozen':False,
        'core_trust':'official-signed-v0.1.11','core_version':'v0.1.11',
        'core_intake_platform':intake.get('platform'),
        'core_sha256':{p.name:sha256(p.read_bytes()).hexdigest() for p in (node,cli)},
        'wsp_source_commit':PINNED_WSP_COMMIT,'synthetic_rpc':False,
        'fixture_funding':bool(a.fund_disposable_wallet),'mainnet_allowed':False,
        'automatic_wallet_transaction_replay':False,'pid_adoption':False,
        'observations':[]}
    owner=session=None;stage='KEYCHAIN'
    try:
        create_directory(a.root)
        owner=CoreSupervisor(a.root,a.core_dir.expanduser().resolve(),authorized=True)
        owner.start(timeout=90)
        pid=_assert_live_original(owner)
        if owner.process.pid!=pid or type(owner.process.pid) is not int:
            raise ValueError('Q05_ORIGINAL_POPEN_DENIED')
        record['observations'].append({'original_popen_owned':True,'core_pid':pid,
            'wamd_sha256':intake.get('wamd_sha256')})
        keychain=a.root/'q05-disposable.keychain-db'
        result=subprocess.run(['/usr/bin/security','create-keychain','-p',
            'public-test-only',str(keychain)],capture_output=True,timeout=15)
        if result.returncode:raise ValueError('Q05_DISPOSABLE_KEYCHAIN_DENIED')
        password=b'public-disposable-q05-native-only'
        stage='CREATE_OWNED_SESSION'
        session=WalletSession.open_owned(owner,a.wsp_source,password,authorized=True,
                                         create=True,keychain=keychain)
        _assert_live_original(owner)
        snap=session.snapshot()
        if (snap.chain!='regtest' or snap.mainnet_allowed or not snap.signer_allowed
                or type(snap.receive_count) is not int or snap.receive_count!=0
                or snap.history_count!=0 or snap.core_sha256!=intake.get('wamd_sha256')):
            raise ValueError('Q05_EMPTY_OWNED_SNAPSHOT_DENIED')
        code=snap.receive_code;digest=snap.core_sha256
        record['observations'].append({'created_empty_owned_session':True,
            'height':snap.height,'history_count':0,'receive_count':0,
            'receive_code_sha256':sha256(code.encode()).hexdigest()})
        if a.fund_disposable_wallet:
            stage='PUBLIC_DISPOSABLE_FIXTURE_FUNDING'
            from wam_regtest.wsp_live import _public_fixture_payment,public_regtest_mining_address
            from wam_sp.keystore import Keyring
            rpc=session._rpc()
            address=public_regtest_mining_address(a.wsp_source)
            generated=rpc._call('generatetoaddress',['101',address])
            if type(generated) is not list or len(generated)!=101:
                raise ValueError('Q05_REGTEST_MATURITY_DENIED')
            txid,atoms,height=_public_fixture_payment(
                rpc,session.ring.accounts()[0],address)
            funded=session.snapshot()
            if (funded.history_count!=1 or funded.receive_count!=1
                    or funded.confirmed_atoms!=atoms or funded.height!=height):
                raise ValueError('Q05_FUNDED_OWNED_SCAN_DENIED')
            record['observations'].append({'real_fixture_payment_txid':txid,
                'height':height,'confirmed_atoms':atoms,'history_count':1,
                'receive_count':1})
            stage='OWNED_PREPARE_SIGN_BROADCAST'
            recipient=Keyring()
            try:pay=recipient.accounts()[0].payment_code()
            finally:recipient.close()
            review=session.prepare(pay,100000,10000)
            session.sign(review.commitment)
            sent=session.broadcast(review.commitment)
            if type(sent) is not str or len(sent)!=64:
                raise ValueError('Q05_OWNED_BROADCAST_DENIED')
            mined=rpc._call('generatetoaddress',['1',address])
            if type(mined) is not list or len(mined)!=1:
                raise ValueError('Q05_OWNED_CONFIRM_DENIED')
            paid=session.snapshot()
            if paid.history_count<2 or paid.receive_count!=1:
                raise ValueError('Q05_OWNED_CONFIRMED_HISTORY_DENIED')
            record['observations'].append({'genuine_owned_broadcast':True,
                'broadcast_txid':sent,'history_count':paid.history_count})
        stage='LOCK_WITHOUT_CORE_SHUTDOWN'
        pid=_assert_live_original(owner)
        session.lock();session=None
        if owner.process is None or owner.process.poll() is not None or owner.process.pid!=pid:
            raise ValueError('Q05_WALLET_LOCK_STOPPED_CORE')
        _assert_live_original(owner)
        record['observations'].append({'wallet_lock_left_core_running':True,'core_pid':pid})
        stage='CORE_REOPEN'
        owner.shutdown();owner.close()
        owner=CoreSupervisor(a.root,a.core_dir.expanduser().resolve(),authorized=True)
        owner.start(timeout=90)
        _assert_live_original(owner)
        stage='RESTORE_OWNED_SESSION'
        session=WalletSession.open_owned(owner,a.wsp_source,password,authorized=True,
                                         create=False,keychain=keychain)
        restored=session.snapshot()
        if restored.receive_code!=code or restored.core_sha256!=digest:
            raise ValueError('Q05_OWNED_RESTORE_CONTINUITY_DENIED')
        if not a.fund_disposable_wallet:
            if restored.history_count!=0 or restored.receive_count!=0:
                raise ValueError('Q05_OWNED_RESTORE_CONTINUITY_DENIED')
        else:
            if restored.history_count<2 or restored.receive_count!=1:
                raise ValueError('Q05_OWNED_FUNDED_RESTORE_DENIED')
        session.lock();session=None
        owner.shutdown();owner.close();owner=None
        record['observations'].append({'restored_same_payment_code':True,
            'funded_restore':bool(a.fund_disposable_wallet)})
        record['status']='PASS'
    except Exception as error:
        record['failure_stage']=stage;record['failure_type']=type(error).__name__
        if session is not None:
            try:session.lock()
            except (OSError,ValueError,RuntimeError):record['wallet_lock_blocked']=True
        record['owned_release_blocked']=False
        if owner is not None and owner.process is not None and owner.process.poll() is None:
            try:owner.recover_stop()
            except (OSError,ValueError,RuntimeError,ManagedCoreError):
                record['owned_release_blocked']=True
    finally:
        _stop_owned(owner)
        record['timestamp_utc']=datetime.now(timezone.utc).isoformat()
        with a.receipt.open('x') as out:json.dump(record,out,indent=2);out.write('\n')
    print(json.dumps({'status':record['status'],'source_sha':head,
                      'observations':len(record['observations']),
                      'fixture_funding':bool(a.fund_disposable_wallet)}))
    if record['status']!='PASS':raise SystemExit(2)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
