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
    assert record['owned_startup_component']['status']=='REAL_CORE_OWNED_STARTUP_COLLISION_AND_PREAUTH_PASS'
    assert record['owned_startup_component']['competing_listener_received_bytes']==0
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
    if args.qt:
        # Real native xcb Fusion GUI close/reopen with persistent managed
        # developer Core under the SAME approved Linux root-witness gate.
        import importlib.util
        path=root/'scripts'/'issue45_t05_real_core.py'
        spec=importlib.util.spec_from_file_location('t05_linux_real_core',path)
        assert spec is not None and spec.loader is not None
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        proof=module.prove(args.core_dir.absolute(),qt=True,
            frozen_executable=args.executable.absolute() if args.executable else None,
            linux_manifest='e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806',
            linux_witness=NativeRootWitness.root/'anchor.sock')
        required=('clean_restart_same_tip','daemon_crash_recovery_same_tip',
                  'independent_gui_client_reopen_same_chain',
                  'disconnected_gui_client_core_survived',
                  'independent_qt_process_reopen_same_chain',
                  'actual_qt_process_killed_after_authenticated_ready',
                  'actual_qt_crash_reconnect_same_tip',
                  'real_qt_gui_close_reopen_same_core','persistent_datadir_reused',
                  'simultaneous_owner_denied')
        assert all(proof.get(name) is True for name in required)
        assert proof['full_gui_q05_qualified'] is False
        record['t05_real_managed_qt']={name:proof[name] for name in required}
        record['t05_real_managed_qt']['test_source_provenance']=proof['test_source_provenance']
        record['t05_real_managed_qt']['full_wallet_q05_pending']=True
        if args.executable:
            assert all(proof.get(name) is True for name in (
                'frozen_supervisor_scan_gui_processes','frozen_gui_clean_kill_reopen_same_tip',
                'frozen_supervisor_verified_shutdown_exit_zero'))
            assert proof['frozen_scope_refusals_before_supervisor']==5
            assert proof['frozen_scope_refusals_prompt_free'] is True
            with Path('linux-frozen-managed-core-evidence.json').open('x') as stream:
                json.dump(proof,stream,sort_keys=True,indent=2);stream.write('\n')
            record['t05_real_managed_qt']['frozen_process_roles']=True
        print('LINUX_T05_REAL_CORE_NATIVE_QT_GUI_REOPEN_PASS_NOT_WALLET_Q05')
    report.write_text(json.dumps(record,indent=2)+'\n')
    print('LINUX_REAL_CORE_ROOT_WITNESS_'+('NATIVE_QT' if args.qt else 'NO_QT_HEADLESS')+'_WALLET_PASS')
finally:
    if args.qt:
        from wam_regtest.desktop import shutdown_qt
        shutdown_qt()
    NativeRootWitness.tearDownClass()
