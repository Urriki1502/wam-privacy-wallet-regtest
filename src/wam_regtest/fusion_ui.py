"""WAM Fusion Signature — shared, presentation-only Qt design system.

One UI for macOS ARM64 and Windows x64. Never queries Core, signs,
alters session policy or invents security scores / WAM-to-fiat prices.
Snapshots are supplied only by the existing verified Core/WSP read path.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QIcon, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QHeaderView,
)
from .wallet_read import WalletReadSnapshot, format_wam


def fusion_palette(mode: str) -> dict[str, str]:
    """Stable cross-platform visual tokens, independent of wallet authority."""
    if mode == "dark":
        return {
            "bg": "#0D121A", "surface": "#151D29", "panel": "#111923",
            "text": "#F5F4F1", "muted": "#ADB9C9", "border": "#293746",
            "tint": "#222E3A", "accent": "#F1C55A", "onaccent": "#211A09",
            "warning": "#382913", "warning_text": "#F9D989",
            "green": "#57DDB4", "blue": "#66B3ED", "red": "#FE8585",
            "hero_bottom": "#101722", "selection": "#3C3527",
            "grid": "#304253", "chart_empty": "#96A5B9",
        }
    if mode == "light":
        return {
            "bg": "#F4F6FA", "surface": "#FFFFFF", "panel": "#FBFCFE",
            "text": "#172537", "muted": "#627188", "border": "#DCE3EC",
            "tint": "#F4F0E8", "accent": "#795507", "onaccent": "#FFFFFF",
            "warning": "#FFF1D4", "warning_text": "#694710",
            "green": "#117C59", "blue": "#2369B5", "red": "#C64152",
            "hero_bottom": "#FDF9F1", "selection": "#FAF0DB",
            "grid": "#E2E9F2", "chart_empty": "#667790",
        }
    raise ValueError("FUSION_THEME_DENIED")


def fusion_stylesheet(mode: str) -> str:
    c = fusion_palette(mode)
    return f"""
      QMainWindow, QWidget#WalletRoot {{background:{c['bg']}; color:{c['text']};}}
      QWidget {{font-family:'Inter','Segoe UI','SF Pro Text','Arial'; font-size:13px;}}
      QFrame#HeaderCard, QFrame#ContentCard, QFrame#FusionPanel {{
          background:{c['surface']}; border:1px solid {c['border']};
          border-radius:15px;
      }}
      QFrame#FusionHero {{
          background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
              stop:0 {c['surface']}, stop:1 {c['hero_bottom']});
          border:1px solid {c['border']}; border-radius:17px;
      }}
      QWidget#FusionInner, QScrollArea#FusionScroll {{
          background:transparent; border:0px;
      }}
      QLabel {{color:{c['text']}; background:transparent; border:0px;}}
      QLabel#WalletMark {{background:transparent;}}
      QLabel#BrandTitle {{font-size:21px; font-weight:800;}}
      QLabel#PageTitle {{font-size:23px; font-weight:750;}}
      QLabel#BalanceValue, QLabel#FusionBalance {{
          font-size:34px; font-weight:800; color:{c['accent']};
      }}
      QLabel#FusionKicker {{font-size:11px; color:{c['muted']}; font-weight:700;}}
      QLabel#FusionCardTitle {{font-size:15px; font-weight:750;}}
      QLabel#FusionCardValue {{font-size:15px; font-weight:750; color:{c['text']};}}
      QLabel#FusionVerified {{color:{c['green']}; font-weight:700;}}
      QLabel#FusionInfo {{color:{c['blue']}; font-weight:650;}}
      QLabel#FusionMuted, QLabel#SecondaryLabel, QLabel#StatusText {{
          color:{c['muted']};
      }}
      QLabel#FusionEmpty {{color:{c['chart_empty']};}}
      QLabel#ReceiveCode {{
          font-family:monospace; font-size:13px; padding:14px;
          background:{c['tint']}; border-radius:9px;
      }}
      QLabel#Warning {{
          background:{c['warning']}; color:{c['warning_text']};
          padding:11px 15px; border-radius:9px; font-weight:700;
      }}
      QListWidget {{
          background:{c['surface']}; color:{c['text']};
          border:1px solid {c['border']}; border-radius:14px;
          padding:8px; font-size:14px;
      }}
      QListWidget::item {{padding:13px 11px; border-radius:9px;}}
      QListWidget::item:selected {{
          background:{c['selection']}; color:{c['accent']}; font-weight:750;
      }}
      QListWidget::item:hover:!selected {{background:{c['tint']};}}
      QLineEdit {{
          background:{c['panel']}; color:{c['text']};
          selection-background-color:{c['selection']};
          border:1px solid {c['border']}; border-radius:9px; padding:10px;
      }}
      QLineEdit:focus {{border:2px solid {c['accent']};}}
      QLineEdit:disabled {{color:{c['muted']}; background:{c['tint']};}}
      QPushButton, QComboBox {{
          background:{c['tint']}; color:{c['text']};
          border:1px solid {c['border']}; border-radius:9px;
          padding:10px 14px; font-weight:650;
      }}
      QPushButton#PrimaryButton, QPushButton#FusionPrimary {{
          background:{c['accent']}; color:{c['onaccent']};
          font-weight:800; border:1px solid {c['accent']};
      }}
      QPushButton#FusionSecondary {{background:{c['panel']};
          color:{c['accent']}; border:1px solid {c['accent']};}}
      QPushButton:disabled {{
          color:{c['muted']}; background:{c['tint']};
          border:1px solid {c['border']};
      }}
      QPushButton:hover:enabled {{border:1px solid {c['accent']};}}
      QPushButton:pressed:enabled {{padding-top:11px; padding-bottom:9px;}}
      QTableWidget, QTableWidget#FusionActivityTable {{
          background:{c['panel']}; alternate-background-color:{c['surface']};
          color:{c['text']}; border:0px; gridline-color:{c['border']};
          selection-background-color:{c['selection']};
      }}
      QHeaderView::section {{
          background:{c['surface']}; color:{c['muted']};
          border:none; border-bottom:1px solid {c['border']};
          padding:8px 9px; font-weight:700;
      }}
      QScrollBar:vertical {{background:{c['bg']}; width:8px;}}
      QScrollBar::handle:vertical {{background:{c['border']}; border-radius:4px; min-height:24px;}}
      QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{height:0px;}}
      QToolTip {{background:{c['surface']}; color:{c['text']};
          border:1px solid {c['border']}; padding:6px;}}
    """


def activity_by_block(snapshot: WalletReadSnapshot | None) -> tuple[tuple[int, int, int], ...]:
    """Plot only CONFIRMED scanner history: (height, credits, debits).

    No synthetic balance reconstruction, spot price, graph interpolation or
    pseudo security score. Rows are verified by the normal wallet read gate.
    """
    if snapshot is None:
        return ()
    if (type(snapshot) is not WalletReadSnapshot or snapshot.synthetic_rpc or
            snapshot.chain != "regtest" or snapshot.mainnet_allowed):
        raise ValueError("FUSION_HISTORY_UNVERIFIED_DENIED")
    blocks: dict[int, list[int]] = {}
    for row in snapshot.history:
        if (type(row.block_height) is not int
                or not 1 <= row.block_height <= snapshot.height
                or type(row.confirmations) is not int or row.confirmations <= 0
                or type(row.credit_atoms) is not int or row.credit_atoms < 0
                or type(row.debit_atoms) is not int or row.debit_atoms < 0):
            raise ValueError("FUSION_HISTORY_UNVERIFIED_DENIED")
        agg = blocks.setdefault(row.block_height, [0, 0])
        agg[0] += row.credit_atoms
        agg[1] += row.debit_atoms
    return tuple((height, *blocks[height]) for height in sorted(blocks)[-14:])


class ChainActivity(QWidget):
    """A truthful chart of confirmed WAM credits/debits grouped by block."""
    def __init__(self):
        super().__init__()
        self._activity: tuple[tuple[int, int, int], ...] = ()
        self._mode = "dark"
        self.setMinimumHeight(155)

    def render_snapshot(self, snapshot: WalletReadSnapshot | None) -> None:
        self._activity = activity_by_block(snapshot)
        self.update()

    def set_theme(self, mode: str) -> None:
        fusion_palette(mode)
        self._mode = mode
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = fusion_palette(self._mode)
        w, h = max(1, self.width()), max(1, self.height())
        if not self._activity:
            painter.setPen(QColor(c["chart_empty"]))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "No confirmed activity at the verified chain tip")
            return
        left, top, right, bottom = 28, 16, w-16, h-26
        if right <= left or bottom <= top:
            return
        painter.setPen(QPen(QColor(c["grid"]), 1))
        for fraction in (0.25, 0.5, 0.75, 1):
            y = bottom-(bottom-top)*fraction
            painter.drawLine(left, int(y), right, int(y))
        max_atoms = max(max(credit, debit) for _, credit, debit in self._activity)
        if max_atoms <= 0:
            painter.setPen(QColor(c["chart_empty"]))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "No incoming or outgoing value in confirmed history")
            return
        count = len(self._activity)
        span = (right-left)/max(count, 1)
        width = min(26.0, max(4.0, span*0.26))
        painter.setPen(Qt.PenStyle.NoPen)
        for i, (height, credit, debit) in enumerate(self._activity):
            center = left + span * (i+0.5)
            scale = bottom - top - 10
            for x_offset, atoms, color in (
                (-width*0.55, credit, c["accent"]),
                (width*0.55, debit, c["blue"]),
            ):
                if atoms <= 0:
                    continue
                bar_height = max(3.0, scale*(atoms/max_atoms))
                painter.setBrush(QColor(color))
                painter.drawRoundedRect(
                    QRectF(center+x_offset-width/2, bottom-bar_height, width, bar_height), 3, 3)
            painter.setPen(QColor(c["muted"]))
            if count < 10 or i % 2 == 0:
                painter.drawText(QRectF(center-span/2, bottom+3, span, 20),
                                 Qt.AlignmentFlag.AlignHCenter, str(height))
            painter.setPen(Qt.PenStyle.NoPen)
        painter.end()


def _card_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("FusionCardTitle")
    return label


def _muted(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("FusionMuted")
    label.setWordWrap(True)
    return label


def fusion_nav_icons(tone: str) -> tuple[QIcon, ...]:
    """One outline-geometry icon set for both native Qt platforms."""
    color = QColor(tone)
    if not color.isValid():
        raise ValueError("FUSION_ICON_COLOR_DENIED")
    icons = []
    for index in range(6):
        pix = QPixmap(40, 40)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(color, 2.4, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if index == 0:  # Overview home
            painter.drawPolyline(QPolygonF([QPointF(7,19),QPointF(20,8),QPointF(33,19)]))
            painter.drawLine(11,17,11,32);painter.drawLine(29,17,29,32)
            painter.drawLine(11,32,29,32)
            painter.drawRect(18,24,5,8)
        elif index == 1:  # Receive
            painter.drawLine(20,7,20,27)
            painter.drawLine(12,19,20,27);painter.drawLine(28,19,20,27)
            painter.drawLine(8,32,32,32)
        elif index == 2:  # History
            painter.drawEllipse(8,8,24,24)
            painter.drawLine(20,13,20,21);painter.drawLine(20,21,26,25)
        elif index == 3:  # Send
            painter.drawPolygon(QPolygonF([QPointF(6,18),QPointF(34,8),
                                           QPointF(25,34),QPointF(19,23),QPointF(6,18)]))
            painter.drawLine(19,23,34,8)
        elif index == 4:  # Security
            painter.drawPolygon(QPolygonF([QPointF(20,6),QPointF(31,12),
                                           QPointF(30,24),QPointF(20,34),
                                           QPointF(10,24),QPointF(9,12),QPointF(20,6)]))
            painter.drawLine(15,20,19,24);painter.drawLine(19,24,26,16)
        else:  # Settings
            painter.drawEllipse(11,11,18,18);painter.drawEllipse(17,17,6,6)
            for a,b,cc,dd in ((20,5,20,10),(20,30,20,35),
                               (5,20,10,20),(30,20,35,20),
                               (9,9,12,12),(28,28,31,31),
                               (9,31,12,28),(28,12,31,9)):
                painter.drawLine(a,b,cc,dd)
        painter.end()
        icons.append(QIcon(pix))
    return tuple(icons)


class FusionOverview(QScrollArea):
    """Overview visible on BOTH platforms and both read-only/full wallets."""
    def __init__(self):
        super().__init__()
        self.setObjectName("FusionScroll")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidgetResizable(True)
        root = QWidget()
        root.setObjectName("FusionInner")
        self.setWidget(root)
        whole = QVBoxLayout(root)
        whole.setContentsMargins(4, 3, 12, 10)
        whole.setSpacing(14)
        header = QHBoxLayout()
        title = QLabel("Overview")
        title.setObjectName("PageTitle")
        header.addWidget(title)
        header.addStretch()
        self.live_badge = _muted("●  AWAITING VERIFIED CORE")
        header.addWidget(self.live_badge)
        whole.addLayout(header)

        top = QHBoxLayout()
        top.setSpacing(14)
        hero = QFrame()
        hero.setObjectName("FusionHero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(23, 19, 23, 19)
        hero_layout.setSpacing(10)
        kicker = QLabel("TOTAL CONFIRMED BALANCE  ·  REGTEST")
        kicker.setObjectName("FusionKicker")
        hero_layout.addWidget(kicker)
        self.balance_value = QLabel("—")
        self.balance_value.setObjectName("FusionBalance")
        self.balance_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        hero_layout.addWidget(self.balance_value)
        self.utxo_details = _muted("Awaiting verified Core/WSP chain state")
        hero_layout.addWidget(self.utxo_details)
        self.pending_note = _muted("Pending and fiat valuation are not available from the verified read model")
        hero_layout.addWidget(self.pending_note)
        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.go_receive = QPushButton("↓  Receive")
        self.go_receive.setObjectName("FusionPrimary")
        self.go_send = QPushButton("↗  Send")
        self.go_send.setObjectName("FusionSecondary")
        self.go_send.setEnabled(False)
        actions.addWidget(self.go_receive)
        actions.addWidget(self.go_send)
        actions.addStretch()
        hero_layout.addLayout(actions)
        top.addWidget(hero, 3)

        status = QFrame()
        status.setObjectName("FusionPanel")
        right = QVBoxLayout(status)
        right.setContentsMargins(18, 17, 18, 17)
        right.setSpacing(10)
        right.addWidget(_card_title("Wallet Health"))
        self.core_status = _muted("Core  ·  Not verified")
        self.scanner_status = _muted("Scanner  ·  Awaiting sync")
        self.vault_status = _muted("Custody  ·  Not attested")
        for item in (self.core_status, self.scanner_status, self.vault_status):
            right.addWidget(item)
        right.addStretch()
        top.addWidget(status, 2)
        whole.addLayout(top)

        middle = QHBoxLayout()
        middle.setSpacing(14)
        chart_card = QFrame()
        chart_card.setObjectName("FusionPanel")
        chart_layout = QVBoxLayout(chart_card)
        chart_layout.setContentsMargins(18, 16, 18, 14)
        chart_layout.addWidget(_card_title("Confirmed On-chain Activity"))
        chart_layout.addWidget(_muted("Actual WAM credits (gold) / debits (blue), by confirmed block"))
        self.chart = ChainActivity()
        chart_layout.addWidget(self.chart)
        middle.addWidget(chart_card, 3)

        evidence = QFrame()
        evidence.setObjectName("FusionPanel")
        ev = QVBoxLayout(evidence)
        ev.setContentsMargins(18, 16, 18, 16)
        ev.addWidget(_card_title("Privacy & Security"))
        self.security_note = _muted(
            "No arbitrary security rating. Status reflects only live Core/WSP and wallet lock state.")
        ev.addWidget(self.security_note)
        self.evidence_text = _muted("No verified blockchain snapshot yet")
        ev.addWidget(self.evidence_text)
        ev.addStretch()
        middle.addWidget(evidence, 2)
        whole.addLayout(middle)

        bottom = QHBoxLayout()
        bottom.setSpacing(14)
        activity_card = QFrame()
        activity_card.setObjectName("FusionPanel")
        activity = QVBoxLayout(activity_card)
        activity.setContentsMargins(18, 16, 18, 16)
        activity.addWidget(_card_title("Recent Confirmed Transactions"))
        self.activity_table = QTableWidget(0, 4)
        self.activity_table.setObjectName("FusionActivityTable")
        self.activity_table.setHorizontalHeaderLabels(("Type", "Block", "Status", "Amount (WAM)"))
        self.activity_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.activity_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.activity_table.setAlternatingRowColors(True)
        self.activity_table.verticalHeader().setVisible(False)
        self.activity_table.horizontalHeader().setStretchLastSection(True)
        self.activity_table.setMinimumHeight(173)
        activity.addWidget(self.activity_table)
        bottom.addWidget(activity_card, 3)

        quick = QFrame()
        quick.setObjectName("FusionPanel")
        quick_layout = QVBoxLayout(quick)
        quick_layout.setContentsMargins(18, 16, 18, 16)
        quick_layout.addWidget(_card_title("Quick Actions"))
        self.open_history = QPushButton("◷  Transaction History")
        self.open_security = QPushButton("◇  Security & Backup")
        self.open_security.setEnabled(False)
        self.manual_sync = QPushButton("↻  Sync verified chain")
        for btn in (self.open_history, self.open_security, self.manual_sync):
            quick_layout.addWidget(btn)
        quick_layout.addStretch()
        bottom.addWidget(quick, 2)
        whole.addLayout(bottom)
        whole.addStretch()

    def set_theme(self, mode: str) -> None:
        self.chart.set_theme(mode)

    def render_snapshot(self, snap: WalletReadSnapshot | None, *, locked: bool = False,
                        operational: bool = False) -> None:
        # No caller may show a cached balance before the underlying read path
        # authorizes the snapshot. On a fault/lock all sensitive values clear.
        if snap is None or locked:
            self.balance_value.setText("—")
            self.utxo_details.setText("No verified spendable snapshot")
            self.live_badge.setText("●  LOCKED / NOT VERIFIED" if locked else "●  NOT SYNCED")
            self.core_status.setText("Core  ·  Not verified")
            self.scanner_status.setText("Scanner  ·  Not verified")
            self.vault_status.setText("Custody  ·  Locked" if locked else "Custody  ·  Not attested")
            self.evidence_text.setText("Refresh from the real REGTEST node to display verified details")
            self.activity_table.setRowCount(0)
            self.chart.render_snapshot(None)
            return
        if (type(snap) is not WalletReadSnapshot or snap.chain != "regtest"
                or snap.synthetic_rpc or snap.mainnet_allowed):
            raise ValueError("FUSION_UNTRUSTED_SNAPSHOT_DENIED")
        self.balance_value.setText(format_wam(snap.confirmed_atoms, grouped=True)+" WAM")
        self.utxo_details.setText(
            f"{snap.confirmed_utxos} confirmed UTXO(s)  ·  Verified block {snap.height}")
        self.live_badge.setText("●  REGTEST VERIFIED")
        self.core_status.setText(f"Core  ·  Verified tip {snap.height}")
        self.scanner_status.setText("Scanner  ·  Synced to Core tip")
        self.vault_status.setText(
            "Custody  ·  Operational test wallet" if operational else "Custody  ·  Read-only test account")
        self.evidence_text.setText(
            "Chain: REGTEST only\nVerified tip: "+snap.tip[:16]+"…\n"
            "Core identity: "+snap.core_sha256[:14]+"…\n"
            "No unverified security score or privacy guarantees")
        self.chart.render_snapshot(snap)
        self.activity_table.setRowCount(min(6, len(snap.history)))
        for n, tx in enumerate(snap.history[:6]):
            incoming = tx.credit_atoms > 0 and tx.debit_atoms == 0
            outgoing = tx.debit_atoms > 0 and tx.credit_atoms == 0
            kind = "Received" if incoming else "Sent" if outgoing else "Activity"
            amount = tx.credit_atoms - tx.debit_atoms
            values = (kind, str(tx.block_height), f"Confirmed ({tx.confirmations})",
                      ("+" if amount > 0 else "") + ("-" if amount < 0 else "") +
                      format_wam(abs(amount)))
            for i, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(tx.txid)
                if i == 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.activity_table.setItem(n, i, item)
