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


class ApprovalWorkerOrdering(unittest.TestCase):
    """Real Qt event delivery; synthetic backend is NOT Core acceptance."""

    def test_gui_wait_deadline_retains_original_future_without_resubmission(self):
        from concurrent.futures import Future
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        from PySide6.QtTest import QTest
        from wam_regtest.managed_gui import ControlWorker
        app = QApplication.instance() or QApplication([])
        future = Future()
        calls = []
        class Executor:
            def submit(self, action, *args, **kwargs):
                calls.append(action)
                return future
        worker = ControlWorker(Executor(), 'snapshot', kwargs={'timeout':0.01})
        ready, denied, pending = [], [], []
        worker.ready.connect(lambda action, result: ready.append(result))
        worker.denied.connect(denied.append)
        worker.pending.connect(pending.append)
        QTimer.singleShot(80, lambda: future.set_result('original-result'))
        worker.start()
        for _ in range(100):
            app.processEvents()
            if ready:
                break
            QTest.qWait(10)
        self.assertTrue(worker.wait(1000))
        self.assertEqual(calls, ['snapshot'])
        self.assertEqual(ready, ['original-result'])
        self.assertEqual(denied, [])
        self.assertEqual(pending, ['WALLET_EXECUTOR_OPERATION_STILL_PENDING'])

    def test_delayed_modal_approval_signs_once_after_prepare_worker_finishes(self):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QDialog
        from unittest.mock import patch
        from wam_regtest.bip39_fusion_gui import Bip39FusionWindow
        from wam_regtest.wallet_executor import WalletExecutor
        from wam_regtest.wallet_session import PaymentReview
        app = QApplication.instance() or QApplication([])
        calls = []
        review = PaymentReview("wamrtsp1public", 300000000, 10000,
                               4449980000, 1, "a" * 64)
        class Backend:
            def public_state(self):
                return dict(locked=False, faulted=False, core_alive=False)
            def execute(self, action, args, kwargs):
                calls.append(action)
                return review if action in ("prepare", "sign") else None
        executor = WalletExecutor(Backend)
        window = Bip39FusionWindow(executor)
        window._ready = window._spend_enabled = True
        class DelayedApproval(QDialog):
            def __init__(self, *args):
                super().__init__(window)
                # Allow the prepare thread's finished signal to be delivered
                # inside the real nested modal event loop before approval.
                QTimer.singleShot(80, self.accept)
        try:
            with patch("wam_regtest.bip39_fusion_gui.PaymentApproval", DelayedApproval):
                self.assertTrue(window._command("prepare", "unused", 1, 1))
                from PySide6.QtTest import QTest
                for _ in range(200):
                    app.processEvents()
                    if window._signed_ready:
                        break
                    QTest.qWait(10)
            self.assertEqual(calls, ["prepare", "sign"])
            self.assertTrue(window.broadcast.isEnabled())
            self.assertFalse(window.cancel.isEnabled())
        finally:
            window._poll.stop()
            executor.request("quit")
            executor.join()
            window.hide()
            window.deleteLater()
            app.processEvents()


if __name__=="__main__":
    unittest.main()
