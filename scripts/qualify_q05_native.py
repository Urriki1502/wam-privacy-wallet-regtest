"""One exact-source native Q05 matrix; retain every disposable profile/receipt.

Windows/Linux must run on their actual native hosts. Linux needs either an
existing approved witness or the explicitly requested qualification fixture.
No CI dispatch, external node, production data or acceptance promotion.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile

from wam_regtest.probe_source import verify_source
from wam_regtest.q05_platforms import detect_adapter


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--core-dir',type=Path,required=True)
    p.add_argument('--wsp-source',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--confirm-disposable-regtest',action='store_true')
    p.add_argument('--linux-developer-manifest')
    p.add_argument('--linux-root-witness',type=Path)
    p.add_argument('--test-root-witness',action='store_true')
    p.add_argument('--stage-official-windows-core',action='store_true')
    a=p.parse_args();project=Path(__file__).resolve().parents[1]
    if (not a.confirm_disposable_regtest or not a.output_dir.is_absolute()
            or a.output_dir.exists() or a.output_dir.is_symlink()
            or a.output_dir.resolve().is_relative_to(project)):
        raise ValueError('Q05_NATIVE_NEW_EXTERNAL_EVIDENCE_REQUIRED')
    proof=verify_source(project);adapter=detect_adapter();adapter.enforce_host()
    a.output_dir.mkdir(mode=0o700)
    record={'source_provenance':proof,'platform':adapter.platform_id,'status':'FAIL',
            'python_version':sys.version.split()[0],'commands':[],'completed':[]}
    if a.stage_official_windows_core:
        from wam_regtest.q05_platforms import stage_windows_core
        stage_windows_core(a.core_dir)
    adapter.prepare_trust(a.core_dir,a.linux_developer_manifest,a.linux_root_witness,
                          test_witness=a.test_root_witness)
    witness=a.linux_root_witness
    if witness is None and getattr(adapter,'_witness',None) is not None:
        witness=adapter._witness.root/'anchor.sock'
    completion=['--owned-session','--fund-disposable-wallet','--interrupt-publication',
        '--recover-after-interruption','--interrupt-recovery-reference','--complete-pending-recovery']
    cases=[('gui','probe_q05_executor_gui.py',[]),('security','probe_q05_security.py',[]),
        ('signed-completion','probe_q05_wallet_checkpoint.py',[*completion,'--reservation','signed']),
        ('uncertain-completion','probe_q05_wallet_checkpoint.py',[*completion,'--reservation','uncertain'])]
    cases += [('negative-'+mode,'probe_q05_wallet_checkpoint.py',['--negative',mode]) for mode in
              ('missing','corrupt','orphan','sidecar','divergent-reference','wrong-wsp')]
    if sys.platform=='darwin':cases.append(('authenticated-control','probe_q05_macos_lifecycle.py',[]))
    parent=Path(tempfile.mkdtemp(prefix='wam-q05-native-matrix-')).resolve(strict=True)
    safe=True
    try:
        for name,script,options in cases:
            root=parent/('wam-fusion-core-'+secrets.token_hex(8))
            receipt=a.output_dir/(name+'.json')
            command=[sys.executable,str(project/'scripts'/script),'--core-dir',str(a.core_dir),
                     '--root',str(root),'--receipt',str(receipt),'--confirm-disposable-regtest',*options]
            if script!='probe_q05_macos_lifecycle.py':command+=['--wsp-source',str(a.wsp_source)]
            if witness is not None:
                command+=['--linux-root-witness',str(witness),'--linux-developer-manifest',
                    a.linux_developer_manifest or
                    'e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806']
                if a.test_root_witness:
                    command+=['--test-root-witness' if script=='probe_q05_executor_gui.py'
                              else '--qualification-test-witness']
            record['commands'].append(command)
            safe=False
            with (a.output_dir/(name+'.log')).open('x') as log:
                result=subprocess.run(command,cwd=project,stdout=log,stderr=subprocess.STDOUT,
                                      timeout=420,check=False)
            item=json.loads(receipt.read_text()) if receipt.is_file() else {}
            safe=item.get('owner_shutdown_verified',item.get('core_shutdown_confirmed')) is True
            if (result.returncode or item.get('status')!='PASS' or not safe
                    or item.get('source_sha')!=proof['candidate_source_sha']):
                raise ValueError('Q05_NATIVE_MATRIX_CASE_FAILED')
            record['completed'].append(name)
            print('Q05_NATIVE_'+name.upper().replace('-','_')+'_PASS',flush=True)
        record['status']='PASS'
    finally:
        # A failed live owner must retain its witness and profile, not lose its
        # authority as a side effect of test cleanup. Never sweep test roots.
        if safe:adapter.teardown()
        record['last_owner_shutdown_verified']=safe
        record['timestamp_utc']=datetime.now(timezone.utc).isoformat()
        with (a.output_dir/'matrix.json').open('x') as out:json.dump(record,out,indent=2);out.write('\n')


if __name__=='__main__':main()
