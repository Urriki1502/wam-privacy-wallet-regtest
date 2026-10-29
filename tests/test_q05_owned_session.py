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

    def test_control_protocol_still_has_no_wallet_password_ops(self):
        from wam_regtest.supervisor_protocol import CONTROL_COMMANDS,READ_COMMANDS
        self.assertFalse({'wallet-create','wallet-unlock','sign','broadcast','scan',
                          'open-owned','managed-gui'} & (CONTROL_COMMANDS|READ_COMMANDS))
