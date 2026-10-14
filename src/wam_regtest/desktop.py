"""Native Qt macOS public-demo REGTEST wallet, reading *real* Core/WSP state.

Nothing here can sign or broadcast. Core is a separately running, verified
v0.1.11 regtest daemon. All balances/history are cleared on RPC failure.
A Qt worker runs live WSP Scanner.sync off the GUI thread.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from PySide6.QtCore import QThread, QTimer, Signal, Qt
from PySide6.QtGui import QFont, QPainter, QColor, QPen, QPixmap, QIcon
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow, QPushButton, QStackedWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .wallet_read import WalletReadSnapshot, read_real_wallet_snapshot


_QT_APPLICATION = None


def qt_application():
    # Qt allows one QApplication lifetime per process. Keep it alive across
    # baseline and operational probes; destroying/recreating it can crash.
    global _QT_APPLICATION
    if _QT_APPLICATION is None:
        _QT_APPLICATION = QApplication.instance() or QApplication([])
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
        self.resize(1020, 680)
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
        mark = QLabel("W")
        mark.setObjectName("WalletMark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.addWidget(mark)
        titles = QVBoxLayout()
        name = QLabel("WAM Privacy Wallet")
        name.setObjectName("BrandTitle")
        sub = QLabel("REAL WAM CORE  ·  BIP352  ·  macOS ARM64")
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
        for label in ("Receive", "Balance", "History"):
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
        receive_layout.addWidget(QLabel("Public test-only scan account · wallet address is NOT a Core sendtoaddress destination"))
        self.receive_code = QLabel("—")
        self.receive_code.setObjectName("ReceiveCode")
        self.receive_code.setWordWrap(True)
        self.receive_code.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        receive_layout.addWidget(self.receive_code)
        receive_layout.addStretch()
        self.stack.addWidget(receive)

        balance = QFrame()
        balance.setObjectName("ContentCard")
        bal_layout = QVBoxLayout(balance)
        bal_layout.setContentsMargins(28, 30, 28, 30)
        title = QLabel("Confirmed balance")
        title.setObjectName("PageTitle")
        bal_layout.addWidget(title)
        self.balance_text = QLabel("—")
        self.balance_text.setObjectName("BalanceValue")
        bal_layout.addWidget(self.balance_text)
        self.utxo_text = QLabel("Awaiting verified chain and SQLite scan")
        self.utxo_text.setObjectName("SecondaryLabel")
        bal_layout.addWidget(self.utxo_text)
        bal_layout.addStretch()
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

        col.addLayout(layout, stretch=1)
        self.navigation.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.navigation.setCurrentRow(0)
        self.refresh_button.clicked.connect(self.request_sync)
        self.appearance.currentIndexChanged.connect(self.apply_theme)

        self._theme_timer = QTimer(self)
        self._theme_timer.setInterval(60_000)
        self._theme_timer.timeout.connect(self.apply_theme)
        self._theme_timer.start()
        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(30_000)
        self._sync_timer.timeout.connect(self.request_sync)
        self._sync_timer.start()
        self.apply_theme()

    def apply_theme(self, *_):
        local = datetime.now().astimezone()
        active = resolve_theme(self.appearance.currentData(), local)
        if self.appearance.currentData() == "auto" and self.session is not None:
            scheme = QApplication.styleHints().colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                active = "dark"
            elif scheme == Qt.ColorScheme.Light:
                active = "light"
        if active == "dark":
            c = dict(bg="#0B1322", surface="#172439", text="#F4F8FF",
                     muted="#A3B5CA", border="#334760", tint="#20374B",
                     accent="#68DDC1", onaccent="#102C2B", warning="#382C21",
                     warning_text="#FFDFA8")
        else:
            c = dict(bg="#F3F6FB", surface="#FFFFFF", text="#172A3E",
                     muted="#5D6C7D", border="#D9E4EC", tint="#EDF4F7",
                     accent="#087E73", onaccent="#FFFFFF", warning="#FFF4E1",
                     warning_text="#79551F")
        self.setStyleSheet(f"""
            QMainWindow, QWidget#WalletRoot {{background:{c['bg']}; color:{c['text']};}}
            QFrame#HeaderCard, QFrame#ContentCard {{
                background:{c['surface']}; border:1px solid {c['border']};
                border-radius:15px;
            }}
            QLabel {{color:{c['text']}; background:transparent; border:none;}}
            QLabel#WalletMark {{background:{c['accent']}; color:{c['onaccent']};
                border-radius:17px; font-size:22px; font-weight:800;
                min-height:40px; max-height:40px; min-width:40px; max-width:40px;}}
            QLabel#BrandTitle {{font-size:21px; font-weight:800;}}
            QLabel#PageTitle {{font-size:23px; font-weight:750;}}
            QLabel#BalanceValue {{font-size:38px; font-weight:800; color:{c['accent']};}}
            QLabel#ReceiveCode {{font-family:monospace; font-size:13px; padding:14px;
                background:{c['tint']}; border-radius:8px;}}
            QLabel#SecondaryLabel, QLabel#StatusText {{color:{c['muted']};}}
            QLabel#Warning {{background:{c['warning']}; color:{c['warning_text']};
                padding:11px 15px; border-radius:9px; font-weight:700;}}
            QListWidget {{background:{c['surface']}; color:{c['text']};
                border:1px solid {c['border']}; border-radius:12px;
                padding:8px; font-size:14px;}}
            QListWidget::item {{padding:14px 10px; border-radius:8px;}}
            QListWidget::item:selected {{background:{c['tint']}; color:{c['accent']};
                font-weight:700;}}
            QPushButton, QComboBox {{background:{c['tint']}; color:{c['text']};
                border:1px solid {c['border']}; border-radius:9px; padding:9px 13px;}}
            QPushButton#PrimaryButton {{background:{c['accent']};
                color:{c['onaccent']}; font-weight:700; border:none;}}
            QPushButton:disabled {{opacity:0.5; color:{c['muted']};}}
            QTableWidget, QHeaderView::section {{background:{c['surface']};
                color:{c['text']}; border:1px solid {c['border']}; padding:6px;}}
        """)
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
        self.balance_text.setText(f"{snap.confirmed_atoms / 100_000_000:,.8f} WAM")
        self.utxo_text.setText(
            f"{snap.confirmed_utxos} confirmed UTXO(s) · block {snap.height}")
        self.history_table.setRowCount(len(snap.history))
        for row, item in enumerate(snap.history):
            values = (
                item.txid,
                str(item.block_height),
                str(item.confirmations),
                f"+{item.credit_atoms / 100_000_000:.8f} / "
                f"-{item.debit_atoms / 100_000_000:.8f}",
            )
            for col, value in enumerate(values):
                self.history_table.setItem(row, col, QTableWidgetItem(value))
        self.status.setText(
            f"VERIFIED LIVE REGTEST · height {snap.height} · "
            f"tip {snap.tip[:14]}… · " +
            ("DISPOSABLE TEST WALLET" if self.session is not None else "READ ONLY"))
        self.snapshot_updated.emit(snap)

    def closeEvent(self, event):
        if self._worker is not None:
            # Do not destroy a running QThread while Core RPC is in progress.
            event.ignore()
            self.status.setText("Waiting for safe scanner shutdown before close")
            return
        self._theme_timer.stop()
        self._sync_timer.stop()
        super().closeEvent(event)


def launch_readonly_wallet(core_dir: Path, datadir: Path, source: Path) -> int:
    app = qt_application()
    window = RegtestWalletWindow(core_dir, datadir, source)
    window.show()
    QTimer.singleShot(0, window.request_sync)
    # Do not destroy window or worker before app event loop returns.
    return app.exec()
