"""K-09 negative crash diagnostics: NO file deletion or unlocking.

Native Core E2E must separately prove real custody. Here disposable dummy
ciphertext filenames/bytes only exercise race/shape/ledger-safe refusal.
"""
from contextlib import nullcontext
from pathlib import Path
from hashlib import sha256
import tempfile
import unittest
from unittest.mock import Mock,patch

from wam_regtest.crash_recovery import (
    _candidate_inventory,inspect_owner_crash_residue,CrashRecoveryRefusal,
    MAX_CANDIDATES,
)
from wam_regtest.vault import CheckpointVault


class K09CrashWindowContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="k09-no-private-wallet-")
        self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name).resolve()
        self.stage=self.folder/(".stage-"+"a"*32)
        self.snap=lambda n:self.folder/f"snapshot-{n:09d}.enc"
        self.data=b"PUBLIC_SYNTHETIC_REGTEST_NOT_A_REAL_WALLET"

    def save(self,path,raw=None):
        path.write_bytes(self.data if raw is None else raw)
        return path

    def preview(self,generation=3):
        return _candidate_inventory(self.folder,generation)

    def test_crash_mid_ciphertext_write_stage_only_preserved(self):
        self.save(self.stage,b"\x00\x01truncated-not-authenticated")
        observed=self.preview()
        self.assertEqual(observed["stage_count"],1)
        self.assertEqual(observed["future_snapshot_count"],0)
        self.assertEqual(observed["candidate_count"],1)
        self.assertFalse(observed["safe_to_discard_proven"])
        self.assertFalse(observed["operator_discard_available"])
        self.assertFalse(observed["signed_or_uncertain_reservations_reconciled"])
        self.assertEqual(self.stage.read_bytes(),b"\x00\x01truncated-not-authenticated")
        self.assertEqual(len(list(self.folder.iterdir())),1)

    def test_crash_after_link_before_unlink_contains_both_paths(self):
        self.save(self.stage)
        future=self.snap(4)
        try:future.hardlink_to(self.stage)
        except (OSError,NotImplementedError):
            self.skipTest("native test filesystem cannot make a hardlink")
        info=self.preview()
        self.assertEqual(info["stage_count"],1)
        self.assertEqual(info["future_snapshot_count"],1)
        self.assertEqual(info["stage_future_snapshot_link_pairs"],1)
        self.assertFalse(info["safe_to_discard_proven"])
        self.assertEqual(self.stage.read_bytes(),self.data)
        self.assertEqual(future.read_bytes(),self.data)
        self.assertEqual(self.stage.stat().st_nlink,2)

    def test_two_crashes_produce_set_of_future_generations(self):
        first=self.save(self.snap(4))
        second=self.save(self.snap(5),b"SECOND_PUBLIC_UNANCHOR")
        observed=self.preview()
        self.assertEqual(observed["stage_count"],0)
        self.assertEqual(observed["future_snapshot_count"],2)
        self.assertEqual(observed["candidate_count"],2)
        self.assertTrue(observed["multiple_future_generations"])
        self.assertFalse(observed["safe_to_discard_proven"])
        self.assertEqual(first.read_bytes(),self.data)
        self.assertEqual(second.read_bytes(),b"SECOND_PUBLIC_UNANCHOR")

    def test_multi_stage_plus_linked_and_multiple_future_snapshots(self):
        self.save(self.stage)
        self.snap(4).hardlink_to(self.stage)
        self.save(self.folder/(".stage-"+"b"*32),b"SECOND_INTERRUPTED")
        self.save(self.snap(5),b"UNANCHORED_DIFFERENT")
        observed=self.preview()
        self.assertEqual(observed["stage_count"],2)
        self.assertEqual(observed["future_snapshot_count"],2)
        self.assertEqual(observed["stage_future_snapshot_link_pairs"],1)
        self.assertTrue(observed["multiple_future_generations"])
        self.assertEqual(len(list(self.folder.iterdir())),4)

    def test_historical_and_anchored_checkpoint_not_classified(self):
        for n in (1,2,3):
            self.save(self.snap(n))
        self.assertEqual(self.preview()["candidate_count"],0)
        self.assertEqual(len(list(self.folder.iterdir())),3)

    def test_symlink_to_newer_checkpoint_is_denied_without_read(self):
        dest=self.save(self.snap(2))
        link=self.snap(4)
        try:link.symlink_to(dest)
        except (OSError,NotImplementedError):
            self.skipTest("native symlink unsupported")
        with self.assertRaisesRegex(
                CrashRecoveryRefusal,"K09_RESIDUE_NATIVE_METADATA_DENIED"):
            self.preview()
        self.assertTrue(link.is_symlink())
        self.assertEqual(dest.read_bytes(),self.data)

    def test_hardlinked_to_external_file_not_mistaken_for_permission(self):
        outside=self.save(self.folder/"original.enc")
        self.stage.hardlink_to(outside)
        view=self.preview()
        self.assertEqual(view["stage_future_snapshot_link_pairs"],0)
        self.assertFalse(view["safe_to_discard_proven"])
        self.assertTrue(outside.exists())

    def test_bounded_candidate_set_fails_closed_before_any_mutation(self):
        for n in range(4,4+MAX_CANDIDATES+1):
            self.save(self.snap(n))
        with self.assertRaisesRegex(
                CrashRecoveryRefusal,"K09_RESIDUE_COUNT_EXCEEDED"):
            self.preview()
        self.assertEqual(len(list(self.folder.iterdir())),MAX_CANDIDATES+1)

    def test_wrong_anchor_generation_and_relative_directory_denied(self):
        for value in (0,-1,True,None,10**9):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                        CrashRecoveryRefusal,"K09_RESIDUE_SCOPE_DENIED"):
                    _candidate_inventory(self.folder,value)
        with self.assertRaises(CrashRecoveryRefusal):
            _candidate_inventory(Path("relative"),3)

    def test_no_operator_consent_no_native_auth_never_reads_or_modifies(self):
        vault=CheckpointVault.__new__(CheckpointVault)
        vault.directory=self.folder
        vault.anchor=Mock()
        vault._storage=Mock()
        with self.assertRaisesRegex(
                CrashRecoveryRefusal,"K09_OPERATOR_CONSENT_REQUIRED"):
            inspect_owner_crash_residue(vault,b"twelve-byte-pw")
        vault.anchor.lease.assert_not_called()
        vault._storage.read.assert_not_called()

    def test_bad_or_missing_owner_secret_denied_before_native_io(self):
        vault=CheckpointVault.__new__(CheckpointVault)
        vault.directory=self.folder
        vault.anchor=Mock()
        vault._storage=Mock()
        for password in (None,"not-bytes",b"",b"short",b"t"*1025):
            with self.subTest(kind=type(password).__name__):
                with self.assertRaises(CrashRecoveryRefusal):
                    inspect_owner_crash_residue(vault,password,authorized=True)
        vault.anchor.lease.assert_not_called()
        vault._storage.read.assert_not_called()


if __name__=="__main__":
    unittest.main()
