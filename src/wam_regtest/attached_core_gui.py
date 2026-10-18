"""T-06 isolated existing-Core inspector; not a wallet/spender GUI.

No managed supervisor, no Core lifecycle buttons, no account/seed/QR,
no wallet RPC, no mining, no Sign/Broadcast. A status failure clears the
previously verified tip and refuses to present stale chain data.
"""
from __future__ import annotations

from pathlib import Path
import re

from PySide6.QtCore import QThread,Signal,QTimer
from PySide6.QtWidgets import (
    QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,
)
from .desktop import qt_application


class _AttachReadWorker(QThread):
    ready=Signal(object)
    denied=Signal(str)

    def __init__(self,core,directory,pid):
        super().__init__()
        self.core,self.directory,self.pid=core,directory,pid

    def run(self):
        try:
            from .attached_core import attach_existing_core
            with attach_existing_core(
                    self.core,self.directory,self.pid,
                    authorized_readonly=True) as reader:
                chain=reader.attest()
                height=chain["blocks"]
                tip=chain["bestblockhash"]
                if (reader.call("getblockcount")!=height
                        or reader.call("getblockhash",[height])!=tip
                        or reader.call("getbestblockhash")!=tip):
                    raise ValueError("ATTACH_TIP_CHANGED")
                self.ready.emit({
                    "chain":"regtest","height":height,"tip":tip,
                    "read_only":True,"mainnet_allowed":False,
                })
        except Exception:
            # Never expose private datadir, RPC credential, PID, path or raw
            # exception through GUI or public test artifacts.
            self.denied.emit("ATTACH_READONLY_VERIFICATION_DENIED")


class ExistingCoreReadOnlyWindow(QMainWindow):
    """GUI entry for an operator-consented ALREADY-RUNNING REGTEST Core."""

    verified=Signal(object)
    refused=Signal(str)

    def __init__(self,core:Path,directory:Path,pid:int):
        super().__init__()
        if (type(core) is not type(Path()) or not core.is_absolute()
                or type(directory) is not type(Path()) or not directory.is_absolute()
                or type(pid) is not int or not 2<=pid<=2**31-1):
            raise ValueError("ATTACH_GUI_EXPLICIT_SCOPE_DENIED")
        self._core,self._directory,self._pid=core,directory,pid
        self._worker=None
        self._proof=None
        self.setWindowTitle("WAM Fusion · Existing Core REGTEST · READ ONLY")
        self.setMinimumSize(650,280)
        root=QWidget()
        self.setCentralWidget(root)
        body=QVBoxLayout(root)
        title=QLabel("EXISTING WAM CORE · REGTEST ONLY")
        title.setObjectName("attachedCoreTitle")
        body.addWidget(title)
        self.warning=QLabel(
            "READ ONLY · No wallet access, signing, broadcast, mining or Core shutdown")
        body.addWidget(self.warning)
        self.status=QLabel("Unverified external Core · no chain data published")
        self.status.setObjectName("attachedCoreStatus")
        body.addWidget(self.status)
        self.chain=QLabel("CHAIN: UNVERIFIED")
        self.tip=QLabel("BEST TIP: UNVERIFIED")
        self.chain.setObjectName("attachedCoreChain")
        self.tip.setObjectName("attachedCoreTip")
        body.addWidget(self.chain)
        body.addWidget(self.tip)
        buttons=QHBoxLayout()
        self.refresh=QPushButton("Verify / Refresh read-only Core")
        self.refresh.clicked.connect(self.request_refresh)
        self.close_button=QPushButton("Close inspector")
        self.close_button.clicked.connect(self.close)
        buttons.addWidget(self.refresh)
        buttons.addWidget(self.close_button)
        body.addLayout(buttons)

    def request_refresh(self):
        if self._worker is not None:return
        self._clear()
        self.status.setText("Authenticating existing Core process and chain…")
        self.refresh.setEnabled(False)
        worker=_AttachReadWorker(self._core,self._directory,self._pid)
        self._worker=worker
        worker.ready.connect(self._verified)
        worker.denied.connect(self._denied)
        worker.finished.connect(self._finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _clear(self):
        self._proof=None
        self.chain.setText("CHAIN: UNVERIFIED")
        self.tip.setText("BEST TIP: UNVERIFIED")

    def _verified(self,proof):
        good=(type(proof) is dict and set(proof)=={
                "chain","height","tip","read_only","mainnet_allowed"}
            and proof["chain"]=="regtest"
            and type(proof["height"]) is int and 0<=proof["height"]<=1000000
            and type(proof["tip"]) is str
            and re.fullmatch("[0-9a-f]{64}",proof["tip"])
            and proof["read_only"] is True
            and proof["mainnet_allowed"] is False)
        if not good:
            self._denied("ATTACH_UNVERIFIED_RESULT")
            return
        self._proof=proof
        self.chain.setText(f"CHAIN: REGTEST · HEIGHT {proof['height']}")
        self.tip.setText("BEST TIP: "+proof["tip"])
        self.status.setText("VERIFIED EXTERNAL CORE · READ ONLY · NO MUTATION")
        self.verified.emit(proof)

    def _denied(self,reason):
        self._clear()
        self.status.setText("EXTERNAL CORE UNVERIFIED · READS BLOCKED")
        self.refused.emit("ATTACH_READONLY_VERIFICATION_DENIED")

    def _finished(self):
        self._worker=None
        self.refresh.setEnabled(True)

    def closeEvent(self,event):
        if self._worker is not None:
            event.ignore()
            self.status.setText("Finishing read-only verification before close")
            return
        super().closeEvent(event)


def launch_attached_readonly_gui(core:Path,directory:Path,pid:int):
    app=qt_application()
    window=ExistingCoreReadOnlyWindow(core,directory,pid)
    window.show()
    QTimer.singleShot(0,window.request_refresh)
    return app.exec()
