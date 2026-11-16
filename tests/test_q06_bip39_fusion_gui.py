"""Q06 normal GUI must reuse the installed Fusion application design.

This is a Qt surface contract only, never a fake pass for real Core, on-chain
transaction, native key custody or signed/frozen binaries.
"""
import ast
import importlib.util
import os
from pathlib import Path
import sys
import unittest

# Never force offscreen on Cocoa/Windows: native platform qualification needs
# the actual desktop plugin. Only headless Linux source tests need a fallback.
if sys.platform == "linux" and not os.environ.get("DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class Q06ExistingFusionUiContract(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("PySide6") is not None,
                         "Native Qt GUI is verified on macOS/Windows and Linux desktop runners")
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
                ("Overview","Receive","History","Send","Security","Settings"))
            self.assertIs(window.stack.widget(0),window.overview)
            self.assertIs(window.stack.widget(1),window.receive_page)
            self.assertIs(window.stack.widget(2),window.history_page)
            self.assertFalse(window.overview.go_send.isEnabled())
            self.assertFalse(window.send.isEnabled())
            window.navigation.setCurrentRow(3)
            self.assertEqual(window.page_title.text(),"Send")
            window.navigation.setCurrentRow(0)
            self.assertEqual(window.page_title.text(),"Overview")
            # Native workspace keeps developer-only actions out of the
            # primary navigation, while preserving original Core controls.
            window.navigation.setCurrentRow(5)
            self.assertEqual(window.page_title.text(),"Settings")
            self.assertFalse(window.advanced_container.isVisible())
            self.assertIs(window.fund.parent(), window.advanced_container)
            self.assertTrue(all(
                not window.navigation.item(i).icon().isNull()
                for i in range(window.navigation.count())))
            self.assertEqual(window.appearance_group.checkedId(),0)
            window.appearance_buttons[2].click()
            self.assertEqual(window.appearance_group.checkedId(),2)
            window.reduce_motion.setChecked(True)
            window.navigation.setCurrentRow(0)
            self.assertTrue(window.reduce_motion.isChecked())
        finally:
            window._poll.stop()
            window.hide()
            window.deleteLater()
            app.processEvents()

    def test_normal_launch_routes_to_fusion_not_old_developer_trial(self):
        # Static contract on Qt-less native runners; this never imports
        # PySide6. Actual live Fusion widgets remain required on GUI runners.
        path=Path(__file__).resolve().parents[1]/"src"/"wam_regtest"/"bip39_owner_gui.py"
        source=path.read_text(encoding="utf8")
        module=ast.parse(source,filename=str(path))
        entry=next((n for n in module.body
                    if isinstance(n,ast.FunctionDef) and n.name=="launch_bip39_trial"),None)
        self.assertIsNotNone(entry)
        body=ast.get_source_segment(source,entry)
        self.assertIn("Bip39FusionWindow(executor)",body)
        self.assertNotIn("window=Bip39TrialWindow(executor)",body)


if __name__=="__main__":
    unittest.main()
