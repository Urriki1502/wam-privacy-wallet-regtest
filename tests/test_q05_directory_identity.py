"""Native volume/file/birth identity; no simulated reboot acceptance claim."""
from hashlib import sha256
import hmac
import json
import unittest
from unittest.mock import patch

import test_q05_core_supervisor as fixture
from wam_regtest import supervisor_journal as journal
from wam_regtest.supervisor_identity import directory_identity,DirectoryIdentityError
from wam_regtest.supervisor_store import read_exact


class PersistentDirectoryContracts(unittest.TestCase):
    setUp=fixture.SupervisorLifecycleUnit.setUp
    owner=fixture.SupervisorLifecycleUnit.owner

    def test_native_identity_survives_child_content_changes(self):
        owner=self.owner();before=directory_identity(owner.directory)
        (owner.directory/'public-fixture').write_bytes(b'changed directory modification time')
        self.assertEqual(directory_identity(owner.directory),before)
        self.assertNotIn('device',before)
        self.assertGreater(before['file_id'],0)

    def test_v2_reopen_ignores_transient_mount_device_change(self):
        owner=self.owner();before=(self.root/'supervisor.event.000001').read_bytes()
        device,inode=owner.journal.legacy_identity;owner.close()
        with patch.object(journal,'_legacy_identity',return_value=[device+1,inode]):
            reopened=self.owner()
        self.assertEqual(reopened.journal.schema,journal.SCHEMA)
        self.assertFalse(reopened._faulted)
        self.assertEqual((self.root/'supervisor.event.000001').read_bytes(),before)

    def test_wrong_volume_or_birth_refuses_without_rebinding(self):
        owner=self.owner();original=dict(owner.journal.identity)
        before=(self.root/'supervisor.event.000001').read_bytes();owner.close()
        for key in ('volume','file_id',next(k for k in original if k.startswith('birth_'))):
            value=original[key]
            wrong=dict(original,**{key:('0'*len(value) if isinstance(value,str) else value+1)})
            with patch.object(journal,'directory_identity',return_value=wrong):
                with self.assertRaises(journal.JournalError):self.owner()
            self.assertEqual((self.root/'supervisor.event.000001').read_bytes(),before)

    def test_native_identity_unavailable_has_no_device_number_fallback(self):
        owner=self.owner();before=(self.root/'supervisor.event.000001').read_bytes();owner.close()
        with patch.object(journal,'directory_identity',side_effect=DirectoryIdentityError('MANAGED_DIRECTORY_NATIVE_ID_DENIED')):
            with self.assertRaises(DirectoryIdentityError):self.owner()
        self.assertEqual((self.root/'supervisor.event.000001').read_bytes(),before)

    def legacy(self,owner):
        path=self.root/'supervisor.event.000001';row=json.loads(path.read_bytes())
        row.pop('mac');row['schema']=journal.LEGACY_SCHEMA
        row['datadir_identity']=owner.journal.legacy_identity
        secret=read_exact(self.root,'supervisor.token',length=32)
        row['mac']=hmac.digest(secret,journal.LEGACY_SCHEMA.encode()+b'\n'+journal._canonical(row),'sha256').hex()
        path.write_bytes(journal._canonical(row))
        return path.read_bytes()

    def test_legacy_same_mount_reopens_without_automatic_migration(self):
        owner=self.owner();original=self.legacy(owner);owner.close()
        reopened=self.owner()
        self.assertEqual(reopened.journal.schema,journal.LEGACY_SCHEMA)
        reopened.journal.append('STARTING')
        self.assertEqual(json.loads((self.root/'supervisor.event.000002').read_text())['schema'],journal.LEGACY_SCHEMA)
        self.assertEqual((self.root/'supervisor.event.000001').read_bytes(),original)

    def test_legacy_mount_change_still_refuses_without_rewriting(self):
        owner=self.owner();original=self.legacy(owner)
        device,inode=owner.journal.legacy_identity;owner.close()
        with patch.object(journal,'_legacy_identity',return_value=[device+1,inode]):
            with self.assertRaises(journal.JournalError):self.owner()
        self.assertEqual((self.root/'supervisor.event.000001').read_bytes(),original)

    def test_schema_cannot_switch_inside_one_authenticated_chain(self):
        owner=self.owner();owner.journal.append('STARTING');owner.close()
        first=self.root/'supervisor.event.000001';self.legacy(owner)
        path=self.root/'supervisor.event.000002';row=json.loads(path.read_bytes())
        row.pop('mac');row['previous']=sha256(first.read_bytes()).hexdigest()
        secret=read_exact(self.root,'supervisor.token',length=32)
        row['mac']=hmac.digest(secret,journal.SCHEMA.encode()+b'\n'+journal._canonical(row),'sha256').hex()
        path.write_bytes(journal._canonical(row))
        with self.assertRaises(journal.JournalError):self.owner()
