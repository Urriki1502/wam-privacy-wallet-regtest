"""K-08 P0 portable clean-device recovery preflight and refusal contracts.

Live WAM Core clean-OS installation, actual native anchor commissioning and
cross-platform history reconciliation are separate evidence gates. No fake
Core or synthetic signer-positive acceptance here.
"""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mnemonic import Mnemonic
from wam_regtest.bip39_wallet import Bip39RegtestKeys
from wam_regtest.portable_recovery import (
    recovery_plan,verify_bip39_owner_for_clean_device,
    require_safe_bootstrap_prerequisites,PortableRecoveryError,
)
from wam_regtest.v1_contracts import BIP39_PROFILE,CORE_PROFILE,RC1_PROFILE

SOURCE=Path(importlib.util.find_spec("wam_sp").origin).resolve().parents[2]
PHRASE=Mnemonic("english").to_mnemonic(bytes([0x35])*32)
PASSPHRASE="public-disposable-regtest-test-only"


class K08PortableRecoveryContracts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="k08-disposable-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.target=self.root/"new-device-only"
        self.source=SOURCE
        with Bip39RegtestKeys(
                PHRASE,source=self.source,passphrase=PASSPHRASE,
                authorized_disposable=True) as keys:
            self.original=keys.public_metadata(0)
            self.original_account2=keys.public_metadata(2)

    def owner(self,**overrides):
        args={"passphrase":PASSPHRASE,"account":0,
              "expected_public":self.original,
              "wsp_source":self.source,"authorized":True}
        args.update(overrides)
        return verify_bip39_owner_for_clean_device(PHRASE,**args)

    def test_four_disjoint_authority_modes_are_explicitly_locked(self):
        expected={
            "bip39-mnemonic":BIP39_PROFILE,
            "core-sqlite-dat":CORE_PROFILE,
            "fusion-encrypted-enc":None,
            "os-native-anchor":None,
        }
        for mode,profile in expected.items():
            with self.subTest(mode=mode):
                plan=recovery_plan(mode,authorized=True)
                self.assertEqual(plan.expected_profile,profile)
                self.assertFalse(plan.cross_os_anchor_copy_allowed)
                self.assertFalse(plan.source_mutation_allowed)
                self.assertTrue(plan.native_owner_proof_required)
                self.assertTrue(plan.pending_reconciliation)
                self.assertFalse(plan.signer_allowed)
                self.assertFalse(plan.balance_claim_allowed)
                self.assertFalse(plan.history_restored)
                self.assertNotIn(PHRASE,repr(plan))
        for mode in (None,True,"legacy-wsp32","mainnet","core-bdb",
                     "new-automatic-sweep","fusion"):
            with self.subTest(mode=mode):
                with self.assertRaises(PortableRecoveryError):
                    recovery_plan(mode,authorized=True)
        with self.assertRaisesRegex(
                PortableRecoveryError,"K08_OPERATOR_CONSENT_REQUIRED"):
            recovery_plan("bip39-mnemonic")

    def test_real_pinned_wsp_64_seed_same_public_identity_locked(self):
        proof=self.owner()
        self.assertEqual(proof["profile"],BIP39_PROFILE)
        self.assertTrue(proof["identity_matched_prior_trusted_receipt"])
        self.assertEqual(proof["account_index"],0)
        for key in ("signer_allowed","broadcast_allowed",
                    "original_os_anchor_transplanted",
                    "native_new_device_anchor_created",
                    "original_core_dat_restored",
                    "original_fusion_enc_restored",
                    "historical_spend_reservations_reconciled",
                    "history_verified","balance_verified","mainnet_allowed"):
            self.assertIs(proof[key],False,key)
        self.assertNotIn("receive_code",proof)
        self.assertNotIn("account_id",proof)
        self.assertNotIn(PHRASE,str(proof))
        self.assertNotIn(PASSPHRASE,str(proof))
        self.assertFalse(self.target.exists())

    def test_wrong_phrase_passphrase_account_chain_and_profile_all_denied(self):
        other=Mnemonic("english").to_mnemonic(bytes([0x36])*32)
        cases=(
            {"passphrase":"WRONG"},
            {"account":1},
            {"account":2},
            {"expected_public":self.original_account2},
            {"expected_public":{**self.original,"chain":"main"}},
            {"expected_public":{**self.original,"genesis":"f"*64}},
            {"expected_public":{**self.original,"profile":RC1_PROFILE}},
            {"expected_public":{**self.original,"receive_code":"wamrtsp1forged"}},
            {"expected_public":{**self.original,"account":True}},
            {"expected_public":None},
            {"authorized":False},
        )
        for bad in cases:
            with self.subTest(case=list(bad)):
                with self.assertRaises(PortableRecoveryError):
                    self.owner(**bad)
        with self.assertRaisesRegex(
                PortableRecoveryError,"K08_BIP39_ORIGINAL_IDENTITY_DENIED"):
            verify_bip39_owner_for_clean_device(
                other,passphrase=PASSPHRASE,account=0,
                expected_public=self.original,wsp_source=self.source,
                authorized=True)

    def test_clean_device_contract_refuses_missing_owner_native_core_and_reconcile(self):
        receipt=self.owner()
        for options in (
            {},
            {"approved_regtest_core":True},
            {"owner_native_auth":True},
            {"original_state_reconciled":True},
            {"approved_regtest_core":True,"owner_native_auth":True},
            {"approved_regtest_core":True,"owner_native_auth":True,
             "original_state_reconciled":1},
        ):
            with self.subTest(options=options):
                with self.assertRaisesRegex(
                        PortableRecoveryError,
                        "K08_CLEAN_DEVICE_OR_RECONCILIATION_PENDING"):
                    require_safe_bootstrap_prerequisites(
                        receipt,target_root=self.target,**options)
        verified=require_safe_bootstrap_prerequisites(
            receipt,target_root=self.target,approved_regtest_core=True,
            owner_native_auth=True,original_state_reconciled=True)
        self.assertEqual(verified["status"],
                         "K08_CLEAN_DEVICE_PREREQUISITES_REVIEWED_ONLY")
        self.assertFalse(verified["wallet_created"])
        self.assertFalse(verified["native_anchor_created"])
        self.assertFalse(verified["signer_allowed"])
        self.assertFalse(verified["broadcast_allowed"])
        self.assertFalse(self.target.exists())

    def test_any_existing_original_vault_or_crash_residue_blocks_bootstrap(self):
        receipt=self.owner()
        chain=self.target/"chain"
        chain.mkdir(parents=True)
        for name in ("wallet-vault","wallet-runtime.sqlite",
                     "wallet-runtime.sqlite-wal",
                     "wallet-runtime.sqlite-shm",
                     "wallet-runtime.sqlite-journal"):
            with self.subTest(name=name):
                path=chain/name
                if name=="wallet-vault":path.mkdir()
                else:path.write_bytes(b"unknown preexisting original")
                with self.assertRaisesRegex(
                        PortableRecoveryError,
                        "K08_EXISTING_WALLET_OR_CRASH_RESIDUE_DENIED"):
                    require_safe_bootstrap_prerequisites(
                        receipt,target_root=self.target,
                        approved_regtest_core=True,owner_native_auth=True,
                        original_state_reconciled=True)
                if path.is_dir():path.rmdir()
                else:path.unlink()

    def test_forged_public_receipt_never_grants_bootstrap(self):
        original=self.owner()
        bads=(
            {},
            {"status":"K08_BIP39_ORIGINAL_PUBLIC_IDENTITY_VERIFIED_LOCKED",
             "signer_allowed":True},
            {**original,"signer_allowed":True},
            {**original,"broadcast_allowed":True},
            {**original,"historical_spend_reservations_reconciled":True},
            {**original,"mainnet_allowed":True},
        )
        for forged in bads:
            with self.subTest(receipt_status=forged.get("status")):
                with self.assertRaises(PortableRecoveryError):
                    require_safe_bootstrap_prerequisites(
                        forged,target_root=self.target,
                        approved_regtest_core=True,owner_native_auth=True,
                        original_state_reconciled=True)

    def test_bip39_preflight_has_no_wallet_creation_core_rpc_or_native_anchor(self):
        with (patch("wam_regtest.managed_wallet_create.create_managed_wallet",
                    side_effect=AssertionError("K08_CANNOT_CREATE_WALLET")),
              patch("wam_regtest.supervisor_client.control",
                    side_effect=AssertionError("K08_CANNOT_CORE_RPC")),
              patch("wam_regtest.custody.anchor",
                    side_effect=AssertionError("K08_CANNOT_NATIVE_ANCHOR"))):
            receipt=self.owner()
            self.assertTrue(receipt["identity_matched_prior_trusted_receipt"])
            self.assertFalse(self.target.exists())


if __name__=="__main__":
    unittest.main()
