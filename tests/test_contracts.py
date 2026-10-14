"""Small negative security tests; never substitute for live-Core CI."""
import json
from pathlib import Path
import tempfile
import unittest

from wam_regtest.core import CoreSmokeError, smoke_real_core, verified_core_paths
from wam_regtest.release import ARCHIVES, ReleaseError, _verify_executable_shape, _NoRedirect


class CoreContractTests(unittest.TestCase):
    def test_consent_denied_before_filesystem_or_process(self):
        with self.assertRaisesRegex(CoreSmokeError, "CORE_REAL_REGTEST_CONSENT_DENIED"):
            smoke_real_core(Path("/nonexistent/path"), explicit_consent=False)
        with self.assertRaisesRegex(CoreSmokeError, "CORE_REAL_REGTEST_CONSENT_DENIED"):
            smoke_real_core(Path("/nonexistent/path"), explicit_consent=1)

    def test_missing_signed_receipt_does_not_start_node(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(CoreSmokeError, "CORE_EXACT_BINARY_DENIED"):
                verified_core_paths(Path(folder))

    def test_manifest_cannot_authorize_mainnet_or_unknown_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            for value in (True, "true", None):
                receipt = {
                    "platform": "macos-arm64", "signed_archive_verified": value,
                    "mainnet_allowed": False,
                    "loader_process_binding_qualified": False,
                    "wamd_sha256": ARCHIVES["macos-arm64"][1],
                }
                (home / "receipt.json").write_text(json.dumps(receipt))
                with self.assertRaises(CoreSmokeError):
                    verified_core_paths(home)

    def test_architecture_requires_exact_signed_executable_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "bad-binary"
            file.write_bytes(b"\x00" * 32)
            for os_arch in ARCHIVES:
                with self.subTest(os_arch=os_arch), self.assertRaises(ReleaseError):
                    _verify_executable_shape(file, os_arch)

    def test_release_downloader_refuses_redirect(self):
        with self.assertRaises(ReleaseError):
            _NoRedirect().redirect_request(None, None, 302, "moved", {}, "http://not-official.test")


if __name__ == "__main__":
    unittest.main()
