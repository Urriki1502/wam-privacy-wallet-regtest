"""Public error categories must never expose arbitrary exceptions or authorize work."""
import unittest
from wam_regtest.gui_errors import operation_error,error_text,INPUT_ERRORS

class ErrorPrivacy(unittest.TestCase):
 def test_arbitrary_exception_text_is_not_displayed_or_even_formatted(self):
  class Hostile(RuntimeError):
   def __str__(self):raise AssertionError('external exception formatted')
  self.assertEqual(operation_error('prepare',Hostile('rpcpassword=private-test-marker')),'WALLET_OPERATION_DENIED_STATE_RETAINED')
  self.assertNotIn('private-test-marker',error_text('rpcpassword=private-test-marker'))
 def test_valid_prefix_with_private_suffix_is_not_a_public_error(self):
  code=operation_error('prepare',ValueError('INSUFFICIENT_SINGLE_CLUSTER_FUNDS rpcpassword=private-test-marker'))
  self.assertNotIn(code,INPUT_ERRORS)
  self.assertNotIn('private-test-marker',error_text(code))
 def test_native_validation_category_is_scoped_to_prepare(self):
  code=operation_error('prepare',ValueError('INSUFFICIENT_SINGLE_CLUSTER_FUNDS'))
  self.assertIn(code,INPUT_ERRORS)
  self.assertNotIn(operation_error('broadcast',ValueError('INSUFFICIENT_SINGLE_CLUSTER_FUNDS')),INPUT_ERRORS)
 def test_history_snapshot_failures_are_public_and_not_generic(self):
  from wam_regtest.wallet_session import WalletSessionError
  for code in ('WALLET_HISTORY_INCONSISTENT','WALLET_HISTORY_INCOMPLETE',
               'WALLET_RESERVATION_INCONSISTENT',
               'WALLET_OWNED_OPEN_DENIED','MANAGED_WALLET_EXISTING_RUNTIME_DENIED'):
   self.assertEqual(operation_error('sync',WalletSessionError(code)),code)
   self.assertNotIn('traceback',error_text(code).lower())
 def test_unknown_long_or_non_string_codes_have_constant_fallback(self):
  fallback=error_text('UNKNOWN')
  for code in (None,1,object(),'x'*10000,'/private/user/wallet.sqlite'):
   self.assertEqual(error_text(code),fallback)

if __name__=='__main__':unittest.main()
