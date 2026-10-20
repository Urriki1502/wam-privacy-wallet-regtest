"""R-06 source-only public manifest transition contracts, no real wallet IO."""
import copy
import unittest

from wam_regtest.r06_release_transition import (
    PINS, PROVENANCE, WSP_PIN, ReleaseTransitionError, review_transition,
)


class R06ReleaseTransitionContracts(unittest.TestCase):
    def manifest(self, platform="macos-arm64", source="a"*40, **overrides):
        r = {
            "schema": "wam-regtest-release-candidate/v1",
            "candidate_id": "WAM-Fusion-REGTEST-RC1",
            "network": "regtest",
            "platform": platform,
            "mainnet_allowed": False,
            "production_qualified": False,
            "official_final_release": False,
            "dev_wam_reviewed": False,
            "native_final_executable_e2e_pass": True,
            "core_provenance": PROVENANCE[platform],
            "core_sha256": dict(PINS[platform]),
            "wsp_source_commit": WSP_PIN,
            "single_commit_build": True,
            "source_head_sha": source,
            "checkout_sha": source,
            "dependencies": {"PyInstaller": "6.0", "coincurve": "20.0"},
            "files_sha256": {"archive.zip": "3"*64},
        }
        r.update(overrides)
        return r

    def test_candidate_never_authorizes_runtime_changes(self):
        source = self.manifest()
        current = self.manifest(source="b"*40)
        result = review_transition(source,current,
                                   previous_provenance_verified=True,
                                   candidate_provenance_verified=True)
        self.assertEqual(result["status"], "R06_MANUAL_STATE_REVIEW_REQUIRED")
        for k in ("core_or_os_auto_upgrade_allowed", "wallet_or_anchor_reset_allowed",
                  "old_signed_or_uncertain_reservations_cleared",
                  "rollback_executable_approved", "install_approved_by_this_review",
                  "cross_platform_migration_qualified", "physical_operator_accepted",
                  "external_dev_reviewed", "r06_full_p0_qualified", "mainnet_allowed"):
            self.assertFalse(result[k], k)

    def test_unproven_artifacts_never_claim_authenticity(self):
        r = review_transition(self.manifest(),self.manifest(source="b"*40))
        self.assertEqual(r["status"],"R06_INDEPENDENT_PROVENANCE_PENDING")
        self.assertFalse(r["candidate_provenance_claimed_verified"])
        self.assertFalse(r["install_approved_by_this_review"])

    def test_fresh_disposable_setup_still_requires_manual_review(self):
        r = review_transition(None,self.manifest(),candidate_provenance_verified=True)
        self.assertEqual(r["status"],"R06_NEW_REGTEST_INSTALL_REVIEW_REQUIRED")
        self.assertIsNone(r["previous_source_sha"])

    def test_synthetic_merge_head_refused_for_release(self):
        r = self.manifest(source="b"*40,checkout_sha="c"*40,
                          single_commit_build=False)
        x = review_transition(self.manifest(),r,
                              previous_provenance_verified=True,
                              candidate_provenance_verified=True)
        self.assertEqual(x["status"],"R06_SYNTHETIC_MERGE_BUILD_DENIED")

    def test_same_source_rebuild_drift_requires_review(self):
        old = self.manifest()
        new = self.manifest(files_sha256={"archive.zip":"4"*64})
        x = review_transition(old,new,previous_provenance_verified=True,
                              candidate_provenance_verified=True)
        self.assertEqual(x["status"],"R06_SAME_SOURCE_ARTIFACT_DRIFT_REVIEW_REQUIRED")
        self.assertFalse(x["install_approved_by_this_review"])

    def test_same_source_no_auto_reinstall(self):
        old = self.manifest()
        x = review_transition(old,copy.deepcopy(old),
                              previous_provenance_verified=True,
                              candidate_provenance_verified=True)
        self.assertEqual(x["status"],"R06_SAME_RELEASE_NO_AUTOMATIC_REINSTALL")

    def test_dependency_change_requires_requalification(self):
        x = review_transition(self.manifest(),
            self.manifest(source="b"*40,dependencies={"PyInstaller":"7.0"}),
            previous_provenance_verified=True,candidate_provenance_verified=True)
        self.assertEqual(x["status"],"R06_DEPENDENCY_CHANGE_REQUALIFICATION_REQUIRED")

    def test_cross_os_transfer_never_inherits_native_anchor(self):
        for platform in ("windows-x64","linux-x86_64-desktop",
                         "linux-x86_64-headless"):
            with self.subTest(platform=platform):
                result=review_transition(self.manifest(),self.manifest(platform,source="b"*40))
                self.assertEqual(result["status"],"R06_OS_CHANGE_MIGRATION_REVIEW_REQUIRED")
                self.assertFalse(result["wallet_or_anchor_reset_allowed"])

    def test_each_known_platform_accepts_public_manifest_not_install(self):
        for platform in PINS:
            with self.subTest(platform=platform):
                result=review_transition(None,self.manifest(platform))
                self.assertEqual(result["status"],"R06_NEW_REGTEST_INSTALL_REVIEW_REQUIRED")
                self.assertFalse(result["install_approved_by_this_review"])

    def test_malicious_network_core_wsp_and_fake_approvals_are_refused(self):
        bad = (
            {"network":"main"}, {"mainnet_allowed":True},
            {"production_qualified":True}, {"official_final_release":True},
            {"dev_wam_reviewed":True}, {"native_final_executable_e2e_pass":False},
            {"core_sha256":{"wamd":"0"*64,"wam-cli":"1"*64}},
            {"core_provenance":"official-signed-v0.1.12"},
            {"wsp_source_commit":"0"*40}, {"source_head_sha":"bad"},
            {"single_commit_build":"true"}, {"dependencies":{"evil":None}},
            {"files_sha256":{"payload":"NOT_SHA"}},
        )
        for values in bad:
            with self.subTest(values=list(values)):
                with self.assertRaises(ReleaseTransitionError):
                    review_transition(None,self.manifest(**values))

    def test_missing_old_receipt_does_not_silently_bless_rollback(self):
        with self.assertRaises(ReleaseTransitionError):
            review_transition({"schema":"unknown"},self.manifest())
        with self.assertRaises(ReleaseTransitionError):
            review_transition(self.manifest(),self.manifest(),
                              previous_provenance_verified=1)

    def test_no_mutation_of_input_manifest(self):
        original=self.manifest()
        candidate=self.manifest(source="b"*40)
        prev=copy.deepcopy(original);new=copy.deepcopy(candidate)
        review_transition(original,candidate)
        self.assertEqual(original,prev)
        self.assertEqual(candidate,new)


if __name__=="__main__":
    unittest.main()
