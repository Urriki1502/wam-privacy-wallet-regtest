"""Q06 scanner candidate codec: source/SQLite fixtures, NOT native Core E2E."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

from mnemonic import Mnemonic
from wam_regtest.bip39_12 import Bip39Regtest12Keys
from wam_regtest.bip39_scanner_checkpoint import (
    SeededCheckpointError, encode_candidate, decode_candidate,
)
from wam_sp.scanner import Scanner

SOURCE = Path(importlib.util.find_spec("wam_sp").origin).resolve().parents[2]
PASSWORD = "disposable Q06 scanner checkpoint test"
OWNER = "a" * 64


class Q06SeededScannerCheckpointContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="q06-scanner-codec-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.phrase = Mnemonic("english").to_mnemonic(bytes(16))
        self.keys = Bip39Regtest12Keys(
            self.phrase, source=SOURCE, authorized_disposable=True,
        )
        self.addCleanup(self.keys.close)
        self.scanners = []

    def scanner(self, name):
        obj = Scanner(self.path / (name + ".sqlite"), self.keys.accounts())
        self.scanners.append(obj)
        self.addCleanup(obj.close)
        return obj

    def _candidate(self):
        scan = self.scanner("original")
        # Pure source fixture: synthesized 'current' status for a genesis-only
        # SQLite store. NO actual Core/owner attestation is claimed or tested.
        scan.ready = True
        scan.verified_tip = scan.store.tip()
        return encode_candidate(self.keys, scan, PASSWORD,
                                owner_binding=OWNER, trusted_tip=scan.store.tip())

    def test_real_wsp_sqlite_checkpoint_roundtrip_does_not_enable_spending(self):
        payload = self._candidate()
        self.assertNotIn(self.phrase.encode(), payload)
        self.assertNotIn(self.keys.public_metadata()["receive_code"].encode(), payload)
        recovered = self.scanner("fresh")
        receipt = decode_candidate(self.keys, recovered, payload, PASSWORD, owner_binding=OWNER)
        self.assertEqual(receipt["account_id"], self.keys.public_metadata()["account_id"])
        self.assertEqual(receipt["receive_code"], self.keys.public_metadata()["receive_code"])
        self.assertEqual(receipt["claimed_height"], 0)
        self.assertEqual(receipt["claimed_tip"], recovered.store.tip()[1])
        self.assertEqual(receipt["status"], "RESTORED_UNVERIFIED_NEEDS_REAL_CORE_RESYNC")
        self.assertFalse(receipt["signer_allowed"])
        self.assertFalse(receipt["broadcast_allowed"])
        self.assertFalse(receipt["mainnet_allowed"])
        self.assertFalse(recovered.ready)
        self.assertIsNone(recovered.verified_tip)

    def test_wrong_password_owner_key_and_ciphertext_fail_closed(self):
        payload = self._candidate()
        for invalid, password, owner in (
            (payload, PASSWORD + "-wrong", OWNER),
            (payload, PASSWORD, "b" * 64),
            (payload[:-1] + bytes([payload[-1] ^ 1]), PASSWORD, OWNER),
        ):
            destination = self.scanner("refusal" + str(len(self.scanners)))
            with self.assertRaises(SeededCheckpointError):
                decode_candidate(self.keys, destination, invalid, password,
                                 owner_binding=owner)
            self.assertFalse(destination.ready)
            self.assertEqual(destination.store.tip()[0], 0)
        other_phrase = Mnemonic("english").to_mnemonic(bytes.fromhex("ff" * 16))
        with Bip39Regtest12Keys(other_phrase, source=SOURCE,
                                authorized_disposable=True) as other_keys:
            destination = Scanner(self.path / "foreign.sqlite", other_keys.accounts())
            self.addCleanup(destination.close)
            with self.assertRaises(SeededCheckpointError):
                decode_candidate(other_keys, destination, payload, PASSWORD, owner_binding=OWNER)

    def test_mismatched_tip_or_unverified_source_and_existing_state_refused(self):
        scan = self.scanner("source")
        with self.assertRaises(SeededCheckpointError):
            encode_candidate(self.keys, scan, PASSWORD, owner_binding=OWNER,
                             trusted_tip=scan.store.tip())
        scan.ready = True
        scan.verified_tip = scan.store.tip()
        with self.assertRaises(SeededCheckpointError):
            encode_candidate(self.keys, scan, PASSWORD, owner_binding=OWNER,
                             trusted_tip=(1, "a"*64))
        payload = self._candidate()
        restored = self.scanner("restored")
        restored.ready = True
        restored.verified_tip = restored.store.tip()
        with self.assertRaises(SeededCheckpointError):
            decode_candidate(self.keys, restored, payload, PASSWORD, owner_binding=OWNER)
        # Existing reservation is irreversible state: even a zero-block DB
        # must not be overwritten with an older checkpoint.
        restored.ready = False
        restored.verified_tip = None
        with restored.store.transaction():
            restored.store.db.execute(
                "INSERT INTO reservations VALUES(?,?,?,?,?)",
                ("a" * 64, 0, "owned-reservation", "signed", 1),
            )
        with self.assertRaises(SeededCheckpointError):
            decode_candidate(self.keys, restored, payload, PASSWORD, owner_binding=OWNER)
        self.assertEqual(restored.store.db.execute(
            "SELECT count(*) FROM reservations").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
