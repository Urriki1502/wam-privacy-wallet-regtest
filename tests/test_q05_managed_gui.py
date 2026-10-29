"""Real Qt events with a fake backend: thread/closure proof, NOT Core E2E."""
from pathlib import Path
import threading
import os
import importlib.util
import time
import tempfile
import json
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
HAVE_QT=importlib.util.find_spec('PySide6') is not None
if HAVE_QT:
    from PySide6.QtCore import QTimer
    from wam_regtest.desktop import qt_application
    from wam_regtest.managed_gui import ManagedWalletWindow
from wam_regtest.wallet_executor import ManagedWalletProxy,WalletExecutor
from wam_regtest.wallet_read import WalletReadSnapshot


class Backend:
    def __init__(self):
        self.thread=threading.get_ident();self.calls=[];self.locked=True;self.alive=True
        self.entered=threading.Event();self.release=threading.Event()
        self.fail_network=self.fail_quit=False;self.funding_failure=None
    def public_state(self):return dict(locked=self.locked,faulted=False,core_alive=self.alive)
    def execute(self,action,args,kwargs):
        self.calls.append((action,threading.get_ident()))
        if action in ('open','unlock'):self.locked=False
        if action=='lock':self.locked=True;return None
        if action=='quit':
            if self.fail_quit:raise ValueError('MANAGED_SHUTDOWN_UNCERTAIN')
            self.locked=True;self.alive=False;return None
        if action=='network':
            self.entered.set();self.release.wait(3)
            if self.fail_network:raise ValueError('FIXTURE_NETWORK_REFUSED')
            return {'network':'regtest'}
        return WalletReadSnapshot('regtest',0,'a'*64,'',0,0,(),'b'*64,
            signer_allowed=True,broadcast_allowed=True,history_count=0,receive_count=0)


