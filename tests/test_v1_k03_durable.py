"""K-03 BIP39 seed->native-vault keyring contracts, not fake Core acceptance."""
import importlib.util
from pathlib import Path
import unittest
from mnemonic import Mnemonic
from wam_regtest.bip39_durable import (
    Bip39DurableKeyring,Bip39KeyringError,restore_keyring,
)
from wam_regtest.bip39_wallet import Bip39RegtestKeys
from wam_regtest.v1_contracts import BIP39_PROFILE
from wam_sp.keystore import Keyring,seal
from wam_sp.hd import silent_key

SOURCE=Path(importlib.util.find_spec("wam_sp").origin).resolve().parents[2]
TEST_PASSWORD=b"public-regtest-native-vault-password"
PUBLIC_12=Mnemonic("english").to_mnemonic(bytes([0x21])*16)
PUBLIC_24=Mnemonic("english").to_mnemonic(bytes([0x42])*32)


class K03SeedSignerContracts(unittest.TestCase):
    def make(self,phrase=PUBLIC_24,*,passphrase="TREZOR",account=0):
        return Bip39DurableKeyring.from_phrase(
            phrase,source=SOURCE,passphrase=passphrase,account=account,
            authorized=True)

    def test_real_bip39_64byte_seed_survives_authenticated_native_key_envelope(self):
        for phrase in (PUBLIC_12,PUBLIC_24):
            with self.subTest(words=len(phrase.split())):
                original=self.make(phrase)
                try:
                    backup=original.backup(TEST_PASSWORD)
                    with Bip39DurableKeyring.restore(backup,TEST_PASSWORD) as restored:
                        self.assertEqual(restored.accounts(),original.accounts())
                        self.assertEqual(restored.spend_secret(0),
                                         original.spend_secret(0))
                        self.assertEqual(restored.accounts()[0].payment_code(),
                                         original.accounts()[0].payment_code())
                        self.assertEqual(len(original._seed),64)
                        self.assertNotIn(bytes(original._seed),backup)
                        self.assertNotIn(phrase.encode(),backup)
                    with self.assertRaises(Bip39KeyringError):
                        Bip39DurableKeyring.restore(backup,b"wrong-public-password")
                finally:
                    original.close()
                self.assertFalse(any(original._seed))
                with self.assertRaises(Bip39KeyringError):
                    original.backup(TEST_PASSWORD)

    def test_native_wsp_signer_uses_same_64byte_bip39_spend_secret(self):
        from wam_sp.wallet import Signer
        with self.make(PUBLIC_24,account=2) as keyring:
            with Bip39RegtestKeys(PUBLIC_24,source=SOURCE,passphrase="TREZOR",
                                  authorized_disposable=True) as other:
                self.assertEqual(keyring.spend_secret(2),
                                 silent_key(bytes(other._seed),2,"spend",
                                            coin_type=1))
                self.assertEqual(keyring.accounts()[0],
                                 other.scan_account(2))
                self.assertIsInstance(Signer(keyring),Signer)
                for bad in (True,-1,0,3,"2"):
                    with self.assertRaises(Bip39KeyringError):
                        keyring.spend_secret(bad)
                with self.assertRaises(Bip39KeyringError):
                    keyring._key("unauthorized")

    def test_versioned_seed_restoration_does_not_reinterpret_original_32bytes(self):
        legacy=Keyring(seed=bytes([0x31])*32)
        try:
            legacy_backup=legacy.backup(TEST_PASSWORD)
            with self.make() as keyring:
                bip39_backup=keyring.backup(TEST_PASSWORD)
                with restore_keyring(bip39_backup,TEST_PASSWORD) as restored:
                    self.assertIs(type(restored),Bip39DurableKeyring)
                    self.assertEqual(restored.accounts(),keyring.accounts())
            with restore_keyring(legacy_backup,TEST_PASSWORD) as legacy_restored:
                self.assertIs(type(legacy_restored),Keyring)
                self.assertEqual(legacy_restored.accounts(),legacy.accounts())
            with self.assertRaises(Bip39KeyringError):
                Bip39DurableKeyring.restore(legacy_backup,TEST_PASSWORD)
        finally:legacy.close()

    def test_wrong_network_version_profile_duplicate_fields_and_32byte_seed_refuse(self):
        import json
        with self.make() as wallet:
            record=json.loads(__import__("wam_sp.keystore",fromlist=["unseal"])
                               .unseal(wallet.backup(TEST_PASSWORD),
                                       TEST_PASSWORD,b"keys"))
        for name,value in (
                ("version",3),("version",True),
                ("profile","wsp1-rc1-unchanged"),
                ("network","mainnet"),("account",True),
                ("account",16),("birthday",0),
                ("seed","aa"*32),("mainnet_allowed",True),
                ("legacy_wsp32_interpretable",True)):
            with self.subTest(name=name):
                damaged={**record,name:value}
                cipher=seal(json.dumps(damaged,sort_keys=True).encode(),
                            TEST_PASSWORD,b"keys")
                with self.assertRaises(Bip39KeyringError):
                    Bip39DurableKeyring.restore(cipher,TEST_PASSWORD)
        raw=json.dumps(record).encode()
        malicious=raw[:-1]+b',"version":4}'
        with self.assertRaises(Bip39KeyringError):
            Bip39DurableKeyring.restore(
                seal(malicious,TEST_PASSWORD,b"keys"),TEST_PASSWORD)

    def test_explicit_consent_is_required_and_no_legacy_wsp_auto_create(self):
        with self.assertRaises(Bip39KeyringError):
            Bip39DurableKeyring.from_phrase(PUBLIC_12,source=SOURCE)
        for seed in (b"\x11"*32,b"\x22"*63,b"\x33"*65,"fake",None):
            with self.assertRaises(Bip39KeyringError):
                Bip39DurableKeyring(seed)
        for idx in (True,-1,16,"0"):
            with self.assertRaises(Exception):
                self.make(account=idx)


if __name__=="__main__":
    unittest.main()
