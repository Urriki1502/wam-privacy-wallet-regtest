"""Fail-closed Windows WSP app bridge contracts; never use real funds or keys."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wam_regtest.windows_core_regtest_smoke import (
    WindowsCoreSmokeError, smoke_signed_windows_regtest,
)
from wam_regtest.windows_wsp_regtest import (
    WindowsWspCoreRpc, WindowsWspError,
)


class WindowsWspBridgeContracts(unittest.TestCase):
    def test_scan_api_has_no_write_authority(self):
        rpc = WindowsWspCoreRpc(Path("cli"), Path("chain"), 18443, {})
        for method in ("sendrawtransaction", "generatetoaddress", "dumpprivkey",
                       "importprivkey", "stop", "walletprocesspsbt"):
            with self.subTest(method=method), self.assertRaisesRegex(
                WindowsWspError, "^WIN_WSP_SCANNER_READ_ONLY_DENIED$"):
                rpc.call(method, [])

    def test_fixture_direct_write_api_rejects_invalid_payloads(self):
        rpc = WindowsWspCoreRpc(Path("cli"), Path("chain"), 18443, {})
        for bad in ("", "hello", "0" * 2_000_001):
            with self.subTest(size=len(bad)), self.assertRaisesRegex(
                WindowsWspError, "^WIN_WSP_PUBLIC_FIXTURE_TX_DENIED$"):
                rpc._call("sendrawtransaction", [bad])
        with self.assertRaisesRegex(WindowsWspError, "^WIN_WSP_PUBLIC_FIXTURE_MINE_DENIED$"):
            rpc._call("generatetoaddress", ["1", "mainnet-address"])

    def test_opt_in_requires_real_wsp_source_before_loading(self):
        missing = Path("missing")
        with patch("wam_regtest.windows_core_regtest_smoke.sys.platform", "win32"), \
             patch("wam_regtest.windows_core_regtest_smoke.platform.machine", return_value="AMD64"):
            for bad in (None, missing):
                with self.subTest(source=bad), self.assertRaisesRegex(
                    WindowsCoreSmokeError, "^WIN_CORE_PUBLIC_FIXTURE_SCOPE_DENIED$"):
                    smoke_signed_windows_regtest(
                        missing, missing, missing, missing,
                        consent=True, confirm_public_fixture_payment=True,
                        wsp_source=bad)
            with self.assertRaisesRegex(
                WindowsCoreSmokeError, "^WIN_CORE_PUBLIC_FIXTURE_SCOPE_DENIED$"):
                smoke_signed_windows_regtest(
                    missing, missing, missing, missing,
                    consent=True, confirm_public_fixture_payment=False,
                    wsp_source=Path.cwd())


if __name__ == "__main__":
    unittest.main()
