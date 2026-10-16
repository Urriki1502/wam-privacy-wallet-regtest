"""Ephemeral Ubuntu acceptance operator; no automatic service install in app."""
import argparse
import json
import os
import platform
import re
from datetime import datetime, timezone
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
    assert record['wsp_live_scan']['scanner_transport']=='owned-http'
    assert record['wsp_live_scan']['cli_and_rehash_forbidden_during_scan'] is True
    assert record['mining_account_component']['status']=='REAL_CORE_REGTEST_MINING_ACCOUNT_MATURITY_PASS'
    assert record['mining_account_component']['owned_http_matches_independent_cli'] is True
    assert record['mining_account_component']['native_gui_depths']==([99,100,101] if args.qt else [])
    assert record['owned_http_read_component']['idle_read_component']['status']=='REAL_CORE_IDLE_READ_RECONNECT_PASS'
    assert record['owned_http_read_component']['node_busy_read_component']['status']=='REAL_CORE_BUSY_READ_RECOVERY_PASS'
    assert record['owned_http_read_component']['status']=='REAL_CORE_OWNED_HTTP_READ_COMPONENT_PASS'
    wallet=record['wallet_live_core']
    assert wallet['operational_snapshot_http']['cli_and_rehash_forbidden'] is True
    assert wallet['operational_snapshot_http']['transport']=='owned-http'
    assert wallet['status']==('REAL_LINUX_CORE_ROOT_WITNESS_NATIVE_QT_WALLET_E2E_PASS' if args.qt else 'REAL_LINUX_CORE_ROOT_WITNESS_HEADLESS_WALLET_E2E_PASS')
    assert record['qt_imported'] is args.qt and record['official_signed_release'] is False
    assert wallet['synthetic_rpc'] is False and wallet['mainnet_allowed'] is False
    assert wallet['confirmed_recipient_atoms']==100000
    if not args.qt:assert wallet['actual_reorg_depths']==[1,12,100]
    else:assert wallet['qt_platform']=='xcb' and wallet['fresh_core_same_keys_reservations'] is True
    checkout=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    head=os.environ.get('WAM_SOURCE_HEAD',checkout)
    assert re.fullmatch('[0-9a-f]{40}',head) and re.fullmatch('[0-9a-f]{40}',checkout)
    # actions/checkout may be shallow: inspect the commit's raw parent header,
    # without fetching network history or accepting an unrelated declared SHA.
    header=subprocess.check_output(['git','cat-file','-p',checkout],cwd=root,text=True).split('\n\n',1)[0]
    parents={line[7:] for line in header.splitlines() if line.startswith('parent ')}
    assert head==checkout or head in parents, 'LINUX_SOURCE_CHECKOUT_IDENTITY_DENIED'
    assert re.fullmatch('[0-9a-f]{64}',record['wam_cli_sha256'])
    record.update(source_head_sha=head,checkout_sha=checkout,
        tested_utc=datetime.now(timezone.utc).isoformat(),
        acceptance_environment={'os':platform.system(),'release':platform.release(),
            'architecture':platform.machine(),'python':platform.python_version(),
            'frozen_entrypoint':args.executable is not None,'qt':args.qt},
        wsp_commit='ac55f13423620252bdbf848c7e8a280c3b84721e')
    report.write_text(json.dumps(record,indent=2)+'\n')
    print('LINUX_REAL_CORE_ROOT_WITNESS_'+('NATIVE_QT' if args.qt else 'NO_QT_HEADLESS')+'_WALLET_PASS')
finally:NativeRootWitness.tearDownClass()
