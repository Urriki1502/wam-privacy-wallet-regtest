"""Q06 Stage A contracts only: 12-word, public vectors, no wallet/Core claim."""
import importlib.util
import json
from pathlib import Path
import unittest

from hashlib import sha256
from mnemonic import Mnemonic
from mnemonic.mnemonic import b58encode
from wam_sp.hd import ExtendedPrivate, HARDENED, silent_key
from wam_sp.wallet import Signer

from wam_regtest.bip39_12 import (
    Bip39Regtest12Keys, Bip39TwelveError, generate_phrase, normalize_phrase, PROFILE,
)

WSP_ROOT = Path(importlib.util.find_spec("wam_sp").origin).resolve().parents[2]
VECTORS = json.loads(
    (Path(__file__).parent / "data/q06_bip39_12_reference.json").read_text()
)["vectors"]


class Q06Bip39TwelveSourceContracts(unittest.TestCase):
    def keys(self, phrase, **kwargs):
        return Bip39Regtest12Keys(
            phrase, source=WSP_ROOT, authorized_disposable=True, **kwargs,
        )

    def test_all_public_twelve_word_vectors_use_full_seed_and_pinned_wsp(self):
        self.assertEqual(len(VECTORS), 8)
        for i, vector in enumerate(VECTORS):
            phrase = Mnemonic("english").to_mnemonic(bytes.fromhex(vector["entropy"]))
            self.assertEqual(len(phrase.split()), 12)
            with self.keys(phrase, passphrase="TREZOR") as original:
                self.assertEqual(len(original._seed), 64, f"SEED_LENGTH_{i}")
                self.assertEqual(bytes(original._seed).hex(), vector["seed"], f"SEED_VECTOR_{i}")
                # Preserve PR #43's public BIP32 root-xprv and role-path proof.
                # Never print xprv/seed on assertion failure.
                root = ExtendedPrivate.master(bytes(original._seed))
                payload = bytes.fromhex("0488ade4") + bytes(9) + root.chain_code + b"\\x00" + root.secret
                checksum = sha256(sha256(payload).digest()).digest()[:4]
                self.assertTrue(b58encode(payload + checksum) == vector["xprv"], f"XPRV_VECTOR_{i}")
                expected_scan = root.derive(
                    (352 | HARDENED, 1 | HARDENED, 0 | HARDENED, 1 | HARDENED, 0)
                )
                self.assertEqual(original.scan_account().scan_secret,
                                 int.from_bytes(expected_scan.secret, "big"), f"SCAN_ROLE_{i}")
                self.assertEqual(original.spend_secret(0),
                                 silent_key(bytes(original._seed), 0, "spend", coin_type=1),
                                 f"SPEND_ROLE_{i}")
                self.assertEqual(original.accounts(), (original.scan_account(),))
                self.assertEqual(Signer(original)._keyring, original)
                self.assertEqual(
                    original.public_metadata()["receive_code"],
                    vector["receive_code"], f"WSP_RECEIVE_VECTOR_{i}",
                )
                with self.keys(phrase, passphrase="TREZOR") as restored:
                    self.assertEqual(original.public_metadata(), restored.public_metadata())
                meta = original.public_metadata()
                self.assertEqual(meta["profile"], PROFILE)
                self.assertEqual(meta["chain"], "regtest")
                self.assertFalse(meta["mainnet_allowed"])
                self.assertFalse(meta["production_qualified"])
                self.assertEqual(meta["paths"]["scan"], "m/352'/1'/0'/1'/0")
                self.assertEqual(meta["paths"]["spend"], "m/352'/1'/0'/0'/0")
                self.assertNotIn("seed", meta)
                self.assertNotIn("mnemonic", meta)

    def test_generate_only_disposable_twelve_words_and_restore_identity(self):
        with self.assertRaises(Bip39TwelveError):
            generate_phrase()
        a = generate_phrase(authorized_disposable=True)
        b = generate_phrase(authorized_disposable=True)
        self.assertEqual(len(a.split()), 12)
        self.assertNotEqual(a, b)
        self.assertEqual(normalize_phrase(a), a)
        with self.keys(a) as one, self.keys(a) as two:
            self.assertEqual(one.public_metadata(), two.public_metadata())

    def test_nfkd_and_passphrase_cannot_accidentally_change_identity(self):
        phrase = Mnemonic("english").to_mnemonic(bytes(16))
        wide = "".join(chr(ord(c) + 0xfee0) if "a" <= c <= "z" else "\u3000" for c in phrase)
        self.assertEqual(normalize_phrase(" \n" + wide + "  \t"), phrase)
        with self.keys(wide, passphrase="caf\u00e9") as a, self.keys(
            phrase, passphrase="cafe\u0301"
        ) as b:
            self.assertEqual(a.public_metadata(), b.public_metadata())
        with self.keys(phrase) as a, self.keys(phrase, passphrase="other-test-passphrase") as b:
            self.assertNotEqual(a.public_metadata(), b.public_metadata())

    def test_rejects_bad_checksum_wrong_count_unknown_word_and_secret_leaks(self):
        twelve = Mnemonic("english").to_mnemonic(bytes(16))
        twentyfour = Mnemonic("english").to_mnemonic(bytes(32))
        bad = ("", None, b"words", False, " ".join(["abandon"] * 12),
               " ".join(["notaword"] * 12), twentyfour, " \ud800 ")
        for value in bad:
            with self.subTest(kind=type(value).__name__), self.assertRaises(Bip39TwelveError):
                normalize_phrase(value)
        with self.assertRaises(Bip39TwelveError):
            Bip39Regtest12Keys(twelve, source=WSP_ROOT)
        with self.assertRaises(Bip39TwelveError):
            self.keys(twelve, profile="mainnet")
        for passphrase in (None, True, "\ud800", "a" * 1025):
            with self.assertRaises(Bip39TwelveError):
                self.keys(twelve, passphrase=passphrase)
        with self.keys(twelve) as keys:
            self.assertEqual(repr(keys), "<Bip39Regtest12Keys redacted>")
            self.assertFalse(hasattr(keys, "backup"))
            self.assertFalse(hasattr(keys, "rotate"))
            for account in (-1, True, 16, None):
                with self.assertRaises(Bip39TwelveError):
                    keys.scan_account(account)
            for epoch in (-1, True, 1, None):
                with self.assertRaises(Bip39TwelveError):
                    keys.spend_secret(epoch)
            for birthday in (0, True, 2**31, None):
                with self.assertRaises(Bip39TwelveError):
                    keys.scan_account(birthday=birthday)
            with self.assertRaises(Bip39TwelveError):
                keys._key(0, "unknown-role")
        keys = self.keys(twelve)
        keys.close()
        self.assertEqual(len(keys._seed), 64)
        self.assertFalse(any(keys._seed))
        with self.assertRaises(Bip39TwelveError):
            keys.public_metadata()


if __name__ == "__main__":
    unittest.main()
