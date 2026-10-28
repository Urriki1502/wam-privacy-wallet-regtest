"""Supplemental readiness/error tests; never synthesize genuine-Core PASS."""
import contextlib
import io
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

from wam_regtest.q04_busy_probe import _wait_for_saturation
from wam_regtest.rpc_contention import RpcContentionError


class BusyReadinessContracts(unittest.TestCase):
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
