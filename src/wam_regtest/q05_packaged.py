"""Explicit final-executable Q05 GUI qualification with bundled resources.

No Core/source override, witness installation, real assets or normal funding.
Only the qualification driver uses public test funding and simulated approvals.
"""
import argparse
import json
from pathlib import Path
import sys


def run(core,source,argv):
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--confirm-disposable-regtest',action='store_true')
    p.add_argument('--linux-developer-manifest')
    p.add_argument('--linux-root-witness',type=Path)
    p.add_argument('--qualification-test-witness',action='store_true')
    a=p.parse_args(argv)
    if (not a.confirm_disposable_regtest or not getattr(sys,'frozen',False)
            or sys.platform=='linux' and (not a.linux_developer_manifest or not a.linux_root_witness)):
        raise ValueError('Q05_FROZEN_EXPLICIT_SCOPE_REQUIRED')
    from .q05_gui_scenario import run_scenario
    record=run_scenario(core,source,a.root,a.receipt,confirmed=True,
        linux_manifest=a.linux_developer_manifest,linux_witness=a.linux_root_witness,
        test_witness=a.qualification_test_witness,_frozen=True)
    print(json.dumps({'status':record['status'],'source_sha':record['source_sha']}))
    return 0 if record['status']=='PASS' and record.get('owner_shutdown_verified') is True else 2
