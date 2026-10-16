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
 def test_exact_transport_categories_are_actionable_without_secret_echo(self):
  from wam_regtest.json_rpc import RpcError
  for code in ('RPC_NODE_BUSY','RPC_AUTHENTICATION_DENIED','RPC_SESSION_CLOSED','RPC_CONNECTION_UNCERTAIN_READ_FAILED'):
   self.assertEqual(operation_error('sync',RpcError(code)),code)
   self.assertNotIn('private-test-marker',error_text(code))
   self.assertEqual(operation_error('sync',RpcError(code+' private-test-marker')),'WALLET_SYNC_UNVERIFIED')
 def test_unknown_long_or_non_string_codes_have_constant_fallback(self):
  fallback=error_text('UNKNOWN')
  for code in (None,1,object(),'x'*10000,'/private/user/wallet.sqlite'):
   self.assertEqual(error_text(code),fallback)

if __name__=='__main__':unittest.main()
