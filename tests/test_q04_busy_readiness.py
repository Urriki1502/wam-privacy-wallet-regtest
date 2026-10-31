"""Supplemental readiness/error tests; never synthesize genuine-Core PASS."""
import contextlib
import io
from pathlib import Path
import sys
import threading
import tempfile
from concurrent.futures import Future
import unittest
from unittest.mock import patch

from wam_regtest.q04_busy_probe import _wait_for_saturation, _wait_for_worker
from wam_regtest.rpc_contention import RpcContentionError


class BusyReadinessContracts(unittest.TestCase):
    def test_worker_requires_new_method_log_and_live_request(self):
        with tempfile.TemporaryDirectory() as root:
            log=Path(root)/'debug.log'
            old=b'ThreadRPCServer method=waitforblockheight user=fixture\n'
            log.write_bytes(old)
            first=Future()
            with self.assertRaisesRegex(RpcContentionError,'Q04_BUSY_WORKER_NOT_OCCUPIED'):
                _wait_for_worker(log,len(old),first,timeout=0)
            with log.open('ab') as out:out.write(old)
            _wait_for_worker(log,len(old),first,timeout=0)
            first.set_result(None)
            with self.assertRaisesRegex(RpcContentionError,'Q04_BUSY_WORKER_NOT_OCCUPIED'):
                _wait_for_worker(log,len(old),first,timeout=0)

    def test_worker_waits_for_actual_dequeue_and_propagates_load_error(self):
        with tempfile.TemporaryDirectory() as root:
            log=Path(root)/'debug.log';log.write_bytes(b'')
            first=Future()
            def dequeued(_):
                log.write_bytes(b'ThreadRPCServer method=waitforblockheight user=fixture\n')
            with patch('wam_regtest.q04_busy_probe.time.sleep',side_effect=dequeued) as wait:
                _wait_for_worker(log,0,first)
            wait.assert_called_once()
            first.set_exception(RpcContentionError('Q04_BUSY_LOAD_DENIED'))
            with self.assertRaisesRegex(RpcContentionError,'Q04_BUSY_LOAD_DENIED'):
                _wait_for_worker(log,0,first)

    def test_worker_diagnostics_have_a_strict_read_bound(self):
        with tempfile.TemporaryDirectory() as root:
            log=Path(root)/'debug.log';log.write_bytes(b'x'*65537)
            with self.assertRaisesRegex(RpcContentionError,'Q04_BUSY_WORKER_LOG_LIMIT'):
                _wait_for_worker(log,0,Future())

    def test_transport_unreachable_is_not_fabricated_busy_evidence(self):
        from wam_regtest.rpc_contention import ContentionAwareRpc
        from wam_regtest.external_core import ExternalAttachmentError
        from unittest.mock import Mock
        read=Mock(side_effect=ExternalAttachmentError('EXTERNAL_ATTACHMENT_RPC_UNREACHABLE'))
        rpc=ContentionAwareRpc(read)
        with self.assertRaises(ExternalAttachmentError):rpc.read('getblockcount',[])
        self.assertEqual(read.call_count,1)
        self.assertFalse(rpc.status()['busy'])

    def test_partial_transmission_or_no_real_rejection_is_not_ready(self):
        for complete,rejected in ((False,True),(True,False),(False,False)):
            sent=[threading.Event() for _ in range(6)];busy=threading.Event()
            for event in sent[:6 if complete else 5]:event.set()
            if rejected:busy.set()
            with self.assertRaisesRegex(RpcContentionError,'Q04_BUSY_LOAD_NOT_SATURATED'):
                _wait_for_saturation(sent,busy,timeout=0)

    def test_late_request_dispatch_waits_for_evidence(self):
        sent=[threading.Event() for _ in range(6)];busy=threading.Event()
        for event in sent[:5]:event.set()
        def progress(_):sent[5].set();busy.set()
        with patch('wam_regtest.q04_busy_probe.time.sleep',side_effect=progress) as wait:
            _wait_for_saturation(sent,busy)
        wait.assert_called_once()

    def test_frozen_linux_exposes_only_fixed_contention_code_and_still_fails(self):
        from wam_regtest.linux_package_entry import main
        for error,expected in ((RpcContentionError('Q04_BUSY_NOT_OBSERVED'),'Q04_BUSY_NOT_OBSERVED'),
            (RpcContentionError('Q04_BUSY_NOT_OBSERVED /private secret'),'LINUX_FROZEN_UNCLASSIFIED')):
            out=io.StringIO()
            with patch.object(sys,'platform','linux'),patch.object(sys,'frozen',True,create=True), \
                 patch.object(sys,'_MEIPASS',str(Path.cwd()),create=True), \
                 patch('platform.machine',return_value='x86_64'), \
                 patch('wam_regtest.wsp_live._pinned_source',side_effect=error), \
                 contextlib.redirect_stderr(out):
                self.assertEqual(main(),2)
            self.assertEqual(out.getvalue(),'LINUX_FROZEN_WALLET_DENIED:'+expected+'\n')
