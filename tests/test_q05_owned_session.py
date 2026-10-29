"""Owned-session attach contracts; not genuine Core E2E."""
from pathlib import Path
from unittest.mock import patch
import sys
import unittest

import test_q05_core_supervisor as fixture
from wam_regtest.wallet_session import WalletSession,WalletSessionError
from wam_regtest import managed_wallet_checkpoint as checkpoint


class OwnedSessionContracts(unittest.TestCase):
    setUp=fixture.SupervisorLifecycleUnit.setUp
    owner=fixture.SupervisorLifecycleUnit.owner

    def test_owned_open_requires_consent_before_owner_or_source(self):
        with patch.object(checkpoint,'_owned') as owned, patch.object(checkpoint,'_pinned_source') as source:
            with self.assertRaisesRegex(WalletSessionError,'EXPLICIT_CONSENT'):
                WalletSession.open_owned(object(),Path('/unused'),
                                         b'public-disposable-password',authorized=False,create=True)
            owned.assert_not_called();source.assert_not_called()

    def test_stopped_owner_never_opens_a_wallet_session(self):
        with self.assertRaisesRegex(WalletSessionError,'ORIGINAL_OWNER|OWNED_SCOPE|OWNED_OPEN'):
            WalletSession.open_owned(self.owner(),Path('/unused'),
                                     b'public-disposable-password',authorized=True)

    def test_dirty_runtime_blocks_owned_open_without_repair(self):
        owner=self.owner()
        runtime=owner.directory/'wallet-runtime.sqlite-wal'
        runtime.write_bytes(b'preserve-wal')
        with patch.object(checkpoint,'_inputs'):
            with self.assertRaisesRegex(WalletSessionError,'EXISTING_RUNTIME'):
                WalletSession.open_owned(owner,Path('/unused'),
                                         b'public-disposable-password',authorized=True)
        self.assertEqual(runtime.read_bytes(),b'preserve-wal')

    def test_publication_ambiguity_is_not_automatic_recovery(self):
        owner=self.owner()
        runtime=owner.directory/'wallet-runtime.sqlite'
        runtime.write_bytes(b'preserve-runtime')
        with patch.object(checkpoint,'_owned'),patch.object(checkpoint,'_pinned_source'):
            row=checkpoint.publication_ambiguity(owner,Path('/unused'),authorized=True)
        self.assertFalse(row['automatic_recovery_allowed'])
        self.assertTrue(row['checkpoint_open_blocked'])
        self.assertEqual(runtime.read_bytes(),b'preserve-runtime')

    def test_gui_close_does_not_proceed_while_sign_or_broadcast_worker_runs(self):
        text=(Path(__file__).resolve().parents[1]/'src/wam_regtest/operational_gui.py').read_text()
        self.assertIn('if self._worker is not None or self._approval_open',text)
        self.assertIn('event.ignore()',text)
        self.assertIn('_run_owner_operation',text)
        self.assertIn('QTimer.singleShot(0',text)
        self.assertNotIn('worker.start()',text)
        cli=(Path(__file__).resolve().parents[1]/'src/wam_regtest/cli.py').read_text()
        self.assertIn('stop_core_on_app_exit=True',cli)

    def test_cli_wires_in_process_managed_gui_not_control_wallet_ops(self):
        text=(Path(__file__).resolve().parents[1]/'src/wam_regtest/cli.py').read_text()
        self.assertIn("'managed-gui'",text)
        self.assertIn('launch_owned_wallet',text)
        self.assertIn('open_owned',Path(__file__).resolve().parents[1]
                      .joinpath('src/wam_regtest/wallet_session.py').read_text())
        from wam_regtest.supervisor_protocol import CONTROL_COMMANDS
        self.assertNotIn('managed-gui',CONTROL_COMMANDS)

    def test_cli_wires_in_process_managed_gui_not_control_wallet_ops_probe_exists(self):
        root=Path(__file__).resolve().parents[1]
        probe=(root/'scripts/probe_q05_owned_session.py').read_text()
        harness=(root/'src/wam_regtest/q05_owned_lifecycle.py').read_text()
        self.assertIn('run_owned_lifecycle',probe)
        self.assertIn('WalletSession.open_owned',harness)
        self.assertIn('wallet_lock_left_core_running',harness)
        self.assertNotIn('owner.shutdown()',harness.split('LOCK_WITHOUT_CORE_SHUTDOWN')[1].split('CORE_REOPEN')[0])
        self.assertNotIn("platform.system()!='Darwin'",probe)
        self.assertIn('WindowsX64Adapter',harness)
        self.assertIn('LinuxX64Adapter',harness)
        self.assertIn('WindowsCredentialAnchor',root.joinpath('src/wam_regtest/custody.py').read_text())
        self.assertIn('APPROVED_LINUX_MANIFEST',harness)
        self.assertIn('wam-fusion-core-',harness)
        self.assertIn('private_temporary_directory',harness)
        self.assertIn('timeout=120',harness)
        self.assertIn('failed_profile_retained',harness)
        self.assertIn('surviving_original_core',harness)
        self.assertIn('paid.receive_count<1',harness)
        self.assertNotIn('paid.receive_count!=1',harness)
        recovery=harness.split('def _same_owner_crash_recovery',1)[1].split('\ndef ',1)[0]
        self.assertIn('owner.recover_dead(authorized=True)',recovery)
        self.assertIn('process.kill()',recovery)
        self.assertIn('create=False',recovery)
        self.assertIn('restored.history_sha256!=history_sha',recovery)
        self.assertIn('restored.tip!=tip',recovery)
        self.assertIn('restored.height!=height',recovery)
        self.assertIn('_require_same_reservation(snap,restored)',recovery)
        self.assertNotIn('restored.height<height',recovery)
        self.assertNotIn('os.kill',recovery)
        self.assertNotIn('.unlink(',recovery)
        self.assertNotIn('rmtree',recovery)
        self.assertNotIn('CoreSupervisor(root,core,authorized=True).recover_dead',recovery)
        denial=harness.split('def _fail_closed_crash',1)[1].split('\ndef ',1)[0]
        self.assertNotIn('recover_dead',denial)
        self.assertIn('Q05_CRASH_START_SHOULD_DENY',denial)
        self.assertIn('CONCURRENT_OWNER_WHILE_CORE_LIVE',harness)
        self.assertIn('SUPERVISOR_STORAGE_LEASE_BUSY',harness)
        self.assertIn('concurrent_owner_refused',harness)
        self.assertIn('second_process_started',harness)
        self.assertNotIn('rival.start',harness)
        wrong=harness.split('def _wrong_core_refused',1)[1].split('\ndef ',1)[0]
        self.assertIn('mainnet_allowed',wrong)
        self.assertIn('not-a-wam-core',wrong)
        self.assertIn('untrusted_core_directory_refused',wrong)
        self.assertIn('Q05_WRONG_CORE_MUTATED_REAL_RECEIPT',wrong)
        self.assertNotIn('.start(',wrong)
        self.assertIn('wrong=base/_profile_name();create_directory(wrong)',harness)
        self.assertNotIn('Popen',wrong)
        self.assertNotIn('.kill(',wrong)
        reattach=harness.split("stage='SAME_OWNER_REATTACH'",1)[1].split("stage='CORE_REOPEN'",1)[0]
        self.assertIn('create=False',reattach)
        self.assertIn('Q05_SAME_OWNER_REATTACH_DENIED',reattach)
        self.assertIn('again.history_sha256!=held.history_sha256',reattach)
        self.assertIn('_require_same_reservation(held,again)',reattach)
        self.assertNotIn('CoreSupervisor(',reattach)
        self.assertNotIn('.kill(',reattach)
        self.assertNotIn('owner.start',reattach)
        reopen=harness.split("stage='CORE_REOPEN'",1)[1].split("stage='RESTORE_OWNED_SESSION'",1)[0]
        self.assertIn('owner.shutdown()',reopen)
        self.assertIn('stopped.poll() is None',reopen)
        self.assertIn('Q05_GRACEFUL_SHUTDOWN_ORIGINAL_STILL_LIVE',reopen)
        self.assertIn('owner.process is stopped',reopen)
        self.assertIn('original_popen_reaped',reopen)
        self.assertNotIn('.kill(',reopen)
        self.assertNotIn('os.kill',reopen)
        self.assertNotIn('rmtree',reopen)
        restore=harness.split("stage='RESTORE_OWNED_SESSION'",1)[1].split(
            "record['scenarios']['wallet_restore']",1)[0]
        self.assertIn('restored.history_sha256!=again.history_sha256',restore)
        self.assertIn('restored.height!=again.height',restore)
        self.assertIn('restored.tip!=again.tip',restore)
        self.assertIn('restored.confirmed_atoms!=again.confirmed_atoms',restore)
        self.assertIn('_require_same_reservation(again,restored)',restore)
        self.assertNotIn('Q05_OWNED_FUNDED_RESTORE_DENIED',restore)
        funded=harness.split('def _funded_same_owner_crash_recovery',1)[1].split('\ndef ',1)[0]
        self.assertIn('owner.recover_dead(authorized=True)',funded)
        self.assertIn('process.kill()',funded)
        self.assertIn('create=False',funded)
        self.assertIn('seen.count(sent)!=1',funded)
        self.assertIn('restored.history_sha256!=pre_digest',funded)
        self.assertIn('restored.tip!=pre_tip',funded)
        self.assertIn('restored.height!=pre_height',funded)
        self.assertIn('_require_same_reservation(paid,restored)',funded)
        self.assertNotIn('restored.height<pre_height',funded)
        self.assertIn('floor!=pre_height',funded)
        self.assertNotIn('floor<pre_height',funded)
        self.assertIn('pre_height>owner._height_snapshot',funded)
        self.assertIn('owner._height_snapshot=floor',funded)
        self.assertIn('_durable_regtest_tip(owner,pre_height)',funded)
        self.assertLess(funded.index('_durable_regtest_tip(owner,pre_height)'),
                        funded.index('process.kill()'))
        durable=harness.split('def _durable_regtest_tip',1)[1].split('\ndef ',1)[0]
        self.assertIn('json.dumps(tip)',durable)
        self.assertIn("'true'",durable)
        self.assertNotIn("'false'",durable)
        self.assertNotIn('generatetoaddress',durable)
        gui=harness.split('def _gui_lifecycle',1)[1].split('\ndef ',1)[0]
        self.assertIn('session.snapshot()',gui)
        self.assertIn('apply_snapshot(snap)',gui)
        self.assertIn('Q05_GUI_HISTORY_DENIED',gui)
        self.assertIn('native_gui_history_matches',gui)
        self.assertIn('page.select_txid(expected[0])',gui)
        self.assertIn('page.older.click()',gui)
        self.assertIn('page.newer.click()',gui)
        self.assertIn('GUI_HISTORY_LIMIT',gui)
        self.assertIn('gui_history_paged',gui)
        self.assertNotIn('broadcast(',gui)
        self.assertNotIn('.mine(',gui)
        self.assertNotIn('close()',gui)
        self.assertNotIn('session.lock(',gui)
        self.assertNotIn('generatetoaddress',funded)
        self.assertNotIn('os.kill',funded)
        self.assertNotIn('.unlink(',funded)
        self.assertNotIn('rmtree',funded)
        self.assertNotIn('broadcast(',funded)

    def test_untrusted_core_directory_is_refused_before_start(self):
        import tempfile
        from wam_regtest.q05_owned_lifecycle import _wrong_core_refused
        with tempfile.TemporaryDirectory() as raw:
            base=Path(raw)
            core=base/'real-core'
            core.mkdir()
            receipt=core/'receipt.json'
            receipt.write_text('{"mainnet_allowed":false}\n',encoding='ascii')
            before=receipt.read_bytes()
            profile=base/'profile'
            profile.mkdir()
            record={'scenarios':{},'observations':[]}
            _wrong_core_refused(core,profile,record)
            self.assertEqual(record['scenarios']['wrong_core_refused'],'PASS')
            row=record['observations'][-1]
            self.assertTrue(row['untrusted_core_directory_refused'])
            self.assertTrue(row['mainnet_receipt_refused'])
            self.assertFalse(row['process_started'])
            self.assertTrue(row['real_core_receipt_unchanged'])
            self.assertEqual(receipt.read_bytes(),before)
            self.assertTrue((profile/'tampered-core'/'receipt.json').is_file())

    def test_host_adapter_matches_this_os_and_refuses_foreign_linux_manifest_pin(self):
        from wam_regtest.q05_owned_lifecycle import (
            APPROVED_LINUX_MANIFEST,detect_adapter,LinuxX64Adapter,OwnedLifecycleError)
        adapter=detect_adapter()
        adapter.enforce_host()
        if sys.platform=='linux':
            self.assertEqual(adapter.platform_id,'linux-x86_64')
            with self.assertRaisesRegex(OwnedLifecycleError,'LINUX_APPROVED_MANIFEST'):
                LinuxX64Adapter().prepare_trust(Path('/unused'),manifest='0'*64)
        self.assertEqual(APPROVED_LINUX_MANIFEST,
                         'e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806')

    def test_reopen_refuses_a_dropped_reservation_fingerprint(self):
        from types import SimpleNamespace
        from wam_regtest.q05_owned_lifecycle import (
            OwnedLifecycleError,_require_same_reservation)
        from wam_regtest.wallet_read import WalletReadSnapshot
        before=SimpleNamespace(reservation_count=2,reservation_sha256='ab'*32,
                               reservation_states=('signed','uncertain'))
        dropped=SimpleNamespace(reservation_count=1,reservation_sha256='cd'*32,
                                reservation_states=('signed',))
        with self.assertRaisesRegex(OwnedLifecycleError,'Q05_RESERVATION_IDENTITY_DENIED'):
            _require_same_reservation(before,dropped)
        missing=SimpleNamespace(reservation_count=None,reservation_sha256=None,
                                reservation_states=None)
        with self.assertRaisesRegex(OwnedLifecycleError,'Q05_RESERVATION_IDENTITY_DENIED'):
            _require_same_reservation(missing,missing)
        _require_same_reservation(before,before)
        unread=WalletReadSnapshot('regtest',1,'a'*64,'code',0,0,(),'b'*64)
        self.assertIsNone(unread.reservation_count)
        self.assertIsNone(unread.reservation_sha256)
        self.assertIsNone(unread.reservation_states)

    def test_control_protocol_still_has_no_wallet_password_ops(self):
        from wam_regtest.supervisor_protocol import CONTROL_COMMANDS,READ_COMMANDS
        self.assertFalse({'wallet-create','wallet-unlock','sign','broadcast','scan',
                          'open-owned','managed-gui'} & (CONTROL_COMMANDS|READ_COMMANDS))