@unittest.skipUnless(HAVE_QT,'Requires the Qt test profile; headless contracts do not qualify GUI')
class ManagedGuiContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=qt_application();cls.app.setQuitOnLastWindowClosed(False)

    def wait(self,condition,timeout=4):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            self.app.processEvents()
            if condition():return
            time.sleep(.002)
        self.fail('Qt condition did not complete')

    def fixture(self):
        created=[]
        def factory():backend=Backend();created.append(backend);return backend
        executor=WalletExecutor(factory)
        root=Path('/unused/wam-fusion-core-0123456789abcdef')
        proxy=ManagedWalletProxy(executor,root,root/'core',root/'wsp')
        window=ManagedWalletWindow(proxy);window.background_available=True;window.show()
        def close():
            if created:created[0].release.set();created[0].fail_quit=False
            window._executor_poll.stop();window._theme_timer.stop();window._sync_timer.stop()
            self.wait(lambda:window._worker is None and not executor.busy)
            if not executor.closed:executor.request('quit')
            self.assertTrue(executor.join());window.hide();window.deleteLater();self.app.processEvents()
        self.addCleanup(close)
        return executor,window,created

    def test_snapshot_reaches_ui_while_all_wallet_work_stays_on_owner_thread(self):
        executor,window,created=self.fixture();received=[]
        window.snapshot_updated.connect(lambda _:received.append(threading.get_ident()))
        window.open_wallet(b'public-disposable-password',create=True)
        self.wait(lambda:window._worker is None and window._snapshot is not None)
        window.request_sync();self.wait(lambda:window._worker is None and len(received)>=2)
        self.assertEqual(set(received),{threading.get_ident()})
        self.assertEqual({t for _,t in created[0].calls},{created[0].thread})
        self.assertNotEqual(created[0].thread,threading.get_ident())
        self.assertFalse(executor.closed)

    def test_close_during_operation_keeps_qt_responsive_then_locks_without_core_stop(self):
        executor,window,created=self.fixture();window.open_wallet(b'public-disposable-password')
        self.wait(lambda:window._worker is None and not window.session.locked)
        pulses=[];timer=QTimer();timer.setInterval(1);timer.timeout.connect(lambda:pulses.append(1));timer.start()
        self.addCleanup(timer.stop)
        window.start_operation('network')
        self.wait(created[0].entered.is_set);window.close()
        end=time.monotonic()+.04
        while time.monotonic()<end:self.app.processEvents();time.sleep(.001)
        self.assertGreater(len(pulses),2);self.assertTrue(window.isVisible())
        self.assertTrue(created[0].alive);self.assertFalse(executor.closed)
        created[0].release.set()
        self.wait(lambda:not window.isVisible() and window.session.locked and window._worker is None)
        self.assertTrue(created[0].alive);self.assertFalse(executor.closed)
        window.reopen();self.assertTrue(window.isVisible())
        self.assertNotIn('quit',[a for a,_ in created[0].calls])

    def test_history_page_requests_use_executor_not_a_live_session_on_qthread(self):
        _,window,created=self.fixture();window.open_wallet(b'public-disposable-password')
        self.wait(lambda:window._worker is None and window._snapshot is not None)
        window._history_page(250);self.wait(lambda:window._worker is None)
        self.assertTrue(any(a=='snapshot' for a,_ in created[0].calls))
        self.assertEqual({t for _,t in created[0].calls},{created[0].thread})

    def test_authenticated_external_release_closes_qt_after_owner_has_exited(self):
        executor,window,_=self.fixture();executor.request('core_status')
        observed=[]
        window.owner_closed.connect(lambda:observed.append((executor.closed,executor.state.core_alive)))
        with patch.object(type(self.app),'quit') as quit_app:
            window._poll_owner();quit_app.assert_not_called()
            self.assertEqual(observed,[])
            executor.request('quit');self.assertTrue(executor.join())
            self.assertFalse(window._quit_completed)
            window._poll_owner();quit_app.assert_called_once_with()
            self.assertEqual(observed,[(True,False)])

    def test_core_restart_requires_explicit_operator_consent(self):
        from PySide6.QtWidgets import QMessageBox
        executor,window,created=self.fixture();executor.request('core_status')
        before=list(created[0].calls)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.No):
            self.assertFalse(window.request_core_restart())
        self.assertEqual(created[0].calls,before)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):
            self.assertTrue(window.request_core_restart())
        self.wait(lambda:window._worker is None and not executor.busy)
        self.assertEqual(created[0].calls[-1],('core_restart',created[0].thread))

    def test_qualification_dialog_fallback_never_selects_a_foreign_window(self):
        from PySide6.QtWidgets import QApplication,QInputDialog
        from wam_regtest.q05_gui_scenario import _owned_dialog
        _,window,_=self.fixture()
        dialog=QInputDialog(window);foreign=QInputDialog()
        try:
            dialog.show();foreign.show();self.app.processEvents()
            with patch.object(QApplication,'activeModalWidget',return_value=foreign):
                self.assertIs(_owned_dialog(window,QInputDialog),dialog)
                dialog.hide();self.assertIsNone(_owned_dialog(window,QInputDialog))
        finally:
            dialog.hide();foreign.hide();dialog.deleteLater();foreign.deleteLater()

    def test_closed_owner_window_accepts_final_qt_cleanup_without_quit_recursion(self):
        executor,window,_=self.fixture();executor.request('quit');self.assertTrue(executor.join())
        window._executor_poll.stop()
        with patch.object(type(self.app),'quit') as quit_app:
            self.assertTrue(window.close());self.assertFalse(window.isVisible())
            quit_app.assert_not_called();self.assertFalse(window._close_requested)

    def test_failed_funding_driver_publishes_fail_then_closes_verified_owner(self):
        from wam_regtest.q05_gui_scenario import Driver
        executor,window,created=self.fixture();window.open_wallet(b'public-disposable-password')
        self.wait(lambda:window._worker is None and not window.session.locked)
        backend=created[0];backend.fail_network=True;backend.release.set()
        with tempfile.TemporaryDirectory() as temp:
            receipt=Path(temp)/'failure.json';record={'observations':[]}
            driver=Driver(window,created,record,60,None,receipt);driver.stage='funding'
            self.addCleanup(driver.timer.stop)
            with patch.object(type(self.app),'quit'):
                window.start_operation('network')
                self.wait(lambda:executor.closed and executor.join(0))
            self.assertEqual(json.loads(receipt.read_text())['failure_stage'],'funding')
            self.assertEqual(record['status'],'FAIL');self.assertEqual(driver.stage,'failed')
            self.assertFalse(backend.alive)
            self.assertEqual([a for a,_ in backend.calls].count('quit'),1)

    def test_failed_shutdown_retains_owner_and_does_not_automatically_retry(self):
        executor,window,created=self.fixture();executor.request('core_status')
        backend=created[0];backend.fail_quit=True
        with patch.object(type(self.app),'quit') as quit_app:
            window.request_quit();self.wait(lambda:window._worker is None and not executor.busy)
            for _ in range(3):window._poll_owner();self.app.processEvents()
            quit_app.assert_not_called()
        self.assertFalse(executor.closed);self.assertFalse(executor.join(0))
        self.assertTrue(backend.alive);self.assertFalse(window._quit_requested)
        self.assertEqual([a for a,_ in backend.calls].count('quit'),1)
