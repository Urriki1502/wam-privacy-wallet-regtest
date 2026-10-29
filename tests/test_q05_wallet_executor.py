"""Serialization/lifetime tests; fake backend is never genuine-Core proof."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
import threading
import unittest

from wam_regtest.wallet_executor import WalletExecutor,WalletExecutorError,FrozenDict


class Backend:
    def __init__(self):
        self.creator=threading.get_ident();self.calls=[];self.fail_quit=False
        self.entered=threading.Event();self.release=threading.Event();self.bad_state=False
        self.alive=True
    def public_state(self):
        if self.bad_state:raise ValueError('private-path-secret')
        return {'locked':False,'faulted':False,'core_alive':self.alive}
    def execute(self,action,args,kwargs):
        self.calls.append((action,threading.get_ident()))
        if action=='broadcast':self.entered.set();self.release.wait(3)
        if action=='sign':raise ValueError('path /private/secret and rpcpassword')
        if action=='quit' and self.fail_quit:raise ValueError('MANAGED_SHUTDOWN_UNCERTAIN')
        if action=='quit':self.alive=False
        return {'action':action,'rows':[1,2]}


class ExecutorContracts(unittest.TestCase):
    def executor(self):
        created=[]
        def factory():
            backend=Backend();created.append(backend);return backend
        executor=WalletExecutor(factory)
        def close():
            if created:created[0].release.set();created[0].fail_quit=False;created[0].bad_state=False
            if executor.busy:
                try:executor._pending.result(timeout=4)
                except WalletExecutorError:pass
            if not executor.closed:executor.request('quit')
            self.assertTrue(executor.join())
        self.addCleanup(close)
        return executor,created

    def test_every_operation_uses_one_persistent_owner_thread(self):
        executor,created=self.executor();executor.request('open')
        with ThreadPoolExecutor(1) as pool:pool.submit(executor.request,'snapshot').result()
        executor.request('lock');executor.request('unlock')
        backend=created[0]
        self.assertEqual({t for _,t in backend.calls},{backend.creator})
        self.assertNotEqual(backend.creator,threading.get_ident())
        self.assertFalse(executor.closed)

    def test_inflight_write_rejects_overlap_and_cannot_be_cancelled(self):
        executor,created=self.executor();executor.request('open')
        pending=executor.submit('broadcast');self.assertTrue(created[0].entered.wait(2))
        self.assertFalse(pending.cancel())
        with self.assertRaises(WalletExecutorError):executor.request('broadcast')
        with self.assertRaises(WalletExecutorError):executor.request('lock')
        created[0].release.set();pending.result(timeout=2)
        self.assertEqual([a for a,_ in created[0].calls].count('broadcast'),1)

    def test_timeout_does_not_retry_or_drop_original_operation(self):
        executor,created=self.executor();executor.request('open')
        with self.assertRaisesRegex(WalletExecutorError,'STILL_PENDING'):
            executor.request('broadcast',timeout=.01)
        self.assertTrue(executor.busy)
        with self.assertRaises(WalletExecutorError):executor.request('broadcast')
        created[0].release.set()

    def test_results_and_state_are_immutable_and_errors_are_private(self):
        executor,_=self.executor();result=executor.request('snapshot')
        self.assertIsInstance(result,FrozenDict);self.assertEqual(result['rows'],(1,2))
        with self.assertRaises(TypeError):result['action']='mutated'
        with self.assertRaises(FrozenInstanceError):executor.state.locked=True
        with self.assertRaisesRegex(WalletExecutorError,'^WALLET_EXECUTOR_DENIED$'):executor.request('sign')

    def test_failed_core_shutdown_keeps_owner_thread_for_explicit_recovery(self):
        executor,created=self.executor();executor.request('open');created[0].fail_quit=True
        with self.assertRaisesRegex(WalletExecutorError,'MANAGED_SHUTDOWN_UNCERTAIN'):executor.request('quit')
        self.assertFalse(executor.closed);executor.request('core_status')

    def test_invalid_command_never_reaches_backend(self):
        executor,created=self.executor()
        with self.assertRaises(WalletExecutorError):executor.request('sendrawtransaction','raw')
        self.assertEqual(created,[])

    def test_state_observation_failure_does_not_abandon_owner(self):
        executor,created=self.executor();executor.request('open');created[0].bad_state=True
        with self.assertRaisesRegex(WalletExecutorError,'STATE_UNVERIFIED'):executor.request('snapshot')
        self.assertTrue(executor.state.faulted);self.assertIsNone(executor.state.core_alive)
        self.assertFalse(executor.closed);created[0].bad_state=False;executor.request('core_status')
