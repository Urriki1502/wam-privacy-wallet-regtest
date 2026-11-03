"""Q06 B2c source contracts: real WSP SQLite/crypto, FAKE Core+OS owner.

Not evidence for genuine signed Core or native clean-device acceptance.
"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

from mnemonic import Mnemonic
from wam_regtest.bip39_12 import Bip39Regtest12Keys
from wam_regtest.bip39_scanner_checkpoint import encode_candidate
from wam_regtest.bip39_reconcile import (
    SeededReconciliationError, reconcile_owned_readonly,
)
from wam_regtest.wsp_live import REGTEST_GENESIS
from wam_sp.scanner import Scanner

SOURCE = Path(importlib.util.find_spec("wam_sp").origin).resolve().parents[2]
PHRASE = Mnemonic("english").to_mnemonic(bytes(16))
PASSWORD = b"Q06 readonly reconciliation test"
BINDING = "a" * 64


class _FakeRpc:
    def __init__(self, *args):
        self.attestations = 0
        self._transport = None

    def attest(self):
        self.attestations += 1

    def call(self, method, args=None):
        if method == "getblockcount":return 0
        if method in ("getbestblockhash", "getblockhash"):return REGTEST_GENESIS
        raise ValueError("FAKE_RPC_METHOD_DENIED")


class _FakeGuard:
    def __init__(self, path):
        self.path = path
        self.check()

    def check(self):
        if not self.path.is_file():
            raise ValueError("SOURCE_GUARD_DENIED")

    def remove_owned(self):
        self.check()
        self.path.unlink()

    def close(self):
        pass


class _FakePrivateStorage:
    def validate_directory(self, path):
        if not path.is_dir() or path.is_symlink():
            raise ValueError("SOURCE_STORAGE_DENIED")


class Q06ReadOnlyReconcileContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="q06-readonly-source-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.owner = SimpleNamespace(directory=self.root, cli=self.root / "fake-cli")
        self.seed_folder = self.root / ("bip39-12-" + "b" * 32)
        self.keys = Bip39Regtest12Keys(PHRASE, source=SOURCE, authorized_disposable=True)
        self.addCleanup(self.keys.close)
        self.original = Scanner(self.root / "original.sqlite", self.keys.accounts())
        self.addCleanup(self.original.close)
        self.original.ready = True
        self.original.verified_tip = self.original.store.tip()
        self.candidate = encode_candidate(
            self.keys, self.original, PASSWORD.decode(),
            owner_binding=BINDING, trusted_tip=(0, REGTEST_GENESIS),
        )
        self.receipt = {
            "status": "ENCRYPTED_CANDIDATE_NEEDS_FRESH_SQLITE_RESTORE",
            "height": 0, "tip": REGTEST_GENESIS,
            "account_id": self.keys.public_metadata()["account_id"],
            "signer_allowed": False, "broadcast_allowed": False,
            "mainnet_allowed": False,
        }
        patches = [
            patch("wam_regtest.bip39_reconcile._owned_password", return_value=PASSWORD.decode()),
            patch("wam_regtest.bip39_reconcile._owned"),
            patch("wam_regtest.bip39_reconcile._owned_tip",
                  return_value=(0, REGTEST_GENESIS)),
            patch("wam_regtest.bip39_reconcile.read_owned_candidate",
                  return_value=(self.candidate, self.receipt)),
            patch("wam_regtest.bip39_reconcile.open_owned_seed_container",
                  side_effect=lambda *a, **kw: Bip39Regtest12Keys(
                      PHRASE, source=SOURCE, authorized_disposable=True)),
            patch("wam_regtest.bip39_reconcile.WalletCoreCli", _FakeRpc),
            patch("wam_regtest.bip39_reconcile.RuntimeGuard", _FakeGuard),
            patch("wam_regtest.bip39_reconcile.custody.storage",
                  return_value=_FakePrivateStorage()),
            patch("wam_regtest.bip39_native_checkpoint._owner_binding",
                  return_value=BINDING),
        ]
        if sys.platform == "win32":
            # Unit fixture only: actual native DACL is qualified separately.
            patches.append(patch(
                "wam_regtest.windows_private_storage.create_managed_runtime",
                side_effect=lambda target:target.touch(exist_ok=False)))
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def check(self):
        return reconcile_owned_readonly(
            self.owner, self.seed_folder, SOURCE, PASSWORD, authorized=True,
        )

    def test_restore_against_attested_mock_core_and_remove_only_fresh_runtime(self):
        public = self.check()
        self.assertEqual(public["status"], "Q06_RECONCILED_READ_ONLY_LOCKED")
        self.assertEqual(public["tip"], REGTEST_GENESIS)
        self.assertEqual(public["account_id"], self.keys.public_metadata()["account_id"])
        self.assertEqual(public["reservation_count"], 0)
        self.assertIs(public["signer_allowed"], False)
        self.assertIs(public["broadcast_allowed"], False)
        self.assertIs(public["mainnet_allowed"], False)
        self.assertIs(public["fresh_runtime_removed"], True)
        self.assertFalse(list(self.root.glob("q06-reconcile-*.sqlite")))
        self.assertTrue((self.root / "original.sqlite").exists())

    def test_core_tip_drift_fails_before_any_runtime_creation(self):
        with patch("wam_regtest.bip39_reconcile._owned_tip",
                   return_value=(1, "f" * 64)):
            with self.assertRaises(SeededReconciliationError):
                self.check()
        self.assertFalse(list(self.root.glob("q06-reconcile-*.sqlite")))

    def test_existing_runtime_not_overwritten_even_when_nonce_collides(self):
        collide = self.root / ("q06-reconcile-" + "c" * 32 + ".sqlite")
        collide.write_bytes(b"operator-owned-state")
        with patch("wam_regtest.bip39_reconcile.secrets.token_hex", return_value="c" * 32):
            with self.assertRaises(SeededReconciliationError):
                self.check()
        self.assertEqual(collide.read_bytes(), b"operator-owned-state")


if __name__ == "__main__":
    unittest.main()
