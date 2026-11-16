"""Startup ordering/source contracts; no mocked result is Core E2E proof."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from wam_regtest.q02_probe import _Node,Q02ProbeError
from wam_regtest.core import CoreSmokeError


class Q02BootReadiness(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.node=object.__new__(_Node)
        self.node.directory=self.root;self.node.cookie=False
        self.node.proc=Mock();self.node.proc.poll.return_value=None
        self.context=Mock(ready=False,faulted=False,credentials=None)
        self.context.binding.process=self.node.proc
        self.identity=patch('wam_regtest.q02_probe.identity',return_value=self.context)
        self.identity.start();self.addCleanup(self.identity.stop)

    @unittest.skipUnless(hasattr(os,'pread'),'native positional reads required')
    def test_original_stdout_marker_never_changes_child_write_offset(self):
        with (self.root/'stdout').open('x+b') as log:
            os.fchmod(log.fileno(),0o600)
            log.write(b'2026-11-06T00:00:00Z init message: Done loading\n');log.flush()
            offset=log.tell()
            self.node._wait_for_macos_loaded(log.fileno(),float('inf'))
            self.assertEqual(log.tell(),offset)
            self.context.binding._assert_image.assert_called()

    @unittest.skipUnless(hasattr(os,'pread'),'native positional reads required')
    def test_nonmarker_and_early_exit_cannot_authorize_first_rpc(self):
        with (self.root/'stdout').open('x+b') as log:
            os.fchmod(log.fileno(),0o600)
            log.write(b'Done loading\nnot init message: Done loading yet\n');log.flush()
            with patch('wam_regtest.q02_probe.time.monotonic',side_effect=[0,2]):
                with self.assertRaisesRegex(Q02ProbeError,'Q02_NODE_START_TIMEOUT'):
                    self.node._wait_for_macos_loaded(log.fileno(),1)
            self.node.proc.poll.return_value=1
            with self.assertRaisesRegex(Q02ProbeError,'Q02_OWNED_NODE_EARLY_EXIT'):
                self.node._wait_for_macos_loaded(log.fileno(),float('inf'))

    @unittest.skipUnless(hasattr(os,'pread'),'native positional reads required')
    def test_foreign_owner_unlinked_log_and_oversize_log_refuse(self):
        with (self.root/'stdout').open('x+b') as log:
            os.fchmod(log.fileno(),0o600)
            self.context.binding.process=Mock()
            with self.assertRaisesRegex(Q02ProbeError,'ORIGINAL_OWNER_REQUIRED'):
                self.node._wait_for_macos_loaded(log.fileno(),float('inf'))
            self.context.binding.process=self.node.proc
            log.truncate(2*1024*1024+1)
            with self.assertRaisesRegex(Q02ProbeError,'LOG_CUSTODY_DENIED'):
                self.node._wait_for_macos_loaded(log.fileno(),float('inf'))
            log.truncate(0);(self.root/'stdout').unlink()
            with self.assertRaisesRegex(Q02ProbeError,'LOG_CUSTODY_DENIED'):
                self.node._wait_for_macos_loaded(log.fileno(),float('inf'))

    def test_only_live_uninitialized_scope_can_retry_warmup_or_unavailable(self):
        for code in ('CORE_RPC_UNAVAILABLE','CORE_RPC_WARMUP'):
            self.assertTrue(self.node._boot_retry_allowed(code))
            self.context.faulted=True;self.assertFalse(self.node._boot_retry_allowed(code))
            self.context.faulted=False;self.context.ready=True
            self.assertFalse(self.node._boot_retry_allowed(code));self.context.ready=False
        for code in ('CORE_LOCAL_NETWORK_POLICY_DENIED','CORE_RPC_SCOPE_FAULTED',
                     'CORE_RPC_AUTHENTICATION_DENIED','CORE_RPC_PROCESS_IDENTITY_DENIED',
                     'CORE_RPC_CREDENTIAL_CHANGED_OR_UNSAFE','CORE_RPC_DENIED'):
            self.assertFalse(self.node._boot_retry_allowed(code))
        self.context.binding.process=Mock()
        self.assertFalse(self.node._boot_retry_allowed('CORE_RPC_WARMUP'))

    def test_cookie_bootstrap_requires_absence_and_no_existing_credential_snapshot(self):
        code='CORE_RPC_CREDENTIAL_CHANGED_OR_UNSAFE';self.node.cookie=True
        self.assertFalse(self.node._boot_retry_allowed(code))
        (self.root/'regtest').mkdir()
        self.assertTrue(self.node._boot_retry_allowed(code))
        cookie=self.root/'regtest/.cookie';cookie.write_bytes(b'unsafe')
        self.assertFalse(self.node._boot_retry_allowed(code))
        cookie.unlink();self.context.credentials=object()
        self.assertFalse(self.node._boot_retry_allowed(code))

    @unittest.skipUnless(hasattr(os,'fchmod'),'macOS descriptor mode contract')
    def test_fatal_first_rpc_is_not_retried_or_reauthenticated(self):
        self.node.proc=None;self.node.core=self.root
        self.node.node=self.root/'wamd';self.node.cli=self.root/'wam-cli'
        proc=Mock();proc.poll.return_value=None
        self.context.binding.process=proc;self.context.faulted=True
        self.node._wait_for_macos_loaded=Mock()
        self.node.call=Mock(side_effect=CoreSmokeError('CORE_LOCAL_NETWORK_POLICY_DENIED'))
        with patch('wam_regtest.q02_probe.sys.platform','darwin'),\
             patch('wam_regtest.q02_probe.subprocess.Popen',return_value=proc),\
             patch('wam_regtest.q02_probe.register'),\
             patch('wam_regtest.q02_probe.reauthenticate_owned') as reauth:
            with self.assertRaisesRegex(CoreSmokeError,'CORE_LOCAL_NETWORK_POLICY_DENIED'):
                self.node.start()
        self.node._wait_for_macos_loaded.assert_called_once()
        self.node.call.assert_called_once_with('getblockcount');reauth.assert_not_called()
