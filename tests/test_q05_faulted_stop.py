"""Original-Popen recovery gates; fixtures do not qualify genuine Core."""
import json
import subprocess
import sys
import unittest
from unittest.mock import Mock,patch

import test_q05_core_supervisor as fixture
from wam_regtest import core_supervisor as module
from wam_regtest.core_process import CoreBindingError
from wam_regtest.supervisor_store import read_exact
from wam_regtest.json_rpc import RpcError


class FaultedOwnerContracts(unittest.TestCase):
    setUp=fixture.SupervisorLifecycleUnit.setUp
    owner=fixture.SupervisorLifecycleUnit.owner

    def test_failure_diagnostic_is_fixed_private_and_create_only(self):
        owner=self.owner()
        owner._record_failure('start',RpcError('RPC_HTTP_DENIED'))
        raw=read_exact(self.root,'supervisor.failure')
        self.assertEqual(json.loads(raw),{'stage':'start','code':'RPC_HTTP_DENIED'})
        owner._record_failure('start',ValueError('secret credential /private/path'))
        self.assertEqual(read_exact(self.root,'supervisor.failure'),raw)

    def test_unknown_diagnostic_never_echoes_exception(self):
        owner=self.owner()
        owner._record_failure('start',RpcError('SECRET_AUTH_TOKEN'))
        raw=read_exact(self.root,'supervisor.failure')
        self.assertNotIn(b'SECRET',raw)
        self.assertEqual(json.loads(raw)['code'],'MANAGED_UNCLASSIFIED_FAILURE')

    def test_foreign_or_missing_handle_never_reaches_stop(self):
        owner=self.owner();owner.process=Mock();owner.process.poll.return_value=0
        owner._registered=True
        with patch.object(module,'_read_cli') as stop:
            with self.assertRaises(module.ManagedCoreError):owner.recover_stop()
            stop.assert_not_called()

    def child(self,owner):
        child=subprocess.Popen([sys.executable,'-c','import sys;sys.stdin.buffer.read()'],
            stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        def cleanup():
            if not child.stdin.closed:child.stdin.close()
            child.wait(timeout=5)
        self.addCleanup(cleanup)
        owner.process=child;owner._registered=True;owner._faulted=True
        owner.journal.append('STARTING')
        owner.journal.append('FAULT',child.pid)
        return child

    def test_original_popen_requires_fresh_native_and_chain_attestation_before_stop(self):
        owner=self.owner();child=self.child(owner)
        binding=Mock(spec=module.OwnedCoreBinding);order=[]
        def graceful(*_):order.append('stop');child.stdin.close()
        with patch.object(module,'OwnedCoreBinding',return_value=binding), \
             patch.object(module,'reauthenticate_owned',side_effect=lambda *a,**k:order.append('attest')), \
             patch.object(module,'_read_cli',side_effect=graceful), \
             patch.object(module,'unregister'):
            owner.recover_stop()
        self.assertEqual(order,['attest','stop'])
        self.assertIsNotNone(child.poll());self.assertIsNone(owner.process)
        self.assertTrue(owner._faulted)
        with self.assertRaises(module.ManagedCoreError):owner.start()

    def test_identity_drift_refuses_and_retains_original_handle(self):
        owner=self.owner();child=self.child(owner)
        with patch.object(module,'OwnedCoreBinding',side_effect=CoreBindingError('RPC_EXECUTABLE_CHANGED')), \
             patch.object(module,'_read_cli') as stop:
            with self.assertRaises(CoreBindingError):owner.recover_stop()
            stop.assert_not_called()
        self.assertIs(owner.process,child)

    def test_wrong_chain_or_credential_reauthentication_cannot_stop(self):
        owner=self.owner();child=self.child(owner)
        with patch.object(module,'OwnedCoreBinding',return_value=Mock(spec=module.OwnedCoreBinding)), \
             patch.object(module,'reauthenticate_owned',side_effect=ValueError('DENIED')), \
             patch.object(module,'_read_cli') as stop:
            with self.assertRaises(ValueError):owner.recover_stop()
            stop.assert_not_called()
        self.assertIs(owner.process,child)
