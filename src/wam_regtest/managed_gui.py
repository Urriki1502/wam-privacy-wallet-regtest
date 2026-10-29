"""Qt bridge to a persistent wallet owner thread; no live session on Qt workers."""
from PySide6.QtCore import QEvent,QObject,QThread,QTimer,Qt,Signal
from PySide6.QtWidgets import QInputDialog,QLineEdit,QMenu,QMessageBox,QSystemTrayIcon

from .operational_gui import OperationalWalletWindow,qt_application
from .wallet_executor import ManagedWalletBackend,ManagedWalletProxy,WalletExecutor
from .gui_errors import operation_error


class ControlWorker(QThread):
    ready=Signal(str,object)
    denied=Signal(str)
    def __init__(self,executor,action,args=(),kwargs=None,parent=None):
        super().__init__(parent)
        self.executor=executor;self.action=action;self.args=args;self.kwargs=kwargs or {}
    def run(self):
        try:self.ready.emit(self.action,self.executor.request(self.action,*self.args,**self.kwargs))
        except Exception as error:self.denied.emit(operation_error(self.action,error))
        finally:self.args=();self.kwargs={}


class QuitFilter(QObject):
    def __init__(self,window):super().__init__(window);self.window=window
    def eventFilter(self,watched,event):
        if event.type()==QEvent.Type.Quit and not self.window.session.executor.closed:
            self.window.request_quit();return True
        return False


