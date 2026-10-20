"""Kernel output parser negatives; no fake Core acceptance."""
import unittest
from pathlib import Path
from unittest.mock import patch
from wam_regtest.core_process import _lsof_match,_linux_socket,OwnedCoreBinding,CoreBindingError
from wam_regtest.json_rpc import ManagedReadRpc,RpcError

class OwnedEndpointContracts(unittest.TestCase):
    def test_exact_server_half_of_established_connection(self):
        data='p123\nf7\nn127.0.0.1:10001->127.0.0.1:20002\nTST=ESTABLISHED\nf8\nn127.0.0.1:10001->127.0.0.1:20003\nTST=ESTABLISHED\n'
        self.assertTrue(_lsof_match(data,123,10001,20002))
        for pid,server,client in [(124,10001,20002),(123,20002,10001),(123,1000,20002),(123,10001,2000)]:
            self.assertFalse(_lsof_match(data,pid,server,client))
        self.assertFalse(_lsof_match(data.replace('ESTABLISHED','LISTEN'),123,10001,20002))

    def test_linux_proc_fd_permission_error_fails_closed(self):
        original=Path.iterdir
        def denied(path):
            if str(path)=='/proc/123/fd':
                raise PermissionError(13,'private')
            yield from original(path)
        with patch.object(Path,'iterdir',denied), patch.object(Path,'read_text') as read_text:
            self.assertFalse(_linux_socket(123,10001,20002))
            read_text.assert_not_called()

    def test_linux_proc_tcp_permission_error_fails_closed(self):
        with patch.object(Path,'iterdir',lambda self: iter(())), patch.object(Path,'read_text',side_effect=PermissionError(13,'private')):
            self.assertFalse(_linux_socket(123,10001,20002))

    def test_process_scope_is_required_before_credentials_or_socket(self):
        from pathlib import Path
        with self.assertRaises(CoreBindingError):OwnedCoreBinding(None,Path('/missing'),Path('/missing'))
        with self.assertRaisesRegex(RpcError,'^RPC_MANAGED_PROCESS_REQUIRED$'):
            ManagedReadRpc(None,None,authorized_readonly=True)
