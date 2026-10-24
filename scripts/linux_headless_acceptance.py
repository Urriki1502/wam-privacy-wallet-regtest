"""Ephemeral Ubuntu acceptance operator; no automatic service install in app."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

parser=argparse.ArgumentParser()
parser.add_argument('--core-dir',type=Path,required=True)
parser.add_argument('--executable',type=Path,help='Execute final frozen bootloader with bundled resources')
parser.add_argument('--qt',action='store_true',help='Native xcb Qt acceptance instead of independent no-Qt headless gate')
args=parser.parse_args()
report=Path('linux-qt-evidence.json' if args.qt else 'linux-headless-evidence.json')
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tests'))
from test_linux_anchor_witness import NativeRootWitness

NativeRootWitness.setUpClass()
try:
    command=([str(args.executable.absolute())] if args.executable else
        [sys.executable,'-m','wam_regtest.cli','linux-wallet','--core-dir',str(args.core_dir.absolute()),
         '--wsp-source-root',str((root/'wsp-upstream').absolute())])
    result=subprocess.run([*command,
        '--manifest-sha256','e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806',
        '--anchor-socket',str(NativeRootWitness.root/'anchor.sock'),
        '--confirm-experimental-developer-regtest','--confirm-qt-e2e' if args.qt else '--confirm-headless-e2e',
        '--report',str(report)],stdin=subprocess.DEVNULL,timeout=600)
    assert result.returncode==0,'LINUX_ACTUAL_HEADLESS_EXECUTABLE_DENIED'
    record=json.loads(report.read_text())
    wallet=record['wallet_live_core']
    assert wallet['status']==('REAL_LINUX_CORE_ROOT_WITNESS_NATIVE_QT_WALLET_E2E_PASS' if args.qt else 'REAL_LINUX_CORE_ROOT_WITNESS_HEADLESS_WALLET_E2E_PASS')
    assert record['qt_imported'] is args.qt and record['official_signed_release'] is False
    assert wallet['synthetic_rpc'] is False and wallet['mainnet_allowed'] is False
    assert wallet['confirmed_recipient_atoms']==100000
    if not args.qt:assert wallet['actual_reorg_depths']==[1,12,100]
    else:assert wallet['qt_platform']=='xcb' and wallet['fresh_core_same_keys_reservations'] is True
    print('LINUX_REAL_CORE_ROOT_WITNESS_'+('NATIVE_QT' if args.qt else 'NO_QT_HEADLESS')+'_WALLET_PASS')
finally:NativeRootWitness.tearDownClass()
