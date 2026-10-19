"""K-10 original REGTEST unlock readiness contracts, read-only only.

These are strict source/unit contracts; mocked Core IPC below is never an
independent real-Core, frozen GUI, clean-OS or physical acceptance result.
"""
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from wam_regtest.k10_original_test_access import (
    inspect_original_regtest_test_readiness, K10TestAccessError,
)
from wam_regtest.wsp_live import REGTEST_GENESIS


class K10OriginalWalletManualUnlockContracts(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix="k10-original-unlock-gate-")
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name).resolve()
        self.core=self.root/"public-core"
        self.wsp=self.root/"public-wsp"
        self.password=b"PUBLIC_K10_DISPOSABLE_ORIGINAL_PASSPHRASE"
        self.status={"state":"ready","core_process_owned":True,"height":101}
        self.profile={"network":"regtest","genesis":REGTEST_GENESIS}
        self.attest={"chain":"regtest","blocks":101,
                     "bestblockhash":"a"*64}
        self.verified={
            "status":"MANAGED_WALLET_ORIGINAL_CHECKPOINT_VERIFIED_LOCKED",
            "network":"regtest","wallet_locked":True,
            "signer_allowed":False,"broadcast_allowed":False,
            "balance_verified":False,"original_native_anchor_verified":True,
            "original_encrypted_checkpoint_verified":True,
            "mainnet_allowed":False,"supervisor_authenticated":True,
            "supervisor_core_identity_verified":True,
        }

    def preflight(self,**kw):
        opts={"authorized":True}
        opts.update(kw)
        return inspect_original_regtest_test_readiness(
            self.root,self.core,self.wsp,self.password,**opts)

    def mock_native(self):
        stack=ExitStack()
        self.addCleanup(stack.close)
        control=stack.enter_context(patch(
            "wam_regtest.supervisor_client.control",
            return_value=dict(self.status)))
        profile=stack.enter_context(patch(
            "wam_regtest.core_supervisor._profile_read",
            return_value=dict(self.profile)))
        verify=stack.enter_context(patch(
            "wam_regtest.managed_wallet_binding.verify_locked_wallet",
            return_value=dict(self.verified)))
        client=stack.enter_context(patch(
            "wam_regtest.managed_scan_client.ManagedScanRpc"))
        reader=client.return_value
        reader.attest.return_value=dict(self.attest)
        def get(method,params=None):
            if method=="getblockhash" and params==[0]:
                return REGTEST_GENESIS
            if method=="getblockhash" and params==[101]:
                return "a"*64
            if method=="getbestblockhash" and params==[]:
                return "a"*64
            raise AssertionError("unsupported method")
        reader.call.side_effect=get
        return control,profile,verify,client,reader

    def test_original_ready_allows_only_separate_manual_unlock_attempt(self):
        control,profile,verify,client,reader=self.mock_native()
        outcome=self.preflight()
        self.assertEqual(
            outcome["status"],"K10_ORIGINAL_REGTEST_MANUAL_OPEN_PREFLIGHT_ONLY")
        self.assertTrue(
            outcome["manual_gui_original_wallet_open_may_be_attempted"])
        for name in (
                "new_os_wallet_restored","portable_clean_host_unlocked",
                "full_reservation_reconciliation_proven",
                "physical_recovery_qualified","active_signer_session_created",
                "signer_allowed","broadcast_allowed","mainnet_allowed"):
            self.assertIs(outcome[name],False,name)
        verify.assert_called_once_with(
            self.root,self.core,self.wsp,self.password,authorized=True)
        client.assert_called_once_with(self.root,authorized_readonly=True)
        reader.close.assert_called_once()
        self.assertEqual(control.call_count,2)
        self.assertEqual(profile.call_count,2)
        self.assertNotIn(str(self.root),str(outcome))
        self.assertNotIn(self.password.decode(),str(outcome))

    def test_consent_and_invalid_scopes_rejected_without_core_access(self):
        self.mock_native()
        with self.assertRaisesRegex(
                K10TestAccessError,"K10_ORIGINAL_TEST_CONSENT_REQUIRED"):
            self.preflight(authorized=False)
        with self.assertRaisesRegex(
                K10TestAccessError,"K10_ORIGINAL_TEST_INPUT_DENIED"):
            inspect_original_regtest_test_readiness(
                Path("relative"),self.core,self.wsp,self.password,
                authorized=True)

    def test_new_host_or_unverified_original_checkpoint_refused(self):
        _,_,verify,_,reader=self.mock_native()
        verify.return_value=dict(self.verified,
                                 original_native_anchor_verified=False)
        with self.assertRaisesRegex(
                K10TestAccessError,"K10_ORIGINAL_OWNER_CHECKPOINT_DENIED"):
            self.preflight()
        reader.attest.assert_not_called()

    def test_wrong_chain_or_changed_tip_denied(self):
        _,_,_,_,reader=self.mock_native()
        for change in (
                {"chain":"main"},
                {"blocks":True},
                {"bestblockhash":"b"*64},
        ):
            with self.subTest(fields=tuple(change)):
                reader.attest.return_value=dict(self.attest,**change)
                with self.assertRaisesRegex(
                        K10TestAccessError,"K10_ORIGINAL_CHAIN_MISMATCH"):
                    self.preflight()

    def test_core_not_owned_or_supervisor_changes_denied(self):
        control,profile,_,_,_=self.mock_native()
        control.return_value=dict(self.status,core_process_owned=False)
        with self.assertRaisesRegex(
                K10TestAccessError,"K10_ORIGINAL_CORE_NOT_READY"):
            self.preflight()
        control.return_value=dict(self.status)
        control.side_effect=[dict(self.status),
                             dict(self.status,height=102)]
        with self.assertRaisesRegex(
                K10TestAccessError,"K10_ORIGINAL_STATE_CHANGED"):
            self.preflight()

    def test_original_verification_error_does_not_leak_path(self):
        _,_,verify,_,_=self.mock_native()
        verify.side_effect=RuntimeError("SECRET INTERNAL PATH")
        with self.assertRaisesRegex(
                K10TestAccessError,"K10_ORIGINAL_TEST_PREFLIGHT_UNVERIFIED"
        ) as caught:
            self.preflight()
        self.assertNotIn("SECRET",str(caught.exception))


if __name__=="__main__":
    unittest.main()
