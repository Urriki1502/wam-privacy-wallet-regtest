"""WAM Fusion UI presentation contracts; never substitute for live-Core E2E."""
import unittest

from dataclasses import replace

from wam_regtest.fusion_pages import describe_broadcast_result
from wam_regtest.fusion_ui import (
    activity_by_block, confirmed_balance_history, fusion_palette, fusion_stylesheet,
)
from wam_regtest.wallet_read import HistoryRow, WalletReadSnapshot


def verified_snapshot(*, synthetic=False, mainnet=False):
    return WalletReadSnapshot(
        chain="regtest", height=105, tip="a"*64,
        receive_code="wamrtsp1-public-demo-test",
        confirmed_atoms=125000000, confirmed_utxos=1,
        history=(
            HistoryRow("b"*64, 103, 3, 150000000, 0),
            HistoryRow("c"*64, 104, 2, 0, 25000000),
            HistoryRow("d"*64, 103, 3, 5000000, 1000000),
        ),
        core_sha256="e"*64, synthetic_rpc=synthetic,
        mainnet_allowed=mainnet,
    )


class FusionDesignContracts(unittest.TestCase):
    def test_dark_light_signature_palette_preserves_accessible_tokens(self):
        dark = fusion_palette("dark")
        light = fusion_palette("light")

        def luminance(hexcolor):
            rgb=[int(hexcolor[i:i+2],16)/255 for i in (1,3,5)]
            linear=[v/12.92 if v<=0.04045 else ((v+0.055)/1.055)**2.4
                    for v in rgb]
            return sum(w*v for w,v in zip((0.2126,0.7152,0.0722),linear))

        def contrast(a,b):
            x,y=sorted((luminance(a),luminance(b)),reverse=True)
            return (x+0.05)/(y+0.05)

        for mode, palette in (("dark", dark), ("light", light)):
            self.assertRegex(palette["accent"],r"^#[0-9A-Fa-f]{6}$")
            self.assertGreaterEqual(contrast(palette["text"],palette["bg"]),7.0)
            self.assertGreaterEqual(contrast(palette["onaccent"],palette["accent"]),4.5)
            self.assertGreaterEqual(contrast(palette["accent"],palette["surface"]),4.5)
            self.assertNotEqual(palette["accent"],palette["brand"])
            self.assertIn("FusionPrimary", fusion_stylesheet(mode))
            self.assertIn("FusionActivityTable", fusion_stylesheet(mode))
            self.assertIn("FusionSegmented", fusion_stylesheet(mode))
            self.assertIn("FusionThemeThumb", fusion_stylesheet(mode))
        # One consistent action color family; WAM brand gold is not reused as
        # a focus/button tint. No dependence on deprecated 2026 Q05 hex values.
        self.assertEqual(dark["accent"], "#E0C36A")
        self.assertEqual(light["accent"], "#7A5A12")
        self.assertNotEqual(dark["bg"], light["bg"])

    def test_invalid_theme_fails_closed(self):
        for mode in ("auto", "", "neon", None, 0, True):
            with self.subTest(mode=mode), self.assertRaisesRegex(
                ValueError, "^FUSION_THEME_DENIED$"
            ):
                fusion_palette(mode)

    def test_missing_snapshot_has_no_synthetic_plot(self):
        self.assertEqual(activity_by_block(None), ())
        self.assertEqual(confirmed_balance_history(None), ())

    def test_incomplete_or_inconsistent_history_does_not_invent_balance_series(self):
        snap = verified_snapshot()
        self.assertEqual(confirmed_balance_history(snap), ())
        incomplete = replace(snap, history_complete=False, confirmed_atoms=129000000)
        self.assertEqual(confirmed_balance_history(incomplete), ())
        paged = replace(snap, history_offset=250, confirmed_atoms=129000000)
        self.assertEqual(confirmed_balance_history(paged), ())
        empty_nonzero = replace(snap, history=(), history_complete=True, confirmed_atoms=1)
        self.assertEqual(confirmed_balance_history(empty_nonzero), ())

    def test_complete_history_reconstructs_exact_confirmed_balance_points(self):
        snap = replace(
            verified_snapshot(),
            confirmed_atoms=150000000,
            height=110,
            history=(
                HistoryRow("b"*64, 108, 3, 200000000, 0),
                HistoryRow("c"*64, 110, 1, 0, 50000000),
            ),
            history_complete=True,
            history_offset=0,
        )
        self.assertEqual(confirmed_balance_history(snap), (
            (107, 0),
            (108, 200000000),
            (110, 150000000),
        ))
        zero = replace(snap, history=(), confirmed_atoms=0, height=3)
        self.assertEqual(confirmed_balance_history(zero), ((3, 0),))

    def test_confirmed_credit_debit_by_real_block_only(self):
        self.assertEqual(activity_by_block(verified_snapshot()), (
            (103, 155000000, 1000000),
            (104, 0, 25000000),
        ))

    def test_synthetic_or_mainnet_snapshot_cannot_drive_chart(self):
        for synthetic, mainnet in ((True, False), (False, True)):
            with self.subTest(synthetic=synthetic, mainnet=mainnet), self.assertRaisesRegex(
                ValueError, "^FUSION_HISTORY_UNVERIFIED_DENIED$"
            ):
                activity_by_block(verified_snapshot(synthetic=synthetic, mainnet=mainnet))

    def test_unconfirmed_rows_cannot_impersonate_verified_chain(self):
        snap = verified_snapshot()
        from dataclasses import replace
        for row in (HistoryRow("f"*64, 105, 0, 123, 0),
                    HistoryRow("f"*64, 106, 1, 123, 0),
                    HistoryRow("f"*64, 105, 1, -1, 0)):
            with self.subTest(row=row), self.assertRaisesRegex(
                ValueError, "^FUSION_HISTORY_UNVERIFIED_DENIED$"
            ):
                activity_by_block(replace(snap, history=(row,)))

    def test_broadcast_result_copy_uses_only_verified_inspect_facts(self):
        txid = "1e66b1d7d7c14d914ac34d523b3d2a9847521e7786fe5c9ba8a1cfa5cee6ff77"
        pending = describe_broadcast_result(txid, {
            "status": "Q06_TX_NOT_IN_CONFIRMED_HISTORY",
            "in_mempool": True,
        })
        self.assertIn("pending in this Core mempool", pending)
        self.assertIn(txid, pending)
        self.assertNotIn("failed", pending.lower())
        confirmed = describe_broadcast_result(txid, {
            "status": "Q06_CONFIRMED_IN_VERIFIED_HISTORY",
            "in_mempool": False,
        })
        self.assertTrue(confirmed.startswith("Confirmed on this REGTEST chain."))
        absent = describe_broadcast_result(txid, {
            "status": "Q06_TX_NOT_IN_CONFIRMED_HISTORY",
            "in_mempool": False,
        })
        self.assertIn("uncertain", absent.lower())
        self.assertNotIn("failed", absent.lower())
        submitted = describe_broadcast_result(txid)
        self.assertTrue(submitted.startswith("Submitted to this Core."))
        self.assertIn("Do not retry", submitted)
        self.assertIn("uncertain", describe_broadcast_result("not-a-txid").lower())

    def test_unverified_snapshot_cannot_drive_balance_history(self):
        for synthetic, mainnet in ((True, False), (False, True)):
            with self.subTest(synthetic=synthetic, mainnet=mainnet), self.assertRaisesRegex(
                ValueError, "^FUSION_HISTORY_UNVERIFIED_DENIED$"
            ):
                confirmed_balance_history(verified_snapshot(synthetic=synthetic, mainnet=mainnet))


