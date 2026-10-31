"""Actual native reference storage/identity; no mock recovery E2E claims."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import test_q05_core_supervisor as fixture
from wam_regtest import wallet_recovery as module
from wam_regtest.supervisor_identity import directory_identity


class RecoveryReferenceContracts(unittest.TestCase):
    setUp=fixture.SupervisorLifecycleUnit.setUp
    owner=fixture.SupervisorLifecycleUnit.owner

    def target(self,owner):
        action='1234567890abcdef';path=owner.directory/('wallet-recovery-'+action)
        self.create_private_directory(path)
        return action,path,directory_identity(path)

    def begin(self,owner):
        action,path,identity=self.target(owner)
        module._append(owner,'a'*32,action=action,state='BEGIN',target_identity=identity,
                       source_anchor=(1,'b'*64))
        return action,path,identity

    def commit(self,owner):
        action,path,identity=self.begin(owner)
        module._append(owner,'a'*32,action=action,state='COMMIT',target_identity=identity,
                       source_anchor=(1,'b'*64),target_anchor=(2,'c'*64))
        return action,path,identity

    def test_no_recovery_uses_original_location_and_public_action_needs_consent(self):
        owner=self.owner()
        self.assertEqual(module.active_location(owner,'a'*32),
                         (owner.directory/'wallet-vault','wallet-runtime.sqlite',None))
        with self.assertRaisesRegex(module.ManagedWalletError,'EXPLICIT_CONSENT'):
            module.recover_checkpoint(object(),Path('/unused'),b'public-test-password')

    def test_pending_never_falls_back_to_original_runtime_or_vault(self):
        owner=self.owner();self.begin(owner)
        before=(self.root/'supervisor.recovery.000001').read_bytes()
        with self.assertRaisesRegex(module.ManagedWalletError,'RECOVERY_PENDING'):
            module.active_location(owner,'a'*32)
        self.assertEqual((self.root/'supervisor.recovery.000001').read_bytes(),before)

    def test_commit_selects_bound_target_and_enforces_native_anchor_floor(self):
        owner=self.owner();action,path,_=self.commit(owner)
        folder,runtime,floor=module.active_location(owner,'a'*32)
        self.assertEqual(folder,path);self.assertEqual(runtime,'wallet-runtime-recovery-'+action+'.sqlite')
        for current in (None,(1,'b'*64),(2,'d'*64)):
            with self.assertRaises(module.ManagedWalletError):module.require_anchor_floor(current,floor)
        module.require_anchor_floor((2,'c'*64),floor)
        module.require_anchor_floor((3,'e'*64),floor)

    def test_missing_or_truncated_reference_is_retained_and_refused(self):
        owner=self.owner();self.commit(owner);owner.close()
        first=self.root/'supervisor.recovery.000001';original=first.read_bytes()
        first.rename(self.root/'preserved-reference')
        with self.assertRaises(module.ManagedWalletError):module.active_location(owner,'a'*32)
        (self.root/'preserved-reference').rename(first);first.write_bytes(original[:-11])
        with self.assertRaises(module.ManagedWalletError):module.active_location(owner,'a'*32)
        self.assertEqual(first.read_bytes(),original[:-11])

    def test_wallet_profile_and_mac_are_not_interchangeable(self):
        owner=self.owner();self.commit(owner)
        with self.assertRaises(module.ManagedWalletError):module.active_location(owner,'d'*32)
        original=owner.profile;owner.profile=dict(original,profile_id='e'*32)
        with self.assertRaises(module.ManagedWalletError):module.active_location(owner,'a'*32)
        owner.profile=original
        file=self.root/'supervisor.recovery.000002';row=json.loads(file.read_bytes())
        row['mac']='0'*64;raw=json.dumps(row).encode();file.write_bytes(raw)
        with self.assertRaises(module.ManagedWalletError):module.active_location(owner,'a'*32)
        self.assertEqual(file.read_bytes(),raw)

    def test_invalid_commit_cannot_publish_without_matching_begin(self):
        owner=self.owner();action,_,identity=self.target(owner)
        with self.assertRaisesRegex(module.ManagedWalletError,'TRANSITION_DENIED'):
            module._append(owner,'a'*32,action=action,state='COMMIT',target_identity=identity,
                           source_anchor=(1,'b'*64),target_anchor=(2,'c'*64))
        self.assertFalse(module.has_recovery_records(owner))

    def test_target_directory_replacement_is_not_adopted(self):
        owner=self.owner();_,path,_=self.commit(owner)
        if sys.platform=='win32':
            from wam_regtest.windows_private_storage import directory_guard
            with directory_guard(path):
                with self.assertRaises(PermissionError):path.rename(self.root/'preserved-target')
            owner.close()
        path.rename(self.root/'preserved-target');self.create_private_directory(path)
        with self.assertRaisesRegex(module.ManagedWalletError,'CONTAINER_CHANGED'):
            module.active_location(owner,'a'*32)

    def test_capacity_and_bad_runtime_names_refuse_before_mutation(self):
        owner=self.owner();action,_,identity=self.commit(owner)
        before=(self.root/'supervisor.recovery.000002').read_bytes()
        with patch.object(module,'MAX_EVENTS',2):
            with self.assertRaises(module.ManagedWalletError):
                module._append(owner,'a'*32,action=action,state='BEGIN',target_identity=identity,
                               source_anchor=(2,'c'*64))
        self.assertEqual((self.root/'supervisor.recovery.000002').read_bytes(),before)
        for name in ('../wallet-runtime.sqlite','foreign.sqlite','wallet-runtime-recovery-NOTHEX.sqlite'):
            with self.assertRaises(module.ManagedWalletError):module._runtime(owner,name)
