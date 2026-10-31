"""Completion transitions with real authenticated references, mocked vault/Core.

These tests are not native cryptography or actual Core qualification.
"""
from contextlib import nullcontext
from pathlib import Path
import unittest
import sys
from unittest.mock import Mock,patch

import test_q05_recovery_reference as references
from wam_regtest import wallet_recovery as module


class RecoveryCompletionContracts(unittest.TestCase):
    setUp=references.RecoveryReferenceContracts.setUp
    owner=references.RecoveryReferenceContracts.owner
    target=references.RecoveryReferenceContracts.target
    begin=references.RecoveryReferenceContracts.begin

    def fixture(self):
        owner=self.owner()
        from wam_regtest.managed_wallet_checkpoint import _publish_reference
        _publish_reference(owner,'a'*32)
        action,path,_=self.begin(owner)
        for generation in (1,2):
            (path/f'snapshot-{generation:09d}.enc').write_bytes(b'fixture-only')
        anchor=Mock();anchor.read.return_value=(2,'c'*64);anchor.lease.side_effect=lambda:nullcontext()
        vault=Mock();vault._expected=(2,'c'*64)
        def restore(runtime,password,**options):
            self.assertEqual(options.get('private_windows_runtime'),sys.platform=='win32')
            runtime.write_bytes(b'owned-fixture-runtime')
            return Mock(),Mock()
        vault.restore.side_effect=restore
        factory=Mock(return_value=vault)
        factory._filename.side_effect=lambda generation:f'snapshot-{generation:09d}.enc'
        self.stack.enter_context(patch.object(module,'_owned'))
        # This suite isolates reference completion with mocked vault payloads.
        # Real sealed source/runtime equivalence has its own regression suite.
        self.stack.enter_context(patch.object(module,'require_recovery_source_equivalence'))
        self.stack.enter_context(patch('wam_regtest.managed_wallet_checkpoint._owned'))
        self.stack.enter_context(patch('wam_regtest.managed_wallet_checkpoint._pinned_source'))
        self.stack.enter_context(patch.object(module.custody,'anchor',return_value=anchor))
        self.stack.enter_context(patch('wam_regtest.vault.CheckpointVault',factory))
        self.stack.enter_context(patch('wam_regtest.wallet_session.WalletCoreCli'))
        self.stack.enter_context(patch.object(module,'_snapshot',return_value={'reservation_sha256':'d'*64}))
        def run(**kwargs):
            return module.complete_recovery(owner,self.core,b'public-test-password',
                    authorized=True,action=action,**kwargs)
        return owner,action,path,anchor,vault,run

    def test_consent_is_required_before_owner_or_storage(self):
        with self.assertRaisesRegex(module.ManagedWalletError,'EXPLICIT_CONSENT'):
            module.complete_recovery(object(),Path('/unused'),b'public-test-password',action='a'*16)

    def test_positive_and_exact_retry_never_save_or_advance_anchor(self):
        owner,action,_,anchor,vault,run=self.fixture()
        result=run();before=tuple(p.read_bytes() for p in sorted(self.root.glob('supervisor.recovery.*')))
        self.assertFalse(result['completion_already_committed']);self.assertFalse(result['anchor_advanced'])
        self.assertEqual(module.active_location(owner,'a'*32)[2],[2,'c'*64])
        self.assertTrue(run()['completion_already_committed'])
        self.assertEqual(before,tuple(p.read_bytes() for p in sorted(self.root.glob('supervisor.recovery.*'))))
        vault.save.assert_not_called();anchor.advance.assert_not_called();anchor._advance_unlocked.assert_not_called()

    def test_wrong_action_missing_or_advanced_anchor_refuse_without_commit(self):
        owner,_,_,anchor,_,run=self.fixture()
        with self.assertRaisesRegex(module.ManagedWalletError,'ACTION_MISMATCH'):
            module.complete_recovery(owner,self.core,b'public-test-password',authorized=True,action='f'*16)
        for value in (None,(1,'b'*64),(3,'e'*64),(True,'c'*64)):
            anchor.read.return_value=value
            with self.assertRaises(module.ManagedWalletError):run()
        self.assertFalse((self.root/'supervisor.recovery.000002').exists())

    def test_unknown_target_stage_and_runtime_remain_untouched(self):
        owner,action,path,_,_,run=self.fixture()
        stage=path/'.stage-unknown';stage.write_bytes(b'preserve-stage')
        with self.assertRaises(module.ManagedWalletError):run()
        self.assertEqual(stage.read_bytes(),b'preserve-stage')
        # No automatic deletion/repair; independently remove only this known
        # unit-test fixture to test the next distinct refusal.
        stage.unlink()
        runtime=owner.directory/('wallet-runtime-recovery-'+action+'.sqlite-wal')
        runtime.write_bytes(b'unknown-runtime')
        with self.assertRaises(module.ManagedWalletError):run()
        self.assertEqual(runtime.read_bytes(),b'unknown-runtime')
        self.assertFalse((self.root/'supervisor.recovery.000002').exists())

    def test_wrong_password_ciphertext_or_restore_failure_cannot_commit(self):
        _,_,_,_,vault,run=self.fixture()
        for hook in (vault._load_payload,vault.restore):
            hook.side_effect=ValueError('fixture-authentication-denied')
            with self.assertRaises(module.ManagedWalletError):run()
            hook.side_effect=None
        self.assertFalse((self.root/'supervisor.recovery.000002').exists())

    def test_identity_and_concurrent_anchor_change_refuse(self):
        _,_,_,anchor,_,run=self.fixture()
        with patch.object(module,'directory_identity',return_value={'foreign':True}):
            with self.assertRaises(module.ManagedWalletError):run()
        anchor.read.side_effect=[(2,'c'*64),(3,'e'*64)]
        with self.assertRaises(module.ManagedWalletError):run()
        self.assertFalse((self.root/'supervisor.recovery.000002').exists())

    def test_cut_before_commit_stays_pending_and_explicit_retry_can_complete(self):
        owner,_,_,_,_,run=self.fixture()
        with patch.object(module,'_append',side_effect=OSError('publication-cut')):
            with self.assertRaises(module.ManagedWalletError):run()
        with self.assertRaisesRegex(module.ManagedWalletError,'RECOVERY_PENDING'):
            module.active_location(owner,'a'*32)
        self.assertTrue(run()['explicit_recovery_completion'])

    def test_cut_after_durable_commit_has_authenticated_idempotent_retry(self):
        _,_,_,anchor,_,run=self.fixture();append=module._append
        def cut(*args,**kwargs):
            append(*args,**kwargs)
            raise OSError('after-durable-commit')
        with patch.object(module,'_append',cut):
            with self.assertRaises(module.ManagedWalletError):run()
        self.assertTrue(run()['completion_already_committed'])
        anchor.read.return_value=(3,'e'*64)
        with self.assertRaises(module.ManagedWalletError):run()
