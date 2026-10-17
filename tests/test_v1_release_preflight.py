"""Negative/shape unit tests for R-01/R-02; mocked signatures NEVER qualify binaries."""
import hashlib
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from wam_regtest.core_release_preflight import (
    ASSETS, CURRENT_APPROVED, IntakeError, ROOT, review_offline, update_signal,
)
from wam_regtest.release import ReleaseError


class Core012IntakeUnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.key, self.sums, self.sig = [self.base / s for s in
                                         ("SIGNING-KEY.asc", "SHA256SUMS", "SHA256SUMS.asc")]
        for p in (self.key, self.sums, self.sig): p.write_bytes(b"untrusted-fixture")

    def archive(self, platform="macos-arm64", *, members=None):
        p = self.base / ASSETS[platform]
        suffix = ".exe" if platform == "windows-x64" else ""
        if members is None:
            members = {f"{ROOT}/bin/wamd{suffix}": b"test-node",
                       f"{ROOT}/bin/wam-cli{suffix}": b"test-cli"}
        if platform == "windows-x64":
            with zipfile.ZipFile(p, "w") as z:
                for name, data in members.items(): z.writestr(name, data)
        else:
            import io
            with tarfile.open(p, "w:gz") as t:
                for name, data in members.items():
                    info = tarfile.TarInfo(name); info.size = len(data)
                    t.addfile(info, io.BytesIO(data))
        return p

    def review(self, p, platform="macos-arm64", **kwargs):
        # A unit mock simulates ONLY the independently authenticated signed digest.
        # Real GPG verification is mandatory when running the production path.
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        with patch("wam_regtest.core_release_preflight._signed_digest", return_value=actual):
            return review_offline(p, self.key, self.sums, self.sig, platform, **kwargs)

    def test_all_three_platforms_stay_unqualified(self):
        for platform in ASSETS:
            with self.subTest(platform=platform):
                result = self.review(self.archive(platform), platform,
                                     release_body="\nMANDATORY: consensus field initialized\n")
                self.assertTrue(result["signed_archive_verified"])
                self.assertEqual(result["advisory_release_signal"], "UNVERIFIED_MANDATORY_CLAIM")
                for key in ("core_version_profile_qualified", "native_core_e2e_qualified",
                            "wallet_signing_authorized", "installation_authorized", "mainnet_allowed",
                            "release_notes_authenticated"):
                    self.assertFalse(result[key])
                self.assertEqual(set(result["expected_members"]),
                                 {"wamd.exe", "wam-cli.exe"} if platform == "windows-x64"
                                 else {"wamd", "wam-cli"})

    def test_rollback_and_unapproved_version_refused(self):
        archive = self.archive()
        for kw in ({"installed": "v0.1.12"}, {"installed": "v0.1.13"},
                   {"minimum": "v0.1.13"}, {"installed": "v0.1.8"},
                   {"minimum": "v0.1.8"}, {"installed": "v0.1.8", "minimum": "v0.1.8"},
                   {"installed": "v0.1.x"}):
            with self.subTest(kw=kw), self.assertRaises(IntakeError):
                self.review(archive, **kw)
        self.assertEqual(CURRENT_APPROVED, "v0.1.11")

    def test_tampered_archive_rejected_even_if_signer_claimed_valid(self):
        archive = self.archive()
        known = hashlib.sha256(archive.read_bytes()).hexdigest()
        archive.write_bytes(archive.read_bytes() + b"tampered")
        with patch("wam_regtest.core_release_preflight._signed_digest", return_value=known):
            with self.assertRaisesRegex(IntakeError, "CORE_RELEASE_ARCHIVE_DIGEST_DENIED"):
                review_offline(archive, self.key, self.sums, self.sig, "macos-arm64")

    def test_bad_signature_and_unsigned_input_refused(self):
        archive = self.archive()
        with patch("wam_regtest.core_release_preflight._signed_digest",
                   side_effect=ReleaseError("RELEASE_SIGNATURE_DENIED")):
            with self.assertRaisesRegex(IntakeError, "CORE_RELEASE_SIGNATURE_DENIED"):
                review_offline(archive, self.key, self.sums, self.sig, "macos-arm64")
        self.sig.unlink()
        with self.assertRaisesRegex(IntakeError, "CORE_RELEASE_FILE_DENIED"):
            self.review(archive)

    def test_unexpected_archive_platform_and_member_refused(self):
        archive = self.archive(members={f"{ROOT}/bin/wamd": b"node",
                                        f"{ROOT}/bin/../bad": b"evil"})
        with self.assertRaisesRegex(IntakeError, "CORE_RELEASE_MEMBER_DENIED"):
            self.review(archive)
        with self.assertRaisesRegex(IntakeError, "CORE_RELEASE_ASSET_DENIED"):
            self.review(archive, "linux-x64")
        with self.assertRaisesRegex(IntakeError, "CORE_RELEASE_PLATFORM_DENIED"):
            self.review(archive, "android")

    def test_release_body_is_advisory_not_authenticated(self):
        self.assertEqual(update_signal(None), "UNKNOWN")
        self.assertEqual(update_signal(" \n MANDATORY: new consensus rule"),
                         "UNVERIFIED_MANDATORY_CLAIM")
        self.assertEqual(update_signal("  \n MANDATORY:"), "UNKNOWN")
        self.assertEqual(update_signal("normal bugfix"), "UNVERIFIED_NORMAL_CLAIM")
        self.assertEqual(update_signal(" \n "), "UNKNOWN")
        with self.assertRaisesRegex(IntakeError, "CORE_RELEASE_NOTES_DENIED"):
            update_signal("A"*70000)

    def test_symlinked_archive_and_missing_binary_refused(self):
        archive = self.archive()
        alias = self.base/"other"; alias.symlink_to(archive)
        with self.assertRaisesRegex(IntakeError, "CORE_RELEASE_FILE_DENIED"):
            self.review(alias)
        archive = self.archive(members={f"{ROOT}/bin/wamd": b"node"})
        with self.assertRaisesRegex(IntakeError,
                                     "CORE_RELEASE_COUNT_DENIED|CORE_RELEASE_BINARY_MEMBERS_DENIED"):
            self.review(archive)

    def test_zero_length_signature_and_gpg_missing_refuse(self):
        p = self.archive()
        self.sig.write_bytes(b"")
        with self.assertRaisesRegex(IntakeError, "CORE_RELEASE_FILE_DENIED"):
            self.review(p)
        self.sig.write_bytes(b"dummy")
        with self.assertRaisesRegex(IntakeError, "CORE_RELEASE_GPG_DENIED"):
            self.review(p, gpg="")

    def test_zip_untrusted_windows_member_and_case_collision(self):
        members = {f"{ROOT}/bin/wamd.exe": b"node", f"{ROOT}/bin/wam-cli.exe": b"cli",
                   f"{ROOT}/bin/WAMD.EXE": b"evil"}
        p = self.archive("windows-x64", members=members)
        with self.assertRaisesRegex(IntakeError, "CORE_RELEASE_MEMBER_DENIED"):
            self.review(p, "windows-x64")

    def test_unsigned_release_notes_cannot_authorize_execution(self):
        p = self.archive()
        for body in ("MANDATORY: urgent upgrade", "v0.1.12 released", None):
            with self.subTest(body=body):
                result = self.review(p, release_body=body)
                self.assertFalse(result["installation_authorized"])
                self.assertFalse(result["wallet_signing_authorized"])
                self.assertFalse(result["release_notes_authenticated"])


if __name__ == "__main__":
    unittest.main()
