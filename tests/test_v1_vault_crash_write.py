"""Q05 crash-write negative contracts; NEVER counts as live-Core acceptance.

No mocks on the wallet's runtime route. These tests only check that native
vault code refuses ambiguous filesystem publication before decryption, backup
or checkpoint overwrite. The separately run signed-Core E2E kills processes
during genuine SQLite and encrypted checkpoint writes.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock
import unittest

from wam_regtest.vault import CheckpointVault,VaultError


class CrashWriteDenial(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(prefix="wam-q05-crash-")
        self.addCleanup(self.temp.cleanup)
        self.dir=Path(self.temp.name)
        self.vault=CheckpointVault.__new__(CheckpointVault)
        self.vault.directory=self.dir
        self.vault.anchor=Mock()
        self.vault._storage=Mock()
        self.record=(3,"a"*64)

    def test_anchored_historical_generations_are_not_misidentified_as_orphans(self):
        for n in (1,2,3):
            (self.dir/CheckpointVault._filename(n)).write_bytes(b"historical")
        self.vault._reject_unanchored_publication(self.record)

    def test_future_generation_denied_before_any_decryption_or_adoption(self):
        (self.dir/CheckpointVault._filename(3)).write_bytes(b"anchored")
        future=self.dir/CheckpointVault._filename(4)
        future.write_bytes(b"future-do-not-delete")
        with self.assertRaisesRegex(VaultError,"VAULT_UNANCHORED_GENERATION_DENIED"):
            self.vault._load_payload(b"regtest-only-password",self.record)
        self.vault._storage.read.assert_not_called()
        self.assertEqual(future.read_bytes(),b"future-do-not-delete")

    def test_interrupted_native_atomic_stage_denied_without_cleanup(self):
        stage=self.dir/(".stage-"+"f"*32)
        stage.write_bytes(b"incomplete-native-publish")
        with self.assertRaisesRegex(VaultError,"VAULT_INTERRUPTED_PUBLICATION_DENIED"):
            self.vault._load_payload(b"regtest-only-password",self.record)
        self.vault._storage.read.assert_not_called()
        self.assertEqual(stage.read_bytes(),b"incomplete-native-publish")

    def test_fresh_wallet_cannot_reuse_unanchored_snapshot_one(self):
        pending=self.dir/CheckpointVault._filename(1)
        pending.write_bytes(b"unanchored-first-generation")
        with self.assertRaisesRegex(VaultError,"VAULT_UNANCHORED_GENERATION_DENIED"):
            self.vault._reject_unanchored_publication(None)
        self.assertTrue(pending.exists())

    def test_future_generation_does_not_depend_on_adjacent_sequence(self):
        pending=self.dir/CheckpointVault._filename(10)
        pending.write_bytes(b"unanchored-skipped-generation")
        with self.assertRaisesRegex(VaultError,"VAULT_UNANCHORED_GENERATION_DENIED"):
            self.vault._reject_unanchored_publication(self.record)

    def test_invalid_anchor_generation_fails_closed(self):
        for record in ((True,"a"*64),(-1,"a"*64)):
            with self.subTest(record=record):
                with self.assertRaisesRegex(VaultError,"VAULT_ANCHOR_GENERATION_DENIED"):
                    self.vault._reject_unanchored_publication(record)


if __name__=="__main__":
    unittest.main()
