"""Owned-session attach contracts; not genuine Core E2E."""
from pathlib import Path
from unittest.mock import patch
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

    def test_cli_wires_in_process_managed_gui_not_control_wallet_ops(self):
        text=(Path(__file__).resolve().parents[1]/'src/wam_regtest/cli.py').read_text()
        self.assertIn("'managed-gui'",text)
        self.assertIn('launch_owned_wallet',text)
        self.assertIn('open_owned',Path(__file__).resolve().parents[1]
                      .joinpath('src/wam_regtest/wallet_session.py').read_text())
        from wam_regtest.supervisor_protocol import CONTROL_COMMANDS
        self.assertNotIn('managed-gui',CONTROL_COMMANDS)

    def test_cli_wires_in_process_managed_gui_not_control_wallet_ops_probe_exists(self):
        probe=Path(__file__).resolve().parents[1]/'scripts/probe_q05_owned_session.py'
        source=probe.read_text()
        self.assertIn('WalletSession.open_owned',source)
        self.assertIn('wallet_lock_left_core_running',source)
        self.assertNotIn('owner.shutdown()',source.split('LOCK_WITHOUT_CORE_SHUTDOWN')[1].split('CORE_REOPEN')[0])

    def test_control_protocol_still_has_no_wallet_password_ops(self):
        from wam_regtest.supervisor_protocol import CONTROL_COMMANDS,READ_COMMANDS
        self.assertFalse({'wallet-create','wallet-unlock','sign','broadcast','scan',
                          'open-owned','managed-gui'} & (CONTROL_COMMANDS|READ_COMMANDS))
