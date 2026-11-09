"""Recoverable native onboarding; no backend/Core/seed creation in negatives."""
import unittest
import importlib.util
from pathlib import Path
from unittest.mock import patch
QT_AVAILABLE = importlib.util.find_spec("PySide6") is not None
if QT_AVAILABLE:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QDialog
from wam_regtest import managed_onboarding as onboarding


@unittest.skipUnless(QT_AVAILABLE, "Requires native Qt-capable runner")
class OnboardingRecovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_folder_cancel_returns_to_real_welcome_without_launch(self):
        dialogs = []
        original = onboarding.welcome_dialog
        def welcome():
            dialog = original()
            dialogs.append(dialog)
            QTimer.singleShot(0, dialog.buttons['create'].click if len(dialogs)==1 else dialog.reject)
            return dialog
        with patch.object(onboarding,'welcome_dialog',side_effect=welcome), \
                patch('PySide6.QtWidgets.QFileDialog.getExistingDirectory',return_value=''), \
                patch('wam_regtest.bip39_owner_gui.launch_bip39_trial') as launch:
            self.assertEqual(onboarding.launch(Path('/unused-core'),Path('/unused-wsp')),0)
        self.assertEqual(len(dialogs),2)
        launch.assert_not_called()

    def test_bad_password_and_confirmation_are_recoverable(self):
        from wam_regtest import bip39_owner_gui as gui
        responses=[('short',True),('public-valid-disposable',True),
                   ('different-disposable',True),('public-valid-disposable',True),
                   ('public-valid-disposable',True)]
        with patch.object(gui.QInputDialog,'getText',side_effect=responses), \
                patch.object(gui.QMessageBox,'warning') as warning:
            password,ok=gui._onboarding_password(None,'create')
        self.assertTrue(ok)
        self.assertEqual(password,'public-valid-disposable')
        self.assertEqual(warning.call_count,2)

    def test_cancel_password_and_reopen_do_not_require_new_confirmation(self):
        from wam_regtest import bip39_owner_gui as gui
        for response in [('',False),('public-valid-disposable',True)]:
            with patch.object(gui.QInputDialog,'getText',return_value=response) as prompt:
                self.assertEqual(gui._onboarding_password(None,'reopen'),response)
                self.assertEqual(prompt.call_count,1)

    def test_expanded_legacy_buttons_remain_inside_their_panels(self):
        dialog=onboarding.welcome_dialog()
        dialog.resize(540,550);dialog.show();self.app.processEvents()
        dialog.legacy_toggle.click();self.app.processEvents()
        try:
            for button in dialog.buttons.values():
                self.assertTrue(button.parentWidget().rect().contains(button.geometry()))
                self.assertGreaterEqual(button.height(),button.minimumSizeHint().height())
        finally:
            dialog.close();dialog.deleteLater();self.app.processEvents()

    def test_chart_endpoint_label_and_dot_stay_inside_native_paint_bounds(self):
        from wam_regtest.fusion_ui import BalanceHistoryChart
        chart=BalanceHistoryChart();chart.resize(300,130)
        chart.render_points(((1,0),(12345678,100)))
        x,y,height,atoms=chart._mapped(chart.width(),chart.height())[-1]
        self.assertLessEqual(x+4.2,chart.width())
        self.assertTrue(chart.rect().contains(chart._height_rect(x,height).toAlignedRect()))
        chart.deleteLater()

    def test_review_long_recipient_wraps_without_changing_exact_tooltip(self):
        from types import SimpleNamespace
        from wam_regtest.wallet_executor import ExecutorState
        from wam_regtest.bip39_fusion_gui import Bip39FusionWindow
        window=Bip39FusionWindow(SimpleNamespace(state=ExecutorState(),busy=False,closed=False))
        try:
            text='Recipient: '+('wamrtsp1'+'q'*114)+'\nFee: 0.00000001 WAM'
            window.review_summary.setText(text)
            self.assertEqual(window.review_summary.toolTip(),text)
            self.assertEqual(window.review_summary.text().replace('\u200b',''),text)
            self.assertIn('\u200b',window.review_summary.text())
        finally:
            window._poll.stop();window.hide();window.deleteLater();self.app.processEvents()

    def test_real_modal_password_recovery_positive_and_negative(self):
        from wam_regtest.onboarding_probe import qualify_password_dialogs
        result=qualify_password_dialogs()
        self.assertTrue(result['invalid_length_recovered'])
        self.assertTrue(result['confirmation_mismatch_recovered'])
        self.assertFalse(result['backend_created'])
