"""Q06 GUI uses immutable executor safety state alongside last scope result."""
from types import SimpleNamespace
import importlib.util
import os
import sys
import unittest
from wam_regtest.gui_errors import operation_error,error_text
from wam_regtest.wallet_executor import WalletExecutorError,ExecutorState
class PublicQ06Errors(unittest.TestCase):
 def test_exact_checkpoint_and_seed_categories_only(self):
  code='Q06_GUI_ANCHORED_SCANNER_REQUIRES_RECONCILIATION'
  self.assertEqual(operation_error('snapshot',WalletExecutorError(code)),'WALLET_NATIVE_CHECKPOINT_VERIFICATION_REQUIRED')
  self.assertEqual(operation_error('unlock',WalletExecutorError('Q06_SEED_REOPEN_DENIED')),'WALLET_UNLOCK_REFUSED')
  self.assertNotEqual(operation_error('broadcast',WalletExecutorError(code)),'WALLET_NATIVE_CHECKPOINT_VERIFICATION_REQUIRED')
  self.assertNotIn('PRIVATE_MARKER',error_text(operation_error('unlock',WalletExecutorError('Q06_SEED_REOPEN_DENIED PRIVATE_MARKER'))))
if sys.platform == 'linux' and not os.environ.get('DISPLAY'):
 os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

@unittest.skipUnless(importlib.util.find_spec('PySide6') is not None,
                     'Qt surface only; native/frozen GUI proof remains required')
class BackendSafetyUi(unittest.TestCase):
 def setUp(self):
  from PySide6.QtWidgets import QApplication
  from wam_regtest.bip39_fusion_gui import Bip39FusionWindow
  self.app=QApplication.instance() or QApplication([])
  self.owner=SimpleNamespace(state=ExecutorState(locked=False,core_alive=True),busy=False,closed=False)
  self.window=Bip39FusionWindow(self.owner);self.window._ready=True;self.window._spend_enabled=True
 def tearDown(self):
  self.window._poll.stop();self.window.hide();self.window.deleteLater();self.app.processEvents()
 def test_cached_spend_flag_cannot_override_backend_safety(self):
  for state in [ExecutorState(locked=True,core_alive=True),ExecutorState(locked=False,core_alive=False),ExecutorState(locked=False,core_alive=None),ExecutorState(locked=False,core_alive=True,reauthentication_required=True)]:
   with self.subTest(state=state):
    self.owner.state=state;self.window._set_actions()
    self.assertFalse(self.window.send.isEnabled());self.assertFalse(self.window.overview.go_send.isEnabled())
    self.window._signed_ready=True;self.window._approved_commitment='a'*64;self.window._set_actions()
    self.assertFalse(self.window.broadcast.isEnabled());self.assertFalse(self.window.cancel.isEnabled())
    self.window._signed_ready=False;self.window._approved_commitment=None
 def test_authenticated_unlocked_core_keeps_existing_spend_controls(self):
  self.window._set_actions();self.assertTrue(self.window.send.isEnabled());self.assertTrue(self.window.overview.go_send.isEnabled())
 def test_denial_never_displays_or_retains_unregistered_private_text(self):
  commitment='a'*64;self.window._approved_commitment=commitment
  self.window._on_denied('UNREGISTERED_PRIVATE_MARKER')
  self.assertNotIn('PRIVATE_MARKER',self.window.status.text());self.assertNotIn('PRIVATE_MARKER',self.window._last_error_code)
  self.assertEqual(self.window._approved_commitment,commitment)
 def test_core_loss_keeps_signed_review_without_replay_or_false_empty_state(self):
  self.owner.state=ExecutorState(locked=False,core_alive=False)
  self.window._approved_commitment='b'*64;self.window._signed_ready=True
  self.window._on_denied('WALLET_CORE_UNAVAILABLE')
  self.assertEqual(self.window._approved_commitment,'b'*64)
  self.assertTrue(self.window._signed_ready)
  self.assertIn('Payment state retained',self.window.review_summary.text())
  self.assertFalse(self.window.broadcast.isEnabled())
  self.assertIsNone(self.window._pending_action)
 def test_initial_open_password_refusal_exposes_only_explicit_authenticated_retry(self):
  self.owner.state=ExecutorState(locked=True,core_alive=True)
  self.window._ready=self.window._spend_enabled=False
  self.window._on_denied('WALLET_UNLOCK_REFUSED')
  self.assertTrue(self.window.unlock.isEnabled())
  self.assertTrue(self.owner.state.locked)
  self.assertFalse(self.window._spend_enabled)
  self.assertIsNone(self.window._pending_action)
if __name__=='__main__':unittest.main(verbosity=2)
