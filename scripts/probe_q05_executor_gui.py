"""Explicit genuine managed GUI qualification; disposable REGTEST profiles only."""
import argparse
import json
from pathlib import Path

from wam_regtest.q05_gui_scenario import run_scenario
from wam_regtest.q05_platforms import stage_windows_core


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--core-dir',type=Path,required=True)
    p.add_argument('--wsp-source',type=Path,required=True)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--confirm-disposable-regtest',action='store_true')
    p.add_argument('--linux-developer-manifest')
    p.add_argument('--linux-root-witness',type=Path)
    p.add_argument('--test-root-witness',action='store_true')
    p.add_argument('--stage-official-windows-core',action='store_true')
    a=p.parse_args()
    if not a.confirm_disposable_regtest:raise SystemExit('Q05_GUI_DISPOSABLE_SCOPE_DENIED')
    if a.stage_official_windows_core:stage_windows_core(a.core_dir)
    record=run_scenario(a.core_dir,a.wsp_source,a.root,a.receipt,confirmed=True,
        linux_manifest=a.linux_developer_manifest,linux_witness=a.linux_root_witness,
        test_witness=a.test_root_witness)
    print(json.dumps({'status':record['status'],'source_sha':record['source_sha'],
        'observations':len(record['observations'])}))
    return 0 if record['status']=='PASS' else 2


if __name__=='__main__':raise SystemExit(main())