class FusionV2PresentationWidgets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from wam_regtest.desktop import qt_application
        cls.app = qt_application()

    def test_overview_uses_verified_series_or_honest_empty_chart(self):
        from wam_regtest.fusion_ui import FusionOverview
        page = FusionOverview()
        self.addCleanup(page.deleteLater)
        page.render_snapshot(verified_snapshot())
        self.assertEqual(page.balance_chart._points, ())
        self.assertTrue(page.balance_value.text().endswith(" WAM"))
        self.assertGreaterEqual(page.balance_value.font().pointSize(), 0)
        from PySide6.QtWidgets import QAbstractButton, QToolButton
        self.assertEqual(page.findChildren(QToolButton, "FusionQuick"), [])
        overview_buttons = [b.text() for b in page.findChildren(QAbstractButton)]
        self.assertIn("Send", overview_buttons)
        self.assertIn("Receive", overview_buttons)
        self.assertNotIn("Backup Wallet", overview_buttons)
        self.assertNotIn("Verify Recovery", overview_buttons)
        self.assertNotIn("Network Status", overview_buttons)
        page.render_snapshot(None, locked=True)
        self.assertEqual(page.balance_value.text(), "—")
        consistent = replace(
            verified_snapshot(),
            confirmed_atoms=150000000,
            height=110,
            history=(
                HistoryRow("b"*64, 108, 3, 200000000, 0),
                HistoryRow("c"*64, 110, 1, 0, 50000000),
            ),
        )
        page.render_snapshot(consistent)
        self.assertEqual(page.balance_chart._points, (
            (107, 0), (108, 200000000), (110, 150000000),
        ))
        page.render_snapshot(
            consistent, available_atoms=100000000, reservation_count=1)
        self.assertIn("Spendable", page.fund_details.text())
        self.assertIn("reserved", page.fund_details.text())

    def test_theme_slider_three_positions_keyboard_and_no_binary_collapse(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from wam_regtest.fusion_ui import ThemeSlider
        slider = ThemeSlider()
        self.addCleanup(slider.deleteLater)
        slider.show()
        self.app.processEvents()
        self.assertEqual([b.toolTip() for b in slider.buttons],
                         ["Automatic", "Light", "Dark"])
        slider.setCurrentIndex(2, animate=False)
        self.assertTrue(slider.buttons[2].isChecked())
        self.assertFalse(slider.buttons[0].isChecked())
        slider.setFocus()
        QTest.keyClick(slider, Qt.Key.Key_Left)
        self.assertEqual(slider.currentIndex(), 1)
        QTest.keyClick(slider, Qt.Key.Key_Home)
        self.assertEqual(slider.currentIndex(), 0)
        QTest.keyClick(slider, Qt.Key.Key_End)
        self.assertEqual(slider.currentIndex(), 2)


if __name__ == "__main__":
    unittest.main()
