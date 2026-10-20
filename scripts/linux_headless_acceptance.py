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
    assert record['mining_account_component']['f01_real_core_unowned_miner_script_negative_denied'] is True
    assert record['mining_account_component']['f07_genuine_regtest_p2pkh_p2sh_validateaddress_parity'] is True
    assert record['mining_account_component']['f09_genuine_core_bounded_read_soak']['status']=='F09_GENUINE_CORE_BOUNDED_READ_SOAK_PASS'
    assert record['mining_account_component']['f09_genuine_core_bounded_read_soak']['budget_version']=='F09_V1_64_CYCLES_180S'
    assert record['mining_account_component']['f09_genuine_core_bounded_read_soak']['cycles_completed']==64
    assert record['mining_account_component']['f09_genuine_core_bounded_read_soak']['read_only_rpc_calls']==192
    assert record['mining_account_component']['f09_genuine_core_bounded_read_soak']['stable_tip'] is True
    assert record['mining_account_component']['f09_genuine_core_bounded_read_soak']['no_core_mutations'] is True
    assert record['mining_account_component']['f09_long_hours_days_runtime_qualified'] is False
    assert record['mining_account_component']['f09_multi_node_peer_sync_qualified'] is False
    assert record['mining_account_component']['f07_mainnet_collision_public_fixture_network_refusal_regtest'] is True
    assert record['mining_account_component']['f07_native_mainnet_parser_runtime_qualified'] is False
    assert record['mining_account_component']['f01_all_miner_fees_core_owned_and_treasury_separate'] is True
    assert record['mining_account_component']['f02_real_core_immature_99_100_and_mature_101_verified'] is True
    assert record['mining_account_component']['f02_no_early_send_or_mempool_mutation'] is True
    assert record['mining_account_component']['f03_real_core_mempool_fee_and_vsize']['mempool_entry_relay_eligible'] is True
    assert record['mining_account_component']['f03_real_core_mempool_fee_and_vsize']['observed_fee_atoms'] == record['mining_account_component']['fee_atoms']
    assert record['mining_account_component']['f03_target_seconds_from_pinned_consensus_source'] == 120
    assert record['mining_account_component']['f03_confirmation_time_guaranteed'] is False
    assert record['mining_account_component']['f03_native_core_one_atom_dust_send_refused_without_mutation'] is True
    assert record['mining_account_component']['f04_core_lock_proof_from_listlockunspent_and_gettxout'] is True
    assert record['mining_account_component']['f04_core_unlock_restored_only_eligibility_not_new_money'] is True
    assert record['mining_account_component']['f04_genuine_core_after_lock']['locked_core_atoms'] == record['mining_account_component']['f04_genuine_core_before_lock']['available_atoms']
    assert record['mining_account_component']['f04_genuine_core_after_lock']['available_atoms'] == 0
    assert [x['f02_core_maturity_witness']['depth'] for x in record['mining_account_component']['maturity']] == [99,100,101]
    assert [x['f02_core_maturity_witness']['wallet_send_allowed_by_maturity'] for x in record['mining_account_component']['maturity']] == [False,False,True]
    assert record['mining_account_component']['native_gui_depths']==([99,100,101] if args.qt else [])
    assert record['owned_http_read_component']['idle_read_component']['status']=='REAL_CORE_IDLE_READ_RECONNECT_PASS'
    assert record['owned_http_read_component']['node_busy_read_component']['status']=='REAL_CORE_BUSY_READ_RECOVERY_PASS'
    assert record['owned_http_read_component']['status']=='REAL_CORE_OWNED_HTTP_READ_COMPONENT_PASS'
    # T-09: exact native OR actually executed frozen Core/WSP RPC receipt.
    t09=record['t09_direct_rpc_evidence']
    assert t09['status']=='T09_REAL_CORE_DIRECT_RPC_COMPONENT_PASS'
    assert t09['platform']=='linux-x86_64'
    assert t09['genuine_busy_idle_recovery_checked'] is True
    assert t09['native_core_authenticated'] is True
    assert t09['real_bip352_receive_and_sqlite'] is True
    assert t09['frozen_entrypoint'] is (args.executable is not None)
    assert t09['physical_accepted'] is False
    assert t09['dev_reviewed'] is False
    assert t09['synthetic_rpc'] is False and t09['mainnet_allowed'] is False
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
        print('LINUX_T05_REAL_CORE_NATIVE_QT_GUI_REOPEN_PASS_NOT_WALLET_Q05')
        # K-03: same qualified developer-Core native root-witness and actual
        # xcb Qt signer, now with a separately typed full 64-byte BIP39 seed.
        # This never tests or touches a real user's miner/datadir.
        k03_path=root/'scripts'/'issue45_managed_spend_e2e.py'
        k03_spec=importlib.util.spec_from_file_location(
            'k03_linux_real_core',k03_path)
        assert k03_spec is not None and k03_spec.loader is not None
        k03_module=importlib.util.module_from_spec(k03_spec)
        k03_spec.loader.exec_module(k03_module)
        k03=k03_module.prove(
            args.core_dir.absolute(),(root/'wsp-upstream').absolute(),
            bip39=True,
            linux_manifest='e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806',
            linux_witness=NativeRootWitness.root/'anchor.sock')
        assert k03['status']=='K03_BIP39_DURABLE_REAL_WSP_SPEND_E2E_PASS'
        assert all(k03[name] is True for name in (
            'k03_bip39_native_seed_to_signer',
            'genuine_wsp_psbtv2_native_signature',
            'exact_original_identity_after_close_reopen',
            'signed_reservation_anchored_before_crypto',
            'broadcast_reservation_persisted_before_rpc',
            'actual_native_fusion_qt_send_sign_broadcast'))
        assert k03['synthetic_rpc'] is False and k03['mainnet_allowed'] is False
        record['k03_bip39_real_managed_qt']={
            'status':k03['status'],
            'actual_wsp_native_bip39_sign_and_reopen':True,
            'synthetic_rpc':False,'mainnet_allowed':False,
        }
        print('LINUX_K03_BIP39_NATIVE_WSP_SIGN_REOPEN_PASS')
        # K-04: verified developer Core + independent root witness remain
        # process-wide immutable. Quarantine restores Core-native SQLite
        # backup only to a second disposable REGTEST daemon, never the user's
        # managed WSP signer or any external miner.
        k04_path=root/'scripts'/'issue45_k04_sqlite_e2e.py'
        k04_spec=importlib.util.spec_from_file_location(
            'k04_linux_core_sqlite',k04_path)
        assert k04_spec is not None and k04_spec.loader is not None
        k04_module=importlib.util.module_from_spec(k04_spec)
        k04_spec.loader.exec_module(k04_module)
        k04=k04_module.prove(args.core_dir.absolute())
        assert k04['status']=='K04_REAL_CORE_SQLITE_RESTORE_QUARANTINE_PASS'
        assert k04['real_core_restorewallet_rpc'] is True
        assert k04['source_immutable'] is True
        assert k04['duplicate_descriptor_identity_denied'] is True
        assert all(k04[key] is True for key in (
            'k06_genuine_core_descriptor_owner_isolation',
            'k06_core_duplicate_owner_refused',
            'k06_core_keys_not_reinterpreted_as_wsp'))
        assert k04['mainnet_allowed'] is False and k04['synthetic_rpc'] is False
        record['k04_core_sqlite_quarantine']={
            'status':k04['status'],
            'real_core_restorewallet':True,'original_wallet_unmodified':True,
            'synthetic_rpc':False,'mainnet_allowed':False}
        print('LINUX_K04_NATIVE_CORE_SQLITE_QUARANTINE_PASS')
        # K-10: two separate real REGTEST Core processes and private backup
        # within the existing independently provisioned native root witness.
        # Never restore this source fixture into the managed WSP wallet.
        sys.path.insert(0,str(root))
        from scripts.issue45_k10_core_same_host_smoke import prove_same_host_disposable_transfer
        k10=prove_same_host_disposable_transfer(
            args.core_dir.absolute(),authorized=True)
        assert k10['status']=='K10_REAL_CORE_SQLITE_SAME_OS_QUARANTINE_PASS'
        assert k10['actual_core_source_and_target_rpc_verified'] is True
        assert k10['source_and_target_descriptor_public_identity_equal'] is True
        assert k10['cross_os_physical_transfer_qualified'] is False
        assert k10['signer_allowed'] is False and k10['broadcast_allowed'] is False
        record['k10_core_sqlite_same_os']={
            'status':k10['status'],
            'actual_core_source_and_target_rpc_verified':True,
            'cross_os_physical_transfer_qualified':False,
            'fusion_wallet_restored':False,
            'signer_allowed':False,'broadcast_allowed':False,
        }
        print('LINUX_K10_NATIVE_CORE_SQLITE_SAME_OS_QUARANTINE_PASS')

    report.write_text(json.dumps(record,indent=2)+'\n')
    print('LINUX_REAL_CORE_ROOT_WITNESS_'+('NATIVE_QT' if args.qt else 'NO_QT_HEADLESS')+'_WALLET_PASS')
finally:
    if args.qt:
        from wam_regtest.desktop import shutdown_qt
        shutdown_qt()
    NativeRootWitness.tearDownClass()
