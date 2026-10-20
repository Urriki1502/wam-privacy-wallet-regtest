"""R-01 synthetic OFFLINE intake contract tests, never Core/GPG signoff.

Real upstream signature verification requires independently sourced public
signing key, signed release assets and native GPG execution on each platform.
"""
from hashlib import sha256
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wam_regtest.r01_release_intake import (
    CoreIntakeRefusal, verify_offline_core_intake,
)
from wam_regtest.release import ReleaseError


class R01OfflineIntakeContracts(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name).resolve()
        self.files = {}
        for name, payload in (
            ("SIGNING-KEY.asc", b"PUBLIC TEST KEY ONLY\n"),
            ("SHA256SUMS", b"PUBLIC SIGNED SUMS FIXTURE\n"),
            ("SHA256SUMS.asc", b"PUBLIC SIGNATURE FIXTURE\n"),
            ("wam-coin-v0.1.12-arm64-apple-darwin.tar.gz", b"NOT EXECUTABLE\n"),
        ):
            p = self.root / name
            p.write_bytes(payload)
            self.files[name] = p

    def kwargs(self):
        return dict(
            version="v0.1.12", platform="macos-arm64",
            archive=self.files["wam-coin-v0.1.12-arm64-apple-darwin.tar.gz"],
            signing_key=self.files["SIGNING-KEY.asc"],
            sha256sums=self.files["SHA256SUMS"],
            signature=self.files["SHA256SUMS.asc"],
        )

    def test_signed_exact_bytes_verify_but_never_approve_activation(self):
        digest = sha256(self.kwargs()["archive"].read_bytes()).hexdigest()
        with patch("wam_regtest.r01_release_intake.release._validate_signed_sums", return_value=digest) as verify:
            receipt = verify_offline_core_intake(**self.kwargs())
        self.assertEqual(verify.call_count, 1)
        self.assertEqual(receipt["status"], "R01_OFFLINE_SIGNATURE_AND_ARCHIVE_PASS_ONLY")
        self.assertEqual(receipt["version"], "v0.1.12")
        self.assertEqual(receipt["archive_sha256"], digest)
        self.assertTrue(receipt["signed_manifest_and_archive_verified"])
        for field in ("trusted_key_distribution_independently_attested",
                      "core_compatibility_qualified", "native_binary_executed",
                      "wallet_signing_or_broadcast_allowed",
                      "core_install_or_activation_allowed", "mainnet_allowed"):
            self.assertFalse(receipt[field], field)

    def test_signed_digest_mismatch_rejected(self):
        with patch("wam_regtest.r01_release_intake.release._validate_signed_sums",
                   return_value="0" * 64):
            with self.assertRaisesRegex(CoreIntakeRefusal, "R01_ARCHIVE_SHA_DENIED"):
                verify_offline_core_intake(**self.kwargs())

    def test_wrong_signer_or_bad_gpg_refused(self):
        with patch("wam_regtest.r01_release_intake.release._validate_signed_sums",
                   side_effect=ReleaseError("RELEASE_SIGNATURE_DENIED")):
            with self.assertRaisesRegex(CoreIntakeRefusal, "R01_SIGNATURE_OR_SIGNER_DENIED"):
                verify_offline_core_intake(**self.kwargs())

    def test_invalid_signed_digest_never_accepted(self):
        for digest in ("A" * 64, "a" * 63, "a" * 64 + "\n", "not-sha"):
            with self.subTest(digest=digest):
                with patch("wam_regtest.r01_release_intake.release._validate_signed_sums",
                           return_value=digest):
                    with self.assertRaisesRegex(CoreIntakeRefusal, "R01_SIGNED_MANIFEST_DENIED"):
                        verify_offline_core_intake(**self.kwargs())

    def test_version_platform_and_asset_are_exact(self):
        with patch("wam_regtest.r01_release_intake.release._validate_signed_sums") as verify:
            for change, error in (
                ({"version": "v0.1.13"}, "R01_RELEASE_SCOPE_DENIED"),
                ({"version": "../v0.1.12"}, "R01_RELEASE_SCOPE_DENIED"),
                ({"platform": "windows-x64"}, "R01_ASSET_PLATFORM_DENIED"),
                ({"platform": "unknown"}, "R01_RELEASE_SCOPE_DENIED"),
                ({"gpg_path": ""}, "R01_RELEASE_SCOPE_DENIED"),
                ({"archive": self.root / "rogue.zip"}, "R01_ASSET_PLATFORM_DENIED"),
            ):
                with self.subTest(change=change):
                    kwargs = self.kwargs()
                    kwargs.update(change)
                    with self.assertRaisesRegex(CoreIntakeRefusal, error):
                        verify_offline_core_intake(**kwargs)
            verify.assert_not_called()

    def test_linked_or_missing_public_input_refused(self):
        source = self.files["SIGNING-KEY.asc"]
        kwargs = self.kwargs()
        alias = self.root / "key-link"
        try:
            alias.symlink_to(source)
        except (OSError, NotImplementedError):
            pass
        else:
            kwargs["signing_key"] = alias
            with self.assertRaisesRegex(CoreIntakeRefusal, "R01_INPUT_TYPE_DENIED"):
                verify_offline_core_intake(**kwargs)
        kwargs["signing_key"] = self.root / "missing.asc"
        with self.assertRaisesRegex(CoreIntakeRefusal, "R01_INPUT_UNAVAILABLE"):
            verify_offline_core_intake(**kwargs)

    def test_hardlinked_file_refused(self):
        alias = self.root / "hardlink.asc"
        try:
            os.link(self.files["SIGNING-KEY.asc"], alias)
        except OSError:
            self.skipTest("hardlinks unavailable on this test filesystem")
        with self.assertRaisesRegex(CoreIntakeRefusal, "R01_INPUT_TYPE_DENIED"):
            verify_offline_core_intake(**self.kwargs())

    def test_zero_and_oversized_public_key_refused_before_gpg(self):
        key = self.files["SIGNING-KEY.asc"]
        with patch("wam_regtest.r01_release_intake.release._validate_signed_sums") as verify:
            key.write_bytes(b"")
            with self.assertRaisesRegex(CoreIntakeRefusal, "R01_INPUT_TYPE_DENIED"):
                verify_offline_core_intake(**self.kwargs())
            key.write_bytes(b"x" * 32769)
            with self.assertRaisesRegex(CoreIntakeRefusal, "R01_INPUT_TYPE_DENIED"):
                verify_offline_core_intake(**self.kwargs())
            verify.assert_not_called()

    def test_recognize_existing_011_without_qualifying_it(self):
        original = self.kwargs()["archive"]
        old = self.root / "wam-coin-v0.1.11-arm64-apple-darwin.tar.gz"
        old.write_bytes(original.read_bytes())
        kwargs = self.kwargs()
        kwargs.update(version="v0.1.11", archive=old)
        digest = sha256(old.read_bytes()).hexdigest()
        with patch("wam_regtest.r01_release_intake.release._validate_signed_sums", return_value=digest):
            record = verify_offline_core_intake(**kwargs)
        self.assertFalse(record["core_compatibility_qualified"])
        self.assertEqual(record["version"], "v0.1.11")


if __name__ == "__main__":
    unittest.main()
