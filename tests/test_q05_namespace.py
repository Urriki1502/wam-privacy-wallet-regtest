"""Ambiguous Q05 vault namespace must refuse before either restore entry."""
from contextlib import ExitStack,nullcontext
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch

from wam_regtest import managed_wallet_checkpoint as checkpoint
from wam_regtest import managed_wallet_session as session


class CheckpointNamespaceContracts(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name).resolve()/'vault'
        if sys.platform=='win32':
            from wam_regtest.windows_private_storage import create_private_directory
            create_private_directory(self.root)
        else:self.root.mkdir(mode=0o700)
        self.current=self.root/'snapshot-000000001.enc';self.current.write_bytes(b'public-fixture')
        self.record=(1,'a'*64)

    def test_current_and_older_snapshots_are_allowed_without_advancing_anchor(self):
        checkpoint.require_checkpoint_namespace(self.root,self.record)
        (self.root/'.vault.lock').write_bytes(b'')
        checkpoint.require_checkpoint_namespace(self.root,self.record)
        (self.root/'snapshot-000000002.enc').write_bytes(b'new-anchored-fixture')
        checkpoint.require_checkpoint_namespace(self.root,(2,'b'*64))

    def test_future_or_stage_or_unknown_bytes_are_refused_and_preserved(self):
        for name in ('snapshot-000000002.enc','.stage-interrupted','unknown.enc','snapshot-000000000.enc'):
            with self.subTest(name=name):
                path=self.root/name;path.write_bytes(b'preserve-ambiguous-fixture')
                with self.assertRaisesRegex(checkpoint.ManagedWalletError,'CHECKPOINT_AMBIGUOUS'):
                    checkpoint.require_checkpoint_namespace(self.root,self.record)
                self.assertEqual(path.read_bytes(),b'preserve-ambiguous-fixture')
                # Only the known unit fixture, never a wallet/profile cleanup.
                path.unlink()

    def test_missing_current_and_malformed_anchor_refuse_without_reset(self):
        preserved=self.root.parent/'preserved';self.current.rename(preserved)
        with self.assertRaises(checkpoint.ManagedWalletError):
            checkpoint.require_checkpoint_namespace(self.root,self.record)
        for record in (None,(True,'a'*64),(0,'a'*64),(1,'wrong'),[1,'a'*64,'extra']):
            with self.subTest(record=record),self.assertRaises(checkpoint.ManagedWalletError):
                checkpoint.require_checkpoint_namespace(self.root,record)
        self.assertEqual(preserved.read_bytes(),b'public-fixture')

    def test_hardlinked_current_cannot_be_used(self):
        import os
        os.link(self.current,self.root.parent/'preserved-link')
        with self.assertRaises(checkpoint.ManagedWalletError):
            checkpoint.require_checkpoint_namespace(self.root,self.record)

    def test_both_managed_entries_refuse_orphan_before_vault_restore_or_runtime(self):
        (self.root/'snapshot-000000002.enc').write_bytes(b'preserve-orphan')
        from wam_regtest.wallet_session import WalletSession,WalletSessionError
        anchor=Mock();anchor.read.return_value=self.record
        anchor.lease.side_effect=lambda:nullcontext()
        owner=SimpleNamespace(directory=self.root,root=self.root,core=self.root,cli=self.root/'cli',receipt={})
        vault=Mock();runtime=self.root/'wallet-runtime.sqlite'
        with ExitStack() as stack:
            if sys.platform=='linux':
                from wam_regtest import linux_private_storage
                stack.enter_context(patch('wam_regtest.custody.storage',return_value=linux_private_storage))
            for module in (checkpoint,session):
                stack.enter_context(patch.object(module,'_inputs'))
                stack.enter_context(patch.object(module,'_owned'))
                stack.enter_context(patch.object(module,'_read_reference',return_value='a'*32))
                stack.enter_context(patch.object(module,'_runtime',return_value=runtime))
            stack.enter_context(patch.object(session,'active_location',return_value=(self.root,runtime.name,None)))
            stack.enter_context(patch('wam_regtest.wallet_recovery.active_location',return_value=(self.root,runtime.name,None)))
            stack.enter_context(patch('wam_regtest.custody.anchor',return_value=anchor))
            stack.enter_context(patch('wam_regtest.vault.CheckpointVault',return_value=vault))
            stack.enter_context(patch('wam_regtest.wallet_session.WalletCoreCli'))
            with self.assertRaises(checkpoint.ManagedWalletError):
                checkpoint.checkpoint(owner,self.root,b'public-fixture-password',authorized=True)
            with self.assertRaises(WalletSessionError):
                session.open_owned(WalletSession,owner,self.root,b'public-fixture-password',authorized=True)
            vault.restore.assert_not_called();anchor.advance.assert_not_called()
        self.assertFalse(runtime.exists())
        self.assertEqual((self.root/'snapshot-000000002.enc').read_bytes(),b'preserve-orphan')
