"""T05 Fusion GUI for the *owned* persistent REGTEST Core supervisor.

This is the actual Fusion Qt shell, not a synthetic console/status mock.
Only the independently authenticated supervisor's status is displayed.
No WSP wallet is created, adopted, unlocked, signed or broadcast here.
Q05 wallet continuity is a separate, still mandatory integration gate.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal, QTimer
from PySide6.QtWidgets import QMessageBox

from .desktop import RegtestWalletWindow, qt_application
from .fusion_ui import action
from .supervisor_client import control
from .supervisor_protocol import public_status

VISIBLE_STATES = {
    "stopped": "STOPPED",
    "starting": "STARTING",
    "syncing": "SYNCING",
    "busy": "BUSY · retry later",
    "ready": "READY",
    "recovery-needed": "RECOVERY NEEDED",
    "error": "ERROR · supervisor refused",
}


class _ManagedStatusWorker(QThread):
    ready = Signal(object)
    denied = Signal(str)

    def __init__(self, root: Path, operation: str):
        super().__init__()
        self.root, self.operation = root, operation

    def run(self):
        try:
            result = control(self.root, self.operation,
                authorized=self.operation != "status", timeout=15 if self.operation != "status" else 3)
            self.ready.emit(result)
        except Exception:
            # Never echo exception text, private paths or RPC credentials.
            self.denied.emit("MANAGED_SUPERVISOR_UNVERIFIED")


class ManagedCoreWindow(RegtestWalletWindow):
    """Fusion GUI lifecycle observer; closing this window NEVER stops Core."""

    def __init__(self, root: Path):
        if type(root) is not type(Path()) or not root.is_absolute():
            raise ValueError("MANAGED_GUI_ROOT_DENIED")
        self._managed_root = root
        # The base Fusion shell is reused; its disposable wallet data loader
        # is never called. A managed WSP session must first be restored safely.
        super().__init__(root / "chain", root / "chain", root / "chain")
        self.setWindowTitle("WAM Fusion · Persistent Core REGTEST")
        self.warning.setText("REGTEST ONLY · MANAGED CORE · WALLET LOCKED / UNVERIFIED")
        self.status.setText("Connecting to authenticated managed Core…")
        self.verification_badge.setText("Core not yet verified")
        self._managed_state = "error"
        self._managed_authenticated = False
        self._clear_balance()
        self.dashboard.go_send.setEnabled(False)
        self.dashboard.manual_sync.setEnabled(True)
        toolbar = self.refresh_button.parentWidget().layout()
        self.start_core = action("Start owned Core", "core")
        self.stop_core = action("Stop owned Core", "core")
        toolbar.addWidget(self.start_core)
        toolbar.addWidget(self.stop_core)
        self.start_core.clicked.connect(lambda: self._execute("start"))
        self.stop_core.clicked.connect(self._confirm_stop)
        # A short timer makes transitions visible without polling from Qt's
        # UI thread or creating an unbounded Core RPC request queue.
        self._sync_timer.setInterval(5_000)
        self._update_controls()

    def _update_controls(self):
        if not hasattr(self, "start_core"):
            return
        idle = self._worker is None
        self.start_core.setEnabled(
            idle and self._managed_authenticated and
            self._managed_state in ("stopped", "recovery-needed")
        )
        self.stop_core.setEnabled(
            idle and self._managed_authenticated and
            self._managed_state in ("ready", "syncing", "busy")
        )
        self.refresh_button.setEnabled(idle)

    def _execute(self, operation: str):
        if self._worker is not None:
            return
        if operation not in ("status", "start", "shutdown"):
            raise ValueError("MANAGED_GUI_OPERATION_DENIED")
        if operation != "status" and not self._managed_authenticated:
            return
        if operation == "start":
            if self._managed_state not in ("stopped", "recovery-needed"):
                return
            self.status.setText("STARTING · requesting verified owned Core startup…")
        elif operation == "shutdown":
            if self._managed_state not in ("ready", "syncing", "busy"):
                return
            self.status.setText("Stopping verified Fusion-owned Core…")
        worker = _ManagedStatusWorker(self._managed_root, operation)
        self._worker = worker
        worker.ready.connect(self._apply_managed_status)
        worker.denied.connect(self._managed_denied)
        worker.finished.connect(self._worker_finished)
        worker.finished.connect(worker.deleteLater)
        self._update_controls()
        worker.start()

    def request_sync(self):
        self._execute("status")

    def _confirm_stop(self):
        if self._managed_state not in ("ready", "syncing", "busy"):
            return
        answer = QMessageBox.question(
            self, "Stop managed REGTEST Core",
            "Stop only the verified Fusion-owned REGTEST Core?\n"
            "Blockchain datadir will be preserved; unrelated Core/miners will not be stopped.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._execute("shutdown")

    def _apply_managed_status(self, status):
        # Double-check caller-supplied state without accepting inferred,
        # fabricated or wrong-chain status, even in UI signal delivery.
        try:
            if type(status) is not dict:
                raise ValueError
            expected = public_status(state=status["state"],
                chain_height=status["height"], owned=status["core_process_owned"])
            if status != expected:
                raise ValueError
            state = expected["state"]
            if state in ("ready", "syncing", "busy") and not expected["core_process_owned"]:
                raise ValueError
            if state == "ready" and expected["height"] is None:
                raise ValueError
        except (ValueError, KeyError, TypeError):
            self._managed_denied("MANAGED_GUI_INVALID_STATUS")
            return
        self._managed_state = state
        self._managed_authenticated = True
        # A supervisor attestation is NOT a scanner/history attestation.
        self._clear_balance()
        height = expected["height"]
        label = VISIBLE_STATES[state]
        self.verification_badge.setText("Managed Core · " + label)
        self.status.setText(
            "REGTEST · " + label +
            (" · height " + str(height) if height is not None else "") +
            " · WSP wallet locked/unverified · no automatic broadcast"
        )
        self._update_controls()

    def _managed_denied(self, _reason):
        self._managed_state = "error"
        self._managed_authenticated = False
        self._clear_balance()
        self.verification_badge.setText("Managed Core · UNVERIFIED")
        self.status.setText(
            "RECOVERY NEEDED · authenticated supervisor unavailable; "
            "no data or wallet state adopted"
        )
        self._update_controls()

    def _worker_finished(self):
        super()._worker_finished()
        self._update_controls()

    def closeEvent(self, event):
        # RegtestWalletWindow prevents deleting in-flight QThreads. It never
        # sends Core stop on window close. Our managed subclass preserves that.
        super().closeEvent(event)


def launch_managed_gui(root: Path) -> int:
    from .supervisor_store import _root
    _root(root)
    app = qt_application()
    window = ManagedCoreWindow(root)
    window.show()
    QTimer.singleShot(0, window.request_sync)
    return app.exec()
