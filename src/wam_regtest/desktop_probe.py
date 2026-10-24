"""Native macOS headless-Qt proof from the running official Core + WSP-1.

This must be called while the REAL wamd process remains live, after a real
BIP352 transaction has been broadcast, mined and found by WSP Scanner. The
window's actual Sync button path runs its own worker: Core RPC -> actual
Scanner.sync -> SQLite -> Qt Receive/Balance/History. No fake snapshot injection.
"""
from __future__ import annotations

from pathlib import Path
import os
import sys


class NativeGuiProbeError(ValueError):
    pass


def probe_running_real_core_gui(
    core_dir: Path, datadir: Path, source_root: Path,
    *, expected_height: int, expected_txid: str, expected_atoms: int,
) -> dict[str, object]:
    if (sys.platform != "darwin" or os.environ.get("QT_QPA_PLATFORM") != "offscreen"
            or expected_height != 102 or type(expected_txid) is not str
            or len(expected_txid) != 64 or type(expected_atoms) is not int
            or expected_atoms <= 0):
        raise NativeGuiProbeError("GUI_REAL_REGTEST_PROBE_SCOPE_DENIED")
    from PySide6.QtCore import QEventLoop, QTimer, QCoreApplication, QEvent, Qt
    from PySide6.QtWidgets import QApplication
    from .desktop import RegtestWalletWindow, qt_application

    app = qt_application()
    win = RegtestWalletWindow(core_dir, datadir, source_root)
    events: dict[str, object] = {}
    loop = QEventLoop()

    def success(snapshot):
        events["snapshot"] = snapshot
        loop.quit()

    def failure(_status):
        events["failed"] = True
        loop.quit()

    def expired():
        events["timeout"] = True
        loop.quit()

    win.snapshot_updated.connect(success)
    win.snapshot_failed.connect(failure)
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(expired)
    timer.start(90_000)
    win.show()
    QTimer.singleShot(0, win.request_sync)
    loop.exec()
    timer.stop()
    worker = win._worker
    if worker is not None:
        if not worker.wait(15_000):
            raise NativeGuiProbeError("GUI_REAL_REGTEST_THREAD_STUCK")
        app.processEvents()
    if ("snapshot" not in events or events.get("failed") or events.get("timeout")
            or win._snapshot is None):
        raise NativeGuiProbeError("GUI_REAL_REGTEST_SYNC_DENIED")
    snap = events["snapshot"]
    if (snap.chain != "regtest" or snap.synthetic_rpc
            or snap.height != expected_height
            or snap.confirmed_atoms != expected_atoms
            or snap.confirmed_utxos != 1
            or len(snap.history) != 1
            or snap.history[0].txid != expected_txid
            or snap.history[0].credit_atoms != expected_atoms
            or snap.signer_allowed or snap.broadcast_allowed or snap.mainnet_allowed):
        raise NativeGuiProbeError("GUI_REAL_REGTEST_MODEL_MISMATCH")
    if (win.receive_code.text() != snap.receive_code
            or not snap.receive_code.startswith("wamrtsp1")
            or win.balance_text.text() != f"{expected_atoms / 100_000_000:,.8f} WAM"
            or win.history_table.rowCount() != 1
            or win.history_table.item(0, 1).data(Qt.ItemDataRole.UserRole) != expected_txid
            or win.history_table.item(0, 4).text() != f"{expected_atoms / 100_000_000:.8f}"
            or win.history_table.item(0, 5).text() != "0.00000000"
            or "VERIFIED LIVE REGTEST" not in win.status.text()
            or win.navigation.count() != 3
            or win.navigation.item(0).text() != "Overview"
            or win.stack.widget(0) is not win.dashboard
            or win.dashboard.balance_value.text() != win.balance_text.text()
            or win.dashboard.activity_table.rowCount() != 1
            or win.dashboard.chart._activity != ((expected_height, expected_atoms, 0),)
            or win.dashboard.go_send.isEnabled()
            or "REGTEST VERIFIED" not in win.dashboard.live_badge.text()):
        raise NativeGuiProbeError("GUI_REAL_REGTEST_VIEW_MISMATCH")
    win.history_page.select_txid(expected_txid)
    if win.history_page.detail_id.text()!=expected_txid:
        raise NativeGuiProbeError("GUI_FULL_TRANSACTION_ID_DETAIL_DENIED")
    win.receive_page.copy_button.click()
    if app.clipboard().text()!=snap.receive_code:
        raise NativeGuiProbeError("GUI_FULL_RECEIVE_CODE_COPY_DENIED")
    win.history_page.copy_button.click()
    if app.clipboard().text()!=expected_txid:
        raise NativeGuiProbeError("GUI_FULL_TRANSACTION_ID_COPY_DENIED")
    path = Path("real-regtest-gui-preview.png").resolve()
    if not win.grab().save(str(path)):
        raise NativeGuiProbeError("GUI_REAL_REGTEST_CAPTURE_DENIED")
    win.close()
    win.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    return {
        "status": "REAL_WAM_CORE_V0_1_11_NATIVE_QT_RECEIVE_BALANCE_HISTORY_PASS",
        "real_core_rpc": True,
        "synthetic_rpc": False,
        "qt_gui_rendered": True,
        "receive_code_from_scanner": True,
        "confirmed_balance_atoms": expected_atoms,
        "confirmed_history_txid": expected_txid,
        "observed_height": expected_height,
        "verified_tip": snap.tip,
        "native_wsp_sqlite_synced": True,
        "gui_background_worker_completed": True,
        "signer_allowed": False,
        "broadcast_allowed": False,
        "mainnet_allowed": False,
    }
