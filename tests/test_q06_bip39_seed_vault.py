"""Q06 B1 pure contract tests; fake native authority is NOT physical/E2E proof.

Real pinned WSP derivation and AES-GCM/scrypt are exercised; storage and
native anti-rollback anchors are injected only at the test boundary.
"""
from contextlib import contextmanager
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from mnemonic import Mnemonic
from wam_regtest.bip39_seed_vault import (
    Bip39SeedCustodyError, _folder, _password, _record,
    create_seed_container, open_seed_container,
    create_owned_seed_container, open_owned_seed_container,
)

SOURCE = Path(importlib.util.find_spec("wam_sp").origin).resolve().parents[2]
PUBLIC_12 = Mnemonic("english").to_mnemonic(bytes(16))
PASSWORD = "disposable q06 source test password"


class FakeStorage:
    def __init__(self):
        self.ciphertexts = {}

    def validate_directory(self, directory):
        if not directory.is_dir() or directory.is_symlink():
            raise ValueError("FAKE_CUSTODY_DENIED")

    def publish(self, folder, name, ciphertext):
        k = (str(folder), name)
        if k in self.ciphertexts:
            raise ValueError("FAKE_CREATE_ONLY_DENIED")
        self.ciphertexts[k] = ciphertext
        (folder / name).write_bytes(ciphertext)  # fake publication namespace only

    def read(self, folder, name):
        return self.ciphertexts[(str(folder), name)]


class FakeAnchor:
    def __init__(self):
        self.current = None
        self.fail_advance = False

    @contextmanager
    def lease(self):
        yield

    def read(self):
        return self.current

    def _advance_unlocked(self, before, after):
        if self.fail_advance:
            raise ValueError("INJECTED_NATIVE_CAS_FAILURE")
        if self.current != before or before is not None or after[0] != 1:
            raise ValueError("FAKE_CAS_DENIED")
        self.current = after


