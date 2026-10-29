"""Real Qt events with a fake backend: thread/closure proof, NOT Core E2E."""
from pathlib import Path
import threading
import os
import importlib.util
import time
import unittest

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
    def public_state(self):return dict(locked=self.locked,faulted=False,core_alive=self.alive)
    def execute(self,action,args,kwargs):
        self.calls.append((action,threading.get_ident()))
        if action in ('open','unlock'):self.locked=False
        if action=='lock':self.locked=True;return None
        if action=='quit':self.locked=True;self.alive=False;return None
        if action=='network':
            self.entered.set();self.release.wait(3);return {'network':'regtest'}
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
            if created:created[0].release.set()
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
