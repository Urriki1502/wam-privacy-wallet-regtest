"""K-10 source contracts, NOT independent physical or frozen-OS acceptance.

Public deterministic BIP39 fixture only, no owner wallets, real funds or
miner Core credentials. Synthetic *receipt labels* cannot attest three hosts.
"""
import importlib.util
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

from mnemonic import Mnemonic

from wam_regtest.bip39_wallet import Bip39RegtestKeys
from wam_regtest.k10_portability import (
    CoreSqliteByteEvidence, K10PortabilityError,
    compare_core_sqlite_bytes, compare_public_os_evidence,
    inspect_original_core_sqlite, probe_original_bip39_identity,
)
from wam_regtest.wsp_live import REGTEST_GENESIS

SOURCE=Path(importlib.util.find_spec("wam_sp").origin).resolve().parents[2]
PHRASE=Mnemonic("english").to_mnemonic(bytes([0x35])*32)
PASSPHRASE="PUBLIC_DISPOSABLE_ONLY_K10"


class K10PublicPortability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with Bip39RegtestKeys(
                PHRASE,source=SOURCE,passphrase=PASSPHRASE,
                authorized_disposable=True) as ring:
            cls.trusted=ring.public_metadata(0)

    def probe(self, **kw):
        params={"passphrase":PASSPHRASE,"account":0,
                "prior_trusted_public":self.trusted,
                "wsp_source":SOURCE,"authorized":True}
        params.update(kw)
        return probe_original_bip39_identity(PHRASE,**params)

    def test_real_pinned_64byte_k02_k03_derivation_agree(self):
        evidence=self.probe()
        self.assertTrue(evidence["original_public_identity_matched"])
        self.assertTrue(evidence["ephemeral_and_durable_wsp_identity_matched"])
        self.assertEqual(evidence["genesis"],REGTEST_GENESIS)
        self.assertEqual(evidence["profile"],self.trusted["profile"])
        self.assertEqual(len(evidence["public_identity_sha256"]),64)
        self.assertFalse(evidence["native_anchor_transplanted"])
        for key in ("portable_restore_created","history_reconciled",
                    "signed_uncertain_reservations_reconciled",
                    "signer_allowed","broadcast_allowed","mainnet_allowed",
                    "physical_os_qualified","frozen_gui_qualified"):
            self.assertFalse(evidence[key],key)
        self.assertNotIn(PHRASE,str(evidence))
        self.assertNotIn(PASSPHRASE,str(evidence))
        self.assertNotIn(self.trusted["receive_code"],str(evidence))

    def test_disposable_native_cli_probe_is_redacted_and_deterministic(self):
        import json
        import subprocess
        import sys
        root=Path(__file__).resolve().parents[1]
        process=subprocess.run(
            [sys.executable,str(root/"scripts"/
                "issue45_k10_public_portability_probe.py"),
             "--disposable-public-fixture"],
            cwd=root,capture_output=True,text=True,timeout=45,check=True)
        self.assertFalse(process.stderr.strip())
        self.assertNotIn(PHRASE,process.stdout)
        self.assertNotIn(PASSPHRASE,process.stdout)
        self.assertNotIn(self.trusted["receive_code"],process.stdout)
        result=json.loads(process.stdout)
        expected=self.probe()
        self.assertEqual(result,expected)
        self.assertFalse(result["physical_os_qualified"])

    def test_wrong_secret_profile_chain_and_account_never_match(self):
        forged=[
            {"passphrase":"WRONG"},
            {"account":1},
            {"account":True},
            {"prior_trusted_public":dict(self.trusted,genesis="f"*64)},
            {"prior_trusted_public":dict(self.trusted,chain="main")},
            {"prior_trusted_public":dict(self.trusted,receive_code="invalid")},
            {"prior_trusted_public":None},
            {"authorized":False},
        ]
        for broken in forged:
            with self.subTest(keys=tuple(broken)):
                with self.assertRaises(K10PortabilityError):
                    self.probe(**broken)

    def test_three_declared_os_agree_without_physical_attestation(self):
        original=self.probe()
        receipts=[
            dict(original,native_platform_observed=target)
            for target in ("macos-arm64","windows-x64","linux-x86_64")
        ]
        result=compare_public_os_evidence(receipts)
        self.assertTrue(result["public_identity_consistent"])
        self.assertFalse(result["signed_os_runner_provenance_verified"])
        self.assertFalse(result["physical_os_qualified"])
        self.assertFalse(result["real_regtest_signed_payment_on_all_os"])
        self.assertFalse(result["safe_to_unlock"])
        self.assertFalse(result["signer_allowed"])

    def test_forged_receipts_or_mismatched_os_are_refused(self):
        orig=self.probe()
        good=[
            dict(orig,native_platform_observed=target)
            for target in ("macos-arm64","windows-x64","linux-x86_64")
        ]
        altered=[
            [dict(good[0],public_identity_sha256="f"*64),good[1],good[2]],
            [dict(good[0],account_index=True),good[1],good[2]],
            [dict(good[0],mainnet_allowed=True),good[1],good[2]],
            [dict(good[0],native_platform_observed="linux-x86_64"),
             good[1],good[2]],
            [dict(good[0],secret="PRIVATE"),good[1],good[2]],
            good[:2],
        ]
        for receipts in altered:
            with self.subTest(size=len(receipts)):
                with self.assertRaises(K10PortabilityError):
                    compare_public_os_evidence(receipts)


