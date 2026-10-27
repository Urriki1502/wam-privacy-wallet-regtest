"""Startup fault fixtures; genuine Popen/kernel/Core proof is a separate probe."""
from contextlib import ExitStack
import subprocess
import unittest
from unittest.mock import Mock, patch

import test_q05_core_supervisor as lifecycle_fixture
from wam_regtest import core_supervisor as module
from wam_regtest.core_process import CoreBindingError, OwnedCoreBinding
from wam_regtest.json_rpc import RpcError


class StartupContracts(unittest.TestCase):
    setUp = lifecycle_fixture.SupervisorLifecycleUnit.setUp
    owner = lifecycle_fixture.SupervisorLifecycleUnit.owner

    def startup(self, owner, *, rpc_effect=None, socket_error=None):
        stack = ExitStack()
        self.addCleanup(stack.close)
        process = Mock(spec=subprocess.Popen)
        process.poll.return_value = None
        binding = Mock(spec=OwnedCoreBinding)
        probe = Mock()
        probe.__enter__ = Mock(return_value=probe)
        probe.__exit__ = Mock(return_value=False)
        spawn = stack.enter_context(patch.object(module.subprocess, 'Popen', return_value=process))
        stack.enter_context(patch.object(module, 'OwnedCoreBinding', return_value=binding))
        registered = stack.enter_context(patch.object(module, 'register'))
        stack.enter_context(patch.object(module.socket, 'create_connection', return_value=probe))
        read = Mock()
        rpc = stack.enter_context(patch.object(module, 'ManagedReadRpc',
            side_effect=rpc_effect, return_value=read))
        if socket_error:
            binding.assert_socket.side_effect = socket_error
        self.addCleanup(lambda: setattr(process, 'poll', Mock(return_value=0)))
        return process, binding, registered, rpc, spawn

    def test_start_registers_only_spawned_process_and_same_datadir(self):
        owner = self.owner()
        process, binding, registered, rpc, spawn = self.startup(owner)
        owner.start(timeout=1)
        self.assertIs(owner.process, process)
        self.assertEqual(owner.state, 'ready')
        self.assertEqual(spawn.call_args.args[0],
            [str(owner.node), f'-datadir={owner.directory}', '-daemon=0'])
        registered.assert_called_once_with(process, owner.core, owner.directory,
                                           authorized_disposable_mutation=True)
        binding.assert_socket.assert_called_once()
        rpc.assert_called_once_with(owner.core, owner.directory,
                                    authorized_readonly=True, binding=binding)
        self.assertNotIn('rpcpassword', str(spawn.call_args))

    def test_warmup_only_retry_preserves_spawn_and_scope(self):
        owner = self.owner()
        read = Mock()
        process, binding, registered, rpc, spawn = self.startup(
            owner, rpc_effect=[RpcError('RPC_CORE_WARMUP'), read])
        with patch.object(module.time, 'sleep'):
            owner.start(timeout=1)
        self.assertIs(owner.read, read)
        self.assertEqual(binding.assert_socket.call_count, 2)
        self.assertEqual(spawn.call_count, 1)
        self.assertEqual(registered.call_count, 1)

    def test_spoofed_socket_refuses_before_authenticated_rpc_without_kill(self):
        owner = self.owner()
        process, binding, registered, rpc, spawn = self.startup(owner,
            socket_error=CoreBindingError('RPC_ENDPOINT_OWNER_DENIED'))
        with self.assertRaises(CoreBindingError): owner.start(timeout=1)
        rpc.assert_not_called()
        self.assertIs(owner.process, process)
        process.terminate.assert_not_called();process.kill.assert_not_called()
        with self.assertRaises(module.ManagedCoreError): owner.start(timeout=1)
        self.assertEqual(spawn.call_count, 1)

    def test_wrong_chain_auth_or_config_never_retried_as_warmup(self):
        for code in ('RPC_GENESIS_DENIED', 'RPC_AUTHENTICATION_DENIED', 'RPC_CONFIG_CHANGED'):
            with self.subTest(code=code):
                owner = self.owner()
                with ExitStack() as transient:
                    process = Mock();process.poll.return_value = None
                    transient.enter_context(patch.object(module.subprocess,'Popen',return_value=process))
                    transient.enter_context(patch.object(module,'OwnedCoreBinding',return_value=Mock(spec=OwnedCoreBinding)))
                    transient.enter_context(patch.object(module,'register'))
                    transient.enter_context(patch.object(module.socket,'create_connection',return_value=MockSocket()))
                    rpc = transient.enter_context(patch.object(module,'ManagedReadRpc',side_effect=RpcError(code)))
                    with self.assertRaises(RpcError): owner.start(timeout=1)
                    self.assertEqual(rpc.call_count,1)
                    self.assertEqual(owner.state,'recovery-needed')
                    process.poll.return_value=1
                    owner.close()

    def test_timeout_retains_datadir_and_uncertain_child_without_replacement(self):
        owner = self.owner()
        before = (owner.directory/'wam.conf').read_bytes()
        process, binding, registered, rpc, spawn = self.startup(owner)
        with patch.object(module.time,'monotonic',side_effect=[0,2]):
            with self.assertRaisesRegex(module.ManagedCoreError,'MANAGED_START_TIMEOUT'):
                owner.start(timeout=1)
        self.assertEqual((owner.directory/'wam.conf').read_bytes(),before)
        self.assertIs(owner.process,process)
        process.terminate.assert_not_called();process.kill.assert_not_called()
        with self.assertRaises(module.ManagedCoreError): owner.close()
        rpc.assert_not_called()
        with self.assertRaises(module.ManagedCoreError): owner.start(timeout=1)
        self.assertEqual(spawn.call_count,1)

    def test_binary_or_process_drift_refused_before_socket_auth(self):
        owner = self.owner()
        process, binding, registered, rpc, spawn = self.startup(owner)
        binding._assert_image.side_effect=CoreBindingError('RPC_EXECUTABLE_CHANGED')
        with self.assertRaises(CoreBindingError):owner.start(timeout=1)
        binding.assert_socket.assert_not_called();rpc.assert_not_called()
        process.terminate.assert_not_called()

    def test_foreign_pid_or_fabricated_handle_is_not_owned_popen(self):
        for foreign in (12345,Mock(),object()):
            with self.assertRaises(CoreBindingError):
                OwnedCoreBinding(foreign,self.core,self.root)


class MockSocket:
    def __enter__(self):return self
    def __exit__(self,*_):pass
