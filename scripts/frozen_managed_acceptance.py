"""Build operator: source harness, FINAL executable supervisor/scanner/Qt roles."""
import argparse
import json
from pathlib import Path
import sys

from issue45_t05_real_core import prove


def main():
    parser=argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('--core-dir',required=True,type=Path)
    parser.add_argument('--executable',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    proof=prove(args.core_dir.absolute(),qt=True,frozen_executable=args.executable.absolute())
    assert all(proof.get(name) is True for name in (
        'frozen_supervisor_scan_gui_processes','frozen_gui_clean_kill_reopen_same_tip',
        'frozen_supervisor_verified_shutdown_exit_zero','actual_qt_crash_reconnect_same_tip',
        'frozen_owned_core_crash_restart_same_tip',
        'authenticated_wsp_sqlite_resume_same_tip'))
    assert proof['frozen_public_scan_processes']==2 and proof['frozen_gui_processes']==3
    assert proof['frozen_scope_refusals_before_supervisor']==6
    assert proof['frozen_scope_refusals_prompt_free'] is True
    assert proof['full_gui_q05_qualified'] is False and proof['mainnet_allowed'] is False
    with args.output.open('x',encoding='utf8') as stream:
        json.dump(proof,stream,sort_keys=True,indent=2);stream.write('\n')
    print('FINAL_FROZEN_MANAGED_CORE_SCAN_QT_PROCESS_LIFECYCLE_PASS_NOT_FULL_Q05')


if __name__=='__main__':
    try:main()
    finally:
        desktop=sys.modules.get('wam_regtest.desktop')
        if desktop is not None:desktop.shutdown_qt()
