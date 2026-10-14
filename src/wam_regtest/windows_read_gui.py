"""Reuse the actual macOS V1 Qt view against the native Windows Core+WSP path.

No fake snapshots or payments, no Windows signer, no on-device human claim.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

from PySide6.QtCore import QEventLoop, QThread, QTimer, Signal
from PySide6.QtWidgets import QLabel

from .desktop import RegtestWalletWindow, qt_application
from .wallet_read import WalletReadSnapshot
from .windows_wallet_read import read_native_windows_wallet


class WindowsGuiProbeError(ValueError):
    """Only fixed UI acceptance status leaves this module."""


class _WindowsReadWorker(QThread):
    ready = Signal(object)
    denied = Signal(str)

    def __init__(self, core, cli, datadir, port, environment, source, digest):
        super().__init__()
        self.params = (core, cli, datadir, port, environment, source, digest)

    def run(self):
        try:
            self.ready.emit(read_native_windows_wallet(*self.params))
        except Exception:
            self.denied.emit("WIN_GUI_REAL_READ_DENIED")


class WindowsReadOnlyWalletWindow(RegtestWalletWindow):
    """Full V1 Receive/Balance/History view; no send/sign buttons."""
    def __init__(self, core: Path, cli: Path, datadir: Path, port: int,
                 environment: dict, wsp_source: Path, core_sha: str):
        self._native_params = (core, cli, datadir, port, environment, wsp_source, core_sha)
        super().__init__(core.parent, datadir, wsp_source)
        self.setWindowTitle("WAM Privacy Wallet · Windows x64 REAL REGTEST")
        self.warning.setText(
            "REGTEST ONLY · PUBLIC DEMO ACCOUNT · NO REAL FUNDS · SEND/SIGN DISABLED"
        )
        for label in self.findChildren(QLabel):
            if "BIP352" in label.text() and "macOS ARM64" in label.text():
                label.setText("REAL WAM CORE  ·  BIP352  ·  Windows x64")

    def request_sync(self):
        if self._worker is not None:
            return
        self.refresh_button.setEnabled(False)
        self.status.setText("Scanning native signed Windows WAM Core + WSP-1 SQLite…")
        worker = _WindowsReadWorker(*self._native_params)
        self._worker = worker
        worker.ready.connect(self.apply_snapshot)
        worker.denied.connect(self._sync_failed)
        worker.finished.connect(self._worker_finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()


def probe_real_windows_wallet_gui(core, cli, datadir, port, environment,
                                  source, digest) -> dict:
    """Real Qt UI thread + native Core RPC + WSP Scanner worker under CI."""
    if sys.platform != "win32" or os.environ.get("QT_QPA_PLATFORM") != "offscreen":
        raise WindowsGuiProbeError("WIN_GUI_OFFSCREEN_NATIVE_SCOPE_DENIED")
    app = qt_application()
    window = WindowsReadOnlyWalletWindow(core, cli, datadir, port, environment, source, digest)
    pending = {"pass": False, "deny": False, "timeout": False}
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)

    def success(snapshot):
        if (type(snapshot) is WalletReadSnapshot and snapshot.chain == "regtest"
                and snapshot.height == 102 and snapshot.confirmed_utxos == 1
                and snapshot.confirmed_atoms > 0 and len(snapshot.history) >= 1
                and snapshot.synthetic_rpc is False
                and snapshot.signer_allowed is False
                and snapshot.broadcast_allowed is False
                and window.balance_text.text().endswith(" WAM")
                and window.receive_code.text() == snapshot.receive_code
                and window.history_table.rowCount() == len(snapshot.history)):
            pending["pass"] = True
        loop.quit()

    def failure(_):
        pending["deny"] = True
        loop.quit()

    def timeout():
        pending["timeout"] = True
        loop.quit()

    window.snapshot_updated.connect(success)
    window.snapshot_failed.connect(failure)
    timer.timeout.connect(timeout)
    window.show()
    timer.start(45000)
    QTimer.singleShot(0, window.request_sync)
    try:
        loop.exec()
        if not pending["pass"] or pending["deny"] or pending["timeout"]:
            raise WindowsGuiProbeError("WIN_GUI_REAL_NATIVE_E2E_DENIED")
        if window.navigation.count() != 3:
            raise WindowsGuiProbeError("WIN_GUI_READ_ONLY_NAVIGATION_DENIED")
        return {
            "status": "WIN64_SIGNED_CORE_WSP_QT_RECEIVE_BALANCE_HISTORY_PASS",
            "real_native_windows_qt_events": True,
            "real_signed_core_rpc": True,
            "native_wsp_sqlite_scan": True,
            "synthetic_rpc": False,
            "signing_allowed": False, "broadcast_allowed": False,
            "mainnet_allowed": False,
            "human_finder_or_installer_acceptance": False,
        }
    finally:
        timer.stop()
        if window._worker is not None:
            if not window._worker.wait(10000):
                raise WindowsGuiProbeError("WIN_GUI_WORKER_SHUTDOWN_DENIED")
            app.processEvents()
        window.close()
        window.deleteLater()
        app.processEvents()