class Q06SeedContainerContracts(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="q06-source-only-")
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name)
        self.storage = FakeStorage()
        self.anchors = {}
        def native(folder, source, keychain=None):
            # Keep the test realistic about source pinning even though
            # native storage/anchor acquisition is deliberately fake.
            from wam_regtest.wsp_live import _pinned_source
            _pinned_source(source)
            wallet_id = _folder(folder)
            self.storage.validate_directory(folder)
            return wallet_id, self.storage, self.anchors.setdefault(wallet_id, FakeAnchor())
        self.addCleanup(patch.stopall)
        patch("wam_regtest.bip39_seed_vault._native", side_effect=native).start()
        patch("wam_regtest.bip39_seed_vault.custody.storage", return_value=self.storage).start()
        patch("wam_regtest.bip39_seed_vault.custody.create_directory",
              side_effect=lambda p: p.mkdir(mode=0o700)).start()

    def create(self, parent=None, phrase=PUBLIC_12):
        return create_seed_container(
            self.parent if parent is None else parent, SOURCE, PASSWORD, phrase,
            authorized_disposable=True,
        )

    def test_sealed_create_reopen_fresh_restore_identical_bip352(self):
        folder, original = self.create()
        ciphertext = self.storage.read(folder, "seed-000000001.enc")
        self.assertNotIn(PUBLIC_12.encode(), ciphertext)
        self.assertNotIn(original["receive_code"].encode(), ciphertext)
        with open_seed_container(folder, SOURCE, PASSWORD) as keys:
            self.assertEqual(keys.public_metadata(), original)
            self.assertEqual(len(keys._seed), 64)
        # New independent container/anchor from the mnemonic, not an
        # adoption/copy of the old keychain or ciphertext.
        fresh = self.parent / "separate-fresh-root"
        fresh.mkdir(mode=0o700)
        restored_folder, restored = self.create(fresh)
        self.assertNotEqual(folder, restored_folder)
        self.assertEqual(original["receive_code"], restored["receive_code"])
        self.assertEqual(original["account_id"], restored["account_id"])
        with open_seed_container(restored_folder, SOURCE, PASSWORD) as recovered:
            self.assertEqual(recovered.public_metadata(), original)

    def test_wrong_password_and_ciphertext_tamper_do_not_repair(self):
        folder, _ = self.create()
        old = self.storage.read(folder, "seed-000000001.enc")
        with self.assertRaisesRegex(Bip39SeedCustodyError, "Q06_SEED_REOPEN_DENIED"):
            open_seed_container(folder, SOURCE, PASSWORD + "wrong")
        self.assertEqual(old, self.storage.read(folder, "seed-000000001.enc"))
        self.storage.ciphertexts[(str(folder), "seed-000000001.enc")] = old[:-1] + bytes([old[-1] ^ 1])
        with self.assertRaises(Bip39SeedCustodyError):
            open_seed_container(folder, SOURCE, PASSWORD)
        self.assertIsNotNone(self.anchors[_folder(folder)].read())

    def test_missing_anchor_does_not_adopt_orphan_or_recreate(self):
        folder, _ = self.create()
        a = self.anchors[_folder(folder)]
        before = self.storage.read(folder, "seed-000000001.enc")
        a.current = None
        with self.assertRaises(Bip39SeedCustodyError):
            open_seed_container(folder, SOURCE, PASSWORD)
        self.assertIsNone(a.read())
        self.assertEqual(self.storage.read(folder, "seed-000000001.enc"), before)
        # A failed CAS leaves an orphan, never promotes it.
        fresh = self.parent / "cas-injected-root"
        fresh.mkdir(mode=0o700)
        previous = FakeAnchor()
        previous.fail_advance = True
        original_native = __import__("wam_regtest.bip39_seed_vault", fromlist=["_native"])
        def refusing(folder, source, keychain=None):
            from wam_regtest.wsp_live import _pinned_source
            _pinned_source(source)
            return _folder(folder), self.storage, previous
        with patch.object(original_native, "_native", side_effect=refusing):
            with self.assertRaises(Bip39SeedCustodyError):
                self.create(fresh)
        self.assertIsNone(previous.read())
        self.assertEqual(len([x for x in self.storage.ciphertexts if x[0].startswith(str(fresh))]), 1)

    def test_unexpected_residue_refuses_reopen_and_preserves_evidence(self):
        folder, _ = self.create()
        unexpected = folder / "unknown-sidecar.enc"
        unexpected.write_bytes(b"untrusted source-only sidecar")
        with self.assertRaisesRegex(Bip39SeedCustodyError, "Q06_SEED_REOPEN_DENIED"):
            open_seed_container(folder, SOURCE, PASSWORD)
        self.assertTrue(unexpected.exists())
        self.assertIsNotNone(self.anchors[_folder(folder)].read())

    def test_existing_q05_profile_and_bad_consent_fail_before_publication(self):
        with self.assertRaises(Bip39SeedCustodyError):
            create_seed_container(self.parent, SOURCE, PASSWORD, PUBLIC_12)
        conflict = self.parent / "wallet-vault"
        conflict.mkdir(mode=0o700)
        with self.assertRaisesRegex(Bip39SeedCustodyError, "Q06_SEED_Q05_PROFILE_CONFLICT"):
            self.create()
        self.assertEqual(self.storage.ciphertexts, {})
        self.assertEqual(self.anchors, {})
        self.assertTrue(conflict.is_dir())

    def test_owner_binding_rejects_ciphertext_adoption_into_other_core(self):
        first = "a" * 64
        another = "b" * 64
        folder, expected = create_seed_container(
            self.parent, SOURCE, PASSWORD, PUBLIC_12, authorized_disposable=True,
            owner_binding=first,
        )
        with open_seed_container(folder, SOURCE, PASSWORD, owner_binding=first) as keys:
            self.assertEqual(keys.public_metadata(), expected)
        for wrong in (None, another):
            with self.assertRaises(Bip39SeedCustodyError):
                open_seed_container(folder, SOURCE, PASSWORD, owner_binding=wrong)
        with self.assertRaises(Bip39SeedCustodyError):
            create_seed_container(
                self.parent, SOURCE, PASSWORD, PUBLIC_12,
                authorized_disposable=True, owner_binding="malformed",
            )

    def test_owned_core_boundary_denies_unverified_owner_and_foreign_path(self):
        fake_owner = SimpleNamespace(directory=self.parent, root=self.parent, profile={})
        # Without the real Q05 CoreSupervisor/process/journal, direct use must
        # fail before any new native file/anchor publication.
        with self.assertRaises(ValueError):
            create_owned_seed_container(
                fake_owner, SOURCE, PASSWORD.encode(), PUBLIC_12, authorized=True,
            )
        self.assertFalse(self.storage.ciphertexts)
        # Contract-injected allowed owner verifies that the authenticated
        # Core-owner binder is sent into the actual encrypted profile record.
        binding = "c" * 64
        with (patch("wam_regtest.bip39_seed_vault._owned_password", return_value=PASSWORD),
              patch("wam_regtest.bip39_seed_vault._owner_binding", return_value=binding),
              patch("wam_regtest.managed_wallet_checkpoint._owned")):
            folder, original = create_owned_seed_container(
                fake_owner, SOURCE, PASSWORD.encode(), PUBLIC_12, authorized=True,
            )
            with open_owned_seed_container(
                fake_owner, folder, SOURCE, PASSWORD.encode(), authorized=True,
            ) as keys:
                self.assertEqual(keys.public_metadata(), original)
            with self.assertRaises(Bip39SeedCustodyError):
                open_owned_seed_container(
                    fake_owner, self.parent.parent / folder.name, SOURCE,
                    PASSWORD.encode(), authorized=True,
                )
            with patch("wam_regtest.bip39_seed_vault._owner_binding", return_value="d"*64):
                with self.assertRaises(Bip39SeedCustodyError):
                    open_owned_seed_container(
                        fake_owner, folder, SOURCE, PASSWORD.encode(), authorized=True,
                    )

    def test_invalid_password_folder_anchor_and_24_word_are_denied(self):
        for bad in ("short", "", True, None, "\ud800"):
            with self.assertRaises(Bip39SeedCustodyError):
                _password(bad)
        for bad in (self.parent / "wallet-vault", self.parent / "bip39-12-00", Path("relative")):
            with self.assertRaises(Bip39SeedCustodyError):
                _folder(bad)
        for bad in (None, (True, "0"*64), (0, "0"*64), (1, "xyz"), [1, "0"*64]):
            with self.assertRaises(Bip39SeedCustodyError):
                _record(bad)
        phrase24 = Mnemonic("english").to_mnemonic(bytes(32))
        with self.assertRaises(ValueError):
            self.create(phrase=phrase24)
        self.assertEqual(self.storage.ciphertexts, {})


if __name__ == "__main__":
    unittest.main()
