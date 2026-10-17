"""Fusion managed-Core widget contracts. Not Q05 real-Core/frozen evidence."""
from pathlib import Path
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox
from wam_regtest.desktop import qt_application
from wam_regtest.managed_gui import ManagedCoreWindow, VISIBLE_STATES
from wam_regtest.supervisor_protocol import public_status


class ManagedFusionWidgetContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = qt_application()

    def setUp(self):
        self.win = ManagedCoreWindow(Path("/tmp/wam-fusion-core-0123456789abcdef")
            if __import__("sys").platform!="win32" else Path("C:/wam-fusion-core-0123456789abcdef"))
        # Deterministically dispose native Qt windows before the interpreter
        # tears down QApplication. Merely closing leaves a QMainWindow object
        # and its native signal connections alive until Python GC at exit.
        self.addCleanup(self._dispose_window)
        # Constructing a GUI cannot start, stop or connect to an unverified Core.
        self.assertEqual(self.win._managed_state, "error")
        self.assertIsNone(self.win.session)
        self.assertIsNone(self.win._snapshot)
        self.assertFalse(self.win.start_core.isEnabled())
        self.assertFalse(self.win.stop_core.isEnabled())

    def _dispose_window(self):
        import gc
        from shiboken6 import delete, isValid
        if self.win is not None:
            window=self.win
            self.assertTrue(window.close())
            # deleteLater() alone depends on the event loop and has left
            # native Qt wrappers alive at Python interpreter finalization.
            delete(window)
            self.assertFalse(isValid(window))
            self.win=None
            del window
            gc.collect()
            self.app.processEvents()

    def test_all_allowed_supervisor_states_are_rendered_without_wallet_adoption(self):
        for state in VISIBLE_STATES:
            with self.subTest(state=state):
                running = state in ("ready","syncing","busy")
                height = 103 if running else None
                result = public_status(state=state,owned=running,chain_height=height)
                self.win._apply_managed_status(result)
                self.assertEqual(self.win._managed_state,state)
                self.assertIn(VISIBLE_STATES[state],self.win.status.text())
                self.assertIsNone(self.win._snapshot)
                self.assertFalse(self.win.dashboard.go_send.isEnabled())
                self.assertFalse(self.win.stop_core.isEnabled() if not running else self.win.start_core.isEnabled())

    def test_wrong_network_and_fabricated_ready_are_rejected_before_wallet(self):
        good = public_status(state="ready",owned=True,chain_height=105)
        for update in ({"chain":"mainnet"},{"mainnet_allowed":True},
                       {"core_process_owned":False},{"height":None},
                       {"height":-1},{"state":"unknown"}):
            with self.subTest(update=update):
                self.win._apply_managed_status({**good,**update})
                self.assertFalse(self.win._managed_authenticated)
                self.assertIsNone(self.win._snapshot)
                self.assertIn("RECOVERY NEEDED",self.win.status.text())

    def test_close_does_not_invoke_core_shutdown_or_create_wallet(self):
        self.win._apply_managed_status(public_status(state="ready",owned=True,chain_height=101))
        with patch("wam_regtest.managed_gui.control",side_effect=AssertionError("Core touched")):
            self.assertTrue(self.win.close())
        self.assertEqual(self.win._managed_state,"ready")

    def test_stop_requires_explicit_confirmation(self):
        self.win._apply_managed_status(public_status(state="ready",owned=True,chain_height=101))
        with patch.object(QMessageBox,"question",return_value=QMessageBox.StandardButton.No):
            with patch.object(self.win,"_execute",side_effect=AssertionError("unapproved stop")):
                self.win._confirm_stop()

    def test_no_start_on_unverified_status(self):
        with patch.object(self.win,"_execute") as command:
            self.win._managed_denied("never display secret")
            self.win.start_core.click()
            command.assert_not_called()
