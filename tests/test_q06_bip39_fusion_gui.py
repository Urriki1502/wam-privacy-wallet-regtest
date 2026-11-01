"""Q06 normal GUI must reuse the installed Fusion application design.

This is a Qt surface contract only, never a fake pass for real Core, on-chain
transaction, native key custody or signed/frozen binaries.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class Q06ExistingFusionUiContract(unittest.TestCase):
    def test_q06_main_window_reuses_existing_fusion_pages_and_owner(self):
        from types import SimpleNamespace
        from PySide6.QtWidgets import QApplication
        from wam_regtest.wallet_executor import ExecutorState
        from wam_regtest.fusion_ui import FusionOverview
        from wam_regtest.fusion_pages import ReceivePage, HistoryPage, PaymentSteps
        from wam_regtest.bip39_fusion_gui import Bip39FusionWindow
        from wam_regtest.managed_onboarding import launch

        app=QApplication.instance() or QApplication([])
        owner=SimpleNamespace(
            state=ExecutorState(),busy=False,closed=False)
        window=Bip39FusionWindow(owner)
        try:
            self.assertIs(window.executor,owner)
            self.assertIsInstance(window.overview,FusionOverview)
            self.assertIsInstance(window.receive_page,ReceivePage)
            self.assertIsInstance(window.history_page,HistoryPage)
            self.assertIsInstance(window.payment_steps,PaymentSteps)
            self.assertEqual(
                tuple(window.navigation.item(i).text() for i in range(window.navigation.count())),
                ("Overview","Receive","History","Send","Security","Advanced"))
            self.assertIs(window.stack.widget(0),window.overview)
            self.assertIs(window.stack.widget(1),window.receive_page)
            self.assertIs(window.stack.widget(2),window.history_page)
            self.assertFalse(window.overview.go_send.isEnabled())
            self.assertFalse(window.send.isEnabled())
            window.navigation.setCurrentRow(3)
            self.assertEqual(window.page_title.text(),"Send")
            window.navigation.setCurrentRow(0)
            self.assertEqual(window.page_title.text(),"Overview")
            self.assertTrue(window.fund.parent() is not window._legacy_layout_holder)
        finally:
            window._poll.stop()
            window.hide()
            window.deleteLater()
            app.processEvents()

    def test_normal_launch_routes_to_fusion_not_old_developer_trial(self):
        import inspect
        from wam_regtest.bip39_owner_gui import launch_bip39_trial
        source=inspect.getsource(launch_bip39_trial)
        self.assertIn("Bip39FusionWindow(executor)",source)
        self.assertNotIn("window=Bip39TrialWindow(executor)",source)


if __name__=="__main__":
    unittest.main()
