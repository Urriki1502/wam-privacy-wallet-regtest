"""K-10 clean-host checks on disposable local paths only (NOT OS install)."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

from mnemonic import Mnemonic

from wam_regtest.bip39_wallet import Bip39RegtestKeys
from wam_regtest.k10_portability import (
    K10PortabilityError,probe_original_bip39_identity,
)
from wam_regtest.k10_clean_host import (
    RESIDUE_NAMES,review_clean_host_target,
)

SOURCE=Path(importlib.util.find_spec("wam_sp").origin).resolve().parents[2]


class K10CleanHostContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        phrase=Mnemonic("english").to_mnemonic(bytes([0x35])*32)
        passwd="PUBLIC_DISPOSABLE_ONLY_K10"
        with Bip39RegtestKeys(
                phrase,source=SOURCE,passphrase=passwd,
                authorized_disposable=True) as keys:
            prior=keys.public_metadata(0)
        cls.receipt=probe_original_bip39_identity(
            phrase,passphrase=passwd,account=0,
            prior_trusted_public=prior,wsp_source=SOURCE,authorized=True)

    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="k10-clean-host-contract-")
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name).resolve()

    def review(self,identity=None,**kwargs):
        return review_clean_host_target(
            self.receipt if identity is None else identity,
            self.root,authorized=True,**kwargs)

    def test_clean_namespace_is_not_restore_authority(self):
        out=self.review()
        self.assertEqual(out["status"],
                         "K10_CLEAN_HOST_NAMESPACE_INSPECTED_LOCKED_ONLY")
        self.assertTrue(out["public_identity_verified_against_prior_receipt"])
        for key in ("path_is_native_custody_attested",
                    "native_new_host_owner_auth_attested",
                    "old_os_anchor_absent_proven",
                    "new_os_anchor_created","core_sqlite_restored",
                    "original_fusion_reservations_reconciled",
                    "original_history_reconciled",
                    "fresh_scanner_rescan_completed","frozen_gui_restored",
                    "safe_to_create_wallet","safe_to_unlock_signer",
                    "signer_allowed","broadcast_allowed","mainnet_allowed"):
            self.assertFalse(out[key],key)
        self.assertEqual(list(self.root.iterdir()),[])

    def test_known_wallet_runtime_and_crash_residues_refused(self):
        chain=self.root/"chain"
        chain.mkdir()
        for name in RESIDUE_NAMES:
            with self.subTest(name=name):
                target=chain/name
                if name=="wallet-vault":
                    target.mkdir()
                else:
                    target.write_bytes(b"DISPOSABLE_CRASH_OR_OLD_WALLET")
                with self.assertRaisesRegex(
                        K10PortabilityError,
                        "K10_CLEAN_HOST_OLD_STATE_DENIED"):
                    self.review()
                if target.is_dir():target.rmdir()
                else:target.unlink()

    def test_symlink_to_missing_state_fails_closed(self):
        chain=self.root/"chain"
        chain.mkdir()
        target=chain/"wallet-runtime.sqlite"
        try:
            target.symlink_to(chain/"not-present.db")
        except (OSError,NotImplementedError):
            self.skipTest("symlink support unavailable")
        with self.assertRaisesRegex(
                K10PortabilityError,"K10_CLEAN_HOST_OLD_STATE_DENIED"):
            self.review()
        self.assertTrue(target.is_symlink())

    def test_chain_symlink_and_forged_receipt_fail_closed(self):
        fake_root=self.root/"chain"
        try:
            fake_root.symlink_to(self.root, target_is_directory=True)
        except (OSError,NotImplementedError):
            self.skipTest("symlink support unavailable")
        with self.assertRaisesRegex(
                K10PortabilityError,"K10_CLEAN_HOST_CHAIN_DENIED"):
            self.review()
        fake_root.unlink()
        forged=[
            dict(self.receipt,safe_to_unlock_signer=True),
            dict(self.receipt,history_reconciled=True),
            dict(self.receipt,mainnet_allowed=True),
            dict(self.receipt,public_identity_sha256="f"*64,
                 native_platform_observed="unknown-os"),
            dict(self.receipt,account_index=True),
            dict(self.receipt,frozen_gui_qualified=True),
        ]
        for receipt in forged:
            with self.assertRaises(K10PortabilityError):
                self.review(receipt)

    def test_explicit_consent_is_mandatory(self):
        with self.assertRaisesRegex(
                K10PortabilityError,"K10_CLEAN_HOST_CONSENT_REQUIRED"):
            review_clean_host_target(self.receipt,self.root)


if __name__=="__main__":
    unittest.main()
