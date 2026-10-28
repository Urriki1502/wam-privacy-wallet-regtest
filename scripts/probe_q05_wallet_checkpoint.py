"""Bounded wallet create/reopen on a fresh signed macOS REGTEST owner.

Uses a new disposable Keychain only. Optional explicitly requested public
fixture funding is probe-only, never product onboarding. No existing wallet,
GUI, default Keychain changes, control-IPC secrets or full acceptance claims.
"""
import argparse
from datetime import datetime,timezone
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
from types import SimpleNamespace

from wam_regtest.core import verified_core_paths
from wam_regtest.core_supervisor import CoreSupervisor
from wam_regtest.custody import create_directory
from wam_regtest.managed_wallet_checkpoint import checkpoint,ManagedWalletError
from wam_regtest.wsp_live import PINNED_WSP_COMMIT,_pinned_source


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--core-dir',required=True,type=Path)
    parser.add_argument('--wsp-source',required=True,type=Path)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--receipt',required=True,type=Path)
    parser.add_argument('--confirm-disposable-regtest',action='store_true')
    parser.add_argument('--fund-disposable-wallet',action='store_true')
    a=parser.parse_args();source=Path(__file__).resolve().parents[1]
    if (not a.confirm_disposable_regtest or platform.system()!='Darwin'
            or platform.machine()!='arm64' or a.root.exists() or a.root.is_symlink()
            or a.receipt.exists()
            or subprocess.check_output(['git','status','--porcelain'],cwd=source)):
        raise SystemExit('Q05_WALLET_PROBE_SCOPE_DENIED')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
    node,cli,intake=verified_core_paths(a.core_dir);_pinned_source(a.wsp_source)
    record={'schema':'q05-empty-wallet-checkpoint-native/v1','status':'FAIL',
        'source_sha':head,'checkout_sha':head,'platform':'macos-arm64','frozen':False,
        'core_trust':'official-signed-v0.1.11','core_version':'v0.1.11',
        'core_sha256':{p.name:sha256(p.read_bytes()).hexdigest() for p in (node,cli)},
        'wsp_source_commit':PINNED_WSP_COMMIT,'wsp_executed':True,
        'python_version':platform.python_version(),
        'dependencies':{p:importlib.metadata.version(p) for p in ('coincurve','cryptography')},
        'adapter_sha256':sha256((source/'src/wam_regtest/managed_wallet_checkpoint.py').read_bytes()).hexdigest(),
        'synthetic_rpc':False,'funding_or_mining':a.fund_disposable_wallet,
        'wallet_signing_or_broadcast':False,
        'public_fixture_signature_and_broadcast':a.fund_disposable_wallet,
        'physical_device_acceptance':False,'mainnet_allowed':False,'observations':[]}
    owner=None;stage='KEYCHAIN'
    try:
        create_directory(a.root)
        owner=CoreSupervisor(a.root,a.core_dir,authorized=True)
        owner.start(timeout=30)
        keychain=a.root/'q05-disposable.keychain-db'
        result=subprocess.run(['/usr/bin/security','create-keychain','-p',
            'public-test-only',str(keychain)],capture_output=True,timeout=15)
        if result.returncode:raise ValueError('Q05_DISPOSABLE_KEYCHAIN_DENIED')
        stage='CREATE'
        password=b'public-disposable-q05-native-only'
        initial=checkpoint(owner,a.wsp_source,password,authorized=True,keychain=keychain,create=True)
        if (initial['height']!=0 or initial['confirmed_atoms']!=0 or initial['history_count']!=0
                or initial['signer_allowed'] or initial['broadcast_allowed']
                or initial['checkpoint'][0]!=1):raise ValueError('Q05_EMPTY_CHECKPOINT_DENIED')
        first=a.root/'chain'/'wallet-vault'/'snapshot-000000001.enc'
        first_digest=sha256(first.read_bytes()).hexdigest()
        record['wallet_id']=initial['wallet_id']
        record['payment_code_sha256']=sha256(initial['payment_code'].encode()).hexdigest()
        record['observations'].append({'created_empty_anchored_generation':initial['checkpoint'],
            'height':initial['height'],'confirmed_atoms':0,'history_count':0,'plaintext_runtime_removed':True})
        stage='DUPLICATE_REFUSAL'
        try:
            checkpoint(owner,a.wsp_source,password,authorized=True,keychain=keychain,create=True)
            raise ValueError('Q05_DUPLICATE_CREATE_ACCEPTED')
        except ManagedWalletError as error:
            if error.args!=('MANAGED_WALLET_EXISTS_OR_UNCERTAIN',):raise
        if sha256(first.read_bytes()).hexdigest()!=first_digest:
            raise ValueError('Q05_DUPLICATE_MUTATED_VAULT')
        if a.fund_disposable_wallet:
            stage='PUBLIC_DISPOSABLE_FIXTURE_FUNDING'
            from wam_regtest.wallet_session import WalletCoreCli
            from wam_regtest.wsp_live import _public_fixture_payment,public_regtest_mining_address
            rpc=WalletCoreCli(owner.cli,owner.directory);rpc.attest()
            address=public_regtest_mining_address(a.wsp_source)
            rpc._call('generatetoaddress',['101',address])
            txid,atoms,height=_public_fixture_payment(rpc,
                SimpleNamespace(payment_code=lambda:initial['payment_code']),address)
            if getattr(rpc,'_transport',None) is not None:rpc._transport.close()
            initial=checkpoint(owner,a.wsp_source,password,authorized=True,keychain=keychain)
            if (initial['confirmed_atoms']!=atoms or initial['height']!=height
                    or initial['history_count']!=1):raise ValueError('Q05_FUNDED_SCAN_DENIED')
            record['observations'].append({'real_fixture_payment_txid':txid,
                'height':height,'confirmed_atoms':atoms,'history_count':1,
                'history_sha256':initial['history_sha256'],'wallet_signing_or_broadcast':False})
        stage='CORE_OWNER_REOPEN'
        owner.shutdown();owner.close()
        owner=CoreSupervisor(a.root,a.core_dir,authorized=True);owner.start(timeout=30)
        stage='RESTORE_AND_LIVE_RESYNC'
        restored=checkpoint(owner,a.wsp_source,password,authorized=True,keychain=keychain)
        if (restored['wallet_id']!=initial['wallet_id']
                or restored['payment_code']!=initial['payment_code']
                or restored['tip']!=initial['tip'] or restored['height']!=initial['height']
                or restored['confirmed_atoms']!=initial['confirmed_atoms']
                or restored['history_count']!=initial['history_count']
                or restored['history_sha256']!=initial['history_sha256']
                or restored['checkpoint'][0]!=initial['checkpoint'][0]+1
                or sha256(first.read_bytes()).hexdigest()!=first_digest):
            raise ValueError('Q05_REOPEN_WALLET_CONTINUITY_DENIED')
        record['observations'].append({'reopened_same_wallet_live_resync':True,
            'anchored_generation':restored['checkpoint'],'original_generation_preserved':True,
            'height':restored['height'],'confirmed_atoms':restored['confirmed_atoms'],
            'history_count':restored['history_count'],'history_sha256':restored['history_sha256'],
            'plaintext_runtime_removed':True})
        stage='SAFE_SHUTDOWN'
        owner.shutdown();owner.close();owner=None
        record['status']='PASS'
    except Exception as error:
        record['failure_stage']=stage;record['failure_type']=type(error).__name__
        context=error.__context__
        if context is not None:record['inner_failure_type']=type(context).__name__
        # Original in-process Popen only, never guessed PID cleanup.
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


if __name__=='__main__':main()
