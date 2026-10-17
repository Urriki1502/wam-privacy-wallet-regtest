"""Fusion managed-Core widget contracts. Not Q05 real-Core/frozen evidence."""
from pathlib import Path
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox
from wam_regtest.desktop import qt_application
from wam_regtest.managed_gui import ManagedCoreWindow, VISIBLE_STATES
from wam_regtest.supervisor_protocol import public_status


class ManagedFusionWidgetContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The native unittest runner calls shutdown_qt() after ALL suites,
        # before Python interpreter teardown. No atexit QApplication work.
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

    def test_hidden_panels_already_belong_to_window(self):
        # A never-shown window must own every responsive panel immediately;
        # waiting for resizeEvent leaves native widgets outside its lifetime.
        from wam_regtest.fusion_ui import ResponsiveRow
        for row in self.win.findChildren(ResponsiveRow):
            for child in row._children:
                self.assertIs(child.parentWidget(), row)
                self.assertIs(child.window(), self.win)
        self.assertIs(self.win.dashboard.hero.window(), self.win)
        self.assertIs(self.win.receive_page.qr.window(), self.win)

    def test_close_waits_for_worker_then_stops_window_timers(self):
        import threading
        import time
        from PySide6.QtCore import QCoreApplication, QEvent
        from shiboken6 import isValid
        started, release = threading.Event(), threading.Event()
        def status(*args, **kwargs):
            started.set()
            if not release.wait(5):
                raise AssertionError("test worker was not released")
            return public_status(state="ready", owned=True, chain_height=101)
        # Supplemental lifetime fixture only. Genuine Core/IPC acceptance is
        # separately required by issue45_t05_real_core.py --qt-e2e.
        with patch("wam_regtest.managed_gui.control", side_effect=status):
            self.win.request_sync()
            worker = self.win._worker
            try:
                self.assertTrue(started.wait(3))
                self.assertFalse(self.win.close())
                self.assertTrue(worker.isRunning())
                self.assertTrue(self.win._sync_timer.isActive())
            finally:
                release.set()
                self.assertTrue(worker.wait(5000))
            deadline = time.monotonic() + 3
            while self.win._worker is not None and time.monotonic() < deadline:
                self.app.processEvents()
            self.assertIsNone(self.win._worker)
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            self.assertFalse(isValid(worker))
        self.assertTrue(self.win.close())
        self.assertFalse(self.win._sync_timer.isActive())
        self.assertFalse(self.win._theme_timer.isActive())
        self.assertFalse(self.win._appearance_connected)


class NativeQtLifetime(unittest.TestCase):
    def test_repeated_hidden_and_visible_gui_destruction_and_clean_process_exit(self):
        program = r'''
from pathlib import Path
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import delete, isValid
from wam_regtest.desktop import qt_application, shutdown_qt
from wam_regtest.managed_gui import ManagedCoreWindow
app = qt_application()
root = Path("C:/wam-fusion-core-0123456789abcdef" if __import__("sys").platform == "win32"
            else "/tmp/wam-fusion-core-0123456789abcdef")
for visible in (False, True) * 6:
    window = ManagedCoreWindow(root)
    assert qt_application() is app and QApplication.instance() is app
    assert window.dashboard.hero.window() is window
    assert window.receive_page.qr.window() is window
    if visible:
        window.show()
        app.processEvents()
        window.resize(900, 680)
        app.processEvents()
    children = window.findChildren(QWidget)
    assert window.close()
    assert not window._sync_timer.isActive() and not window._theme_timer.isActive()
    delete(window)
    assert not isValid(window) and all(not isValid(child) for child in children)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
assert not QApplication.topLevelWidgets()
shutdown_qt()
assert not isValid(app) and QApplication.instance() is None
shutdown_qt()  # idempotent: no second native destruction
print("QT_LIFETIME_AND_SHUTDOWN_PASS", flush=True)
'''
        result = subprocess.run([sys.executable, "-X", "faulthandler", "-c", program],
                                env=os.environ.copy(), capture_output=True,
                                text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr[-5000:])
        self.assertIn("QT_LIFETIME_AND_SHUTDOWN_PASS", result.stdout)
