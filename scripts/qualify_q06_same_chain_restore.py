"""Explicit native fixture operator; never targets a retained wallet profile."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--core-dir',type=Path,required=True)
    p.add_argument('--wsp-source',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--stage-windows',action='store_true')
    p.add_argument('--test-root-witness',action='store_true')
    p.add_argument('--confirm-disposable-regtest',action='store_true')
    a=p.parse_args()
    if (not a.confirm_disposable_regtest or not a.report.is_absolute()
            or a.report.exists() or a.report.is_symlink()):
        raise ValueError('Q06_SAME_CHAIN_NATIVE_SCOPE_DENIED')
    from wam_regtest.probe_source import verify_source
    proof=verify_source(Path(__file__).resolve().parents[1])
    from wam_regtest.q05_platforms import detect_adapter,stage_windows_core
    from wam_regtest.q06_same_chain_restore_probe import qualify
    from wam_regtest.core import verified_core_paths
    adapter=detect_adapter();adapter.enforce_host()
    core=a.core_dir.absolute();source=a.wsp_source.absolute()
    if a.stage_windows:
        if sys.platform!='win32':raise ValueError('Q06_NATIVE_WINDOWS_STAGE_REQUIRED')
        stage_windows_core(core)
    adapter.prepare_trust(core,test_witness=a.test_root_witness)
    node,cli,_=verified_core_paths(core)
    result=qualify(core,source,a.report.parent,adapter)
    result['source_provenance']=proof
    result['core_sha256']={b.name:sha256(b.read_bytes()).hexdigest() for b in (node,cli)}
    result['wsp_source_commit']='ac55f13423620252bdbf848c7e8a280c3b84721e'
    with a.report.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    if result['all_original_owners_shutdown_verified']:adapter.teardown()
    print('Q06_NATIVE_SAME_CHAIN_RESULT='+result['status'],flush=True)
    return 0 if result['status']=='FRESH_PROFILE_SAME_CHAIN_HISTORY_RESTORE_PASS' else 1
if __name__=='__main__':raise SystemExit(main())
