"""Real sealed WSP payload/SQLite comparisons; Core/anchor are unit fixtures.

These tests prove refusal before restoration, not native qualification.
"""
import base64
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import test_q05_recovery_reference as references
from wam_regtest import wallet_recovery as module
from wam_regtest import managed_wallet_checkpoint as checkpoint
from wam_sp.keystore import seal
from wam_sp.store import SCHEMA,TABLES

PASSWORD=b'public-disposable-test-password'


class RecoveryEquivalenceContracts(unittest.TestCase):
    setUp=references.RecoveryReferenceContracts.setUp
    owner=references.RecoveryReferenceContracts.owner
    target=references.RecoveryReferenceContracts.target
    begin=references.RecoveryReferenceContracts.begin
    commit=references.RecoveryReferenceContracts.commit

    def setup_source(self):
        owner=self.owner()
        if sys.platform=='linux':
            from wam_regtest import linux_private_storage
            self.stack.enter_context(patch.object(module.custody,'storage',return_value=linux_private_storage))
        folder=owner.directory/'wallet-vault';self.create_private_directory(folder)
        self.data={'schema':3,'identity':json.dumps({'version':2,'network':'fixture','accounts':[]},
                      sort_keys=True,separators=(',',':')),'tables':{name:[] for name in TABLES}}
        self.data['tables']['reservations']=[['a'*64,0,'b'*64,'draft',1]]
        self.payload=self.payload_for(self.data)
        anchor=Mock(wallet_id='a'*32);anchor.read.return_value=(1,'b'*64)
        from contextlib import nullcontext
        anchor.lease.side_effect=lambda:nullcontext()
        self.vault=SimpleNamespace(directory=folder,anchor=anchor,_load_payload=Mock())
        self.future_payload=self.payload
        self.vault._load_payload.side_effect=lambda password,record: (
            self.payload if record[0]==1 else self.future_payload)
        self.runtime=owner.directory/'wallet-runtime.sqlite'
        return owner,anchor

    def payload_for(self,data,keys=None):
        def sealed(value,domain):
            return base64.b64encode(seal(module._canonical(value),PASSWORD,domain)).decode('ascii')
        return {'checkpoint':sealed(data,b'checkpoint'),
                'keys':sealed({'public-unit-fixture':True} if keys is None else keys,b'keys')}

    def database(self,data=None):
        data=self.data if data is None else data
        if sys.platform=='win32':
            from wam_regtest.windows_private_storage import create_managed_runtime
            create_managed_runtime(self.runtime)
        else:self.runtime.touch(mode=0o600)
        db=sqlite3.connect(self.runtime)
        try:
            db.executescript(SCHEMA);db.execute('PRAGMA user_version=3')
            db.executemany('INSERT INTO meta VALUES(?,?)', [('identity',data['identity']),('profile','WSP-1')])
            for name,rows in data['tables'].items():
                db.executemany('INSERT INTO '+name+' VALUES('+','.join('?'*TABLES[name])+')',rows)
            db.commit()
        finally:db.close()

    def orphan(self,data=None,keys=None):
        path=self.vault.directory/'snapshot-000000002.enc'
        if not path.exists():
            module.custody.storage().publish(self.vault.directory,path.name,
                                            seal(b'unit-ciphertext-lookup',PASSWORD,b'recovery'))
        self.future_payload=self.payload_for(self.data if data is None else data,keys)
        return path

    def check(self,owner):
        return module._require_no_divergent_source(owner,self.vault,(1,'b'*64),PASSWORD,self.payload)

    def preserved(self,owner):
        return {p.relative_to(owner.root).as_posix():sha256(p.read_bytes()).hexdigest()
                for p in owner.root.rglob('*') if p.is_file()}

    def test_equivalent_runtime_and_reencrypted_orphan_allow_readonly_comparison(self):
        owner,anchor=self.setup_source();self.database();self.orphan()
        before=self.preserved(owner)
        self.check(owner)
        self.assertEqual(before,self.preserved(owner));anchor.advance.assert_not_called()
        anchor._advance_unlocked.assert_not_called()

    def test_missing_runtime_and_no_future_snapshot_need_no_restore_or_keys(self):
        owner,_=self.setup_source()
        with patch('wam_sp.keystore.Keyring') as keys:
            self.check(owner)
            keys.assert_not_called()
        self.assertFalse(self.runtime.exists())

    def test_each_irreversible_orphan_without_runtime_refuses_and_preserves(self):
        owner,anchor=self.setup_source()
        for state in ('signed','uncertain'):
            with self.subTest(state=state):
                changed=deepcopy(self.data);changed['tables']['reservations'][0][3]=state
                self.orphan(changed);before=self.preserved(owner)
                with self.assertRaisesRegex(module.ManagedWalletError,'UNANCHORED_STATE_DIVERGED'):
                    self.check(owner)
                self.assertEqual(before,self.preserved(owner))
        anchor.advance.assert_not_called();self.assertFalse(self.runtime.exists())

    def test_each_irreversible_runtime_without_orphan_refuses_and_preserves(self):
        owner,_=self.setup_source();self.database()
        for state in ('signed','uncertain'):
            with self.subTest(state=state):
                with sqlite3.connect(self.runtime) as db:
                    db.execute('UPDATE reservations SET state=?',(state,))
                before=self.preserved(owner)
                with self.assertRaisesRegex(module.ManagedWalletError,'UNANCHORED_STATE_DIVERGED'):
                    self.check(owner)
                self.assertEqual(before,self.preserved(owner))

    def test_equivalent_orphan_does_not_hide_divergent_runtime(self):
        owner,_=self.setup_source();self.orphan()
        changed=deepcopy(self.data);changed['tables']['reservations'][0][3]='signed';self.database(changed)
        with self.assertRaisesRegex(module.ManagedWalletError,'UNANCHORED_STATE_DIVERGED'):self.check(owner)

    def test_keys_identity_and_other_table_differences_refuse(self):
        owner,_=self.setup_source()
        changed=deepcopy(self.data);changed['tables']['contacts']=[['x','name','code']]
        self.orphan(changed)
        with self.assertRaises(module.ManagedWalletError):self.check(owner)
        self.orphan(keys={'different-public-unit-fixture':True})
        with self.assertRaises(module.ManagedWalletError):self.check(owner)
        changed=deepcopy(self.data);changed['identity']='foreign'
        self.orphan(changed)
        with self.assertRaises(ValueError):self.check(owner)

    def test_bad_password_corrupt_or_legacy_checkpoint_does_not_create_runtime(self):
        owner,_=self.setup_source();self.orphan()
        for payload in ({'checkpoint':'not-base64','keys':'?'},
                        self.payload_for(dict(self.data,schema=2))):
            with self.subTest(payload_kind=payload['checkpoint'][:8]):
                with self.assertRaises((ValueError,KeyError)):
                    module._require_no_divergent_source(owner,self.vault,(1,'b'*64),PASSWORD,payload)
        with self.assertRaises(ValueError):
            module._require_no_divergent_source(owner,self.vault,(1,'b'*64),b'wrong-password',self.payload)
        self.assertFalse(self.runtime.exists())

    def test_unknown_stage_generation_zero_and_sidecars_refuse_without_cleanup(self):
        owner,_=self.setup_source()
        for name in ('.stage-interrupted','snapshot-000000000.enc'):
            path=self.vault.directory/name;path.write_bytes(b'preserve')
            with self.assertRaises(module.ManagedWalletError):self.check(owner)
            self.assertEqual(path.read_bytes(),b'preserve');path.unlink() # Only this unit fixture.
        for suffix in ('-journal','-wal','-shm'):
            path=self.runtime.with_name(self.runtime.name+suffix);path.write_bytes(b'preserve')
            with self.assertRaises(module.ManagedWalletError):self.check(owner)
            self.assertEqual(path.read_bytes(),b'preserve');path.unlink()

    def test_runtime_wrong_meta_version_extra_schema_and_corruption_are_readonly_denials(self):
        owner,_=self.setup_source();self.database()
        for sql in ("UPDATE meta SET value='foreign' WHERE key='identity'",
                    'PRAGMA user_version=2','CREATE TABLE unknown(x)'):
            with sqlite3.connect(self.runtime) as db:db.execute(sql)
            before=self.preserved(owner)
            with self.assertRaises(module.ManagedWalletError):self.check(owner)
            self.assertEqual(before,self.preserved(owner))
            with sqlite3.connect(self.runtime) as db:
                db.execute('UPDATE meta SET value=? WHERE key=\'identity\'',(self.data['identity'],))
                db.execute('PRAGMA user_version=3')
        self.runtime.write_bytes(b'corrupt-public-fixture')
        with self.assertRaises(sqlite3.Error):self.check(owner)
        self.assertEqual(self.runtime.read_bytes(),b'corrupt-public-fixture')

    def test_physical_row_order_ignored_but_duplicates_and_types_preserved(self):
        rows={'reservations':[['a',0],['b',1]]}
        self.assertEqual(module._table_rows(rows),module._table_rows({'reservations':list(reversed(rows['reservations']))}))
        self.assertNotEqual(module._table_rows(rows),module._table_rows({'reservations':rows['reservations']*2}))
        self.assertNotEqual(module._table_rows(rows),module._table_rows({'reservations':[['a','0'],['b',1]]}))

    def test_runtime_symlink_or_hardlink_is_never_adopted(self):
        import os
        owner,_=self.setup_source();self.database()
        original=self.runtime.with_name('preserved-unit-runtime.sqlite')
        self.runtime.rename(original)
        os.link(original,self.runtime)
        before=self.preserved(owner)
        with self.assertRaises(ValueError):self.check(owner)
        self.assertEqual(before,self.preserved(owner))
        self.runtime.unlink() # Only the newly created unit-test hardlink.
        if sys.platform!='win32':
            self.runtime.symlink_to(original)
            with self.assertRaises((OSError,ValueError)):self.check(owner)
            self.assertTrue(self.runtime.is_symlink())

    def test_source_deadline_and_history_budget_refuse_before_mutation(self):
        owner,anchor=self.setup_source();self.orphan();before=self.preserved(owner)
        with patch.object(module.time,'monotonic',side_effect=[0,16]):
            with self.assertRaisesRegex(module.ManagedWalletError,'AUDIT_BUDGET'):self.check(owner)
        with patch.object(module,'_records',return_value=([{'state':'BEGIN'}]*65,None)):
            with self.assertRaisesRegex(module.ManagedWalletError,'AUDIT_BUDGET'):
                module.require_recovery_source_equivalence(owner,self.core,PASSWORD,anchor)
        self.assertEqual(before,self.preserved(owner));anchor.advance.assert_not_called()

    def test_missing_native_anchor_cannot_be_replaced_by_equivalent_orphan(self):
        owner,anchor=self.setup_source();checkpoint._publish_reference(owner,'a'*32);self.orphan()
        anchor.read.return_value=None
        with patch.object(module,'_inputs'),patch.object(module.custody,'anchor',return_value=anchor),\
                patch('wam_regtest.vault.CheckpointVault') as vault:
            with self.assertRaisesRegex(module.ManagedWalletError,'RECOVERY_DENIED') as caught:
                module.recover_checkpoint(owner,self.core,PASSWORD,authorized=True)
            self.assertEqual(caught.exception.__context__.args,('MANAGED_RECOVERY_ANCHOR_REQUIRED',))
            vault.assert_not_called()
        anchor.advance.assert_not_called();self.assertFalse(module.has_recovery_records(owner))

    def test_legacy_committed_recovery_cannot_hide_original_irreversible_orphan(self):
        owner,anchor=self.setup_source();self.commit(owner)
        changed=deepcopy(self.data);changed['tables']['reservations'][0][3]='signed';self.orphan(changed)
        before=self.preserved(owner)
        with patch('wam_regtest.vault.CheckpointVault',return_value=self.vault):
            with self.assertRaisesRegex(module.ManagedWalletError,'UNANCHORED_STATE_DIVERGED'):
                module.require_recovery_source_equivalence(owner,self.core,PASSWORD,anchor)
        self.assertEqual(before,self.preserved(owner));anchor.advance.assert_not_called()

    def test_pending_and_committed_equivalent_sources_audit_without_native_write(self):
        owner,anchor=self.setup_source();action,_,identity=self.begin(owner);self.database();self.orphan()
        with patch('wam_regtest.vault.CheckpointVault',return_value=self.vault):
            module.require_recovery_source_equivalence(owner,self.core,PASSWORD,anchor)
            module._append(owner,'a'*32,action=action,state='COMMIT',target_identity=identity,
                           source_anchor=(1,'b'*64),target_anchor=(2,'c'*64))
            module.require_recovery_source_equivalence(owner,self.core,PASSWORD,anchor)
        anchor.advance.assert_not_called();anchor._advance_unlocked.assert_not_called()

    def test_audit_decoding_errors_are_normalized_for_managed_entries(self):
        owner,anchor=self.setup_source();self.begin(owner)
        with patch('wam_regtest.vault.CheckpointVault',return_value=self.vault),\
                patch.object(module,'_require_no_divergent_source',side_effect=sqlite3.DatabaseError('bad')):
            with self.assertRaisesRegex(module.ManagedWalletError,'SOURCE_AMBIGUOUS'):
                module.require_recovery_source_equivalence(owner,self.core,PASSWORD,anchor)

    def test_recovery_refuses_divergence_before_core_restore_or_reference_publication(self):
        owner,anchor=self.setup_source();checkpoint._publish_reference(owner,'a'*32)
        changed=deepcopy(self.data);changed['tables']['reservations'][0][3]='uncertain';self.orphan(changed)
        before=self.preserved(owner)
        with patch.object(module,'_inputs'),patch.object(module.custody,'anchor',return_value=anchor),\
                patch('wam_regtest.vault.CheckpointVault',return_value=self.vault),\
                patch('wam_regtest.wallet_session.WalletCoreCli') as rpc,\
                patch.object(module,'_append') as append:
            with self.assertRaisesRegex(module.ManagedWalletError,'RECOVERY_DENIED'):module.recover_checkpoint(owner,self.core,PASSWORD,authorized=True)
            rpc.assert_not_called();append.assert_not_called()
        self.assertEqual(before,self.preserved(owner));anchor.advance.assert_not_called()

    def test_managed_open_checkpoint_and_completion_enforce_retained_source_audit(self):
        owner,anchor=self.setup_source();checkpoint._publish_reference(owner,'a'*32)
        action,_,_=self.commit(owner)
        changed=deepcopy(self.data);changed['tables']['reservations'][0][3]='signed';self.orphan(changed)
        from wam_regtest import managed_wallet_session
        from wam_regtest.wallet_session import WalletSession,WalletSessionError
        with patch.object(module,'_inputs'),patch.object(checkpoint,'_inputs'),\
                patch.object(managed_wallet_session,'_inputs'),patch.object(managed_wallet_session,'_owned'),\
                patch.object(module.custody,'anchor',return_value=anchor),\
                patch('wam_regtest.vault.CheckpointVault',return_value=self.vault),\
                patch('wam_regtest.wallet_session.WalletCoreCli'),\
                patch.object(module,'_append') as append:
            anchor.read.return_value=(2,'c'*64)
            for operation,error in ((lambda:checkpoint.checkpoint(owner,self.core,PASSWORD,authorized=True),module.ManagedWalletError),
                    (lambda:WalletSession.open_owned(owner,self.core,PASSWORD,authorized=True),WalletSessionError),
                    (lambda:module.complete_recovery(owner,self.core,PASSWORD,authorized=True,action=action),module.ManagedWalletError)):
                before=self.preserved(owner)
                with self.assertRaises(error) as caught:operation()
                self.assertEqual(caught.exception.__context__.args,
                                 ('MANAGED_RECOVERY_UNANCHORED_STATE_DIVERGED',))
                self.assertEqual(before,self.preserved(owner))
            append.assert_not_called()
        anchor.advance.assert_not_called();anchor._advance_unlocked.assert_not_called()
