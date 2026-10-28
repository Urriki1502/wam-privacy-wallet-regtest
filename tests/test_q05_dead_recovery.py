"""Same-owner recovery capability tests; no mock Core acceptance."""
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

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

    def test_no_consent_or_new_owner_cannot_adopt_recorded_pid(self):
        owner=self.owner();self.exited_child(owner)
        with patch.object(owner,'start') as start:
            with self.assertRaises(module.ManagedCoreError):owner.recover_dead()
            owner.close();other=self.owner()
            with self.assertRaises(module.ManagedCoreError):other.recover_dead(authorized=True)
            start.assert_not_called()

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

