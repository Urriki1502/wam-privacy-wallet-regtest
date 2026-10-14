"""Native Qt macOS REGTEST view, reading *real* Core/WSP state.

The baseline view is read-only; the operational subclass adds gated payments. Core is a separately running, verified
v0.1.11 regtest daemon. All balances/history are cleared on RPC failure.
A Qt worker runs live WSP Scanner.sync off the GUI thread.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import QThread, QTimer, Signal, Qt
from PySide6.QtGui import QFont, QPainter, QColor, QPen, QPixmap, QIcon
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow, QPushButton, QStackedWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .wallet_read import WalletReadSnapshot, read_real_wallet_snapshot, format_wam
from .branding import brand_image
from .fusion_ui import FusionOverview, fusion_palette, fusion_stylesheet


_QT_APPLICATION = None


def qt_application():
    # Qt allows one QApplication lifetime per process. Keep it alive across
    # baseline and operational probes; destroying/recreating it can crash.
    global _QT_APPLICATION
    if _QT_APPLICATION is None:
        _QT_APPLICATION = QApplication.instance() or QApplication([])
        _QT_APPLICATION.setWindowIcon(QIcon(str(brand_image())))
        _QT_APPLICATION.setApplicationDisplayName("WAM Privacy Wallet REGTEST")
    return _QT_APPLICATION


def shutdown_qt():
    global _QT_APPLICATION
    if _QT_APPLICATION is not None:
        _QT_APPLICATION.closeAllWindows()
        _QT_APPLICATION.processEvents()
        _QT_APPLICATION.shutdown()
        _QT_APPLICATION = None


def _wallet_icons(tone: str) -> tuple[QIcon, ...]:
    icons = []
    for which in range(3):
        pix = QPixmap(40, 40)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(tone), 2.4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if which == 0:  # download arrow
            painter.drawLine(20, 7, 20, 27)
            painter.drawLine(11, 19, 20, 28)
            painter.drawLine(29, 19, 20, 28)
            painter.drawLine(8, 33, 32, 33)
        elif which == 1:  # wallet
            painter.drawRoundedRect(6, 10, 28, 21, 4, 4)
            painter.drawRoundedRect(24, 17, 14, 9, 3, 3)
            painter.drawPoint(30, 21)
        else:  # clock/history
            painter.drawEllipse(7, 7, 26, 26)
            painter.drawLine(20, 12, 20, 21)
            painter.drawLine(20, 21, 27, 25)
        painter.end()
        icons.append(QIcon(pix))
    return tuple(icons)


def resolve_theme(mode: str, local_time: datetime) -> str:
    if (type(mode) is not str or mode not in ("auto", "light", "dark")
            or type(local_time) is not datetime
            or local_time.tzinfo is None or local_time.utcoffset() is None):
        raise ValueError("REGTEST_GUI_THEME_DENIED")
    if mode == "auto":
        return "light" if 6 <= local_time.hour < 18 else "dark"
    return mode


class _ReadWorker(QThread):
    ready = Signal(object)
    denied = Signal(str)

    def __init__(self, core_dir: Path, datadir: Path, source: Path, session=None):
        super().__init__()
        self._core_dir, self._datadir, self._source = core_dir, datadir, source
        self.session = session

    def run(self):
        try:
            result = (self.session.snapshot() if self.session is not None else
                      read_real_wallet_snapshot(self._core_dir, self._datadir, self._source))
            self.ready.emit(result)
        except Exception:
            # Never forward external RPC messages, paths or private data.
            self.denied.emit("REGTEST_NODE_OR_WSP_SCAN_UNAVAILABLE")


class RegtestWalletWindow(QMainWindow):
    """Real read-only balance; no signer/send controls exist."""
    snapshot_updated = Signal(object)
    snapshot_failed = Signal(str)

    def __init__(self, core_dir: Path, datadir: Path, source: Path, *, session=None):
        super().__init__()
        self.session = session
        self._core_dir, self._datadir, self._source = core_dir, datadir, source
        self._worker = None
        self._snapshot = None
        self.setWindowTitle("WAM Privacy Wallet · Real REGTEST")
        self.setWindowIcon(QIcon(str(brand_image())))
        self.setMinimumSize(960, 660)
        self.resize(1240, 820)
        base = QWidget()
        base.setObjectName("WalletRoot")
        self.setCentralWidget(base)
        col = QVBoxLayout(base)
        col.setContentsMargins(22, 20, 22, 20)
        col.setSpacing(12)
        header = QFrame()
        header.setObjectName("HeaderCard")
        h = QHBoxLayout(header)
        h.setContentsMargins(20, 14, 20, 14)
        mark = QLabel()
        mark.setPixmap(QPixmap(str(brand_image())).scaled(64,64,
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        mark.setFixedSize(64,64)
        mark.setObjectName("WalletMark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.addWidget(mark)
        titles = QVBoxLayout()
        name = QLabel("WAM Privacy Wallet")
        name.setObjectName("BrandTitle")
        sub = QLabel("REAL WAM CORE  ·  BIP352  ·  "+("Windows x64" if sys.platform=="win32" else "macOS ARM64"))
        sub.setObjectName("SecondaryLabel")
        titles.addWidget(name)
        titles.addWidget(sub)
        h.addLayout(titles)
        h.addStretch()
        self.appearance = QComboBox()
        for label, value in (
            ("Auto · local time", "auto"), ("Light", "light"), ("Dark", "dark"),
        ):
            self.appearance.addItem(label, value)
        h.addWidget(self.appearance)
        self.refresh_button = QPushButton("↻  Sync live")
        self.refresh_button.setObjectName("PrimaryButton")
        h.addWidget(self.refresh_button)
        col.addWidget(header)

        warning = QLabel("REGTEST ONLY  ·  PUBLIC DEMO ACCOUNT  ·  NO REAL FUNDS  ·  SEND/SIGN DISABLED")
        warning.setObjectName("Warning")
        warning.setWordWrap(True)
        col.addWidget(warning)
        self.warning = warning

        self.status = QLabel("NOT SYNCED — live Core verification required")
        self.status.setObjectName("StatusText")
        col.addWidget(self.status)

        layout = QHBoxLayout()
        layout.setSpacing(14)
        self.navigation = QListWidget()
        self.navigation.setFixedWidth(205)
        self.navigation.setIconSize(__import__("PySide6.QtCore", fromlist=["QSize"]).QSize(24, 24))
        for label in ("Overview", "Receive", "History"):
            self.navigation.addItem(QListWidgetItem(label))
        layout.addWidget(self.navigation)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, stretch=1)

        receive = QFrame()
        receive.setObjectName("ContentCard")
        receive_layout = QVBoxLayout(receive)
        receive_layout.setContentsMargins(28, 30, 28, 30)
        receive_layout.setSpacing(18)
        title = QLabel("Receive · BIP352")
        title.setObjectName("PageTitle")
        receive_layout.addWidget(title)
        receive_hint = QLabel("Disposable REGTEST silent-payment address · use a BIP352 sender")
        receive_hint.setWordWrap(True)
        receive_layout.addWidget(receive_hint)
        self.receive_code = QLabel("—")
        self.receive_code.setObjectName("ReceiveCode")
        self.receive_code.setWordWrap(True)
        self.receive_code.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        receive_layout.addWidget(self.receive_code)
        receive_layout.addStretch()
        self.stack.addWidget(receive)

        # Replace the old balance-only panel with the WAM Fusion dashboard.
        # Retain the EXACT existing value-label references for verified E2E.
        balance = FusionOverview()
        self.dashboard = balance
        self.balance_text = balance.balance_value
        self.utxo_text = balance.utxo_details
        self.stack.addWidget(balance)

        hist = QFrame()
        hist.setObjectName("ContentCard")
        hist_layout = QVBoxLayout(hist)
        hist_layout.setContentsMargins(24, 26, 24, 24)
        title = QLabel("On-chain transaction history")
        title.setObjectName("PageTitle")
        hist_layout.addWidget(title)
        self.history_table = QTableWidget(0, 4)
        self.history_table.setHorizontalHeaderLabels(("Transaction ID", "Height", "Confirmed", "Credit / Debit"))
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.setColumnWidth(0, 285)
        hist_layout.addWidget(self.history_table)
        self.stack.addWidget(hist)
        # The dashboard is visually first, but source E2E still uses Send=3,
        # Security=4 and Settings=5. Read-only wallet remains exactly 3 tabs.
        self.stack.insertWidget(0, balance)

        col.addLayout(layout, stretch=1)
        self.navigation.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.navigation.setCurrentRow(0)
        self.refresh_button.clicked.connect(self.request_sync)
        self.appearance.currentIndexChanged.connect(self.apply_theme)
        self.dashboard.go_receive.clicked.connect(lambda: self.navigation.setCurrentRow(1))
        self.dashboard.open_history.clicked.connect(lambda: self.navigation.setCurrentRow(2))
        self.dashboard.manual_sync.clicked.connect(self.request_sync)

        self._theme_timer = QTimer(self)
        self._theme_timer.setInterval(60_000)
        self._theme_timer.timeout.connect(self.apply_theme)
        self._theme_timer.start()
        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(30_000)
        self._sync_timer.timeout.connect(self.request_sync)
        self._sync_timer.start()
        QApplication.styleHints().colorSchemeChanged.connect(self.apply_theme)
        self._appearance_connected = True
        self.apply_theme()

    def apply_theme(self, *_):
        local = datetime.now().astimezone()
        active = resolve_theme(self.appearance.currentData(), local)
        if self.appearance.currentData() == "auto":
            scheme = QApplication.styleHints().colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                active = "dark"
            elif scheme == Qt.ColorScheme.Light:
                active = "light"
        c = fusion_palette(active)
        self.setStyleSheet(fusion_stylesheet(active))
        self.dashboard.set_theme(active)
        for item, icon in zip(
            (self.navigation.item(i) for i in range(3)), _wallet_icons(c["accent"])
        ):
            item.setIcon(icon)

    def request_sync(self):
        if self._worker is not None:
            return
        self.refresh_button.setEnabled(False)
        self.status.setText("Scanning signed WAM Core REGTEST and WSP-1 SQLite…")
        worker = _ReadWorker(self._core_dir, self._datadir, self._source, self.session)
        self._worker = worker
        worker.ready.connect(self.apply_snapshot)
        worker.denied.connect(self._sync_failed)
        worker.finished.connect(self._worker_finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _worker_finished(self):
        self._worker = None
        self.refresh_button.setEnabled(True)

    def _clear_balance(self):
        self._snapshot = None
        self.receive_code.setText("—")
        self.balance_text.setText("—")
        self.utxo_text.setText("Unverified — live scan required")
        self.history_table.setRowCount(0)
        self.dashboard.render_snapshot(None, locked=bool(
            self.session is not None and (self.session.locked or self.session.faulted)
        ))

    def _sync_failed(self, reason: str):
        self._clear_balance()
        self.status.setText("DENIED: REGTEST_NODE_OR_WSP_SCAN_UNAVAILABLE")
        self.snapshot_failed.emit("REGTEST_NODE_OR_WSP_SCAN_UNAVAILABLE")

    def apply_snapshot(self, snap: WalletReadSnapshot):
        if (type(snap) is not WalletReadSnapshot or snap.chain != "regtest"
                or not snap.demo_account_only or snap.synthetic_rpc
                or snap.signer_allowed is not (self.session is not None)
                or snap.broadcast_allowed is not (self.session is not None)
                or snap.mainnet_allowed):
            self._sync_failed("REGTEST_UNTRUSTED_SNAPSHOT_DENIED")
            return
        self._snapshot = snap
        self.receive_code.setText(snap.receive_code)
        self.balance_text.setText(format_wam(snap.confirmed_atoms,grouped=True)+" WAM")
        self.utxo_text.setText(
            f"{snap.confirmed_utxos} confirmed UTXO(s) · block {snap.height}")
        self.history_table.setRowCount(len(snap.history))
        for row, item in enumerate(snap.history):
            values = (
                item.txid,
                str(item.block_height),
                str(item.confirmations),
                "+"+format_wam(item.credit_atoms)+" / -"+format_wam(item.debit_atoms),
            )
            for col, value in enumerate(values):
                self.history_table.setItem(row, col, QTableWidgetItem(value))
        self.status.setText(
            f"VERIFIED LIVE REGTEST · height {snap.height} · "
            f"tip {snap.tip[:14]}… · " +
            ("DISPOSABLE TEST WALLET" if self.session is not None else "READ ONLY"))
        try:
            self.dashboard.render_snapshot(snap, operational=self.session is not None)
        except (TypeError, ValueError):
            self._sync_failed("FUSION_UNTRUSTED_HISTORY_DENIED")
            return
        self.snapshot_updated.emit(snap)

    def closeEvent(self, event):
        if self._worker is not None:
            # Do not destroy a running QThread while Core RPC is in progress.
            event.ignore()
            self.status.setText("Waiting for safe scanner shutdown before close")
            return
        self._theme_timer.stop()
        self._sync_timer.stop()
        if self._appearance_connected:
            QApplication.styleHints().colorSchemeChanged.disconnect(self.apply_theme)
            self._appearance_connected = False
        super().closeEvent(event)


def launch_readonly_wallet(core_dir: Path, datadir: Path, source: Path) -> int:
    app = qt_application()
    window = RegtestWalletWindow(core_dir, datadir, source)
    window.show()
    QTimer.singleShot(0, window.request_sync)
    # Do not destroy window or worker before app event loop returns.
    return app.exec()
