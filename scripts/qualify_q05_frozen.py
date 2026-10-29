"""Execute final managed GUI bootloader; no editable wallet/source substitution.

Linux witness is provisioned ONLY by this explicit disposable test harness.
Keep profiles/receipts, including FAIL. Never sweep or repair an old workspace.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import secrets
import subprocess
import sys
import tempfile


def require_receipt(record,executable,source):
    if (record.get('status')!='PASS' or record.get('owner_shutdown_verified') is not True
            or record.get('frozen') is not True or record.get('synthetic_rpc') is not False
            or record.get('mainnet_allowed') is not False or record.get('source_sha')!=source
            or record.get('wsp_source_commit')!='ac55f13423620252bdbf848c7e8a280c3b84721e'
            or record.get('source_provenance',{}).get('frozen_executable_sha256')!=sha256(executable.read_bytes()).hexdigest()
            or record.get('qt_platform')!={'Darwin':'cocoa','Windows':'windows','Linux':'xcb'}.get(platform.system())
            or len(record.get('observations',[]))!=6
            or record['observations'][-1].get('automatic_wallet_replay') is not False):
        raise ValueError('Q05_FINAL_FROZEN_RECEIPT_DENIED')


def main():
    p=argparse.ArgumentParser();p.add_argument('--executable',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    binary=a.executable.absolute();receipt=a.output.absolute()
    if not binary.is_file() or binary.is_symlink() or receipt.exists() or receipt.is_symlink():
        raise ValueError('Q05_FINAL_FROZEN_SCOPE_DENIED')
    source=os.environ.get('WAM_SOURCE_HEAD') or subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    # Canonicalize only our freshly created test parent BEFORE wallet creation.
    # macOS tempfile's /var alias must not be passed to no-follow custody.
    parent=Path(tempfile.mkdtemp(prefix='wam-q05-final-gui-')).resolve(strict=True)
    root=parent/('wam-fusion-core-'+secrets.token_hex(8))
    args=[str(binary),'--ci-q05-managed-wallet','--root',str(root),'--receipt',str(receipt),
        '--confirm-disposable-regtest']
    env={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV')
        and not k.startswith(('DYLD_','QT_','QML_'))}
    env['QT_QPA_PLATFORM']={'Darwin':'cocoa','Windows':'windows','Linux':'xcb'}[platform.system()]
    witness=None
    if sys.platform=='win32':
        system=Path(os.environ['SystemRoot']);env['PATH']=str(system/'System32')+os.pathsep+str(system)
        env['QT_SCALE_FACTOR']='1.25'  # Logical scaling, not physical operator acceptance.
    else:env['PATH']='/usr/bin:/bin:/usr/sbin:/sbin'
    try:
        if sys.platform=='linux':
            sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
            os.environ['WAM_ROOT_WITNESS_NATIVE_TESTS']='1'
            from test_linux_anchor_witness import NativeRootWitness
            NativeRootWitness.setUpClass();witness=NativeRootWitness
            args+=['--linux-developer-manifest','e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806',
                '--linux-root-witness',str(witness.root/'anchor.sock'),'--qualification-test-witness']
        subprocess.run(args,env=env,cwd=parent,check=True,timeout=420)
        require_receipt(json.loads(receipt.read_text()),binary,source)
        print('Q05_FINAL_FROZEN_MANAGED_GUI_LIFECYCLE_PASS')
        base=json.loads(receipt.read_text())
        # Run the actual bundled code for custody/fault cases too. Each case
        # gets a NEW profile; all failed profiles/receipts stay on disk.
        completion=['--owned-session','--fund-disposable-wallet',
            '--interrupt-publication','--recover-after-interruption',
            '--interrupt-recovery-reference','--complete-pending-recovery']
        cases=[('security','security',[]),
            ('signed-completion','checkpoint',[*completion,'--reservation','signed']),
            ('uncertain-completion','checkpoint',[*completion,'--reservation','uncertain'])]
        cases += [('negative-'+mode,'checkpoint',['--negative',mode]) for mode in
                  ('missing','corrupt','orphan','sidecar','divergent-reference','wrong-wsp')]
        commands=[]
        for name,scenario,options in cases:
            target=parent/('wam-fusion-core-'+secrets.token_hex(8))
            result=receipt.with_name(receipt.stem+'-'+name+'.json')
            if result.exists() or result.is_symlink():raise ValueError('Q05_FINAL_FROZEN_SCOPE_DENIED')
            command=[str(binary),'--ci-q05-managed-wallet','--scenario',scenario,
                '--root',str(target),'--receipt',str(result),'--confirm-disposable-regtest',*options]
            if witness is not None:
                command+=['--linux-developer-manifest',
                    'e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806',
                    '--linux-root-witness',str(witness.root/'anchor.sock'),'--qualification-test-witness']
            commands.append(command)
            subprocess.run(command,env=env,cwd=parent,check=True,timeout=420)
            item=json.loads(result.read_text())
            require_supplement(item,base,binary,scenario,options)
            print('Q05_FINAL_FROZEN_'+name.upper().replace('-','_')+'_PASS',flush=True)
        with receipt.with_name(receipt.stem+'-commands.json').open('x') as out:
            json.dump({'gui':args,'supplements':commands},out,indent=2);out.write('\n')
    finally:
        if witness is not None:witness.tearDownClass()
        # Intentionally retain the entire managed profile, no rmtree/temp context.


def require_supplement(item,base,binary,scenario,options):
    if (item.get('status')!='PASS' or item.get('owner_shutdown_verified') is not True
            or item.get('frozen') is not True or item.get('synthetic_rpc') is not False
            or item.get('mainnet_allowed') is not False
            or any(item.get(k)!=base.get(k) for k in
                   ('source_sha','checkout_sha','core_sha256','wsp_source_commit','platform','core_trust'))
            or item.get('source_provenance',{}).get('frozen_executable_sha256')!=sha256(binary.read_bytes()).hexdigest()):
        raise ValueError('Q05_FINAL_FROZEN_SUPPLEMENT_DENIED')
    observations=item.get('observations',[])
    if scenario=='security':
        if (len(observations)!=3 or observations[0].get('cross_process_competing_owner_refused') is not True
                or observations[0].get('authenticated_control_reconnect_same_original_owner') is not True
                or observations[0].get('wrong_hmac_shutdown_refused_without_journal_mutation') is not True
                or observations[1].get('credential_bytes_sent')!=0
                or observations[2].get('explicit_original_backend_quit_verified') is not True):
            raise ValueError('Q05_FINAL_FROZEN_SUPPLEMENT_DENIED')
    elif '--negative' in options:
        mode=options[options.index('--negative')+1]
        if (item.get('qualification_scope')!='NEGATIVE_'+mode.upper()
                or not any(o.get('negative_checkpoint')==mode and
                    o.get('native_anchor_unchanged') is True and
                    o.get('original_and_hostile_bytes_preserved') is True for o in observations)):
            raise ValueError('Q05_FINAL_FROZEN_SUPPLEMENT_DENIED')
    elif (item.get('qualification_scope')!='EXPLICIT_PENDING_RECOVERY_COMPLETION'
            or item.get('recovery_completed') is not True
            or item.get('automatic_wallet_transaction_replay') is not False
            or item.get('wallet_broadcast_calls_total')!=(1 if 'uncertain' in options else 0)
            or not any(o.get('explicit_pending_commit_completed') is True for o in observations)
            or not any(o.get('reopened_same_wallet_live_resync') is True for o in observations)):
        raise ValueError('Q05_FINAL_FROZEN_SUPPLEMENT_DENIED')


if __name__=='__main__':main()
