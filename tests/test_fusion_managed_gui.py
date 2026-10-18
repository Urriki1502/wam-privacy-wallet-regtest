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

    def test_t07_busy_state_increases_refresh_interval_without_unlocking_wallet(self):
        ready=public_status(state="ready",owned=True,chain_height=101)
        busy=public_status(state="busy",owned=True)
        self.win._apply_managed_status(ready)
        self.assertEqual(self.win._sync_timer.interval(),5_000)
        self.win._apply_managed_status(busy)
        self.assertEqual(self.win._sync_timer.interval(),15_000)
        self.assertIn("NODE BUSY",self.win.status.text())
        self.assertIn("RETRYING",self.win.status.text())
        self.assertFalse(self.win._wallet_checkpoint_verified)
        self.assertIsNone(self.win._snapshot)
        self.assertIsNone(self.win._managed_height)
        self.assertFalse(self.win.dashboard.go_send.isEnabled())
        self.win._apply_managed_status(ready)
        self.assertEqual(self.win._sync_timer.interval(),5_000)
        self.assertEqual(self.win._managed_height,101)

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


    def _original_wallet_fixture(self):
        from wam_sp.keystore import ScanAccount
        from wam_sp.core import pub
        from wam_regtest.wallet_read import WalletReadSnapshot,HistoryRow
        code=ScanAccount(0,1,pub(2),birthday=1).payment_code()
        return WalletReadSnapshot(
            chain="regtest",height=101,tip="b"*64,receive_code=code,
            confirmed_atoms=27000,confirmed_utxos=1,
            history=(HistoryRow("a"*64,101,1,27000,0),),
            core_sha256="c"*64,synthetic_rpc=False,demo_account_only=False,
            signer_allowed=False,broadcast_allowed=False,mainnet_allowed=False)

    def test_original_wallet_snapshot_never_adopted_without_manual_approval(self):
        snap=self._original_wallet_fixture()
        self.win._apply_managed_status(public_status(
            state="ready",owned=True,chain_height=101))
        self.win._apply_wallet_snapshot(snap)
        self.assertIsNone(self.win._snapshot)
        self.assertFalse(self.win.dashboard.go_send.isEnabled())
        self.assertIn("UNVERIFIED",self.win.status.text())
        self.assertFalse(self.win._wallet_read_authorized)

    def test_valid_original_wallet_renders_real_readonly_pages_no_spending(self):
        snap=self._original_wallet_fixture()
        self.win._apply_managed_status(public_status(
            state="ready",owned=True,chain_height=101))
        self.win._wallet_read_authorized=True
        self.win._apply_wallet_snapshot(snap)
        self.assertIs(self.win._snapshot,snap)
        self.assertTrue(self.win._wallet_checkpoint_verified)
        self.assertEqual(self.win.receive_page.code,snap.receive_code)
        self.assertIsNone(self.win.session)
        self.assertFalse(self.win.dashboard.go_send.isEnabled())
        self.assertIn("signing/broadcast DISABLED",self.win.status.text())
        self.assertEqual(self.win._sync_timer.interval(),30_000)
        # Any authenticated status refresh removes stale verified balances,
        # even when the observed block height is unchanged.
        self.win._apply_managed_status(public_status(
            state="ready",owned=True,chain_height=101))
        self.assertIsNone(self.win._snapshot)
        self.assertFalse(self.win._wallet_checkpoint_verified)
        self.assertFalse(self.win.dashboard.go_send.isEnabled())
        self.assertEqual(self.win._sync_timer.interval(),5_000)

    def test_reject_fabricated_demo_mainnet_signer_or_wrong_height(self):
        from dataclasses import replace
        snap=self._original_wallet_fixture()
        self.win._apply_managed_status(public_status(
            state="ready",owned=True,chain_height=101))
        cases=(
            {"demo_account_only":True},{"synthetic_rpc":True},
            {"signer_allowed":True},{"broadcast_allowed":True},
            {"mainnet_allowed":True},{"height":102},
            {"receive_code":"mainnet-wrong-address"},
            {"core_sha256":"unknown"},
        )
        for change in cases:
            with self.subTest(change=change):
                self.win._wallet_read_authorized=True
                self.win._apply_wallet_snapshot(replace(snap,**change))
                self.assertIsNone(self.win._snapshot)
                self.assertFalse(self.win._wallet_read_authorized)
                self.assertFalse(self.win.dashboard.go_send.isEnabled())
        # Never let the inherited public-demo path show any balance.
        from wam_regtest.wallet_read import WalletReadSnapshot
        self.win.apply_snapshot(replace(snap,demo_account_only=True))
        self.assertIsNone(self.win._snapshot)

    def test_native_manual_gui_wallet_scan_worker_and_clean_qthread_teardown(self):
        import time
        from PySide6.QtCore import QCoreApplication,QEvent
        from PySide6.QtWidgets import QLineEdit
        snap=self._original_wallet_fixture()
        self.win._wallet_core_dir=Path.cwd()/"pinned-core"
        self.win._wallet_wsp_source=Path.cwd()/"pinned-wsp"
        self.win._apply_managed_status(public_status(
            state="ready",owned=True,chain_height=101))
        self.assertTrue(self.win.view_wallet_button.isEnabled())
        with (patch("wam_regtest.managed_gui.QInputDialog.getText",
                    return_value=("public-test-only-regtest-password",True)) as dialog,
              patch("wam_regtest.managed_wallet_snapshot.read_managed_wallet_snapshot",
                    return_value=snap) as source):
            self.win.view_wallet_button.click()
            self.assertIsNotNone(self.win._worker)
            self.assertFalse(self.win.close())  # In-flight native QThread
            deadline=time.monotonic()+8
            while self.win._worker is not None and time.monotonic()<deadline:
                self.app.processEvents()
                time.sleep(.005)
            self.assertIsNone(self.win._worker)
            QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
            self.assertEqual(dialog.call_count,1)
            self.assertEqual(source.call_count,1)
            self.assertTrue(source.call_args.kwargs["authorized_readonly"])
            self.assertFalse(source.call_args.kwargs["authorized_persist_checkpoint"])
            self.assertIs(self.win._snapshot,snap)
            self.assertFalse(self.win.dashboard.go_send.isEnabled())
        self.assertTrue(self.win.close())

    def test_native_gui_wallet_scan_failure_redacts_secret_and_clears_balance(self):
        import time
        self.win._wallet_core_dir=Path.cwd()/"pinned-core"
        self.win._wallet_wsp_source=Path.cwd()/"pinned-wsp"
        self.win._apply_managed_status(public_status(
            state="ready",owned=True,chain_height=101))
        with (patch("wam_regtest.managed_gui.QInputDialog.getText",
                    return_value=("public-test-only-regtest-password",True)),
              patch("wam_regtest.managed_wallet_snapshot.read_managed_wallet_snapshot",
                    side_effect=ValueError("PRIVATE_SECRET_CANARY"))):
            self.win.view_wallet_button.click()
            deadline=time.monotonic()+8
            while self.win._worker is not None and time.monotonic()<deadline:
                self.app.processEvents()
                time.sleep(.005)
            self.assertIsNone(self.win._worker)
            self.assertIsNone(self.win._snapshot)
            self.assertFalse(self.win._wallet_checkpoint_verified)
            self.assertFalse(self.win.dashboard.go_send.isEnabled())
            self.assertNotIn("CANARY",self.win.status.text())
        self.assertTrue(self.win.close())


    def test_manual_create_original_wallet_and_explicit_read_only_gui_state(self):
        import time
        from PySide6.QtCore import QCoreApplication,QEvent
        proof={"status":"MANAGED_REGTEST_WSP_WALLET_CREATED_LOCKED",
               "network":"regtest","wallet_locked":True,
               "signer_allowed":False,"broadcast_allowed":False,
               "mainnet_allowed":False}
        self.win._wallet_core_dir=Path.cwd()/"pinned-core"
        self.win._wallet_wsp_source=Path.cwd()/"pinned-wsp"
        self.win._apply_managed_status(public_status(
            state="ready",owned=True,chain_height=101))
        self.assertTrue(self.win.create_wallet_button.isEnabled())
        with (patch.object(QMessageBox,"question",
                           return_value=QMessageBox.StandardButton.Yes),
              patch("wam_regtest.managed_gui.QInputDialog.getText",
                    side_effect=[("regtest-passphrase-only",True),
                                 ("regtest-passphrase-only",True)]),
              patch("wam_regtest.managed_wallet_create.create_managed_wallet",
                    return_value=proof) as create):
            self.win.create_wallet_button.click()
            self.assertIsNotNone(self.win._worker)
            deadline=time.monotonic()+6
            while self.win._worker is not None and time.monotonic()<deadline:
                self.app.processEvents()
                time.sleep(.005)
            self.assertIsNone(self.win._worker)
            QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
            create.assert_called_once()
            self.assertTrue(create.call_args.kwargs["authorized"])
            self.assertIsNone(self.win._snapshot)
            self.assertIsNone(self.win.session)
            self.assertFalse(self.win.dashboard.go_send.isEnabled())
            self.assertIn("CREATED AND ENCRYPTED",self.win.status.text())

    def test_create_mismatched_password_and_cancel_never_touch_custody(self):
        self.win._wallet_core_dir=Path.cwd()/"pinned-core"
        self.win._wallet_wsp_source=Path.cwd()/"pinned-wsp"
        self.win._apply_managed_status(public_status(
            state="ready",owned=True,chain_height=101))
        with patch("wam_regtest.managed_wallet_create.create_managed_wallet") as create:
            with patch.object(QMessageBox,"question",
                              return_value=QMessageBox.StandardButton.No):
                self.win.create_wallet_button.click()
            create.assert_not_called()
            with (patch.object(QMessageBox,"question",
                               return_value=QMessageBox.StandardButton.Yes),
                  patch("wam_regtest.managed_gui.QInputDialog.getText",
                        side_effect=[("regtest-one-password",True),
                                     ("regtest-other-password",True)])):
                self.win.create_wallet_button.click()
            create.assert_not_called()
        self.assertIsNone(self.win._snapshot)
        self.assertFalse(self.win.dashboard.go_send.isEnabled())

    def test_explicit_sync_saves_checkpoint_but_plain_view_does_not(self):
        import time
        from PySide6.QtCore import QCoreApplication,QEvent
        snap=self._original_wallet_fixture()
        self.win._wallet_core_dir=Path.cwd()/"pinned-core"
        self.win._wallet_wsp_source=Path.cwd()/"pinned-wsp"
        self.win._apply_managed_status(public_status(
            state="ready",owned=True,chain_height=101))
        for button,persist in ((self.win.view_wallet_button,False),
                               (self.win.sync_wallet_button,True)):
            with (patch("wam_regtest.managed_gui.QInputDialog.getText",
                        return_value=("regtest-passphrase-only",True)),
                  patch("wam_regtest.managed_wallet_snapshot.read_managed_wallet_snapshot",
                        return_value=snap) as reader):
                button.click()
                deadline=time.monotonic()+6
                while self.win._worker is not None and time.monotonic()<deadline:
                    self.app.processEvents()
                    time.sleep(.005)
                self.assertIsNone(self.win._worker)
                QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
                self.assertEqual(reader.call_count,1)
                self.assertIs(reader.call_args.kwargs["authorized_persist_checkpoint"],persist)
                self.assertIs(reader.call_args.kwargs["authorized_readonly"],True)
                self.assertIs(self.win._snapshot,snap)
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
