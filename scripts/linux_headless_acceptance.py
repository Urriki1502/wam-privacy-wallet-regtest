"""Ephemeral Ubuntu acceptance operator; no automatic service install in app."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

parser=argparse.ArgumentParser()
parser.add_argument('--core-dir',type=Path,required=True)
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tests'))
from test_linux_anchor_witness import NativeRootWitness

NativeRootWitness.setUpClass()
try:
    result=subprocess.run([sys.executable,'-m','wam_regtest.cli','linux-wallet',
        '--core-dir',str(args.core_dir.absolute()),
        '--manifest-sha256','e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806',
        '--anchor-socket',str(NativeRootWitness.root/'anchor.sock'),
        '--wsp-source-root',str((root/'wsp-upstream').absolute()),
        '--confirm-experimental-developer-regtest','--confirm-headless-e2e',
        '--report','linux-headless-evidence.json'],stdin=subprocess.DEVNULL,timeout=600)
    assert result.returncode==0,'LINUX_ACTUAL_HEADLESS_EXECUTABLE_DENIED'
    record=json.loads(Path('linux-headless-evidence.json').read_text())
    wallet=record['wallet_live_core']
    assert wallet['status']=='REAL_LINUX_CORE_ROOT_WITNESS_HEADLESS_WALLET_E2E_PASS'
    assert record['qt_imported'] is False and record['official_signed_release'] is False
    assert wallet['synthetic_rpc'] is False and wallet['mainnet_allowed'] is False
    assert wallet['actual_reorg_depths']==[1,12,100] and wallet['confirmed_recipient_atoms']==100000
    print('LINUX_REAL_CORE_ROOT_WITNESS_NO_QT_HEADLESS_WALLET_PASS')
finally:NativeRootWitness.tearDownClass()
