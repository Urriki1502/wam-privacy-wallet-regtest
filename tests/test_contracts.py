"""Small negative security tests; never substitute for live-Core CI."""
import json
from pathlib import Path
import tempfile
import unittest

from wam_regtest.core import CoreSmokeError, smoke_real_core, verified_core_paths, _early_exit_category
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

    def test_early_exit_redacts_real_daemon_messages(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertEqual(
                _early_exit_category(root), "CORE_DAEMON_EARLY_EXIT_LOG_UNAVAILABLE"
            )
            samples = (
                ("dyld: Library not loaded: /private/sensitive/libsomething.dylib",
                 "CORE_MACOS_DYNAMIC_LIBRARY_UNAVAILABLE"),
                ("Error: Unknown configuration value rpcmystery in config file",
                 "CORE_DAEMON_OPTION_UNSUPPORTED"),
                ("Error: unable to bind to 127.0.0.1:19001",
                 "CORE_DAEMON_PORT_BIND_DENIED"),
                ("private data must NEVER be included in an error",
                 "CORE_DAEMON_EARLY_EXIT_UNCLASSIFIED"),
            )
            for raw, expected in samples:
                (root / "core-output.log").write_text(raw)
                result = _early_exit_category(root)
                self.assertEqual(result, expected)
                self.assertNotIn("private", result.lower())
                self.assertNotIn("19001", result)

    def test_release_downloader_refuses_redirect(self):
        with self.assertRaises(ReleaseError):
            _NoRedirect().redirect_request(None, None, 302, "moved", {}, "http://not-official.test")


if __name__ == "__main__":
    unittest.main()
