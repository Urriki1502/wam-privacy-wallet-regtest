"""WAM Fusion UI presentation contracts; never substitute for live-Core E2E."""
import unittest

from wam_regtest.fusion_ui import activity_by_block, fusion_palette, fusion_stylesheet
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
        for mode, palette in (("dark", dark), ("light", light)):
            self.assertIn("#", palette["accent"])
            self.assertNotEqual(palette["bg"], palette["text"])
            self.assertIn("FusionPrimary", fusion_stylesheet(mode))
            self.assertIn("FusionActivityTable", fusion_stylesheet(mode))
        self.assertEqual(dark["accent"], "#F1C55A")
        self.assertEqual(light["accent"], "#795507")
        self.assertNotEqual(dark["bg"], light["bg"])

    def test_invalid_theme_fails_closed(self):
        for mode in ("auto", "", "neon", None, 0, True):
            with self.subTest(mode=mode), self.assertRaisesRegex(
                ValueError, "^FUSION_THEME_DENIED$"
            ):
                fusion_palette(mode)

    def test_missing_snapshot_has_no_synthetic_plot(self):
        self.assertEqual(activity_by_block(None), ())

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


if __name__ == "__main__":
    unittest.main()
