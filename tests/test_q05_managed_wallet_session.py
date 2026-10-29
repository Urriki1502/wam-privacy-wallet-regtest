"""Managed session boundaries; genuine Core proof is a separate native probe."""
from pathlib import Path
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import MagicMock,Mock,patch

import test_q05_core_supervisor as fixture
from wam_regtest import managed_wallet_session as module
from wam_regtest.wallet_session import WalletSession,WalletSessionError


class ManagedSessionContracts(unittest.TestCase):
    setUp=fixture.SupervisorLifecycleUnit.setUp
    owner=fixture.SupervisorLifecycleUnit.owner

    def runtime(self):
        path=self.root/'wallet-runtime.sqlite';path.write_bytes(b'owned-test-runtime');path.chmod(0o600)
        return path

    def test_consent_and_foreign_owner_before_keys_or_runtime(self):
        for authorized in (False,True):
            with self.assertRaises(WalletSessionError):
                WalletSession.open_owned(object(),self.core,b'public-test-password',authorized=authorized)
        self.assertEqual(list(self.root.iterdir()),[])

    def test_create_cannot_ignore_recovery_residue_or_missing_reference(self):
        owner=self.owner();residue=self.root/'supervisor.recovery.000001';residue.write_bytes(b'preserve')
        with patch.object(module,'_inputs'):
            with self.assertRaises(WalletSessionError):
                WalletSession.open_owned(owner,self.core,b'public-test-password',authorized=True,create=True)
        self.assertEqual(residue.read_bytes(),b'preserve')
        self.assertFalse((owner.directory/'wallet-vault').exists())

    def test_pending_reference_is_not_opened_as_original_container(self):
        owner=self.owner()
        from wam_regtest.managed_wallet_checkpoint import ManagedWalletError
        with patch.object(module,'_inputs'),patch.object(module,'_read_reference',return_value='a'*32),\
                patch.object(module,'active_location',side_effect=ManagedWalletError('MANAGED_RECOVERY_PENDING')):
            with self.assertRaises(WalletSessionError):
                WalletSession.open_owned(owner,self.core,b'public-test-password',authorized=True)
        self.assertFalse((owner.directory/'wallet-runtime.sqlite').exists())

    def test_runtime_replacement_is_preserved_instead_of_deleted(self):
        path=self.runtime();guard=module.RuntimeGuard(path);self.addCleanup(guard.close)
        # Windows can correctly pin the live file against rename. Close the
        # native guard only to exercise the separate closed-guard refusal.
        try:path.rename(self.root/'preserved-original')
        except PermissionError:
            guard.close()
        else:path.write_bytes(b'unknown-replacement')
        with self.assertRaises(ValueError):guard.remove_owned()
        if path.exists() and path.read_bytes()==b'unknown-replacement':
            self.assertEqual(path.read_bytes(),b'unknown-replacement')

    def test_runtime_sidecar_is_never_swept(self):
        path=self.runtime();guard=module.RuntimeGuard(path);self.addCleanup(guard.close)
        sidecar=path.with_name(path.name+'-wal');sidecar.write_bytes(b'unknown-sidecar')
        with self.assertRaises(ValueError):guard.remove_owned()
        self.assertEqual(sidecar.read_bytes(),b'unknown-sidecar');self.assertTrue(path.exists())

    def test_known_fresh_runtime_can_close_without_stopping_core(self):
        path=self.runtime();guard=module.RuntimeGuard(path)
        session=self.session(guard);lease=session._managed_lease;module.close_session(session)
        self.assertFalse(path.exists());self.assertIsNone(session.ring)
        lease.__exit__.assert_called_once()
        session._managed_owner.shutdown.assert_not_called()

    def session(self,guard):
        return SimpleNamespace(_managed_thread=threading.get_ident(),locked=False,
            _managed_owner=Mock(),ring=Mock(),scanner=Mock(),_managed_runtime_guard=guard,
            _managed_lease=MagicMock(),_disclosure_gate=None,_close_rpc=Mock(),_password=b'public-test-password')

    def test_wrong_thread_cannot_close_or_release_live_session(self):
        path=self.runtime();guard=module.RuntimeGuard(path);self.addCleanup(guard.close)
        session=self.session(guard);session._managed_thread=-1
        with self.assertRaises(WalletSessionError):module.close_session(session)
        session.scanner.close.assert_not_called();session._managed_lease.__exit__.assert_not_called()
        self.assertTrue(path.exists())

    def test_scanner_close_failure_still_closes_keys_and_lease_preserving_runtime(self):
        path=self.runtime();guard=module.RuntimeGuard(path);session=self.session(guard)
        ring=session.ring;lease=session._managed_lease
        session.scanner.close.side_effect=ValueError('uncertain-close')
        with self.assertRaises(WalletSessionError):module.close_session(session)
        ring.close.assert_called_once();lease.__exit__.assert_called_once();self.assertTrue(path.exists())
