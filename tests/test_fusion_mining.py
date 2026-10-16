"""Supplemental Qt presentation negatives; actual Core GUI remains mandatory."""
import unittest


class MiningPresentation(unittest.TestCase):
    def test_mining_ui_rejects_reward_substitution_and_clears_stale_values(self):
        from wam_regtest.desktop import qt_application
        from wam_regtest.mining_gui import MiningAccountPage
        from wam_regtest.mining_read import MiningSnapshot
        from wam_regtest.mining_account import MiningWalletBalance,RewardSplit
        app=qt_application();page=MiningAccountPage()
        try:
            snapshot=MiningSnapshot(101,'a'*64,MiningWalletBalance(4750000000,0,0,4750000000,1),RewardSplit.regtest(102))
            page.render_snapshot(snapshot)
            self.assertEqual(page.values['available_atoms'].text(),'47.50000000 WAM')
            self.assertIn('treasury excluded',page.state.text())
            for invalid in (object(),MiningSnapshot(101,'a'*64,snapshot.balance,RewardSplit.regtest(151))):
                with self.assertRaisesRegex(ValueError,'^MINING_GUI_SNAPSHOT_DENIED$'):page.render_snapshot(invalid)
                self.assertTrue(all(v.text()=='—' for v in page.values.values()))
            page.render_snapshot(None);self.assertEqual(page.reward.text(),'—')
        finally:
            page.widget.close();page.widget.deleteLater();app.processEvents()
