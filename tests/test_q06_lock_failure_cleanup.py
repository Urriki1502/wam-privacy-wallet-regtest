"""Independent close-fault source contracts; not native/frozen custody proof."""
from types import SimpleNamespace
from unittest.mock import Mock,patch
import unittest
from wam_regtest.bip39_spend_session import Q06OwnedSpendSession,Q06SpendSessionError

class LockCleanup(unittest.TestCase):
 def session(self):
  s=Q06OwnedSpendSession.__new__(Q06OwnedSpendSession)
  s._close_rpc=Mock();s.scanner=Mock();s.ring=Mock();s._password=b'public-unit-password'
  s._q06_uncertain=s.faulted=False;s.runtime=Mock()
  s._q06_guard=Mock();s.vault=SimpleNamespace(anchor=Mock(),_expected=(1,'a'*64))
  s.vault.anchor.read.return_value=s.vault._expected
  s._prepared=s._signed=s._review=s._tip=object()
  return s
 def test_independent_cleanup_for_each_fault(self):
  for failed in ('rpc','scanner','ring','anchor','guard_check','guard_close'):
   with self.subTest(failed=failed):
    s=self.session();ring=s.ring;scanner=s.scanner;guard=s._q06_guard
    target={'rpc':s._close_rpc,'scanner':scanner.close,'ring':ring.close,'anchor':s.vault.anchor.read,'guard_check':guard.check,'guard_close':guard.close}[failed]
    target.side_effect=OSError('PRIVATE_TEST_ERROR_MUST_NOT_ESCAPE')
    with patch('wam_regtest.bip39_spend_session._remove_known_scanner_lock') as remove:
     with self.assertRaises(Q06SpendSessionError) as error:s.lock()
    self.assertEqual(error.exception.args,('Q06_SPEND_RUNTIME_PRESERVED',))
    ring.close.assert_called_once();scanner.close.assert_called_once();guard.close.assert_called_once()
    self.assertIsNone(s.ring);self.assertIsNone(s.scanner);self.assertIsNone(s._password)
    self.assertIsNone(s._signed);self.assertTrue(s._q06_uncertain)
    if failed in ('rpc','scanner','ring','anchor','guard_check'):
     remove.assert_not_called();guard.remove_owned.assert_not_called()
 def test_irreversible_or_faulted_session_preserves_runtime(self):
  for field in ('_q06_uncertain','faulted'):
   s=self.session();setattr(s,field,True);guard=s._q06_guard;ring=s.ring
   with patch('wam_regtest.bip39_spend_session._remove_known_scanner_lock') as remove:
    with self.assertRaises(Q06SpendSessionError):s.lock()
   remove.assert_not_called();guard.remove_owned.assert_not_called();ring.close.assert_called_once()
   self.assertTrue(s.locked)
 def test_clean_lock_removes_only_authenticated_owned_runtime(self):
  s=self.session();guard=s._q06_guard
  with patch('wam_regtest.bip39_spend_session._remove_known_scanner_lock') as remove:s.lock()
  remove.assert_called_once_with(s.runtime);guard.check.assert_called_once();guard.remove_owned.assert_called_once()
  self.assertTrue(s.locked);self.assertFalse(s._q06_uncertain)

class UnlockSnapshotRouting(unittest.TestCase):
 def test_seed_only_anchored_unlock_never_autoscans(self):
  from PySide6.QtWidgets import QApplication
  from wam_regtest.bip39_fusion_gui import Bip39FusionWindow
  from wam_regtest.wallet_executor import ExecutorState
  app=QApplication.instance() or QApplication([])
  window=Bip39FusionWindow(SimpleNamespace(state=ExecutorState(locked=False,core_alive=True),busy=False,closed=False))
  try:
   window._on_ready('unlock',dict(backup_status='verified',receive_code='wamrtsp1public',account_id='public',checkpoint_present=True,signer_allowed=False,broadcast_allowed=False))
   self.assertIsNone(window._pending_action)
   self.assertFalse(window._spend_enabled)
   self.assertIsNone(window._last_verified)
  finally:
   window._poll.stop();window.hide();window.deleteLater();app.processEvents()
if __name__=='__main__':unittest.main(verbosity=2)
