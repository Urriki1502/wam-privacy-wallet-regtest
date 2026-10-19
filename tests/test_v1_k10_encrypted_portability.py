"""K-10 disposable encrypted v4 backup portability, with no wallet writes.

Source tests use deterministic PUBLIC BIP39 phrases from known entropy and
in-memory authenticated encryption. This does NOT qualify a physical OS
transfer, original signer, Core restore or final recovery.
"""
import importlib.util
from pathlib import Path
import unittest

from mnemonic import Mnemonic

from wam_regtest.bip39_wallet import Bip39RegtestKeys
from wam_regtest.bip39_durable import Bip39DurableKeyring
from wam_regtest.k10_encrypted_portability import inspect_portable_k03_backup
from wam_regtest.k10_portability import (
    K10PortabilityError,probe_original_bip39_identity,
)

SOURCE=Path(importlib.util.find_spec("wam_sp").origin).resolve().parents[2]
PASSWORD=b"PUBLIC_K10_BACKUP_ENVELOPE_TEST_PASSWORD_123"


class K10EncryptedWspBackupContracts(unittest.TestCase):
    def fixture(self, *, bits=256, account=0, passphrase="PUBLIC_K10_ONLY"):
        phrase=Mnemonic("english").to_mnemonic(bytes([0x35])*int(bits/8))
        with Bip39RegtestKeys(
                phrase,source=SOURCE,passphrase=passphrase,
                authorized_disposable=True) as public:
            trusted=public.public_metadata(account)
        with Bip39DurableKeyring.from_phrase(
                phrase,source=SOURCE,passphrase=passphrase,
                account=account,authorized=True) as ring:
            backup=ring.backup(PASSWORD)
        return phrase, trusted, backup

    def test_12_and_24_word_real_pinned_v4_backup_reopen(self):
        for bits,account in ((128,0),(256,0),(256,2)):
            with self.subTest(bits=bits,account=account):
                phrase,trusted,encrypted=self.fixture(
                    bits=bits,account=account)
                result=inspect_portable_k03_backup(
                    encrypted,PASSWORD,account=account,
                    prior_trusted_public=trusted,authorized=True)
                prior=probe_original_bip39_identity(
                    phrase,passphrase="PUBLIC_K10_ONLY",account=account,
                    prior_trusted_public=trusted,wsp_source=SOURCE,
                    authorized=True)
                self.assertTrue(result["k03_encrypted_envelope_authenticated"])
                self.assertEqual(result["public_identity_sha256"],
                                 prior["public_identity_sha256"])
                self.assertFalse(result["wallet_created"])
                self.assertFalse(result["safe_to_sign"])
                self.assertFalse(result["new_os_native_anchor_created"])
                self.assertFalse(result["fusion_checkpoint_restored"])
                self.assertFalse(result["reservation_history_reconciled"])
                self.assertFalse(result["broadcast_allowed"])
                self.assertNotIn(phrase,str(result))
                self.assertNotIn(trusted["receive_code"],str(result))

    def test_wrong_password_and_mutated_or_truncated_envelope_denied(self):
        _, trusted,encrypted=self.fixture()
        mutated=bytearray(encrypted)
        mutated[-1]^=0x1
        for backup,password in (
                (encrypted,b"WRONG_ENOUGH_PASSWORD_123"),
                (bytes(mutated),PASSWORD),
                (encrypted[:25],PASSWORD),
                (encrypted[:-20],PASSWORD),
                (b"NOT_AN_ENVELOPE",PASSWORD),
                (b"x"*(16*1024*1024+1),PASSWORD),
        ):
            with self.subTest(length=len(backup)):
                with self.assertRaises(K10PortabilityError):
                    inspect_portable_k03_backup(
                        backup,password,account=0,
                        prior_trusted_public=trusted,authorized=True)

    def test_wrong_account_public_receipt_or_flags_denied(self):
        _,trusted,encrypted=self.fixture(account=2)
        attempts=(
            (0,trusted),
            (True,trusted),
            (2,dict(trusted,chain="main")),
            (2,dict(trusted,receive_code="forged")),
            (2,dict(trusted,account=True)),
            (2,dict(trusted,production_qualified=True)),
            (2,dict(trusted,unrecognized_extra_field="private")),
        )
        for account,public in attempts:
            with self.subTest(account=account):
                with self.assertRaises(K10PortabilityError):
                    inspect_portable_k03_backup(
                        encrypted,PASSWORD,account=account,
                        prior_trusted_public=public,authorized=True)

    def test_explicit_consent_required(self):
        _,trusted,backup=self.fixture()
        with self.assertRaisesRegex(K10PortabilityError,
                                    "K10_PORTABLE_BACKUP_CONSENT_REQUIRED"):
            inspect_portable_k03_backup(
                backup,PASSWORD,account=0,prior_trusted_public=trusted)
        with self.assertRaisesRegex(K10PortabilityError,
                                    "K10_PORTABLE_BACKUP_SCOPE_DENIED"):
            inspect_portable_k03_backup(
                backup,"not-bytes",account=0,
                prior_trusted_public=trusted,authorized=True)

    def test_legacy_wsp_32_byte_backup_not_imported_as_k03(self):
        from wam_sp.keystore import Keyring
        with Keyring(seed=bytes([0x22])*32) as ring:
            legacy=ring.backup(PASSWORD)
        _,trusted,_=self.fixture()
        with self.assertRaisesRegex(K10PortabilityError,
                                    "K10_PORTABLE_BACKUP_UNVERIFIED"):
            inspect_portable_k03_backup(
                legacy,PASSWORD,account=0,
                prior_trusted_public=trusted,authorized=True)


if __name__=="__main__":
    unittest.main()
