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
from PySide6.QtGui import QFont, QFontDatabase, QPainter, QColor, QPen, QPixmap, QIcon
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow, QPushButton, QStackedWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .wallet_read import WalletReadSnapshot, read_real_wallet_snapshot, format_wam
from .branding import brand_image
from .fusion_ui import ActionFlowLayout, FusionOverview, fusion_palette, fusion_stylesheet, fusion_nav_icons, vector_icon, label, action
from .fusion_pages import ReceivePage, HistoryPage


_QT_APPLICATION = None


def qt_application():
    # Qt allows one QApplication lifetime per process. Keep it alive across
    # baseline and operational probes; destroying/recreating it can crash.
    global _QT_APPLICATION
    if _QT_APPLICATION is None:
        _QT_APPLICATION = QApplication.instance() or QApplication([])
        families=set(QFontDatabase.families())
        preferred={'win32':('Segoe UI','Arial'),'darwin':('Helvetica Neue','Avenir Next','Arial')}.get(sys.platform,('Noto Sans','DejaVu Sans','Liberation Sans'))
        family=next((f for f in preferred if f in families),None)
        if family:_QT_APPLICATION.setFont(QFont(family,11))
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
        except Exception as error:
            # Never forward external RPC messages, paths or private data.
            from .gui_errors import operation_error
            self.denied.emit(operation_error('sync',error))


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
        self.setMinimumSize(820,600)
        self.resize(1280,800)
        base=QWidget();base.setObjectName('WalletRoot');self.setCentralWidget(base)
        shell=QHBoxLayout(base);shell.setContentsMargins(0,0,0,0);shell.setSpacing(0)
        sidebar=QFrame();sidebar.setObjectName('FusionSidebar');sidebar.setFixedWidth(214)
        side=QVBoxLayout(sidebar);side.setContentsMargins(18,26,18,20);side.setSpacing(20)
        brand=QHBoxLayout();mark=QLabel();mark.setPixmap(QPixmap(str(brand_image())).scaled(44,44,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation));mark.setFixedSize(44,44);brand.addWidget(mark)
        title=QVBoxLayout();title.addWidget(label('WAM','BrandTitle'));title.addWidget(label('FUSION 2.0','FusionKicker'));brand.addLayout(title);brand.addStretch();side.addLayout(brand)
        side.addWidget(label('WALLET WORKSPACE','FusionKicker'))
        self.navigation=QListWidget();self.navigation.setIconSize(__import__('PySide6.QtCore',fromlist=['QSize']).QSize(22,22))
        self.navigation.addItems(('Overview','Receive','History'));side.addWidget(self.navigation,1)
        side.addWidget(label('REGTEST','FusionBadge'))
        self.warning=label('PUBLIC DEMO ACCOUNT / NO REAL FUNDS / SEND & SIGN DISABLED','Warning');side.addWidget(self.warning)
        side.addWidget(label('WAM Core v0.1.11\nBIP352 · WSP-1','FusionMuted'));shell.addWidget(sidebar)
        workspace=QWidget();workspace.setObjectName('FusionTransparent');col=QVBoxLayout(workspace);col.setContentsMargins(28,0,22,12);col.setSpacing(18)
        topbar=QFrame();topbar.setObjectName('FusionTopbar');top=ActionFlowLayout(topbar);top.setContentsMargins(0,18,0,18)
        self.workspace_title=label('Privacy wallet','FusionCardTitle');self.workspace_title.setProperty('fusion_toolbar_title',True);top.addWidget(self.workspace_title)
        self.verification_badge=label('Not verified','FusionBadge');top.addWidget(self.verification_badge)
        self.appearance=QComboBox()
        for text,value in (('Auto · system','auto'),('Signature Light','light'),('Signature Dark','dark')):self.appearance.addItem(text,value)
        top.addWidget(self.appearance);self.refresh_button=action('Sync live','sync');top.addWidget(self.refresh_button);col.addWidget(topbar)
        self.stack=QStackedWidget();col.addWidget(self.stack,1)
        self.dashboard=FusionOverview();self.balance_text=self.dashboard.balance_value;self.utxo_text=self.dashboard.utxo_details;self.stack.addWidget(self.dashboard)
        self.receive_page=ReceivePage();self.receive_code=self.receive_page.receive_code;self.stack.addWidget(self.receive_page)
        self.history_page=HistoryPage();self.history_table=self.history_page.table;self.stack.addWidget(self.history_page)
        self.status=label('Not synced · live Core verification required','StatusText');col.addWidget(self.status);shell.addWidget(workspace,1)
        self.navigation.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.navigation.currentRowChanged.connect(lambda i:self.workspace_title.setText(('Overview','Receive','History','Send','Security','Settings')[i] if 0<=i<6 else 'Privacy wallet'))
        self.navigation.setCurrentRow(0);self.refresh_button.clicked.connect(self.request_sync);self.appearance.currentIndexChanged.connect(self.apply_theme)
        self.dashboard.go_receive.clicked.connect(lambda:self.navigation.setCurrentRow(1));self.dashboard.open_history.clicked.connect(lambda:self.navigation.setCurrentRow(2));self.dashboard.manual_sync.clicked.connect(self.request_sync)
        self.dashboard.transaction_selected.connect(self._open_transaction)

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
        self._active_theme=active
        self.dashboard.set_theme(active)
        self.history_page.set_theme(active)
        for button in self.findChildren(QPushButton):
            name=button.property("fusion_icon")
            if name:button.setIcon(vector_icon(name,c["onaccent"] if button.objectName() in ("FusionPrimary","PrimaryButton") else c["accent"],self.devicePixelRatioF()))
        for icon_label in self.findChildren(QLabel):
            name=icon_label.property("fusion_icon_label")
            if name:icon_label.setPixmap(vector_icon(name,c["accent"],self.devicePixelRatioF()).pixmap(24,24))
        for item, icon in zip(
            (self.navigation.item(i) for i in range(self.navigation.count())),
            fusion_nav_icons(c["accent"]),
        ):
            item.setIcon(icon)

    def request_sync(self):
        if self._worker is not None:
            return
        self.refresh_button.setEnabled(False)
        self.status.setText("Verifying WAM Core REGTEST and WSP-1 SQLite…")
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
        self.receive_page.render_snapshot(None)
        self.history_page.render_snapshot(None)
        self.balance_text.setText('—');self.utxo_text.setText('Unverified · live scan required')
        self.verification_badge.setText('Not verified')
        self.dashboard.render_snapshot(None, locked=bool(
            self.session is not None and (self.session.locked or self.session.faulted)
        ))

    def _sync_failed(self, reason: str):
        from .gui_errors import error_text,public_code
        reason=public_code(reason,fallback='WALLET_SYNC_UNVERIFIED')
        self._clear_balance()
        self.status.setText(error_text(reason,fallback='WALLET_SYNC_UNVERIFIED'))
        self.snapshot_failed.emit(reason)

    def apply_snapshot(self, snap: WalletReadSnapshot):
        # Original encrypted WSP accounts are allowed ONLY for the explicit
        # native-managed-spending session. The public-demo and readonly paths
        # retain their original, strict demo_account_only boundary.
        from .managed_spend_session import ManagedWalletSession
        real_managed=type(self.session) is ManagedWalletSession
        if (type(snap) is not WalletReadSnapshot or snap.chain != "regtest"
                or snap.demo_account_only is real_managed or snap.synthetic_rpc
                or snap.signer_allowed is not (self.session is not None)
                or snap.broadcast_allowed is not (self.session is not None)
                or snap.mainnet_allowed):
            self._sync_failed("REGTEST_UNTRUSTED_SNAPSHOT_DENIED")
            return
        self._snapshot = snap
        try:
            self.receive_page.render_snapshot(snap)
            self.history_page.render_snapshot(snap)
        except (TypeError,ValueError):
            self._sync_failed('FUSION_UNTRUSTED_RECEIVE_DENIED');return
        self.verification_badge.setText('Core verified · '+str(snap.height))
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

    def _open_transaction(self,txid):
        self.navigation.setCurrentRow(2)
        self.history_page.select_txid(txid)

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