class ManagedWalletWindow(OperationalWalletWindow):
    def __init__(self,proxy):
        if type(proxy) is not ManagedWalletProxy:raise ValueError('MANAGED_GUI_PROXY_REQUIRED')
        self._close_requested=self._quit_requested=self._quit_completed=False
        self._after_control=None;self.background_available=False
        super().__init__(proxy)
        self.setWindowTitle('WAM Fusion · Managed REGTEST')
        self.warning.setText('REGTEST ONLY · MANAGED CORE · NO REAL FUNDS')
        # Mining stays an explicit test/advanced tool, never normal onboarding.
        self.mine_button.hide()
        self.mine_notice.hide()
        self._executor_poll=QTimer(self);self._executor_poll.setInterval(100)
        self._executor_poll.timeout.connect(self._poll_owner);self._executor_poll.start()

    def _update_controls(self):
        super()._update_controls()
        if self.session.executor.busy or self._close_requested or self._quit_requested:
            for widget in getattr(self,'_actions',()):widget.setEnabled(False)
            for name in ('refresh_button','prepare_button','sign_button','broadcast_button',
                         'cancel_button','backup_button','lock_button','unlock_button','recover_button'):
                widget=getattr(self,name,None)
                if widget is not None:widget.setEnabled(False)

    def request_sync(self):
        if self.session.executor.busy:return
        super().request_sync()

    def _history_page(self,offset):
        if self.session.executor.busy:return
        super()._history_page(offset)

    def _control(self,action,*args,**kwargs):
        if self._worker is not None or self.session.executor.busy:return False
        worker=ControlWorker(self.session.executor,action,args,kwargs,self)
        self._worker=worker
        worker.ready.connect(self._control_ready,Qt.ConnectionType.QueuedConnection)
        worker.denied.connect(self._control_denied,Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(self._worker_finished)
        worker.finished.connect(worker.deleteLater)
        self._update_controls();worker.start();return True

    def open_wallet(self,password,*,create=False):
        return self._control('open',password,create=create)

    def _control_ready(self,action,result):
        if action=='open':
            self.apply_snapshot(result);self.status.setText('Managed wallet ready · REGTEST')
        elif action=='lock' and self._close_requested:
            self._close_requested=False
            self._clear_balance()
            if self.background_available:self.hide()
            else:self.showMinimized()  # Keep a reachable window if no tray exists.
        elif action=='quit':self._quit_completed=True
        elif action=='recovery_status':
            self._after_control=lambda:self._approve_recovery(result['pending_action'])
        elif action in ('recover','complete_recovery'):
            self._clear_balance();self.status.setText('Recovery completed · unlock to verify the live wallet')
        self._update_controls()

    def _control_denied(self,reason):
        self._close_requested=self._quit_requested=False;self._after_control=None
        self._operation_denied(reason)

    def _worker_finished(self):
        super()._worker_finished()
        if self._after_control is not None:
            after=self._after_control;self._after_control=None;QTimer.singleShot(0,after)
        self._poll_owner()

    def _poll_owner(self):
        self._update_controls()
        if self._worker is not None or self.session.executor.busy or self._approval_open:return
        if self._quit_completed or self.session.executor.closed:
            if self.session.executor.closed and self.session.executor.join(0):
                self._executor_poll.stop()
                from PySide6.QtWidgets import QApplication
                QApplication.instance().quit()
        elif self._quit_requested:self._control('quit')
        elif self._close_requested:self._control('lock')

    def closeEvent(self,event):
        event.ignore()
        self._close_requested=True
        self.status.setText('Locking wallet safely · managed Core stays running')
        self._poll_owner()

    def reopen(self):
        if self.session.executor.closed:return
        self._close_requested=False;self.showNormal();self.raise_();self.activateWindow()

    def request_quit(self):
        self._quit_requested=True;self._close_requested=False
        self.status.setText('Finishing wallet operation before explicit managed-Core shutdown')
        self._poll_owner()

    def recover_wallet(self):
        if self._worker is not None or self.session.executor.busy:return
        self._control('recovery_status')

    def _approve_recovery(self,action):
        self._approval_open=True
        try:
            text=('Complete the authenticated pending recovery transaction?' if action else
                  'Recover the current anchored wallet into a fresh container?\nExisting recovery data will be preserved.')
            if QMessageBox.question(self,'Managed wallet recovery',text,
                    QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
            password=self._passphrase('Authenticate the existing wallet checkpoint')
            if password is None:return
        finally:self._approval_open=False
        if action:self._control('complete_recovery',password,action)
        else:self._control('recover',password)


def launch_managed(root,core,source,*,authorized=False,create=False,keychain=None,
                   _backend_factory=None,_window_hook=None):
    if authorized is not True:raise ValueError('MANAGED_EXPLICIT_CONSENT_REQUIRED')
    app=qt_application();app.setQuitOnLastWindowClosed(False)
    factory=_backend_factory or (lambda:ManagedWalletBackend(root,core,source,keychain=keychain))
    executor=WalletExecutor(factory)
    proxy=ManagedWalletProxy(executor,root,core,source);window=ManagedWalletWindow(proxy)
    window._quit_filter=QuitFilter(window);app.installEventFilter(window._quit_filter)
    tray=None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray=QSystemTrayIcon(window.windowIcon(),window);menu=QMenu()
        menu.addAction('Open REGTEST wallet',window.reopen)
        menu.addAction('Stop managed Core and quit',window.request_quit)
        tray.setContextMenu(menu);tray.show();window.background_available=True
    window.show()
    if _window_hook is not None:_window_hook(window)
    while True:
        password,ok=QInputDialog.getText(window,'Managed REGTEST wallet',
            'Wallet passphrase (12+ characters)',QLineEdit.EchoMode.Password)
        if not ok or 12<=len(password.encode())<=1024:break
        QMessageBox.warning(window,'Wallet passphrase','Use a passphrase of 12–1024 bytes.')
    if ok:window.open_wallet(password.encode(),create=create)
    else:window.request_quit()
    password=''
    result=app.exec()
    # A normal Qt quit must have positive owner shutdown. An unexpected event
    # loop exit retains the non-daemon owner thread; never kill guessed PIDs.
    if not executor.closed:raise ValueError('MANAGED_OWNER_STILL_ACTIVE')
    executor.join();return result
