"""R-04 package output integrity: public bytes, NOT native/Core acceptance."""
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from wam_regtest.r04_package_audit import (
    PackageAuditError, audit_candidate_output,
)


class R04PackageAuditContracts(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory(prefix="wam-r04-public-only-")
        self.addCleanup(td.cleanup)
        self.root = Path(td.name) / "published-output"
        self.root.mkdir()
        self.payload = self.root / "candidate-public-only.zip"
        self.payload.write_bytes(b"public NOT a genuine Core package")
        self.nested = self.root / "ui-scale" / "public.json"
        self.nested.parent.mkdir()
        self.nested.write_text('{"public":true}\n', encoding="utf8")
        self.manifest = self.root / "RELEASE_CANDIDATE_MANIFEST.json"
        self.sums = self.root / "SHA256SUMS.txt"
        self.record = {
            "schema": "wam-regtest-release-candidate/v1",
            "candidate_id": "WAM-Fusion-REGTEST-RC1",
            "network": "regtest",
            "platform": "windows-x64",
            "mainnet_allowed": False,
            "production_qualified": False,
            "official_final_release": False,
            "dev_wam_reviewed": False,
            "native_final_executable_e2e_pass": True,
            "source_head_sha": "a"*40,
            "checkout_sha": "a"*40,
            "wsp_source_commit": "b"*40,
            "core_sha256": {"wamd.exe": "c"*64, "wam-cli.exe": "d"*64},
            "files_sha256": {
                "candidate-public-only.zip": sha256(self.payload.read_bytes()).hexdigest(),
                "ui-scale/public.json": sha256(self.nested.read_bytes()).hexdigest(),
            },
        }
        self.write_manifest()

    def write_manifest(self):
        self.manifest.write_text(json.dumps(self.record, sort_keys=True)+"\n", encoding="utf8")
        self.write_sums()

    def write_sums(self):
        self.sums.write_text(
            "".join(sha256(p.read_bytes()).hexdigest()+"  "+p.name+"\n"
                    for p in sorted(self.root.iterdir()) if p.is_file() and p != self.sums),
            encoding="ascii",
        )

    def assert_refused(self):
        with self.assertRaises(PackageAuditError):
            audit_candidate_output(self.root, expected_platform="windows-x64")

    def test_verified_self_consistent_public_inventory_is_never_a_release_approval(self):
        receipt = audit_candidate_output(self.root, expected_platform="windows-x64")
        self.assertEqual(receipt["status"], "R04_PUBLIC_OUTPUT_INVENTORY_MATCH_ONLY")
        self.assertEqual(receipt["files_checked"], 4)
        for field in ("native_execution_verified_by_this_audit",
                      "publisher_signature_verified_by_this_audit",
                      "byte_identical_cross_build_reproducibility_qualified",
                      "physical_operator_accepted", "r04_full_p0_qualified",
                      "mainnet_allowed"):
            self.assertIs(receipt[field], False)

    def test_wrong_platform_and_manifests_cannot_promote(self):
        with self.assertRaises(PackageAuditError):
            audit_candidate_output(self.root, expected_platform="macos-arm64")
        for field, value in (
            ("network", "main"),
            ("platform", "unsupported"),
            ("mainnet_allowed", True),
            ("production_qualified", True),
            ("official_final_release", True),
            ("dev_wam_reviewed", True),
            ("native_final_executable_e2e_pass", False),
            ("source_head_sha", "a"*39),
        ):
            with self.subTest(field=field):
                old = self.record[field]
                self.record[field] = value
                self.write_manifest()
                self.assert_refused()
                self.record[field] = old
                self.write_manifest()

    def test_tampered_missing_and_extra_nested_members_denied(self):
        self.payload.write_bytes(b"tampered")
        self.assert_refused()
        self.payload.write_bytes(b"public NOT a genuine Core package")
        self.nested.unlink()
        self.assert_refused()
        self.nested.write_text('{"public":true}\n',encoding="utf8")
        (self.root/"injected").write_bytes(b"unexpected")
        self.assert_refused()

    def test_signed_top_level_checksums_must_match_payload_and_manifest(self):
        self.sums.write_text("0"*64+"  candidate-public-only.zip\n")
        self.assert_refused()
        self.write_sums()
        self.sums.write_text(self.sums.read_text()+"0"*64+"  candidate-public-only.zip\n")
        self.assert_refused()
        self.write_sums()
        self.sums.write_text(self.sums.read_text().replace("  candidate-public-only.zip",
                                                        "  ../candidate-public-only.zip"))
        self.assert_refused()

    def test_manifest_duplicate_keys_cannot_be_parsed(self):
        raw=self.manifest.read_text()
        self.manifest.write_text(raw.replace('"network": "regtest",',
            '"network": "main", "network": "regtest",'))
        self.write_sums()
        self.assert_refused()

    def test_corrupt_archive_manifest_digest_or_member_hash_denied(self):
        self.record["core_sha256"]["wamd.exe"]="X"*64
        self.write_manifest()
        self.assert_refused()
        self.record["core_sha256"]["wamd"]="c"*64
        self.record["files_sha256"]["candidate-public-only.zip"]="0"*64
        self.write_manifest()
        self.assert_refused()

    def test_symlinked_member_denied(self):
        (self.root/"fake-link").symlink_to(self.payload)
        self.assert_refused()

    def test_case_colliding_public_member_refused(self):
        (self.root/"Candidate-public-only.zip").write_bytes(b"other")
        self.assert_refused()

    def test_known_output_sha_cannot_relabel_wrong_root(self):
        with self.assertRaises(PackageAuditError):
            audit_candidate_output(self.root/"nonexistent", expected_platform="windows-x64")


if __name__=="__main__":
    unittest.main()