class K10CoreSqlitePortability(unittest.TestCase):
    def test_refuses_without_explicit_owner_intent(self):
        with self.assertRaisesRegex(
                K10PortabilityError,"K10_CORE_SOURCE_CONSENT_REQUIRED"):
            inspect_original_core_sqlite(Path("/nonexistent"))
        with self.assertRaisesRegex(
                K10PortabilityError,"K10_CORE_COMPARE_CONSENT_REQUIRED"):
            compare_core_sqlite_bytes(None,None)

    def test_same_bytes_proves_only_same_bytes(self):
        original=CoreSqliteByteEvidence("a"*64,8192)
        restored=CoreSqliteByteEvidence("a"*64,8192)
        self.assertNotIn("aaaa",repr(original))
        r=compare_core_sqlite_bytes(original,restored,authorized=True)
        self.assertTrue(r["byte_content_identical"])
        for k in ("core_native_descriptor_identity_qualified",
                  "regtest_chain_attested_by_core",
                  "cross_os_core_restore_qualified","history_reconciled",
                  "signed_uncertain_reservations_reconciled",
                  "signer_allowed","broadcast_allowed"):
            self.assertFalse(r[k])
        self.assertNotIn("a"*64,str(r))

    def test_bit_flip_and_invalid_provenance_are_refused(self):
        src=CoreSqliteByteEvidence("a"*64,8192)
        for target in (CoreSqliteByteEvidence("b"*64,8192),
                       CoreSqliteByteEvidence("a"*64,16384),
                       CoreSqliteByteEvidence("x",8192),
                       CoreSqliteByteEvidence("a"*64,True),{}):
            with self.subTest(kind=type(target).__name__):
                with self.assertRaises(K10PortabilityError):
                    compare_core_sqlite_bytes(src,target,authorized=True)

    def test_real_sqlite_header_path_read_only_and_immutable(self):
        import sqlite3,os
        with tempfile.TemporaryDirectory(prefix="K10-public-sqlite-") as folder:
            source=Path(folder)/"wallet.dat"
            conn=sqlite3.connect(source)
            conn.execute("CREATE TABLE public_disposable_fixture (v INTEGER)")
            conn.commit()
            conn.close()
            source.chmod(0o600)
            before=source.read_bytes()
            evidence=inspect_original_core_sqlite(source,authorized=True)
            self.assertEqual(evidence.size,len(before))
            self.assertEqual(source.read_bytes(),before)
            self.assertEqual(len(evidence.checksum),64)
            self.assertFalse(any(p.name.startswith("wallet-")
                                 for p in source.parent.iterdir()))


if __name__=="__main__":
    unittest.main()
