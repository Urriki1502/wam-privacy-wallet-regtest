"""Real native journal storage, mocked Core; no platform acceptance claim."""
import json
import sys
import unittest
from unittest.mock import patch

import test_q05_core_supervisor as fixture
from wam_regtest import core_supervisor as module
from wam_regtest.supervisor_journal import LifecycleJournal,JournalError
from wam_regtest.supervisor_store import read_exact


class JournalContracts(unittest.TestCase):
    setUp=fixture.SupervisorLifecycleUnit.setUp
    owner=fixture.SupervisorLifecycleUnit.owner

    def test_clean_restart_verifies_chain_and_preserves_datadir(self):
        owner=self.owner();owner.journal.append('STARTING')
        owner.journal.append('RUNNING',12345);owner.journal.append('STOPPING',12345)
        owner.journal.append('CLEAN');old=owner.directory.stat().st_ino
        owner.close();new=self.owner()
        self.assertFalse(new._faulted);self.assertEqual(new.journal.state,'CLEAN')
        self.assertEqual(new.directory.stat().st_ino,old)
        self.assertEqual(len(new.journal.events),5)

    def test_supervisor_crash_intent_without_clean_marker_refuses_reentry(self):
        owner=self.owner();owner.journal.append('STARTING')
        owner.journal.append('RUNNING',12345)
        owner.close()  # Fixture: no real process; preserve durable dirty record.
        new=self.owner();self.assertTrue(new._faulted)
        self.assertEqual(new.status()['state'],'recovery-needed')
        with patch.object(module.subprocess,'Popen') as spawn:
            with self.assertRaises(module.ManagedCoreError):new.start()
            with self.assertRaises(module.ManagedCoreError):new.recover_stop()
            spawn.assert_not_called()

    def test_truncated_record_is_retained_and_refused(self):
        owner=self.owner();owner.journal.append('STARTING');owner.close()
        file=self.root/'supervisor.event.000002';raw=file.read_bytes()[:-8];file.write_bytes(raw)
        with self.assertRaises(JournalError):self.owner()
        self.assertEqual(file.read_bytes(),raw)

    def test_missing_middle_and_forged_clean_are_not_repaired(self):
        owner=self.owner();owner.journal.append('STARTING');owner.journal.append('FAULT');owner.close()
        path=self.root/'supervisor.event.000002';path.rename(self.root/'preserved-unit-event')
        with self.assertRaises(JournalError):self.owner()
        self.assertFalse(path.exists())

    def test_wrong_key_or_profile_refused(self):
        owner=self.owner()
        for profile,secret in ((dict(owner.profile,profile_id='f'*32),b'x'*32),
                               (owner.profile,b'x'*32)):
            with self.assertRaises(JournalError):
                LifecycleJournal(self.root,profile,secret,owner.directory)

    def test_changed_datadir_identity_refuses_even_same_config(self):
        owner=self.owner()
        if sys.platform=='win32':
            # Native no-delete-share guards prevent the POSIX-style live
            # rename attack. Prove that first, then exercise durable identity
            # checking after normal owner/lease closure permits replacement.
            with self.assertRaises(PermissionError):
                owner.directory.rename(self.root/'preserved-chain')
            owner.close()
        owner.directory.rename(self.root/'preserved-chain')
        self.create_private_directory(owner.directory)
        with self.assertRaises(JournalError):owner.journal.reserve_start()

    def test_state_machine_and_capacity_fail_before_process_creation(self):
        owner=self.owner()
        with self.assertRaises(JournalError):owner.journal.append('CLEAN')
        with patch('wam_regtest.supervisor_journal.MAX_EVENTS',16), \
             patch.object(module.subprocess,'Popen') as spawn:
            with self.assertRaises(JournalError):owner.start()
            spawn.assert_not_called()
        self.assertEqual(owner.journal.state,'CLEAN')

    def test_no_silent_legacy_profile_initialization(self):
        owner=self.owner();owner.close()
        (self.root/'supervisor.event.000001').rename(self.root/'preserved-unit-event')
        with self.assertRaises(JournalError):self.owner()
        self.assertFalse((self.root/'supervisor.event.000001').exists())
