"""Single-writer lease negatives use only disposable profile fixture files."""
from pathlib import Path
import os
import tempfile
import unittest

from wam_regtest.persistent_profile import create_disposable_profile,PersistentProfileError
from wam_regtest.persistent_lease import hold_profile

A='a'*64
B='b'*64
C='c'*64


@unittest.skipUnless(os.name=='posix','Windows requires a separate native ACL and lease review')
class SingleWriterLeaseContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='wam-t05-lease-')
        self.addCleanup(self.temp.cleanup)
        parent=Path(self.temp.name).resolve(strict=True)/'wam-fusion-regtest-profiles'
        parent.mkdir(mode=0o700)
        self.root,_=create_disposable_profile(parent,expected_genesis=A,
                 expected_node_sha256=B,expected_cli_sha256=C,authorized=True)

    def lease(self,**kwargs):
        return hold_profile(self.root,expected_genesis=kwargs.get('genesis',A),
                            expected_node_sha256=B,expected_cli_sha256=C)

    def test_competing_lease_refused_and_next_owner_can_acquire(self):
        with self.lease() as receipt:
            self.assertFalse(receipt['persistent_runtime_qualified'])
            with self.assertRaisesRegex(PersistentProfileError,'PROFILE_SINGLE_WRITER_BUSY'):
                with self.lease():pass
        with self.lease() as receipt:
            self.assertEqual(receipt['network'],'regtest')

    def test_changed_profile_pin_denied_before_lock_creation(self):
        with self.assertRaisesRegex(PersistentProfileError,'PROFILE_TRUST_PINS_MISMATCH'):
            with self.lease(genesis='f'*64):pass
        self.assertFalse((self.root/'session.lock').exists())

    def test_symlink_lock_denied(self):
        target=self.root/'separate'
        target.write_bytes(b'')
        target.chmod(0o600)
        (self.root/'session.lock').symlink_to(target)
        with self.assertRaisesRegex(PersistentProfileError,'PROFILE_LEASE_UNVERIFIED'):
            with self.lease():pass

    def test_inode_swap_during_lease_detected_without_deleting_replacement(self):
        lock=self.root/'session.lock'
        with self.assertRaisesRegex(PersistentProfileError,'PROFILE_LEASE_INODE_CHANGED'):
            with self.lease():
                lock.unlink()
                lock.write_bytes(b'')
                lock.chmod(0o600)
        self.assertTrue(lock.exists())
