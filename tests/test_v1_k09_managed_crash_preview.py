"""K-09 managed crash-preview *contracts*; real Core/native E2E is deferred.

These tests only prove that the GUI service is scoped to the existing
original wallet and never authorizes cleanup, signing, or broadcasting.
"""
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from wam_regtest.managed_wallet_crash_preview import (
    CrashPreviewError,inspect_managed_crash_preview
)
from wam_regtest.wsp_live import REGTEST_GENESIS


class K09OriginalWalletCrashPreviewContracts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="k09-managed-preview-contract-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.core=self.root/"public-core-binary-dir"
        self.wsp=self.root/"public-pinned-wsp"
        self.password=b"PUBLIC_FIXTURE_ORIGINAL_WALLET_PASSWORD"
        self.profile={
            "network":"regtest","genesis":REGTEST_GENESIS,
            "core_sha256":"a"*64,"cli_sha256":"b"*64,
        }
        self.wallet={"wallet_id":"c"*32}
        self.status={"state":"ready","core_process_owned":True,"height":101}
        self.receipt={
            "status":"K09_OWNER_VERIFIED_READ_ONLY_RESIDUE_PREVIEW",
            "network":"regtest",
            "original_anchor_verified":True,
            "original_owner_envelope_authenticated":True,
            "safe_to_discard_proven":False,
            "operator_discard_available":False,
            "wallet_unlocked":False,
            "signer_allowed":False,
            "broadcast_allowed":False,
            "automatic_cleanup_allowed":False,
            "candidate_count":0,
        }

    def call(self,**kwargs):
        return inspect_managed_crash_preview(
            self.root,self.core,self.wsp,self.password,**kwargs)

    def test_scope_and_separate_consent_denied_before_io(self):
        for extra in ({},{ "authorized":True,"observe_recent_core":"yes"}):
            with self.subTest(extra=extra):
                with self.assertRaises(CrashPreviewError):
                    self.call(**extra)
        with self.assertRaises(CrashPreviewError):
            inspect_managed_crash_preview(
                Path("relative"),self.core,self.wsp,self.password,
                authorized=True)

    def fake_native(self):
        stack=ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch("wam_regtest.supervisor_store._root"))
        control=stack.enter_context(
            patch("wam_regtest.supervisor_client.control",
                  return_value=dict(self.status)))
        stack.enter_context(patch("wam_regtest.core_supervisor._profile_read",
                                  return_value=dict(self.profile)))
        stack.enter_context(patch("wam_regtest.core.verified_core_paths",
                                  return_value=(None,None,{
                                      "platform":"linux-x86_64",
                                      "wamd_sha256":"a"*64,
                                      "wam_cli_sha256":"b"*64})))
        stack.enter_context(patch("wam_regtest.wsp_live._pinned_source"))
        stack.enter_context(patch("wam_regtest.custody.platform_name",
                                  return_value="linux-x86_64"))
        storage=stack.enter_context(patch("wam_regtest.custody.storage"))
        stack.enter_context(patch("wam_regtest.custody.anchor",
                                  return_value=Mock()))
        stack.enter_context(patch("wam_regtest.managed_wallet_reopen.read",
                                  return_value=self.wallet))
        stack.enter_context(patch("wam_regtest.managed_wallet_reopen.make",
                                  return_value=self.wallet))
        stack.enter_context(patch("wam_regtest.vault.CheckpointVault"))
        inspect=stack.enter_context(patch(
            "wam_regtest.crash_recovery.inspect_owner_crash_residue",
            return_value=dict(self.receipt)))
        return control,storage,inspect,stack

    def test_existing_wallet_scope_does_not_create_or_mutate_anything(self):
        control,storage,inspect,_=self.fake_native()
        result=self.call(authorized=True)
        self.assertEqual(result,self.receipt)
        inspect.assert_called_once()
        self.assertIs(inspect.call_args.kwargs["authorized"],True)
        self.assertIs(inspect.call_args.kwargs["audit_reservations"],True)
        self.assertIs(inspect.call_args.kwargs["authorized_core_observation"],False)
        self.assertIsNone(inspect.call_args.kwargs["core_read_rpc"])
        self.assertFalse(result["operator_discard_available"])
        self.assertEqual(control.call_count,2)
        self.assertEqual(storage.return_value.validate_directory.call_count,2)

    def test_core_preview_must_have_explicit_operator_choice(self):
        _,_,inspect,stack=self.fake_native()
        rpc=Mock()
        factory=stack.enter_context(
            patch("wam_regtest.managed_scan_client.ManagedScanRpc",
                  return_value=rpc))
        receipt=self.call(authorized=True,observe_recent_core=True)
        self.assertEqual(receipt,self.receipt)
        self.assertIs(inspect.call_args.kwargs["core_read_rpc"],rpc)
        self.assertIs(inspect.call_args.kwargs["authorized_core_observation"],True)
        factory.assert_called_once_with(self.root,authorized_readonly=True)
        rpc.close.assert_called_once()

    def test_supervisor_change_or_forged_unlock_evidence_is_denied(self):
        control,_,inspect,_=self.fake_native()
        control.side_effect=[
            self.status,dict(self.status,height=102)]
        with self.assertRaisesRegex(
                CrashPreviewError,"K09_MANAGED_SUPERVISOR_CHANGED"):
            self.call(authorized=True)
        control.side_effect=None
        control.return_value=dict(self.status)
        inspect.return_value=dict(self.receipt,wallet_unlocked=True)
        with self.assertRaisesRegex(
                CrashPreviewError,"K09_MANAGED_EVIDENCE_INVALID"):
            self.call(authorized=True)


if __name__=="__main__":
    unittest.main()
