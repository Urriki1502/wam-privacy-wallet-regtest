"""Startup refusal/real socket contracts; no mock counts as Core acceptance."""
from pathlib import Path
import socket
import unittest
from wam_regtest.owned_start import disposable_core, _reserved_ports
from wam_regtest.core import CoreSmokeError


class OwnedStartupContracts(unittest.TestCase):
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
