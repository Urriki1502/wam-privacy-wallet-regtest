"""Stage A unit/native-store tests; mocked Core is never acceptance evidence."""
from contextlib import ExitStack
import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from wam_regtest import core_supervisor as module
from wam_regtest.core_supervisor import CoreSupervisor, ManagedCoreError
from wam_regtest.json_rpc import RpcError
from wam_regtest.supervisor_protocol import PROTOCOL, request_proof, SupervisorProtocolError
from wam_regtest.supervisor_store import read_exact


class SupervisorLifecycleUnit(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / 'wam-fusion-core-0123456789abcdef'
        if sys.platform == 'win32':
            from wam_regtest.windows_private_storage import create_private_directory
            self.create_private_directory = create_private_directory
        else:
            self.create_private_directory = lambda p: p.mkdir(mode=0o700)
        self.create_private_directory(self.root)
        self.core = self.root.parent / 'core'
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(module, 'verified_core_paths', return_value=(
            self.core / 'wamd', self.core / 'wam-cli',
            {'wamd_sha256': 'a' * 64, 'wam_cli_sha256': 'b' * 64})))
        self.stack.enter_context(patch.object(module,'_metadata',return_value=('fixture-only',)))
        # Keep real native supervisor storage, profile/config files and locks.
        # Only Core verification/process/RPC and platform policy are fixtures.
        self.stack.enter_context(patch.object(module, 'storage', return_value=Mock()))
        self.stack.enter_context(patch.object(module, 'create_directory',
            side_effect=self.create_private_directory))

    def owner(self):
        owner = CoreSupervisor(self.root, self.core, authorized=True)
        self.addCleanup(owner.close)
        return owner

    def runtime(self, owner):
        owner.process = Mock()
        owner.process.pid = 12345
        owner.journal.append('STARTING')
        owner.journal.append('RUNNING',owner.process.pid)
        owner.process.poll.return_value = None
        owner.binding = Mock()
        owner.read = Mock()
        owner.read.call.return_value = {'blocks': 101, 'initialblockdownload': False}
        self.addCleanup(lambda: setattr(owner.process, 'poll', Mock(return_value=0))
                        if owner.process is not None else None)

    def test_profile_datadir_and_token_survive_owner_reopen(self):
        owner = self.owner()
        before = {name: read_exact(self.root, name) for name in
                  ('supervisor.profile', 'supervisor.token')}
        directory = owner.directory
        marker = directory / 'public-history-fixture'
        marker.write_bytes(b'preserve')
        owner.close()
        other = self.owner()
        self.assertEqual(other.directory, directory)
        for name, raw in before.items():
            self.assertEqual(read_exact(self.root, name), raw)
        self.assertEqual(marker.read_bytes(), b'preserve')

    def test_competing_owner_cannot_change_profile(self):
        owner = self.owner()
        before = read_exact(self.root, 'supervisor.profile')
        with self.assertRaises(ValueError):
            CoreSupervisor(self.root, self.core, authorized=True)
        self.assertEqual(read_exact(self.root, 'supervisor.profile'), before)
        self.assertEqual(owner.status()['state'], 'stopped')

    def test_live_owner_lease_blocks_second_supervisor_without_new_process(self):
        from wam_regtest.supervisor_store import SupervisorStorageError
        owner = self.owner()
        self.runtime(owner)
        pid = owner.process.pid
        profile = read_exact(self.root, 'supervisor.profile')
        chain = owner.directory
        with self.assertRaises(SupervisorStorageError) as caught:
            CoreSupervisor(self.root, self.core, authorized=True)
        self.assertEqual(caught.exception.args, ('SUPERVISOR_STORAGE_LEASE_BUSY',))
        self.assertEqual(owner.process.pid, pid)
        self.assertIsNone(owner.process.poll())
        self.assertEqual(read_exact(self.root, 'supervisor.profile'), profile)
        self.assertEqual(owner.directory, chain)
        self.assertFalse(owner._faulted)

    def test_partial_namespace_is_never_repaired(self):
        (self.root / 'unknown').write_bytes(b'preserve')
        with self.assertRaises(ManagedCoreError):
            CoreSupervisor(self.root, self.core, authorized=True)
        self.assertFalse((self.root / 'chain').exists())
        self.assertEqual((self.root / 'unknown').read_bytes(), b'preserve')

    def test_config_drift_and_core_upgrade_refused_without_rewrite(self):
        owner = self.owner()
        before = (owner.directory / 'wam.conf').read_bytes()
        (owner.directory / 'wam.conf').write_bytes(before + b'proxy=127.0.0.1:1\n')
        with self.assertRaises(ManagedCoreError):
            owner.start()
        self.assertIsNone(owner.process)
        (owner.directory / 'wam.conf').write_bytes(before)
        owner.receipt['wamd_sha256'] = 'c' * 64
        with self.assertRaises(ManagedCoreError):
            owner.start()

    def test_consent_and_external_process_never_grant_ownership(self):
        with self.assertRaises(ManagedCoreError):
            CoreSupervisor(self.root, self.core)
        owner = self.owner()
        with patch.object(module, '_read_cli') as stop:
            with self.assertRaises(ManagedCoreError):
                owner.shutdown()
            stop.assert_not_called()

    def test_invalid_auth_never_reaches_lifecycle(self):
        owner = self.owner()
        nonce = 'a' * 32
        challenge = owner.guard.hello()['challenge']
        raw = (json.dumps(dict(protocol=PROTOCOL, op='start', nonce=nonce, challenge=challenge,
            proof=request_proof(b'x' * 32, 'start', nonce, challenge))) + '\n').encode()
        with patch.object(owner, 'start') as start:
            with self.assertRaises(SupervisorProtocolError):
                owner.handle(raw, challenge)
            start.assert_not_called()

    def test_live_owner_cannot_be_closed_by_gui_disconnect(self):
        owner = self.owner()
        self.runtime(owner)
        with self.assertRaises(ManagedCoreError):
            owner.close()
        self.assertIsNotNone(owner.listener)
        owner.process.terminate.assert_not_called()

    def test_busy_status_is_coalesced_but_ownership_rechecked(self):
        owner = self.owner()
        self.runtime(owner)
        owner.read.call.side_effect = RpcError('RPC_NODE_BUSY')
        self.assertEqual(owner.status()['state'], 'busy')
        self.assertEqual(owner.status()['state'], 'busy')
        self.assertEqual(owner.read.call.call_count, 1)
        self.assertEqual(owner.binding._assert_image.call_count, 2)

    def test_auth_drift_does_not_report_busy_or_retry(self):
        owner = self.owner()
        self.runtime(owner)
        owner.read.call.side_effect = RpcError('RPC_CONFIG_CHANGED')
        self.assertEqual(owner.status()['state'], 'recovery-needed')
        self.assertFalse(owner.status()['core_process_owned'])
        self.assertEqual(owner.read.call.call_count, 1)
        with self.assertRaises(ManagedCoreError):
            owner.start()

    def test_crashed_core_has_no_automatic_restart(self):
        owner = self.owner()
        self.runtime(owner)
        owner.process.poll.return_value = 1
        with patch.object(module.subprocess, 'Popen') as spawn:
            self.assertEqual(owner.status()['state'], 'recovery-needed')
            with self.assertRaises(ManagedCoreError):
                owner.start()
            spawn.assert_not_called()

    def test_stop_uses_existing_signed_cli_not_http_write(self):
        owner = self.owner()
        self.runtime(owner)
        with patch.object(module, '_read_cli') as stop, patch.object(module, 'unregister'):
            owner.shutdown()
            stop.assert_called_once_with([str(owner.cli), f'-datadir={owner.directory}', 'stop'])
        self.assertIsNone(owner.process)
        self.assertEqual(owner.state, 'stopped')

    def test_uncertain_stop_retains_owner_and_never_force_kills(self):
        owner = self.owner()
        self.runtime(owner)
        with patch.object(module, '_read_cli', side_effect=RuntimeError('private diagnostic')):
            with self.assertRaisesRegex(ManagedCoreError, '^MANAGED_SHUTDOWN_UNCERTAIN$'):
                owner.shutdown()
        self.assertEqual(owner.state, 'recovery-needed')
        owner.process.terminate.assert_not_called()
        owner.process.kill.assert_not_called()

    def test_occupied_rpc_port_never_spawns_or_rewrites_config(self):
        owner = self.owner()
        before = (owner.directory / 'wam.conf').read_bytes()
        with module._listener(module.local_rpc_port(owner.directory)):
            with patch.object(module.subprocess, 'Popen') as spawn:
                with self.assertRaises(OSError):
                    owner.start()
                spawn.assert_not_called()
        self.assertEqual((owner.directory / 'wam.conf').read_bytes(), before)

    def test_authenticated_control_reply_and_replay_refusal(self):
        owner = self.owner()
        secret = read_exact(self.root, 'supervisor.token', length=32)
        nonce = 'a' * 32
        challenge = owner.guard.hello()['challenge']
        raw = (json.dumps(dict(protocol=PROTOCOL, op='status', nonce=nonce, challenge=challenge,
            proof=request_proof(secret, 'status', nonce, challenge))) + '\n').encode()
        result = owner.handle(raw, challenge)
        self.assertEqual(result['nonce'], nonce)
        self.assertEqual(len(result['proof']), 64)
        with self.assertRaises(SupervisorProtocolError):
            owner.handle(raw, challenge)
