"""Startup refusal/real socket contracts; no mock counts as Core acceptance."""
from pathlib import Path
import socket
import unittest
from wam_regtest.owned_start import disposable_core, _reserved_ports
from wam_regtest.core import CoreSmokeError


class OwnedStartupContracts(unittest.TestCase):
    def test_linux_native_socket_inspection_errors_are_denials_not_ownership(self):
        from unittest.mock import patch
        from wam_regtest.core_process import _linux_socket, CoreBindingError
        for error in (PermissionError('PRIVATE_CANARY'), FileNotFoundError('PRIVATE_CANARY')):
            with patch('wam_regtest.core_process.Path.iterdir', side_effect=error):
                with self.assertRaisesRegex(CoreBindingError, '^RPC_NATIVE_SOCKET_PROOF_DENIED$'):
                    _linux_socket(123, 12345, 12346)
        with patch('wam_regtest.core_process.Path.iterdir', return_value=iter(())), \
             patch('wam_regtest.core_process.Path.read_text', side_effect=PermissionError('PRIVATE_CANARY')):
            with self.assertRaisesRegex(CoreBindingError, '^RPC_NATIVE_SOCKET_PROOF_DENIED$'):
                _linux_socket(123, 12345, 12346)

    def test_live_child_native_socket_denial_never_creates_authenticated_client(self):
        from types import SimpleNamespace
        from unittest.mock import Mock, MagicMock, patch
        from wam_regtest.core_process import CoreBindingError
        from wam_regtest.owned_start import _ready
        import subprocess
        binding=SimpleNamespace(process=Mock(), directory=Path('/not-opened'),
            core=Path('/not-opened'), assert_socket=Mock(
                side_effect=CoreBindingError('RPC_NATIVE_SOCKET_PROOF_DENIED')))
        binding.process.poll.return_value=None
        binding.process.wait.side_effect=subprocess.TimeoutExpired('public-test-child', 1)
        with patch('wam_regtest.owned_start.socket.create_connection', return_value=MagicMock()), \
             patch('wam_regtest.owned_start.time.monotonic', return_value=1), \
             patch('wam_regtest.owned_start.ManagedReadRpc') as client:
            with self.assertRaisesRegex(CoreSmokeError, '^CORE_START_ENDPOINT_OWNERSHIP_DENIED$'):
                _ready(binding, 12345, 100)
            client.assert_not_called()
            binding.assert_socket.assert_called_once()

    @unittest.skipUnless(__import__('sys').platform == 'linux', 'native Linux kernel permission case')
    def test_actual_nondumpable_child_fd_denial_remains_closed(self):
        # Real kernel access denial, not Core or blockchain acceptance.
        import select
        import subprocess
        import sys
        from wam_regtest.core_process import _linux_socket, CoreBindingError
        code=('import ctypes,sys;lib=ctypes.CDLL(None);'
              'assert lib.prctl(4,0,0,0,0)==0;'
              'print("NONDUMPABLE_TEST_CHILD",flush=True);sys.stdin.buffer.read(1)')
        child=subprocess.Popen([sys.executable, '-c', code], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            self.assertTrue(select.select([child.stdout], [], [], 10)[0])
            self.assertEqual(child.stdout.readline(128), b'NONDUMPABLE_TEST_CHILD\n')
            with self.assertRaisesRegex(CoreBindingError, '^RPC_NATIVE_SOCKET_PROOF_DENIED$'):
                _linux_socket(child.pid, 12345, 12346)
        finally:
            child.stdin.close()
            if child.poll() is None:
                try:child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill();child.wait(timeout=5)
            child.stdout.close()

    def test_process_exit_during_native_image_lookup_remains_an_ownership_denial(self):
        from unittest.mock import Mock, patch
        from wam_regtest.core_process import OwnedCoreBinding, CoreBindingError
        binding=object.__new__(OwnedCoreBinding)
        binding.process=Mock(args=['public-fixture'],pid=123)
        binding.process.poll.return_value=None
        binding._argv=['public-fixture'];binding.directory=Path('/not-opened')
        with patch('wam_regtest.core_process._image',side_effect=FileNotFoundError('PRIVATE_CANARY')):
            with self.assertRaisesRegex(CoreBindingError,'^RPC_PROCESS_IMAGE_DENIED$'):
                binding._assert_image()

    def test_tcp_timeout_before_any_auth_may_wait_but_permissions_never_authenticate(self):
        from types import SimpleNamespace
        from unittest.mock import Mock,MagicMock,patch
        from wam_regtest.owned_start import _ready
        binding=SimpleNamespace(process=Mock(),directory=Path('/not-opened'),core=Path('/not-opened'),assert_socket=Mock())
        binding.process.poll.return_value=None
        read=Mock();read.attest.return_value={'blocks':0}
        with patch('wam_regtest.owned_start.socket.create_connection',side_effect=[socket.timeout(),MagicMock()]) as connect, \
             patch('wam_regtest.owned_start.time.monotonic',return_value=1), \
             patch('wam_regtest.owned_start.time.sleep'), \
             patch('wam_regtest.owned_start.ManagedReadRpc',return_value=read) as client:
            self.assertIs(_ready(binding,12345,100),read)
            self.assertEqual(connect.call_count,2);client.assert_called_once();binding.assert_socket.assert_called_once()
        with patch('wam_regtest.owned_start.socket.create_connection',side_effect=PermissionError(13,'PRIVATE_CANARY')), \
             patch('wam_regtest.owned_start.time.monotonic',return_value=1), \
             patch('wam_regtest.owned_start.ManagedReadRpc') as client:
            with self.assertRaisesRegex(CoreSmokeError,'^CORE_START_TCP_PROBE_DENIED_13$'):_ready(binding,12345,100)
            client.assert_not_called()

    def test_consent_scope_and_budget_fail_before_any_process(self):
        for consent in (False,None,1,'yes'):
            with self.assertRaisesRegex(CoreSmokeError,'^CORE_START_EXPLICIT_DISPOSABLE_CONSENT_REQUIRED$'):
                with disposable_core(None,authorized=consent):self.fail('unexpected process')
        for timeout in (True,0,241,float('inf'),float('nan'),'90'):
            with self.assertRaisesRegex(CoreSmokeError,'^CORE_START_TIMEOUT_DENIED$'):
                with disposable_core(None,authorized=True,timeout=timeout):self.fail('unexpected process')
        for path in (None,'/not-a-path-object',Path('relative')):
            with self.assertRaisesRegex(CoreSmokeError,'^CORE_START_PATH_DENIED$'):
                with disposable_core(path,authorized=True):self.fail('unexpected process')

    def test_ports_are_distinct_and_held_until_config_publication_finishes(self):
        for _ in range(10):
            with _reserved_ports() as ports:
                self.assertEqual(len(set(ports)),2)
                for port in ports:
                    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as contender:
                        with self.assertRaises(OSError):contender.bind(('127.0.0.1',port))

    def test_no_existing_datadir_or_endpoint_attachment_arguments(self):
        for arg in ('datadir','endpoint','config','wallet','process'):
            with self.assertRaises(TypeError):
                with disposable_core(Path('/not-opened'),authorized=True,**{arg:'owner'}):pass

    def test_only_positive_startup_warmup_is_bounded_and_other_failures_not_replayed(self):
        from types import SimpleNamespace
        from unittest.mock import Mock,MagicMock,patch
        from wam_regtest.owned_start import _ready
        from wam_regtest.json_rpc import RpcError
        binding=SimpleNamespace(process=Mock(),directory=Path('/not-opened'),core=Path('/not-opened'),assert_socket=Mock())
        binding.process.poll.return_value=None
        with patch('wam_regtest.owned_start.socket.create_connection',return_value=MagicMock()), \
             patch('wam_regtest.owned_start.time.monotonic',return_value=1), \
             patch('wam_regtest.owned_start.time.sleep'), \
             patch('wam_regtest.owned_start.ManagedReadRpc',side_effect=RpcError('RPC_CORE_WARMUP')) as client:
            with self.assertRaisesRegex(CoreSmokeError,'^CORE_START_WARMUP_LIMIT$'):_ready(binding,12345,100)
            self.assertEqual(client.call_count,30)
        for code in ('RPC_AUTHENTICATION_DENIED','RPC_CONNECTION_UNCERTAIN_READ_FAILED','RPC_REPLY_INVALID','RPC_CORE_READ_REFUSED'):
            with patch('wam_regtest.owned_start.socket.create_connection',return_value=MagicMock()), \
                 patch('wam_regtest.owned_start.time.monotonic',return_value=1), \
                 patch('wam_regtest.owned_start.ManagedReadRpc',side_effect=RpcError(code)) as client:
                with self.assertRaisesRegex(RpcError,'^'+code+'$'):_ready(binding,12345,100)
                self.assertEqual(client.call_count,1)
