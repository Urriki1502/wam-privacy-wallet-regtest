"""Read-only supervisor-to-wallet binding contracts; NOT genuine-Core Q05."""
from pathlib import Path
import unittest
from unittest.mock import patch

from wam_regtest.managed_wallet_binding import (
    ManagedWalletBindingError, verify_locked_wallet,
)
from wam_regtest.supervisor_protocol import public_status
from wam_regtest.wsp_live import REGTEST_GENESIS


class ManagedWalletBindingContracts(unittest.TestCase):
    def setUp(self):
        self.root=Path.cwd()/"wam-fusion-core-0123456789abcdef"
        self.core=Path.cwd()/"pinned-core"
        self.source=Path.cwd()/"pinned-wsp"
        self.password=b"public-regtest-test-passphrase"
        self.profile={"network":"regtest","genesis":REGTEST_GENESIS,
                      "core_sha256":"a"*64,"cli_sha256":"b"*64}
        self.receipt={"wamd_sha256":"a"*64,"wam_cli_sha256":"b"*64}
        self.status=public_status(state="ready",chain_height=101,owned=True)
        self.checkpoint={"status":"MANAGED_WALLET_ORIGINAL_CHECKPOINT_VERIFIED_LOCKED",
                         "network":"regtest","wallet_locked":True,
                         "signer_allowed":False,"broadcast_allowed":False,
                         "balance_verified":False,
                         "original_native_anchor_verified":True,
                         "original_encrypted_checkpoint_verified":True,
                         "mainnet_allowed":False}

    def bindings(self, *, statuses=None, profiles=None, checkpoint=None):
        from contextlib import ExitStack
        stack=ExitStack()
        seq=[self.status,self.status] if statuses is None else statuses
        pseq=[self.profile,self.profile] if profiles is None else profiles
        conn=stack.enter_context(patch("wam_regtest.managed_wallet_binding.control",
                                       side_effect=seq))
        stack.enter_context(patch("wam_regtest.managed_wallet_binding._profile_read",
                                  side_effect=pseq))
        stack.enter_context(patch("wam_regtest.managed_wallet_binding.verified_core_paths",
                                  return_value=(self.core/"wamd",self.core/"wam-cli",self.receipt)))
        preflight=stack.enter_context(patch(
            "wam_regtest.managed_wallet_binding.preflight_existing_checkpoint",
            return_value=self.checkpoint if checkpoint is None else checkpoint))
        return stack,conn,preflight

    def test_authentic_ready_owner_and_native_checkpoint_are_locked_only(self):
        stack,conn,preflight=self.bindings()
        with stack:
            result=verify_locked_wallet(self.root,self.core,self.source,
                                        self.password,authorized=True)
            self.assertTrue(result["supervisor_authenticated"])
            self.assertTrue(result["supervisor_core_identity_verified"])
            self.assertTrue(result["wallet_locked"])
            for field in ("signer_allowed","broadcast_allowed","balance_verified","mainnet_allowed"):
                self.assertFalse(result[field])
            self.assertEqual([c.args[1] for c in conn.call_args_list],["status","status"])
            self.assertEqual(preflight.call_count,1)
            self.assertEqual(preflight.call_args.args[1],self.root/"chain")
            self.assertTrue(preflight.call_args.kwargs["authorized"])

    def test_no_implicit_unlock_consent_or_external_path(self):
        stack,conn,preflight=self.bindings()
        with stack:
            with self.assertRaisesRegex(ManagedWalletBindingError,"CONSENT_REQUIRED"):
                verify_locked_wallet(self.root,self.core,self.source,self.password)
            with self.assertRaisesRegex(ManagedWalletBindingError,"INPUT_DENIED"):
                verify_locked_wallet(self.root,Path("relative"),self.source,
                                     self.password,authorized=True)
            conn.assert_not_called()
            preflight.assert_not_called()

    def test_unready_or_foreign_core_refused_before_decrypt(self):
        for state in (public_status(state="busy",owned=True),
                      public_status(state="recovery-needed"),
                      public_status(state="ready",owned=False,chain_height=101)):
            with self.subTest(state=state["state"]):
                stack,conn,preflight=self.bindings(statuses=[state,state])
                with stack, self.assertRaisesRegex(ManagedWalletBindingError,"CORE_NOT_READY"):
                    verify_locked_wallet(self.root,self.core,self.source,
                                         self.password,authorized=True)
                preflight.assert_not_called()

    def test_mismatched_executable_hash_refused_before_decrypt(self):
        wrong={**self.profile,"core_sha256":"f"*64}
        stack,conn,preflight=self.bindings(profiles=[wrong])
        with stack, self.assertRaisesRegex(ManagedWalletBindingError,"CORE_MISMATCH"):
            verify_locked_wallet(self.root,self.core,self.source,
                                 self.password,authorized=True)
        preflight.assert_not_called()

    def test_status_or_core_profile_change_during_checkpoint_refused(self):
        other=public_status(state="ready",owned=True,chain_height=102)
        for statuses,profiles in (([self.status,other],None),
                                  (None,[self.profile,{**self.profile,"cli_sha256":"f"*64}])):
            with self.subTest(statuses=statuses):
                stack,conn,preflight=self.bindings(statuses=statuses,profiles=profiles)
                with stack,self.assertRaisesRegex(ManagedWalletBindingError,"STATE_CHANGED"):
                    verify_locked_wallet(self.root,self.core,self.source,
                                         self.password,authorized=True)
                self.assertEqual(preflight.call_count,1)

    def test_bogus_checkpoint_cannot_grant_spend_or_balance(self):
        for override in ({"signer_allowed":True},{"broadcast_allowed":True},
                         {"balance_verified":True},{"mainnet_allowed":True},
                         {"original_native_anchor_verified":False}):
            with self.subTest(override=override):
                stack,_,_=self.bindings(checkpoint={**self.checkpoint,**override})
                with stack,self.assertRaisesRegex(ManagedWalletBindingError,
                                                  "CHECKPOINT_UNVERIFIED"):
                    verify_locked_wallet(self.root,self.core,self.source,
                                         self.password,authorized=True)

    def test_private_failure_never_leaks_paths_or_secrets(self):
        stack,_,preflight=self.bindings()
        with stack:
            preflight.side_effect=RuntimeError("SENSITIVE_SECRET_PATH")
            with self.assertRaisesRegex(ManagedWalletBindingError,
                                        "^MANAGED_WALLET_BINDING_DENIED$") as failure:
                verify_locked_wallet(self.root,self.core,self.source,
                                     self.password,authorized=True)
            self.assertNotIn("SENSITIVE",str(failure.exception))


if __name__=="__main__":
    unittest.main()
