"""Supplemental authorization/journal tests, never positive Core E2E evidence."""
import hashlib
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from wam_regtest.owned_recovery import (recover_index,pending_recoveries,
    IndexRecoveryError,_encoded,SCHEMA)
from wam_regtest.supervisor_store import create_once


class RecoveryScope(unittest.TestCase):
    def test_reindex_only_moving_tip_reopens_a_fresh_fully_attested_read(self):
        from types import SimpleNamespace
        from unittest.mock import Mock,MagicMock
        from wam_regtest.owned_recovery import _wait_reindexed
        from wam_regtest.json_rpc import RpcError
        binding=Mock();binding._assert_image=Mock();binding.assert_socket=Mock()
        owner=SimpleNamespace(process=Mock(),binding=binding,read=None,
            core=Path('/not-opened-core'),directory=Path('/not-opened-chain'))
        owner.process.poll.return_value=None
        reader=Mock();reader._connection.port=12345
        reader.attest.return_value={'blocks':101,'bestblockhash':'a'*64}
        reader.call.return_value='a'*64
        with patch('wam_regtest.json_rpc.ManagedReadRpc',side_effect=[RpcError('RPC_TIP_IDENTITY_DENIED'),reader]) as create, \
             patch('wam_regtest.owned_recovery.socket.create_connection',return_value=MagicMock()), \
             patch('wam_regtest.owned_recovery.time.monotonic',return_value=0), \
             patch('wam_regtest.owned_recovery.time.sleep'):
            self.assertEqual(_wait_reindexed(owner,12345,101,'a'*64,10),1)
            self.assertEqual(create.call_count,2)
            self.assertEqual(binding.assert_socket.call_count,2)
            reader.call.assert_called_once_with('getblockhash',[101])

    def test_reindex_never_retries_auth_genesis_version_or_uncertain_connections(self):
        from types import SimpleNamespace
        from unittest.mock import Mock,MagicMock
        from wam_regtest.owned_recovery import _wait_reindexed
        from wam_regtest.json_rpc import RpcError
        for code in ('RPC_AUTHENTICATION_DENIED','RPC_GENESIS_DENIED','RPC_CONFIG_CHANGED',
                     'RPC_VERSION_CAPABILITY_DENIED','RPC_CORE_READ_REFUSED','RPC_CONNECTION_UNCERTAIN_READ_FAILED'):
            binding=Mock();binding._assert_image=Mock();binding.assert_socket=Mock()
            owner=SimpleNamespace(process=Mock(),binding=binding,read=None,
                core=Path('/not-opened-core'),directory=Path('/not-opened-chain'))
            owner.process.poll.return_value=None
            with patch('wam_regtest.json_rpc.ManagedReadRpc',side_effect=RpcError(code)) as create, \
                 patch('wam_regtest.owned_recovery.socket.create_connection',return_value=MagicMock()), \
                 patch('wam_regtest.owned_recovery.time.monotonic',return_value=0):
                with self.assertRaises(RpcError):_wait_reindexed(owner,12345,101,'a'*64,10)
                create.assert_called_once()

    def test_expired_reindex_budget_cannot_publish_a_checkpoint(self):
        from wam_regtest.owned_recovery import _wait_reindexed
        with patch('wam_regtest.owned_recovery.time.monotonic',return_value=10), \
             patch('wam_regtest.json_rpc.ManagedReadRpc') as create:
            with self.assertRaisesRegex(IndexRecoveryError,'^RECOVERY_ORIGINAL_HEIGHT_TIP_NOT_RESTORED$'):
                _wait_reindexed(None,12345,101,'a'*64,10)
            create.assert_not_called()
    def test_reindex_argv_is_not_accepted_by_an_ordinary_binding(self):
        import subprocess
        from wam_regtest.core_process import OwnedCoreBinding,CoreBindingError
        process=object.__new__(subprocess.Popen)
        core=Path('/not-opened-core');directory=Path('/not-opened-chain')
        base=[str(core/'wamd'),f'-datadir={directory}','-daemon=0']
        process.args=base+['-reindex=1']
        with self.assertRaisesRegex(CoreBindingError,'^RPC_OWNED_PROCESS_REQUIRED$'):
            OwnedCoreBinding(process,core,directory)
        for option in ('-reindex','-reindex-chainstate=1','-txindex=1'):
            process.args=base+[option]
            with self.assertRaisesRegex(CoreBindingError,'^RPC_OWNED_PROCESS_REQUIRED$'):
                OwnedCoreBinding(process,core,directory,reindex=True)
    def test_consent_checkpoint_and_budget_are_required_before_profile_access(self):
        with patch('wam_regtest.core_supervisor.CoreSupervisor') as owner:
            for approval in (False,None,1,'yes'):
                with self.assertRaisesRegex(IndexRecoveryError,'^RECOVERY_EXPLICIT_EXISTING_REGTEST_REINDEX_APPROVAL_REQUIRED$'):
                    recover_index(None,None,expected_height=101,expected_tip='a'*64,authorized_reindex=approval)
            for height,tip in ((True,'a'*64),(0,'a'*64),(1000001,'a'*64),(101,None),(101,'a'*63),(101,'A'*64)):
                with self.assertRaisesRegex(IndexRecoveryError,'^RECOVERY_EXACT_ORIGINAL_CHAIN_REQUIRED$'):
                    recover_index(None,None,expected_height=height,expected_tip=tip,authorized_reindex=True)
            for timeout in (True,0,241,float('inf')):
                with self.assertRaisesRegex(IndexRecoveryError,'^RECOVERY_BOUNDED_TIMEOUT_REQUIRED$'):
                    recover_index(None,None,expected_height=101,expected_tip='a'*64,authorized_reindex=True,timeout=timeout)
            owner.assert_not_called()

    def test_frozen_operator_cannot_override_pinned_core_pair(self):
        from wam_regtest.supervisor_cli import recover_from_bundle
        for args in (['--core-dir','/external'],['--core-dir=/external']):
            with self.assertRaisesRegex(ValueError,'^MANAGED_BUNDLE_CORE_OVERRIDE_DENIED$'):
                recover_from_bundle(Path('/bundled'),args)

    def test_pending_recovery_refuses_normal_start_before_any_spawn_or_rpc(self):
        from wam_regtest.core_supervisor import CoreSupervisor,ManagedCoreError
        owner=CoreSupervisor.__new__(CoreSupervisor)
        owner._lock=threading.RLock();owner.root=Path('/not-opened');owner.profile={}
        with patch('wam_regtest.owned_recovery.pending_recoveries',return_value=['pending']), \
             patch('wam_regtest.core_supervisor.subprocess.Popen') as spawn, \
             patch('wam_regtest.core_supervisor.local_rpc_port') as rpc:
            with self.assertRaisesRegex(ManagedCoreError,'^MANAGED_INDEX_RECOVERY_PENDING$'):owner.start()
            spawn.assert_not_called();rpc.assert_not_called()


