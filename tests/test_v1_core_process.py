"""Kernel output parser negatives; no fake Core acceptance."""
import unittest
from wam_regtest.core_process import _lsof_match,OwnedCoreBinding,CoreBindingError
from wam_regtest.json_rpc import ManagedReadRpc,RpcError

class OwnedEndpointContracts(unittest.TestCase):
    def test_exact_server_half_of_established_connection(self):
        data='p123\nf7\nn127.0.0.1:10001->127.0.0.1:20002\nTST=ESTABLISHED\nf8\nn127.0.0.1:10001->127.0.0.1:20003\nTST=ESTABLISHED\n'
        self.assertTrue(_lsof_match(data,123,10001,20002))
        for pid,server,client in [(124,10001,20002),(123,20002,10001),(123,1000,20002),(123,10001,2000)]:
            self.assertFalse(_lsof_match(data,pid,server,client))
        self.assertFalse(_lsof_match(data.replace('ESTABLISHED','LISTEN'),123,10001,20002))

    def test_process_scope_is_required_before_credentials_or_socket(self):
        from pathlib import Path
        with self.assertRaises(CoreBindingError):OwnedCoreBinding(None,Path('/missing'),Path('/missing'))
        with self.assertRaisesRegex(RpcError,'^RPC_MANAGED_PROCESS_REQUIRED$'):
            ManagedReadRpc(None,None,authorized_readonly=True)
