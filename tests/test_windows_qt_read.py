"""Fail-closed test of Windows real-source Qt wallet read bridge."""
from pathlib import Path
import unittest

from wam_regtest.windows_wallet_read import WindowsWalletReadError, read_native_windows_wallet


class WinRealReadBoundaryTests(unittest.TestCase):
    def test_missing_or_noncanonical_inputs_never_serve_balance(self):
        for core in (Path("relative.exe"), Path("nonexistent-absolute-file.exe").absolute()):
            with self.subTest(core=str(core)), self.assertRaises(WindowsWalletReadError):
                read_native_windows_wallet(
                    core, Path("cli.exe").absolute(), Path("datadir").absolute(),
                    18443, {}, Path("source").absolute(), "0"*64)

    def test_untrusted_hash_denied_before_scanner(self):
        missing = Path("no-core.exe").absolute()
        for bad in ("", "A"*64, "ab"*31, "0"*64+"x"):
            with self.subTest(digest=bad), self.assertRaisesRegex(
                WindowsWalletReadError, "^WIN_READ_SCOPE_DENIED$"
            ):
                read_native_windows_wallet(
                    missing, missing, missing.parent, 18443,
                    {}, missing.parent, bad)


if __name__ == "__main__":
    unittest.main()
