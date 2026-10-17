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

    def test_verify_wallet_requires_opt_in_resources_and_ready_supervisor(self):
        self.win._apply_managed_status(public_status(
            state="ready",owned=True,chain_height=101))
        self.assertFalse(self.win.verify_wallet_button.isEnabled())
        self.win._wallet_core_dir=Path.cwd()/"pinned-core"
        self.win._wallet_wsp_source=Path.cwd()/"pinned-wsp"
        self.win._update_controls()
        self.assertTrue(self.win.verify_wallet_button.isEnabled())
        with patch("wam_regtest.managed_gui.QInputDialog.getText",
                   return_value=("test-only-regtest-password",False)) as dialog:
            self.win.verify_wallet_button.click()
            self.assertEqual(dialog.call_count,1)
            self.assertIsNone(self.win._worker)
        self.win._managed_denied("untrusted")
        self.assertFalse(self.win.verify_wallet_button.isEnabled())
        self.assertFalse(self.win._wallet_checkpoint_verified)

    def test_locked_wallet_verification_never_grants_balance_or_spending(self):
        proof={
            "status":"MANAGED_WALLET_ORIGINAL_CHECKPOINT_VERIFIED_LOCKED",
            "network":"regtest","wallet_locked":True,
            "signer_allowed":False,"broadcast_allowed":False,
            "balance_verified":False,"original_native_anchor_verified":True,
            "original_encrypted_checkpoint_verified":True,
            "mainnet_allowed":False,"supervisor_authenticated":True,
            "supervisor_core_identity_verified":True,
        }
        self.win._apply_managed_status(public_status(
            state="ready",owned=True,chain_height=101))
        self.win._apply_wallet_preflight(proof)
        self.assertTrue(self.win._wallet_checkpoint_verified)
        self.assertIn("WALLET STILL LOCKED",self.win.status.text())
        self.assertIsNone(self.win.session)
        self.assertIsNone(self.win._snapshot)
        self.assertFalse(self.win.dashboard.go_send.isEnabled())
        for mutation in ({"signer_allowed":True},{"balance_verified":True},
                         {"mainnet_allowed":True},{"wallet_locked":False}):
            with self.subTest(mutation=mutation):
                self.win._apply_wallet_preflight({**proof,**mutation})
                self.assertFalse(self.win._wallet_checkpoint_verified)
                self.assertNotIn("WALLET STILL LOCKED",self.win.status.text())
                self.assertFalse(self.win.dashboard.go_send.isEnabled())
        self.win._apply_wallet_preflight(proof)
        self.win._apply_managed_status(public_status(
            state="busy",owned=True))
        self.assertFalse(self.win._wallet_checkpoint_verified)

    def test_native_worker_verifies_original_checkpoint_only_with_manual_password(self):
        import time
        from PySide6.QtWidgets import QLineEdit
        from PySide6.QtCore import QCoreApplication,QEvent
        from wam_regtest.managed_wallet_binding import verify_locked_wallet
        self.win._wallet_core_dir=Path.cwd()/"pinned-core"
        self.win._wallet_wsp_source=Path.cwd()/"pinned-wsp"
        self.win._apply_managed_status(public_status(
            state="ready",owned=True,chain_height=101))
        proof={
            "status":"MANAGED_WALLET_ORIGINAL_CHECKPOINT_VERIFIED_LOCKED",
            "network":"regtest","wallet_locked":True,
            "signer_allowed":False,"broadcast_allowed":False,
            "balance_verified":False,"original_native_anchor_verified":True,
            "original_encrypted_checkpoint_verified":True,
            "mainnet_allowed":False,"supervisor_authenticated":True,
            "supervisor_core_identity_verified":True,
        }
        with (patch("wam_regtest.managed_gui.QInputDialog.getText",
                    return_value=("public-regtest-password",True)),
              patch("wam_regtest.managed_wallet_binding.verify_locked_wallet",
                    return_value=proof) as locked):
            self.win.verify_wallet_button.click()
            self.assertIsNotNone(self.win._worker)
            self.assertFalse(self.win.close())
            deadline=time.monotonic()+5
            while self.win._worker is not None and time.monotonic()<deadline:
                self.app.processEvents()
                time.sleep(.005)
            self.assertIsNone(self.win._worker)
            QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
            self.assertTrue(self.win._wallet_checkpoint_verified)
            self.assertEqual(locked.call_count,1)
            self.assertEqual(locked.call_args.kwargs,{"authorized":True})
        self.assertIsNone(self.win.session)
        self.assertIsNone(self.win._snapshot)
        self.assertFalse(self.win.dashboard.go_send.isEnabled())

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

    def test_password_dialog_cannot_start_background_worker_or_allow_window_close(self):
        import threading
        import time
        from PySide6.QtCore import QEventLoop,QTimer
        released=threading.Event();workers=[];observed=[]
        self.win._wallet_core_dir=Path.cwd()/"pinned-core"
        self.win._wallet_wsp_source=Path.cwd()/"pinned-wsp"
        self.win._apply_managed_status(public_status(state="ready",owned=True,chain_height=101))
        def status(*args,**kwargs):
            released.wait(3)
            return public_status(state="ready",owned=True,chain_height=101)
        def dialog(*args,**kwargs):
            loop=QEventLoop()
            def tick():
                self.win.request_sync()  # Actual Qt delivery inside nested dialog loop.
                if self.win._worker is not None:workers.append(self.win._worker)
                observed.append(self.win._worker is None)
                observed.append(not self.win.close())
                loop.quit()
            QTimer.singleShot(0,tick)
            loop.exec()
            return "",False
        try:
            with (patch("wam_regtest.managed_gui.control",side_effect=status),
                  patch("wam_regtest.managed_gui.QInputDialog.getText",side_effect=dialog)):
                self.win._verify_wallet()
                self.assertEqual(observed,[True,True])
        finally:
            released.set()
            for worker in workers:self.assertTrue(worker.wait(5000))
            deadline=time.monotonic()+3
            while self.win._worker is not None and time.monotonic()<deadline:
                self.app.processEvents();time.sleep(.005)

    def test_stop_confirmation_suspends_background_sync_and_always_restores_guard(self):
        self.win._apply_managed_status(public_status(state="ready",owned=True,chain_height=101))
        def confirm(*args,**kwargs):
            self.win.request_sync()
            return QMessageBox.StandardButton.No
        try:
            with (patch("wam_regtest.managed_gui.QMessageBox.question",side_effect=confirm),
                  patch("wam_regtest.managed_gui._ManagedStatusWorker") as worker):
                self.win._confirm_stop()
                worker.assert_not_called()
        finally:
            # A failing old implementation may have assigned the mock worker.
            # It is never a real thread; keep the failure's cleanup independent.
            self.win._worker=None
        self.assertFalse(self.win._managed_dialog_open)
        self.assertTrue(self.win.refresh_button.isEnabled())

    def test_password_dialog_failure_clears_guard_and_stale_state_never_starts_verification(self):
        self.win._wallet_core_dir=Path.cwd()/"pinned-core"
        self.win._wallet_wsp_source=Path.cwd()/"pinned-wsp"
        self.win._apply_managed_status(public_status(state="ready",owned=True,chain_height=101))
        with patch("wam_regtest.managed_gui.QInputDialog.getText",side_effect=RuntimeError("fixture")):
            with self.assertRaises(RuntimeError):self.win._verify_wallet()
        self.assertFalse(self.win._managed_dialog_open)
        def changed(*args,**kwargs):
            self.win._managed_denied("fixture-state-changed")
            return "public-regtest-password",True
        with (patch("wam_regtest.managed_gui.QInputDialog.getText",side_effect=changed),
              patch("wam_regtest.managed_gui._LockedWalletWorker") as worker):
            self.win._verify_wallet()
            worker.assert_not_called()
        self.assertIsNone(self.win._worker)

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
