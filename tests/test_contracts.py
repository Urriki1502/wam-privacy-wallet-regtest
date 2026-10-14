"""Small negative security tests; never substitute for live-Core CI."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from wam_regtest.core import CoreSmokeError, smoke_real_core, verified_core_paths, _early_exit_category, _write_private_config
from wam_regtest.release import ARCHIVES, ReleaseError, _verify_executable_shape, _NoRedirect
from wam_regtest.wsp_live import LiveCoreReadOnlyCli, RealWspScanError, _pinned_source, REGTEST_GENESIS


class CoreContractTests(unittest.TestCase):
    def test_payment_e2e_requires_both_explicit_consent_and_pinned_wsp(self):
        with self.assertRaisesRegex(CoreSmokeError,
                                    "^CORE_REAL_REGTEST_CONSENT_DENIED$"):
            smoke_real_core(Path("/nonexistent"), explicit_consent=False,
                            wsp_payment_e2e=True)
        for flag in (True, 1, "true", None):
            if flag is True:
                target = "CORE_PUBLIC_FIXTURE_PAYMENT_SCOPE_DENIED"
            elif flag is None:
                continue  # ordinary non-payment mode, tested separately
            else:
                target = "CORE_PUBLIC_FIXTURE_PAYMENT_SCOPE_DENIED"
            with self.subTest(flag=flag), self.assertRaisesRegex(
                CoreSmokeError, "^" + target + "$"
            ):
                smoke_real_core(Path("/nonexistent"), explicit_consent=True,
                                wsp_payment_e2e=flag)
        with self.assertRaisesRegex(CoreSmokeError,
                                    "^CORE_PUBLIC_FIXTURE_PAYMENT_SCOPE_DENIED$"):
            smoke_real_core(Path("/nonexistent"), explicit_consent=True,
                            wsp_payment_e2e=True, wsp_source=None)

    def test_live_scanner_rpc_cannot_access_write_methods_or_unqualified_chain(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root).absolute()
            rpc = LiveCoreReadOnlyCli(folder / "wam-cli", folder)
            for method in (
                "sendrawtransaction", "walletprocesspsbt", "createwallet",
                "dumpprivkey", "generatetoaddress", "stop", "getblock",
            ):
                with self.subTest(method=method), self.assertRaisesRegex(
                    RealWspScanError, "^WSP_LIVE_METHOD_DENIED$",
                ):
                    rpc.call(method)
            self.assertEqual(len(REGTEST_GENESIS), 64)

    def test_pinned_wsp_source_never_imports_unknown_package(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root).absolute()
            with self.assertRaisesRegex(RealWspScanError, "^WSP_SOURCE_PIN_DENIED$"):
                _pinned_source(folder)

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

    def test_mutable_receipt_cannot_authorize_replaced_macos_cli(self):
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder)
            receipt={
                "platform":"macos-arm64","signed_archive_verified":True,
                "mainnet_allowed":False,"loader_process_binding_qualified":False,
                "wamd_sha256":ARCHIVES["macos-arm64"][1],"wam_cli_sha256":"0"*64,
            }
            (home/"receipt.json").write_text(json.dumps(receipt))
            with self.assertRaisesRegex(CoreSmokeError,"CORE_RECEIPT_DENIED"):
                verified_core_paths(home)

    def test_architecture_requires_exact_signed_executable_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "bad-binary"
            file.write_bytes(b"\x00" * 32)
            for os_arch in ARCHIVES:
                with self.subTest(os_arch=os_arch), self.assertRaises(ReleaseError):
                    _verify_executable_shape(file, os_arch)

    def test_real_core_config_network_options_are_regtest_scoped(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            _write_private_config(root, 29453, 29455)
            conf = root / "wam.conf"
            payload = conf.read_text()
            global_section, regtest_section = payload.split("[regtest]\n")
            self.assertEqual(global_section, "regtest=1\nserver=1\n")
            self.assertIn("rpcport=29453\n", regtest_section)
            self.assertIn("port=29455\n", regtest_section)
            self.assertIn("connect=0\n", regtest_section)
            self.assertIn("listen=0\n", regtest_section)
            self.assertNotIn("rpcpassword=", global_section)
            self.assertNotIn("rpcbind=", global_section)
            self.assertEqual(os.stat(conf).st_mode & 0o777, 0o600)

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
                 "CORE_DAEMON_EXIT_LOG_TOKENS_ERROR"),
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
