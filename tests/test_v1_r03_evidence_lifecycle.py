"""R-03 versioned public receipts: verify lifecycle, not synthetic Core."""
import unittest

from wam_regtest.r03_evidence_lifecycle import (
    SCHEMA, IDENTITY_KEYS, r03_effective_status, r03_invalidation_reasons,
)


class R03EvidenceLifecycleContracts(unittest.TestCase):
    def setUp(self):
        self.identity = {
            "code_sha": "a"*40,
            "os": "macos",
            "architecture": "arm64",
            "core_version": "v0.1.11",
            "core_network": "regtest",
            "core_genesis_sha256": "b"*64,
            "wamd_sha256": "c"*64,
            "wam_cli_sha256": "d"*64,
            "wsp_commit": "e"*40,
            "signer_source_sha256": "1"*64,
            "custody_source_sha256": "2"*64,
            "gui_source_sha256": "3"*64,
            "dependency_lock_sha256": "4"*64,
            "packaging_manifest_sha256": "5"*64,
            "test_environment_sha256": "6"*64,
        }
        self.record = {
            "schema": SCHEMA,
            "status": "PASS",
            "kind": "SOURCE",
            "identity": self.identity.copy(),
            "tested_utc": "2026-10-20T09:00:00Z",
            "test_ref": "public-signed-runner-evidence",
            "receipt_sha256": "f"*64,
        }

    def test_complete_identity_is_explicit_no_unlisted_dependencies(self):
        self.assertEqual(set(self.identity), set(IDENTITY_KEYS))
        self.assertEqual(r03_effective_status(self.record,self.identity),"PENDING")
        self.assertEqual(r03_effective_status(self.record,self.identity,
                                              receipt_verified=True),"PASS")

    def test_each_material_change_stales_old_pass(self):
        for k in IDENTITY_KEYS:
            new=dict(self.identity)
            if k == "os": new.update(os="windows", architecture="x64")
            elif k == "architecture": new.update(os="windows", architecture="x64")
            elif k == "core_version": new[k]="v0.1.12"
            elif k == "core_network": continue  # non-REGTEST is REFUSED, not qualified
            elif k in ("code_sha","wsp_commit"): new[k]="0"*40
            else: new[k]="0"*64
            with self.subTest(k=k):
                self.assertEqual(r03_effective_status(self.record,new,
                                                      receipt_verified=True),"STALE")
                self.assertIn(k,r03_invalidation_reasons(self.identity,new))

    def test_failing_old_receipt_also_stales_when_target_changed(self):
        failed={**self.record,"status":"FAIL"}
        self.assertEqual(r03_effective_status(failed,self.identity,
                                              receipt_verified=True),"FAIL")
        changed={**self.identity,"gui_source_sha256":"0"*64}
        self.assertEqual(r03_effective_status(failed,changed),"STALE")

    def test_pending_skip_and_explicit_stale_not_promoted(self):
        for value in ("SKIP","PENDING",None,"SOURCE_PASS","UNKNOWN"):
            with self.subTest(value=value):
                self.assertEqual(r03_effective_status(
                    {**self.record,"status":value},self.identity,
                    receipt_verified=True),"PENDING")
        self.assertEqual(r03_effective_status(
            {**self.record,"status":"STALE"},self.identity,
            receipt_verified=True),"STALE")

    def test_bad_identity_and_non_regtest_never_pass(self):
        for new in ({}, {**self.identity,"core_network":"main"},
                    {**self.identity,"core_network":"test"},
                    {**self.identity,"wamd_sha256":"bad"},
                    {**self.identity,"os":"unknown"},
                    {**self.identity,"architecture":"x64"},
                    {**self.identity,"unapproved_extra":"foo"}):
            with self.subTest(new=new):
                self.assertEqual(r03_effective_status(self.record,new,
                                                      receipt_verified=True),"PENDING")
                self.assertEqual(r03_invalidation_reasons(self.identity,new),
                                 ("R03_IDENTITY_INCOMPLETE",))

    def test_original_receipt_malformed_cannot_qualify(self):
        bad={**self.record,"identity":{**self.identity,"code_sha":"FAKE"}}
        self.assertEqual(r03_effective_status(bad,self.identity,
                                              receipt_verified=True),"PENDING")

    def test_unverified_receipt_metadata_is_never_its_own_proof(self):
        for verified in (False, None, 1, "true"):
            with self.subTest(verified=verified):
                self.assertEqual(r03_effective_status(self.record,self.identity,
                                                      receipt_verified=verified),"PENDING")

    def test_invalid_receipt_fields_refused(self):
        for change in (
            {"schema":"wam-fusion-r03-evidence-lifecycle/v999"},
            {"tested_utc":"2026-10-20T09:00:00+07:00"},
            {"tested_utc":"2026-10-20T09:00:00"},
            {"tested_utc":"malformed"},
            {"tested_utc":None},
            {"test_ref":""},
            {"receipt_sha256":None},
            {"receipt_sha256":"F"*64},
            {"receipt_sha256":"0"*63},
            {"kind":"UNKNOWN"},
        ):
            with self.subTest(change=change):
                self.assertEqual(r03_effective_status(
                    {**self.record,**change},self.identity,receipt_verified=True),"PENDING")

    def test_evidence_layers_are_independent(self):
        for kind in ("CORE_E2E","FROZEN","PHYSICAL","DEV_REVIEWED"):
            with self.subTest(kind=kind):
                self.assertEqual(r03_effective_status(
                    {**self.record,"kind":kind},self.identity,
                    receipt_verified=True),"PENDING")
        self.assertEqual(r03_effective_status(
            {**self.record,"kind":"CORE_E2E","genuine_core":True},
            self.identity,receipt_verified=True),"PASS")
        frozen={**self.record,"kind":"FROZEN","genuine_core":True,
                "final_entrypoint":True,"artifact_sha256":"9"*64}
        self.assertEqual(r03_effective_status(frozen,self.identity,
                                              receipt_verified=True),"PASS")
        self.assertEqual(r03_effective_status(
            {**self.record,"kind":"PHYSICAL",
             "authorized_operator_receipt_verified":True,
             "authorized_operator_ref":"independent-operator-receipt"},
            self.identity,receipt_verified=True),"PASS")
        self.assertEqual(r03_effective_status(
            {**self.record,"kind":"DEV_REVIEWED",
             "authorized_operator_receipt_verified":True,
             "authorized_operator_ref":"independent-dev-review"},
            self.identity,receipt_verified=True),"PASS")

    def test_public_invalidation_names_do_not_expose_secrets(self):
        changed={**self.identity,"custody_source_sha256":"0"*64,
                 "packaging_manifest_sha256":"0"*64}
        self.assertEqual(r03_invalidation_reasons(self.identity,changed),
                         ("custody_source_sha256","packaging_manifest_sha256"))

    def test_no_candidate_or_non_dict_record_can_pass(self):
        for candidate in (None,"",[],1):
            self.assertEqual(r03_effective_status(self.record,candidate,
                                                  receipt_verified=True),"PENDING")
        self.assertEqual(r03_effective_status(None,self.identity,
                                              receipt_verified=True),"PENDING")


if __name__ == "__main__":
    unittest.main()
