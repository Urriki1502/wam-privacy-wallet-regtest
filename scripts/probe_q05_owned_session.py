"""Q05 owned WalletSession START→RESTORE on genuine native Core.

Platform-neutral lifecycle lives in wam_regtest.q05_owned_lifecycle.
This CLI only selects host adapters and writes a sanitized receipt.
LOCK_WITHOUT_CORE_SHUTDOWN is asserted in the harness: wallet lock never
calls owner.shutdown() before CORE_REOPEN.
"""
import argparse
from pathlib import Path
import sys

from wam_regtest.q05_owned_lifecycle import (
    OwnedLifecycleError,run_owned_lifecycle,stage_windows_core)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--core-dir',required=True,type=Path)
    parser.add_argument('--wsp-source',required=True,type=Path)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--receipt',required=True,type=Path)
    parser.add_argument('--confirm-disposable-regtest',action='store_true')
    parser.add_argument('--fund-disposable-wallet',action='store_true')
    parser.add_argument('--linux-developer-manifest')
    parser.add_argument('--linux-root-witness',type=Path)
    parser.add_argument('--confirm-gui-lifecycle',action='store_true')
    parser.add_argument('--skip-fail-closed',action='store_true')
    parser.add_argument('--stage-windows-core',action='store_true')
    a=parser.parse_args()
    core=a.core_dir.expanduser().resolve()
    if a.stage_windows_core:
        stage_windows_core(core)
    record=run_owned_lifecycle(
        core_dir=core,
        wsp_source=a.wsp_source.expanduser().resolve(),
        root=a.root.expanduser().resolve(),
        receipt=a.receipt.expanduser().resolve(),
        confirm=bool(a.confirm_disposable_regtest),
        funded=bool(a.fund_disposable_wallet),
        linux_manifest=a.linux_developer_manifest,
        linux_witness=(a.linux_root_witness.expanduser().resolve()
                       if a.linux_root_witness else None),
        gui=bool(a.confirm_gui_lifecycle),
        fail_closed=not a.skip_fail_closed)
    print({'status':record['status'],'source_sha':record['source_sha'],
           'platform':record['platform'],
           'observations':len(record['observations']),
           'fixture_funding':bool(a.fund_disposable_wallet),
           'scenarios':record['scenarios']})
    if record['status']=='BLOCKED':
        raise SystemExit(3)
    if record['status']!='PASS':
        raise SystemExit(2)
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except OwnedLifecycleError as error:
        print(error.args[0] if error.args else type(error).__name__,file=sys.stderr)
        raise SystemExit(2)
