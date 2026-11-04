"""WAM Fusion UI presentation contracts; never substitute for live-Core E2E."""
import unittest

from wam_regtest.fusion_pages import describe_broadcast_result
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


if __name__ == "__main__":
    unittest.main()
