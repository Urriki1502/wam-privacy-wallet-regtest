"""Q06 B2b contract fixtures; mocked native Core/anchor, REAL pinned WSP crypto.

This is NOT signed Core, physical, real native Keychain or frozen E2E proof.
"""
from contextlib import contextmanager
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from mnemonic import Mnemonic
from wam_regtest.bip39_12 import Bip39Regtest12Keys
from wam_regtest.bip39_native_checkpoint import (
    SeededNativeCheckpointError, publish_owned_candidate, read_owned_candidate,
)
from wam_regtest.bip39_scanner_checkpoint import decode_candidate
from wam_regtest.wsp_live import REGTEST_GENESIS
from wam_sp.scanner import Scanner

SOURCE = Path(importlib.util.find_spec("wam_sp").origin).resolve().parents[2]
PASSWORD = "Q06 native candidate disposable password"
SEED_ID = "f" * 32
BINDING = "a" * 64
PHRASE = Mnemonic("english").to_mnemonic(bytes(16))


class FakeStorage:
    def __init__(self):
        self.data = {}

    def validate_directory(self, path):
        if not path.is_dir() or path.is_symlink():
            raise ValueError("FAKE_PRIVATE_DIRECTORY_DENIED")

    def publish(self, folder, name, value):
        key = (str(folder), name)
        if key in self.data:
            raise ValueError("FAKE_CREATE_ONLY")
        self.data[key] = value
        (folder / name).write_bytes(value)

    def read(self, folder, name):
        return self.data[(str(folder), name)]


class FakeAnchor:
    wallet_id = "b" * 32

    def __init__(self):
        self.value = None
        self.fail_cas = False

    @contextmanager
    def lease(self):
        yield

    def read(self):
        return self.value

    def _advance_unlocked(self, before, after):
        if self.fail_cas:
            raise ValueError("INJECTED_CAS_CUT")
        if before is not None or self.value != before or after[0] != 1:
            raise ValueError("CAS_DENIED")
        self.value = after


