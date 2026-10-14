"""Strict GUI/control tests: no fake Core, no synthetic chain or user keys."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

from wam_regtest.core import CoreSmokeError, smoke_real_core
from wam_regtest.wallet_read import RealWalletReadError, read_real_wallet_snapshot
from wam_regtest.desktop import resolve_theme


class RealMacosWalletContracts(unittest.TestCase):
    def test_local_timezone_day_night_and_manual_override(self):
        vn = timezone(timedelta(hours=7))
        for hour, minute, theme in (
            (0, 0, "dark"), (5, 59, "dark"),
            (6, 0, "light"), (17, 59, "light"),
            (18, 0, "dark"), (23, 59, "dark"),
        ):
            with self.subTest(hour=hour, minute=minute):
                self.assertEqual(
                    resolve_theme("auto", datetime(2026, 10, 14, hour, minute, tzinfo=vn)),
                    theme,
                )
        instant = datetime(2026, 10, 13, 23, 30, tzinfo=timezone.utc)
        self.assertEqual(resolve_theme("auto", instant), "dark")
        self.assertEqual(resolve_theme("auto", instant.astimezone(vn)), "light")
        self.assertEqual(resolve_theme("dark", instant.astimezone(vn)), "dark")
        self.assertEqual(resolve_theme("light", instant), "light")

    def test_malformed_theme_does_not_invoke_network_or_change_state(self):
        clock = datetime(2026, 10, 14, 9, tzinfo=timezone.utc)
        for bad in ("", "system", "solar", 1, None, True):
            with self.subTest(bad=bad), self.assertRaisesRegex(
                ValueError, "^REGTEST_GUI_THEME_DENIED$"
            ):
                resolve_theme(bad, clock)
        with self.assertRaisesRegex(ValueError, "^REGTEST_GUI_THEME_DENIED$"):
            resolve_theme("auto", datetime(2026, 10, 14, 9))

    def test_gui_e2e_requires_positive_regtest_payment_and_consent(self):
        with self.assertRaisesRegex(
            CoreSmokeError, "^CORE_REAL_GUI_SCOPE_DENIED$",
        ):
            smoke_real_core(Path("/untrusted"), explicit_consent=True,
                            gui_e2e=True, wsp_payment_e2e=False)
        for malformed in ("true", 1, None):
            with self.subTest(malformed=malformed), self.assertRaisesRegex(
                CoreSmokeError, "^CORE_REAL_GUI_SCOPE_DENIED$",
            ):
                smoke_real_core(Path("/untrusted"), explicit_consent=True,
                                gui_e2e=malformed, wsp_payment_e2e=True,
                                wsp_source=Path("/untrusted"))

    def test_no_core_wallet_projection_from_unknown_filesystem(self):
        with self.assertRaises(RealWalletReadError):
            read_real_wallet_snapshot(
                Path("/does-not-exist"), Path("/not-a-regtest-datadir"),
                Path("/not-wsp-source"),
            )


if __name__ == "__main__":
    unittest.main()