class NativeRecoveryJournal(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='wam-recovery-journal-')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()/'wam-fusion-core-1234567890abcdef'
        if sys.platform=='win32':
            from wam_regtest.windows_private_storage import create_private_directory
            create_private_directory(self.root)
        else:self.root.mkdir(mode=0o700)
        self.profile={'profile_id':'1'*32,'core_sha256':'2'*64,'cli_sha256':'3'*64}
        self.name='supervisor.recovery.'+'4'*32+'.intent'
        self.obj={'schema':SCHEMA,**self.profile,'height':101,'tip':'5'*64}

    def test_intent_survives_a_new_reader_and_never_means_completion(self):
        raw=_encoded(self.obj);create_once(self.root,self.name,raw)
        expected=[(self.name,self.obj,hashlib.sha256(raw).hexdigest())]
        self.assertEqual(pending_recoveries(self.root,self.profile),expected)
        self.assertEqual(pending_recoveries(self.root,dict(self.profile)),expected)

    def test_completion_requires_exact_intent_digest_and_verified_shutdown(self):
        raw=_encoded(self.obj);create_once(self.root,self.name,raw)
        create_once(self.root,self.name[:-6]+'complete',_encoded({'schema':SCHEMA,
            'intent_sha256':hashlib.sha256(raw).hexdigest(),
            'exact_chain_verified':True,'clean_owned_shutdown':True}))
        self.assertEqual(pending_recoveries(self.root,self.profile),[])

    def test_truncated_wrong_profile_or_unconfirmed_records_fail_closed(self):
        for data in (b'{',_encoded({**self.obj,'profile_id':'9'*32})):
            with self.subTest(data=data):
                # Separate fresh native roots, never repair a bad record.
                root=self.root.parent/('wam-fusion-core-'+hashlib.sha256(data).hexdigest()[:16])
                if sys.platform=='win32':
                    from wam_regtest.windows_private_storage import create_private_directory
                    create_private_directory(root)
                else:root.mkdir(mode=0o700)
                create_once(root,self.name,data)
                with self.assertRaises(IndexRecoveryError):pending_recoveries(root,self.profile)

    def test_unknown_profile_never_creates_a_lock_or_launches_core(self):
        before=list(self.root.iterdir())
        with patch('wam_regtest.core_supervisor.subprocess.Popen') as spawn:
            with self.assertRaises(ValueError):
                recover_index(self.root,Path('/not-opened'),expected_height=101,
                    expected_tip='a'*64,authorized_reindex=True)
            spawn.assert_not_called()
        self.assertEqual(list(self.root.iterdir()),before)

    def test_wrong_completion_digest_does_not_clear_pending_state(self):
        create_once(self.root,self.name,_encoded(self.obj))
        create_once(self.root,self.name[:-6]+'complete',_encoded({'schema':SCHEMA,
            'intent_sha256':'0'*64,'exact_chain_verified':True,'clean_owned_shutdown':True}))
        with self.assertRaisesRegex(IndexRecoveryError,'^RECOVERY_COMPLETION_UNVERIFIED$'):
            pending_recoveries(self.root,self.profile)

    def test_orphan_completion_cannot_authorize_start(self):
        create_once(self.root,self.name[:-6]+'complete',b'{}')
        with self.assertRaisesRegex(IndexRecoveryError,'^RECOVERY_JOURNAL_ORPHAN_DENIED$'):
            pending_recoveries(self.root,self.profile)

    def test_chain_hardlinks_are_denied_before_core_mutation(self):
        import os
        from wam_regtest.owned_recovery import _chain_tree
        first=self.root/'original.dat';first.write_bytes(b'disposable-public-block-fixture')
        os.link(first,self.root/'alias.dat')
        with self.assertRaisesRegex(IndexRecoveryError,'^RECOVERY_CHAIN_LINK_OR_SPECIAL_FILE_DENIED$'):
            _chain_tree(self.root)


if __name__=='__main__':unittest.main()