class NativeCandidateContracts(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory(prefix="q06-native-source-")
        self.addCleanup(root.cleanup)
        self.parent = Path(root.name)
        self.owner = SimpleNamespace(directory=self.parent)
        self.seed_folder = self.parent / ("bip39-12-" + SEED_ID)
        self.seed_folder.mkdir(mode=0o700)
        self.snapshot_folder = self.parent / ("bip39-12-scan-" + SEED_ID)
        self.storage, self.anchor = FakeStorage(), FakeAnchor()
        self.crypto_keys = Bip39Regtest12Keys(PHRASE, source=SOURCE, authorized_disposable=True)
        self.addCleanup(self.crypto_keys.close)
        self.scan = Scanner(self.parent / "q06-scanner-original.sqlite", self.crypto_keys.accounts())
        self.addCleanup(self.scan.close)
        self.scan.ready = True
        self.scan.verified_tip = self.scan.store.tip()
        self.flush_calls = []
        stack = patch.multiple(
            "wam_regtest.bip39_native_checkpoint",
            _owned_password=lambda *a: PASSWORD,
            _owner_binding=lambda *a: BINDING,
            _owned_tip=lambda *a: (0, REGTEST_GENESIS),
            open_owned_seed_container=lambda *a, **kw: Bip39Regtest12Keys(
                PHRASE, source=SOURCE, authorized_disposable=True),
            _native=lambda *a, **kw: (self.storage, self.anchor),
        )
        stack.start()
        self.addCleanup(stack.stop)
        storage_patch = patch(
            "wam_regtest.bip39_native_checkpoint.custody.storage",
            return_value=self.storage,
        )
        storage_patch.start()
        self.addCleanup(storage_patch.stop)
        directory_patch = patch(
            "wam_regtest.bip39_native_checkpoint.custody.create_directory",
            side_effect=lambda p: p.mkdir(mode=0o700),
        )
        directory_patch.start()
        self.addCleanup(directory_patch.stop)
        flush = patch(
            "wam_regtest.managed_wallet_checkpoint.durable_core_checkpoint",
            side_effect=lambda *a: self.flush_calls.append(a),
        )
        flush.start()
        self.addCleanup(flush.stop)

    def publish(self):
        return publish_owned_candidate(
            self.owner, self.seed_folder, self.scan, SOURCE, PASSWORD.encode(),
            authorized=True,
        )

    def read(self):
        return read_owned_candidate(
            self.owner, self.seed_folder, SOURCE, PASSWORD.encode(), authorized=True,
        )

    def test_native_one_shot_publish_attested_tip_and_encrypted_read_roundtrip(self):
        receipt = self.publish()
        self.assertEqual(receipt["status"], "ANCHORED_ENCRYPTED_CANDIDATE_ONLY")
        self.assertEqual(receipt["height"], 0)
        self.assertEqual(receipt["tip"], REGTEST_GENESIS)
        self.assertFalse(receipt["signer_allowed"])
        self.assertFalse(receipt["broadcast_allowed"])
        self.assertEqual(len(self.flush_calls), 1)
        self.assertEqual(self.flush_calls[0][1:], (0, REGTEST_GENESIS))
        self.assertIsNotNone(self.anchor.value)
        ciphertext = self.storage.read(self.snapshot_folder, "snapshot-000000001.enc")
        self.assertNotIn(PHRASE.encode(), ciphertext)
        self.assertNotIn(self.crypto_keys.public_metadata()["receive_code"].encode(), ciphertext)
        blob, read_receipt = self.read()
        self.assertEqual(read_receipt["status"], "ENCRYPTED_CANDIDATE_NEEDS_FRESH_SQLITE_RESTORE")
        self.assertFalse(read_receipt["signer_allowed"])
        self.assertFalse(read_receipt["broadcast_allowed"])
        fresh = Scanner(self.parent / "q06-scanner-fresh.sqlite", self.crypto_keys.accounts())
        self.addCleanup(fresh.close)
        decoded = decode_candidate(
            self.crypto_keys, fresh, blob, PASSWORD, owner_binding=BINDING,
        )
        self.assertEqual(decoded["account_id"], self.crypto_keys.public_metadata()["account_id"])
        self.assertEqual(decoded["status"], "RESTORED_UNVERIFIED_NEEDS_REAL_CORE_RESYNC")
        self.assertFalse(fresh.ready)

    def test_duplicate_publication_is_denied_without_overwrite(self):
        self.publish()
        before = self.storage.read(self.snapshot_folder, "snapshot-000000001.enc")
        with self.assertRaises(SeededNativeCheckpointError):
            self.publish()
        self.assertEqual(before, self.storage.read(self.snapshot_folder, "snapshot-000000001.enc"))
        self.assertEqual(self.anchor.value[0], 1)

    def test_durable_core_flush_fails_before_new_folder_or_anchor(self):
        with patch("wam_regtest.managed_wallet_checkpoint.durable_core_checkpoint",
                   side_effect=ValueError("FAKE_CORE_FLUSH_DENIED")):
            with self.assertRaises(SeededNativeCheckpointError):
                self.publish()
        self.assertFalse(self.snapshot_folder.exists())
        self.assertIsNone(self.anchor.read())

    def test_orphan_from_anchor_cas_cut_is_preserved_never_adopted(self):
        self.anchor.fail_cas = True
        with self.assertRaises(SeededNativeCheckpointError):
            self.publish()
        orphan = self.snapshot_folder / "snapshot-000000001.enc"
        self.assertTrue(orphan.exists())
        self.assertIsNone(self.anchor.read())
        with self.assertRaises(SeededNativeCheckpointError):
            self.read()
        self.assertTrue(orphan.exists())
        with self.assertRaises(SeededNativeCheckpointError):
            self.publish()

    def test_read_denies_missing_anchor_tampering_residue_and_core_tip_drift(self):
        self.publish()
        initial = self.anchor.read()
        self.anchor.value = None
        with self.assertRaises(SeededNativeCheckpointError):
            self.read()
        self.anchor.value = initial
        ciphertext = self.storage.read(self.snapshot_folder, "snapshot-000000001.enc")
        self.storage.data[(str(self.snapshot_folder), "snapshot-000000001.enc")] = (
            ciphertext[:-1] + bytes([ciphertext[-1] ^ 1])
        )
        with self.assertRaises(SeededNativeCheckpointError):
            self.read()
        self.storage.data[(str(self.snapshot_folder), "snapshot-000000001.enc")] = ciphertext
        residue = self.snapshot_folder / "unknown-residue.enc"
        residue.write_bytes(b"untrusted")
        with self.assertRaises(SeededNativeCheckpointError):
            self.read()
        residue.unlink()
        with patch("wam_regtest.bip39_native_checkpoint._owned_tip",
                   return_value=(1, "f"*64)):
            with self.assertRaises(SeededNativeCheckpointError):
                self.read()
        self.assertEqual(self.anchor.read(), initial)

    def test_bad_scanner_identity_and_unverified_tip_refused_before_flush(self):
        self.scan.ready = False
        with self.assertRaises(SeededNativeCheckpointError):
            self.publish()
        self.assertFalse(self.flush_calls)
        self.assertFalse(self.snapshot_folder.exists())
        self.scan.ready = True
        self.scan.verified_tip = self.scan.store.tip()
        with patch("wam_regtest.bip39_native_checkpoint._owned_tip",
                   return_value=(1, "f"*64)):
            with self.assertRaises(SeededNativeCheckpointError):
                self.publish()
        self.assertFalse(self.flush_calls)
        self.assertFalse(self.snapshot_folder.exists())


if __name__ == "__main__":
    unittest.main()
