"""Same-owner recovery capability tests; no mock Core acceptance."""
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock,Mock,patch

import test_q05_core_supervisor as fixture
from wam_regtest import core_supervisor as module


class DeadRecoveryContracts(unittest.TestCase):
    setUp=fixture.SupervisorLifecycleUnit.setUp
    owner=fixture.SupervisorLifecycleUnit.owner

    def exited_child(self,owner):
        child=subprocess.Popen([sys.executable,'-c','pass'],stdout=subprocess.DEVNULL)
        child.wait(timeout=5)
        owner.process=child;owner.binding=Mock(spec=module.OwnedCoreBinding)
        owner.binding.process=child;owner._registered=True;owner._faulted=True
        owner.journal.append('STARTING');owner.journal.append('RUNNING',child.pid)
        owner.journal.append('FAULT',child.pid)
        return child

    def test_dead_original_handle_can_request_one_scoped_recovery(self):
        owner=self.owner();child=self.exited_child(owner)
        owner._height_snapshot=101
        with patch.object(module,'identity',return_value=SimpleNamespace(binding=SimpleNamespace(process=child))), \
             patch.object(module,'unregister'),patch.object(owner,'start') as start:
            owner.recover_dead(authorized=True)
            start.assert_called_once_with(_recovering=True)
        self.assertEqual(owner._minimum_recovery_height,101)
        self.assertEqual(owner.journal.state,'RECOVERING')

    def test_missing_context_or_other_process_never_launches(self):
        owner=self.owner();child=self.exited_child(owner)
        for scope in (None,SimpleNamespace(binding=SimpleNamespace(process=object()))):
            with patch.object(module,'identity',return_value=scope),patch.object(owner,'start') as start:
                with self.assertRaises(module.ManagedCoreError):owner.recover_dead(authorized=True)
                start.assert_not_called()

    def test_prior_cycle_pid_reuse_cannot_authorize_unattested_launch(self):
        owner=self.owner();child=self.exited_child(owner)
        owner.journal.append('STOPPING',child.pid);owner.journal.append('CLEAN')
        # Model PID reuse after a successful earlier cycle. The current launch
        # failed before RUNNING, so old same-owner/same-PID evidence is stale.
        owner.journal.append('STARTING');owner.journal.append('FAULT',child.pid)
        with patch.object(module,'identity',return_value=SimpleNamespace(binding=SimpleNamespace(process=child))), \
             patch.object(owner,'start') as start:
            with self.assertRaisesRegex(module.ManagedCoreError,'MANAGED_RECOVERY_ATTESTED_CHILD_REQUIRED'):
                owner.recover_dead(authorized=True)
            start.assert_not_called()
        self.assertEqual(owner.journal.state,'FAULT')

    def test_no_consent_or_new_owner_cannot_adopt_recorded_pid(self):
        owner=self.owner();self.exited_child(owner)
        with patch.object(owner,'start') as start:
            with self.assertRaises(module.ManagedCoreError):owner.recover_dead()
            owner.close();other=self.owner()
            with self.assertRaises(module.ManagedCoreError):other.recover_dead(authorized=True)
            start.assert_not_called()

    def test_recovery_boot_waits_until_the_same_child_reaches_the_attested_tip(self):
        owner=self.owner()
        owner.journal.append('STARTING')
        owner.journal.append('RUNNING',4242)
        owner.journal.append('RECOVERING',4242)
        owner._minimum_recovery_height=101
        owner._faulted=False
        child=Mock();child.pid=5151;child.poll.return_value=None
        self.addCleanup(lambda: child.poll.return_value if child.poll.return_value==0 else setattr(child.poll,'return_value',0))
        binding=Mock();binding.process=child
        binding.assert_socket=Mock();binding._assert_image=Mock()
        rpc=Mock();rpc.call.side_effect=(
            {'blocks':0,'initialblockdownload':True},
            {'blocks':101,'initialblockdownload':False})
        with patch.object(module.subprocess,'Popen',return_value=child) as popen, \
             patch.object(module,'OwnedCoreBinding',return_value=binding), \
             patch.object(module,'register'), \
             patch.object(module.socket,'create_connection',return_value=MagicMock()), \
             patch.object(module,'_read_cli'), \
             patch.object(module,'ManagedReadRpc',return_value=rpc), \
             patch.object(module.time,'sleep'):
            owner.start(timeout=90,_recovering=True)
        popen.assert_called_once()
        self.assertIs(owner.process,child)
        self.assertEqual(owner.state,'ready')
        self.assertEqual(owner._height_snapshot,101)
        self.assertEqual(rpc.call.call_count,2)
        self.assertEqual(owner.journal.state,'RUNNING')

    def test_recovery_boot_failure_is_dirty_and_never_auto_retried(self):
        owner=self.owner();child=self.exited_child(owner)
        with patch.object(module,'identity',return_value=SimpleNamespace(binding=SimpleNamespace(process=child))), \
             patch.object(module,'unregister'), \
             patch.object(owner,'start',side_effect=module.ManagedCoreError('MANAGED_START_TIMEOUT')) as start:
            with self.assertRaises(module.ManagedCoreError):owner.recover_dead(authorized=True)
            self.assertEqual(start.call_count,1)
        self.assertTrue(owner._faulted);self.assertEqual(owner.journal.state,'FAULT')

    def test_release_never_relinquishes_live_child(self):
        owner=self.owner();process=Mock();process.poll.return_value=None;owner.process=process
        with self.assertRaises(module.ManagedCoreError):owner.release()
        self.assertFalse(owner._release_requested)
        process.poll.return_value=0

