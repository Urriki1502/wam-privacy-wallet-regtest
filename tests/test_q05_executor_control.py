"""Actual HMAC control socket routes only finite commands to owner thread.

Core startup is mocked; no wallet secret/control capability or Core PASS claimed.
"""
import threading
import time
import unittest
from unittest.mock import patch

import test_q05_core_supervisor as fixture
from wam_regtest.core_supervisor import CoreSupervisor
from wam_regtest.supervisor_protocol import public_status
from wam_regtest.supervisor_client import control
from wam_regtest.wallet_executor import ManagedWalletBackend,WalletExecutor


class SerializedControlContracts(unittest.TestCase):
    setUp=fixture.SupervisorLifecycleUnit.setUp

    def test_join_waits_for_original_control_listener_before_profile_reopen(self):
        entered, finish = threading.Event(), threading.Event()
        def serve(owner):
            entered.set()
            finish.wait(5)
        with patch.object(CoreSupervisor,'start'), patch.object(CoreSupervisor,'serve',serve):
            executor=WalletExecutor(lambda:ManagedWalletBackend(self.root,self.core,self.core))
            try:
                executor.request('core_start')
                self.assertTrue(entered.wait(2))
                executor.request('quit')
                # Closing a socket while another thread accepts on it can
                # retain its kernel listener until that thread returns.
                self.assertFalse(executor.join(.01))
                finish.set()
                self.assertTrue(executor.join(2))
                self.assertFalse(executor._backend._control_thread.is_alive())
            finally:
                finish.set()
                if not executor.closed:executor.request('quit')
                executor.join()

    def test_authenticated_control_and_release_stay_on_original_executor(self):
        threads=[]
        def status():threads.append(threading.get_ident());return public_status(state='stopped')
        with patch.object(CoreSupervisor,'start'),patch.object(CoreSupervisor,'status',side_effect=status):
            executor=WalletExecutor(lambda:ManagedWalletBackend(self.root,self.core,self.core))
            try:
                executor.request('core_start')
                reply=control(self.root,'status')
                self.assertEqual(reply['state'],'stopped')
                self.assertEqual(set(threads),{executor._thread.ident})
                self.assertNotEqual(executor._thread.ident,threading.get_ident())
                reply=control(self.root,'release',authorized=True)
                self.assertEqual(reply['state'],'stopped')
                deadline=time.monotonic()+3
                while not executor.closed and time.monotonic()<deadline:time.sleep(.01)
                self.assertTrue(executor.closed);self.assertTrue(executor.join())
            finally:
                if not executor.closed:executor.request('quit')
                executor.join()
