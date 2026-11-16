"""Recovery cleanup failure must not strand derived seed bytes; source-only."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import importlib.util,tempfile,unittest
from mnemonic import Mnemonic
from wam_regtest.bip39_12 import Bip39Regtest12Keys
from wam_regtest.bip39_recovery_proof import verify_mnemonic_on_original_chain,Q06RecoveryProofError
SOURCE=Path(importlib.util.find_spec('wam_sp').origin).resolve().parents[2]
class RecoveryClose(unittest.TestCase):
 def test_scanner_close_fault_still_closes_keys_transport_guard(self):
  phrase=Mnemonic('english').to_mnemonic(bytes(16))
  keys=Bip39Regtest12Keys(phrase,source=SOURCE,authorized_disposable=True)
  scanner=Mock();scanner.close.side_effect=OSError('PRIVATE_ERROR_NOT_PUBLIC')
  guard=Mock();rpc=Mock();rpc.attest.side_effect=ValueError('PUBLIC_TEST_ATTEST_FAULT')
  baseline=SimpleNamespace(chain='regtest',signer_allowed=True,history_count=0,history_sha256='0'*64,receive_code=keys.public_metadata()['receive_code'])
  with tempfile.TemporaryDirectory() as directory:
   # Source-only close-fault test: native directory custody is exercised by
   # the real Core/frozen probe, not this synthetic scanner fixture.
   with (patch('wam_regtest.bip39_recovery_proof._owned'),patch('wam_regtest.bip39_recovery_proof.Bip39Regtest12Keys',return_value=keys),patch('wam_sp.scanner.Scanner',return_value=scanner),patch('wam_regtest.bip39_recovery_proof.RuntimeGuard',return_value=guard),patch('wam_regtest.bip39_recovery_proof.WalletCoreCli',return_value=rpc),patch('wam_regtest.bip39_recovery_proof.custody.create_directory',side_effect=lambda p:p.mkdir(mode=0o700))):
    try:
     with self.assertRaises(Q06RecoveryProofError):verify_mnemonic_on_original_chain(SimpleNamespace(directory=Path(directory).resolve(),cli=Path("/public-test-cli")),SOURCE,phrase,baseline)
    finally:
     closed=keys._closed;zero=not any(keys._seed);keys.close()
   self.assertTrue(closed);self.assertTrue(zero)
   rpc._transport.close.assert_called_once();guard.close.assert_called_once();guard.remove_owned.assert_not_called()
if __name__=='__main__':unittest.main()
