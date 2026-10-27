"""Read-only external-node monitor. Closing it never stops Core or a miner."""
from PySide6.QtCore import QThread, Signal, QTimer
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton
from .external_core import ExternalCoreAttachment
from .rpc_contention import ContentionAwareRpc, RpcContentionError


class _Refresh(QThread):
    ready=Signal(int)
    busy=Signal()
    denied=Signal()
    def __init__(self,rpc):
        super().__init__();self.rpc=rpc
    def run(self):
        try:
            height=self.rpc.read('getblockcount',[])
            if type(height) is not int or not 0<=height<2**31:raise ValueError
            self.ready.emit(height)
        except RpcContentionError as error:
            if error.args==('RPC_NODE_BUSY',):self.busy.emit()
            else:self.denied.emit()
        except Exception:self.denied.emit()


class ExternalNodeWindow(QMainWindow):
    """Explicitly approved REGTEST observation, with no wallet/write controls."""
    def __init__(self,attachment):
        if type(attachment) is not ExternalCoreAttachment:
            raise ValueError('EXTERNAL_GUI_ATTACHMENT_REQUIRED')
        super().__init__()
        self.attachment=attachment
        self.rpc=ContentionAwareRpc(attachment.read)
        self.worker=None;self.faulted=False
        self.setWindowTitle('WAM REGTEST · External node · Read only')
        panel=QWidget();layout=QVBoxLayout(panel)
        layout.addWidget(QLabel('External Core remains operator-owned. Closing this monitor does not stop it.'))
        self.status_label=QLabel('Ready to verify REGTEST height')
        self.height_label=QLabel('Height: unverified')
        self.refresh=QPushButton('Refresh read-only status')
        for widget in (self.status_label,self.height_label,self.refresh):layout.addWidget(widget)
        self.setCentralWidget(panel);self.resize(680,180)
        self.refresh.clicked.connect(self.request_sync)
        self.timer=QTimer(self);self.timer.setInterval(1000)
        self.timer.timeout.connect(self.request_sync);self.timer.start()

    def request_sync(self):
        if self.faulted or self.worker is not None:return
        if self.rpc.status()['busy']:
            # Coalescing suppresses RPC, never the external-process identity check.
            try:self.attachment._assert_process_image()
            except Exception:self._denied();return
            self._busy();return
        self.worker=_Refresh(self.rpc)
        self.worker.ready.connect(self._ready)
        self.worker.busy.connect(self._busy)
        self.worker.denied.connect(self._denied)
        self.worker.finished.connect(self._finished)
        self.refresh.setEnabled(False);self.worker.start()

    def _ready(self,height):
        self.height_label.setText('Height: '+str(height))
        self.status_label.setText('Verified REGTEST · Read only')
    def _busy(self):
        self.height_label.setText('Height: unverified')
        self.status_label.setText('Node busy · retrying after cooldown')
    def _denied(self):
        self.faulted=True;self.height_label.setText('Height: unverified')
        self.status_label.setText('Node identity or connection unavailable · reopen with explicit approval')
        self.attachment.close()
    def _finished(self):
        worker=self.worker;self.worker=None
        self.refresh.setEnabled(not self.faulted)
        if worker is not None:worker.deleteLater()
    def closeEvent(self,event):
        if self.worker is not None:
            event.ignore();return
        self.timer.stop();self.attachment.close();event.accept()


def launch(attachment):
    from .desktop import qt_application
    app=qt_application();window=ExternalNodeWindow(attachment)
    window.show();window.request_sync();app.exec()
    return 0
