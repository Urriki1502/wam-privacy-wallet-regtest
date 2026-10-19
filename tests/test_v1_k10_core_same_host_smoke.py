"""K-10 smoke-runner orchestration contracts, NOT native Core qualification."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.issue45_k10_core_same_host_smoke import (
    prove_same_host_disposable_transfer,
)


class K10SameHostCoreSmokeContracts(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory(prefix="k10-public-same-host-unit-")
        self.addCleanup(t.cleanup)
        self.core=Path(t.name).resolve()/"public-core-only"

    def test_one_source_and_one_isolated_destination_never_authorize_signer(self):
        fixture={
            "backup_sha256":"a"*64,
            "public_descriptor_sha256":"b"*64,
        }
        result={
            "status":"K10_CORE_SQLITE_ISOLATED_RESTORE_VERIFIED",
            "core_native_restorewallet_observed":True,
            "descriptor_public_identity_matched_expected":True,
            "source_backup_byte_identity_preserved":True,
            "signer_allowed":False,
            "broadcast_allowed":False,
        }
        with patch(
                "scripts.issue45_k10_core_same_host_smoke.generate_disposable_core_fixture",
                return_value=fixture) as source, patch(
                "scripts.issue45_k10_core_same_host_smoke.qualify_isolated_core_restore",
                return_value=result) as target:
            out=prove_same_host_disposable_transfer(self.core,authorized=True)
        self.assertTrue(out["actual_core_source_and_target_rpc_verified"])
        self.assertFalse(out["cross_os_physical_transfer_qualified"])
        self.assertFalse(out["original_wsp_reservations_reconciled"])
        self.assertFalse(out["signer_allowed"])
        self.assertFalse(out["broadcast_allowed"])
        self.assertFalse(out["mainnet_allowed"])
        source.assert_called_once()
        target.assert_called_once()
        private_directory=source.call_args.args[1]
        self.assertTrue(private_directory.is_absolute())
        self.assertEqual(target.call_args.args[1],
                         private_directory/"core-wallet-backup.dat")
        self.assertFalse(private_directory.exists())
        self.assertEqual(target.call_args.kwargs["authorized"],True)

    def test_refuses_restored_signer_claim_or_unverified_descriptor(self):
        fixture={"backup_sha256":"a"*64,"public_descriptor_sha256":"b"*64}
        positive={
            "status":"K10_CORE_SQLITE_ISOLATED_RESTORE_VERIFIED",
            "core_native_restorewallet_observed":True,
            "descriptor_public_identity_matched_expected":True,
            "source_backup_byte_identity_preserved":True,
            "signer_allowed":False,"broadcast_allowed":False,
        }
        for negative in (
                dict(positive,signer_allowed=True),
                dict(positive,broadcast_allowed=True),
                dict(positive,descriptor_public_identity_matched_expected=False),
        ):
            with self.subTest(change=negative):
                with patch(
                    "scripts.issue45_k10_core_same_host_smoke.generate_disposable_core_fixture",
                    return_value=fixture), patch(
                    "scripts.issue45_k10_core_same_host_smoke.qualify_isolated_core_restore",
                    return_value=negative):
                    with self.assertRaisesRegex(
                            ValueError,"K10_LOCAL_DISPOSABLE_TRANSFER_FAILED"):
                        prove_same_host_disposable_transfer(
                            self.core,authorized=True)

    def test_refuses_wrong_scope_without_launching_source(self):
        with patch(
                "scripts.issue45_k10_core_same_host_smoke.generate_disposable_core_fixture"
        ) as source:
            with self.assertRaisesRegex(
                    ValueError,"K10_LOCAL_DISPOSABLE_SCOPE_DENIED"):
                prove_same_host_disposable_transfer(self.core,authorized=False)
            with self.assertRaisesRegex(
                    ValueError,"K10_LOCAL_DISPOSABLE_SCOPE_DENIED"):
                prove_same_host_disposable_transfer(
                    Path("relative-core"),authorized=True)
            source.assert_not_called()


if __name__=="__main__":
    unittest.main()
