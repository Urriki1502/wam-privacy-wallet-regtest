"""Fusion Black & Gold Qt presentation: verified snapshots, never wallet authority."""
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QPointF, QSize, Signal, Property, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import (
    QColor, QPainter, QPen, QIcon, QPixmap, QPolygonF, QLinearGradient,
    QPainterPath, QFont, QFontMetrics, QRadialGradient,
)
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QWidget, QToolTip, QSizePolicy, QTableWidget, QTableWidgetItem,
    QPlainTextEdit, QCheckBox, QToolButton, QButtonGroup,
)
from .wallet_read import WalletReadSnapshot, format_wam
from .branding import brand_image
from .fusion_motion import motion_reduced, slide_geometry, fade_widget, CHART_MS, StatusGlyph
from .fusion_status import classify

SPACING = (4, 8, 12, 16, 24, 32)
TYPE = {'display': 48, 'heading': 26, 'section': 17, 'body': 14, 'caption': 12}
FUSION_NAV_PAGES = (
    ('Overview', 'overview'),
    ('Receive', 'receive'),
    ('History', 'history'),
    ('Send', 'send'),
    ('Security', 'security'),
    ('Network', 'network'),
    ('Settings', 'settings'),
)


def fusion_palette(mode):
    if mode == 'dark':
        return dict(
            bg='#0B0B0D', surface='#141416', panel='#1C1C20', text='#F7F4EC',
            muted='#B7B1A4', border='#2F2A22', tint='#1F1C16', accent='#E0C36A',
            onaccent='#1A1406', warning='#3A3018', warning_text='#F1C77D',
            green='#3DDC97', blue='#7EB6FF', red='#FF8B8F', hero_bottom='#1A150C',
            selection='#3A3018', grid='#3A342C', chart_empty='#8E8A80',
            hover='#24221C', sidebar='#09090B', success='#3DDC97',
            pending='#E5BE79', error='#FF8B8F', focus='#E0C36A', shadow='#000000',
            brand='#E8C98A', segment='#1A1814')
    if mode == 'light':
        return dict(
            bg='#F6F3EC', surface='#FFFFFF', panel='#F3EEE3', text='#1C1914',
            muted='#6A6458', border='#E4DCC8', tint='#EFE6D4', accent='#7A5A12',
            onaccent='#FFF8E8', warning='#FFF4D8', warning_text='#80561A',
            green='#0F7A52', blue='#1666CC', red='#B8424C', hero_bottom='#F4EBD6',
            selection='#F0E2BE', grid='#E4DCC8', chart_empty='#8E8A80',
            hover='#E8DCC3', sidebar='#F4EFE4', success='#0F7A52',
            pending='#91601D', error='#B8424C', focus='#7A5A12', shadow='#E8E0D0',
            brand='#9B742E', segment='#E9E1CF')
    raise ValueError('FUSION_THEME_DENIED')


def fusion_stylesheet(mode):
    c = fusion_palette(mode)
    return f"""
    QMainWindow,QWidget#WalletRoot,QDialog,QMessageBox,QInputDialog {{
        background:{c['bg']};color:{c['text']};
    }}
    QWidget {{font-size:14px;}}
    QFrame#FusionSidebar {{background:{c['sidebar']};border-right:1px solid {c['border']};}}
    QFrame#FusionTopbar {{background:{c['bg']};border-bottom:1px solid {c['border']};}}
    QFrame#FusionPanel,QFrame#ContentCard,QFrame#HeaderCard,QDialog#FusionApproval,QDialog#FusionPanel {{
        background:{c['surface']};border:1px solid {c['border']};border-radius:18px;
    }}
    QFrame#FusionInset {{background:{c['panel']};border:1px solid {c['border']};border-radius:14px;}}
    QFrame#FusionHero {{background:transparent;}}
    QFrame#FusionSegmented {{background:{c['segment']};border:1px solid {c['border']};border-radius:12px;}}
    QToolButton#FusionSegment {{background:transparent;color:{c['muted']};border:0;border-radius:9px;padding:8px 12px;font-weight:600;}}
    QToolButton#FusionSegment:checked {{background:transparent;color:{c['onaccent']};}}
    QToolButton#FusionSegment:hover:!checked {{color:{c['text']};}}
    QToolButton#FusionAdvanced {{background:transparent;color:{c['accent']};border:0;text-align:left;padding:10px;font-weight:600;}}
    QToolButton#FusionQuick {{
        background:{c['surface']};color:{c['text']};border:1px solid {c['border']};
        border-radius:14px;padding:12px 14px;font-weight:600;text-align:left;
    }}
    QToolButton#FusionQuick:hover:enabled {{border:1px solid {c['accent']};background:{c['hover']};}}
    QToolButton#FusionQuick:disabled {{color:{c['muted']};}}
    QFrame#FusionThemeThumb {{background:{c['accent']};border:0;border-radius:10px;}}
    QFrame#FusionDimmer {{background:rgba(12,12,14,0.38);border:0;}}
    QFrame#FusionFlyout {{
        background:{c['surface']};border:1px solid {c['border']};border-radius:18px;
    }}
    QWidget#FusionInner,QScrollArea#FusionScroll,QWidget#FusionTransparent {{background:transparent;border:0;}}
    QLabel {{color:{c['text']};background:transparent;border:0;}}
    QLabel#BrandTitle {{font-size:18px;font-weight:700;letter-spacing:0.2px;color:{c['brand']};}}
    QLabel#PageTitle {{font-size:28px;font-weight:700;}}
    QLabel#FusionBalance,QLabel#BalanceValue {{font-size:48px;font-weight:700;color:{c['text']};letter-spacing:-0.8px;}}
    QLabel#FusionDenom {{font-size:22px;font-weight:700;color:{c['brand']};}}
    QLabel#FusionKicker {{font-size:11px;font-weight:600;color:{c['muted']};letter-spacing:0.8px;}}
    QLabel#FusionCardTitle {{font-size:16px;font-weight:600;}}
    QLabel#FusionCardValue {{font-size:20px;font-weight:600;}}
    QLabel#FusionMuted,QLabel#SecondaryLabel,QLabel#StatusText,QLabel#FusionEmpty {{color:{c['muted']};font-size:13px;}}
    QLabel#FusionVerified {{color:{c['green']};font-weight:600;}}
    QLabel#FusionInfo {{color:{c['blue']};}}
    QLabel#FusionGold {{color:{c['warning_text']};font-weight:600;}}
    QLabel#FusionBadge {{color:{c['onaccent']};background:{c['accent']};border:0;border-radius:10px;padding:5px 10px;font-size:11px;font-weight:700;}}
    QLabel#Warning {{color:{c['warning_text']};background:{c['warning']};border-radius:9px;padding:10px;min-height:64px;font-size:11px;}}
    QLabel#ReceiveCode,QPlainTextEdit#ReceiveCode {{
        font-size:14px;background:{c['panel']};border:1px solid {c['border']};border-radius:12px;padding:16px;
    }}
    QListWidget {{background:transparent;color:{c['muted']};border:0;padding:2px;font-size:14px;outline:0;}}
    QListWidget::item {{padding:9px 12px;border-radius:11px;margin:2px 0;}}
    QListWidget::item:selected {{background:{c['accent']};color:{c['onaccent']};font-weight:700;}}
    QListWidget::item:hover:!selected {{background:{c['hover']};color:{c['text']};}}
    QLineEdit,QTextEdit,QPlainTextEdit {{
        background:{c['panel']};color:{c['text']};selection-background-color:{c['selection']};
        border:1px solid {c['border']};border-radius:12px;padding:12px;
    }}
    QLineEdit:focus,QPushButton:focus,QComboBox:focus,QToolButton:focus {{border:2px solid {c['focus']};}}
    QLineEdit:disabled {{color:{c['muted']};background:{c['bg']};}}
    QPushButton,QComboBox {{
        background:{c['tint']};color:{c['text']};border:1px solid {c['border']};
        border-radius:12px;padding:12px 17px;font-weight:600;
    }}
    QPushButton#PrimaryButton,QPushButton#FusionPrimary {{
        background:{c['accent']};color:{c['onaccent']};border:1px solid {c['accent']};
    }}
    QPushButton#FusionSecondary {{background:{c['tint']};color:{c['text']};border:1px solid {c['border']};}}
    QPushButton#FusionDestructive {{background:{c['surface']};color:{c['red']};border:1px solid {c['border']};}}
    QPushButton:hover:enabled,QComboBox:hover {{background:{c['hover']};border:1px solid {c['focus']};}}
    QPushButton#FusionPrimary:hover:enabled,QPushButton#PrimaryButton:hover:enabled {{
        background:{c['brand']};border:1px solid {c['onaccent']};
    }}
    QPushButton:pressed:enabled {{background:{c['selection']};}}
    QPushButton#FusionPrimary:disabled,QPushButton#PrimaryButton:disabled,
    QPushButton#FusionSecondary:disabled,QPushButton#FusionDestructive:disabled,QPushButton:disabled {{
        background:{c['panel']};color:{c['muted']};border:1px solid {c['border']};
    }}
    QComboBox::drop-down {{border:0;width:22px;}}
    QComboBox QAbstractItemView {{
        background:{c['surface']};color:{c['text']};selection-background-color:{c['selection']};
        border:1px solid {c['border']};
    }}
    QCheckBox {{color:{c['text']};spacing:8px;}}
    QCheckBox::indicator {{width:17px;height:17px;border:1px solid {c['muted']};border-radius:4px;background:{c['panel']};}}
    QCheckBox::indicator:checked {{background:{c['accent']};border:1px solid {c['accent']};}}
    QTableWidget,QTableWidget#FusionActivityTable {{
        background:{c['surface']};alternate-background-color:{c['surface']};color:{c['text']};
        border:0;gridline-color:{c['border']};selection-background-color:{c['selection']};selection-color:{c['text']};
    }}
    QTableWidget::item {{padding:10px;border-bottom:1px solid {c['border']};}}
    QTableWidget::item:selected {{background:{c['selection']};color:{c['text']};}}
    QHeaderView::section {{
        background:{c['surface']};color:{c['muted']};border:0;border-bottom:1px solid {c['border']};
        padding:10px;font-size:12px;font-weight:600;
    }}
    QProgressBar:horizontal {{background:{c['panel']};border:1px solid {c['border']};border-radius:8px;min-height:6px;max-height:6px;}}
    QProgressBar::chunk {{background:{c['accent']};border-radius:4px;}}
    QScrollBar:vertical {{background:transparent;width:7px;}}
    QScrollBar::handle:vertical {{background:{c['border']};border-radius:3px;min-height:30px;}}
    QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{height:0;}}
    QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {{background:transparent;}}
    QToolTip {{background:{c['surface']};color:{c['text']};border:1px solid {c['border']};padding:8px;}}
    """


class StateSwitch(QCheckBox):
    """Two-position visual switch retaining Qt checkbox focus/key semantics."""
    def sizeHint(self):
        return QSize(self.fontMetrics().horizontalAdvance(self.text()) + 68, 34)

    def hitButton(self, position):
        return self.rect().contains(position)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            painter.setOpacity(0.45)
        mode = self.property('fusion_mode') or 'dark'
        colors = fusion_palette(mode if mode in ('dark', 'light') else 'dark')
        track = QRectF(2, (self.height() - 24) / 2, 46, 24)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colors['green'] if self.isChecked() else colors['border']))
        painter.drawRoundedRect(track, 12, 12)
        painter.setBrush(QColor(colors['onaccent'] if self.isChecked() else colors['text']))
        painter.drawEllipse(QRectF(28 if self.isChecked() else 6, track.y() + 4, 16, 16))
        painter.setPen(QColor(colors['text']))
        painter.drawText(QRectF(58, 0, self.width() - 58, self.height()),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(colors['focus']), 1))
            painter.drawRoundedRect(track.adjusted(-1, -1, 1, 1), 13, 13)


class ThemeSlider(QFrame):
    """Three-position Automatic / Light / Dark control with a sliding thumb."""
    currentChanged = Signal(int)

    def __init__(self, *, compact=False):
        super().__init__()
        self.setObjectName('FusionSegmented')
        self.setAccessibleName('Appearance: Automatic, Light or Dark')
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._index = 0
        self._compact = compact
        self._move = None
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(0)
        self._indicator = QFrame(self)
        self._indicator.setObjectName('FusionThemeThumb')
        self._indicator.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        for index, (icon, title) in enumerate((('auto', 'Automatic'), ('sun', 'Light'), ('moon', 'Dark'))):
            button = QToolButton()
            button.setObjectName('FusionSegment')
            button.setCheckable(True)
            button.setAutoRaise(True)
            button.setText('' if compact else title)
            button.setToolTip(title)
            button.setAccessibleName(title + ' appearance')
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            button.setProperty('fusion_icon', icon)
            button.setToolButtonStyle(
                Qt.ToolButtonStyle.ToolButtonIconOnly if compact
                else Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.setMinimumWidth(36 if compact else 96)
            self.group.addButton(button, index)
            self.buttons.append(button)
            layout.addWidget(button, 1)
        self.buttons[0].setChecked(True)
        self.group.idClicked.connect(self._clicked)
        self.setFixedHeight(36 if compact else 42)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        if compact:
            self.setFixedWidth(138)
        else:
            self.setMaximumWidth(420)

    def currentIndex(self):
        return self._index

    def setCurrentIndex(self, index, animate=True):
        if index not in (0, 1, 2):
            return
        block = self.group.blockSignals(True)
        self.buttons[index].setChecked(True)
        self.group.blockSignals(block)
        self._slide(index, animate=animate)
        if index != self._index:
            self._index = index
            self.currentChanged.emit(index)

    def _clicked(self, index):
        self._slide(index, animate=True)
        if index != self._index:
            self._index = index
            self.currentChanged.emit(index)

    def _thumb_rect(self, index):
        return self.buttons[index].geometry().adjusted(2, 2, -2, -2)

    def _slide(self, index, animate=True):
        rect = self._thumb_rect(index)
        if self._move is not None:
            self._move.stop()
            self._move = None
        if not animate or motion_reduced(self):
            self._indicator.setGeometry(rect)
            return
        self._move = slide_geometry(self._indicator, rect, parent=self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._indicator.setGeometry(self._thumb_rect(self._index))
        self._indicator.lower()
        for button in self.buttons:
            button.raise_()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Home, Qt.Key.Key_End):
            if event.key() == Qt.Key.Key_Left:
                index = max(0, self._index - 1)
            elif event.key() == Qt.Key.Key_Right:
                index = min(2, self._index + 1)
            elif event.key() == Qt.Key.Key_Home:
                index = 0
            else:
                index = 2
            self.setCurrentIndex(index)
            event.accept()
            return
        super().keyPressEvent(event)


class ReadableText(QPlainTextEdit):
    """Selectable exact plaintext with genuine wrap-anywhere; no hidden characters."""
    def __init__(self, text=''):
        super().__init__()
        from PySide6.QtGui import QTextOption, QFontDatabase
        self.setReadOnly(True)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAnywhere)
        families = set(QFontDatabase.families())
        family = next((f for f in ('Menlo', 'Consolas', 'Courier New') if f in families), None)
        self.setFont(QFont(family, 10) if family else QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setPlainText(text)
        self._fit()

    def text(self):
        return self.toPlainText()

    def setText(self, text):
        if text != self.toPlainText():
            self.setPlainText(text)
        self._fit()

    def _fit(self):
        import math
        fm = self.fontMetrics()
        width = max(80, self.viewport().width() - 28)
        lines = sum(max(1, math.ceil(fm.horizontalAdvance(line) / width)) for line in self.toPlainText().split('\n'))
        self.setFixedHeight(min(340, max(100, lines * fm.lineSpacing() + 64)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit()

    def minimumSizeHint(self):
        return QSize(0, 68)


def label(text='', role='FusionMuted', selectable=False):
    if role == 'ReceiveCode':
        obj = ReadableText(text)
        obj.setObjectName(role)
        return obj
    obj = QLabel(text)
    obj.setObjectName(role)
    obj.setWordWrap(role not in ('FusionKicker', 'FusionBadge'))
    obj.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
    if role in ('FusionCardTitle', 'FusionCardValue', 'FusionMuted', 'FusionBalance', 'BalanceValue'):
        obj.setMinimumWidth(0)
    if role in ('FusionCardTitle', 'FusionCardValue'):
        obj.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        obj.setWordWrap(True)
    if role in ('FusionBalance', 'BalanceValue'):
        obj.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        obj.setMinimumHeight(56)
        obj.setWordWrap(True)
    if role == 'FusionDenom':
        obj.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)
    if role == 'FusionBadge':
        obj.setFixedHeight(28)
        obj.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    if selectable:
        obj.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return obj


def panel(title=None, subtitle=None, *, inset=False):
    obj = QFrame()
    obj.setObjectName('FusionInset' if inset else 'FusionPanel')
    layout = QVBoxLayout(obj)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(12)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    if title:
        layout.addWidget(label(title, 'FusionCardTitle'))
    if subtitle:
        layout.addWidget(label(subtitle))
    return obj, layout


def page(title, subtitle, kicker='WAM FUSION / REGTEST'):
    scroll = QScrollArea()
    scroll.setObjectName('FusionScroll')
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidgetResizable(True)
    root = QWidget()
    root.setObjectName('FusionInner')
    scroll.setWidget(root)
    layout = QVBoxLayout(root)
    layout.setContentsMargins(4, 4, 12, 16)
    layout.setSpacing(20)
    layout.addWidget(label(kicker, 'FusionKicker'))
    layout.addWidget(label(title, 'PageTitle'))
    layout.addWidget(label(subtitle))
    return scroll, layout


def action(text, icon, primary=False):
    button = QPushButton(text)
    button.setProperty('fusion_icon', icon)
    button.setObjectName('FusionPrimary' if primary else 'FusionSecondary')
    button.setIconSize(QSize(18, 18))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def quick_action(text, icon):
    button = QToolButton()
    button.setObjectName('FusionQuick')
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    button.setProperty('fusion_icon', icon)
    button.setText(text)
    button.setIconSize(QSize(18, 18))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    button.setMinimumHeight(48)
    return button


_NAMES = tuple(name for _, name in FUSION_NAV_PAGES)


def vector_icon(name, tone, dpr=2):
    """One original outline geometry family, rasterized at device resolution."""
    color = QColor(tone)
    if not color.isValid():
        raise ValueError('FUSION_ICON_COLOR_DENIED')
    pix = QPixmap(int(24 * dpr), int(24 * dpr))
    pix.setDevicePixelRatio(dpr)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(color, 1.65, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)

    def line(a, b, c, d):
        p.drawLine(QPointF(a, b), QPointF(c, d))

    if name in ('overview', 'home'):
        p.drawPolygon(QPolygonF([QPointF(12, 3), QPointF(21, 11), QPointF(21, 21), QPointF(3, 21), QPointF(3, 11)]))
        p.drawRect(QRectF(9, 14, 6, 7))
    elif name in ('receive', 'send'):
        if name == 'receive':
            line(12, 3, 12, 16); line(7, 11, 12, 16); line(17, 11, 12, 16); line(4, 20, 20, 20)
        else:
            p.drawPolygon(QPolygonF([QPointF(3, 10), QPointF(21, 3), QPointF(14, 21), QPointF(10, 14)]))
            line(10, 14, 21, 3)
    elif name == 'history':
        p.drawEllipse(QRectF(4, 4, 16, 16)); line(12, 7, 12, 12); line(12, 12, 16, 14)
    elif name in ('security', 'anchor'):
        p.drawPolygon(QPolygonF([QPointF(12, 3), QPointF(20, 7), QPointF(19, 16), QPointF(12, 21), QPointF(5, 16), QPointF(4, 7)]))
        line(8, 12, 11, 15); line(11, 15, 16, 9)
    elif name == 'settings':
        p.drawEllipse(QRectF(6, 6, 12, 12)); p.drawEllipse(QRectF(10, 10, 4, 4))
        for a, b, c, d in ((12, 2, 12, 5), (12, 19, 12, 22), (2, 12, 5, 12), (19, 12, 22, 12),
                           (4, 4, 6, 6), (18, 18, 20, 20), (4, 20, 6, 18), (18, 6, 20, 4)):
            line(a, b, c, d)
    elif name == 'network':
        p.drawEllipse(QRectF(9, 3, 6, 6)); p.drawEllipse(QRectF(3, 15, 6, 6)); p.drawEllipse(QRectF(15, 15, 6, 6))
        line(12, 9, 6, 15); line(12, 9, 18, 15)
    elif name == 'copy':
        p.drawRoundedRect(QRectF(8, 8, 12, 13), 2, 2); line(4, 16, 4, 3); line(4, 3, 16, 3)
    elif name in ('lock', 'unlock'):
        p.drawRoundedRect(QRectF(5, 10, 14, 11), 2, 2)
        p.drawArc(QRectF(8, 3, 8, 12), 0 if name == 'lock' else 20 * 16, 180 * 16)
        line(12, 14, 12, 17)
    elif name == 'backup':
        p.drawRoundedRect(QRectF(4, 4, 16, 17), 2, 2); line(8, 4, 8, 10); line(8, 10, 16, 10); line(16, 10, 16, 4); p.drawRect(QRectF(8, 15, 8, 6))
    elif name == 'sync':
        p.drawArc(QRectF(4, 4, 16, 16), 35 * 16, 260 * 16); line(19, 3, 20, 9); line(20, 9, 14, 8)
    elif name == 'core':
        p.drawRoundedRect(QRectF(6, 6, 12, 12), 2, 2); p.drawRect(QRectF(10, 10, 4, 4))
    elif name == 'wallet':
        p.drawRoundedRect(QRectF(3, 7, 18, 13), 2, 2); p.drawRoundedRect(QRectF(14, 11, 7, 5), 1.5, 1.5)
    elif name == 'chain':
        p.drawRoundedRect(QRectF(3, 8, 9, 6), 2, 2); p.drawRoundedRect(QRectF(12, 10, 9, 6), 2, 2)
    elif name == 'check':
        line(5, 12, 10, 17); line(10, 17, 20, 6)
    elif name == 'sun':
        p.drawEllipse(QRectF(9, 9, 6, 6))
        for a, b, c, d in ((12, 2, 12, 5), (12, 19, 12, 22), (2, 12, 5, 12), (19, 12, 22, 12),
                           (5, 5, 7, 7), (17, 17, 19, 19), (5, 19, 7, 17), (17, 7, 19, 5)):
            line(a, b, c, d)
    elif name == 'moon':
        crescent = QPainterPath()
        crescent.addEllipse(QRectF(5, 4, 14, 16))
        punch = QPainterPath()
        punch.addEllipse(QRectF(10, 5, 13, 14))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawPath(crescent.subtracted(punch))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(color, 1.65, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    elif name == 'auto':
        p.drawEllipse(QRectF(4, 4, 16, 16))
        p.setBrush(color)
        p.drawPie(QRectF(4, 4, 16, 16), 90 * 16, 180 * 16)
        p.setBrush(Qt.BrushStyle.NoBrush)
    else:
        p.drawEllipse(QRectF(5, 5, 14, 14)); line(12, 7, 12, 17); line(7, 12, 17, 12)
    p.end()
    return QIcon(pix)


def fusion_nav_icons(tone):
    return tuple(vector_icon(name, tone) for name in _NAMES)


def nav_icon_for(title, tone, dpr=2):
    lookup = dict(FUSION_NAV_PAGES)
    return vector_icon(lookup.get(title, 'overview'), tone, dpr)


def activity_by_block(snapshot):
    if snapshot is None:
        return ()
    if type(snapshot) is not WalletReadSnapshot or snapshot.synthetic_rpc or snapshot.chain != 'regtest' or snapshot.mainnet_allowed:
        raise ValueError('FUSION_HISTORY_UNVERIFIED_DENIED')
    blocks = {}
    for row in snapshot.history:
        if (type(row.block_height) is not int or not 1 <= row.block_height <= snapshot.height
                or type(row.confirmations) is not int or row.confirmations <= 0
                or type(row.credit_atoms) is not int or row.credit_atoms < 0
                or type(row.debit_atoms) is not int or row.debit_atoms < 0):
            raise ValueError('FUSION_HISTORY_UNVERIFIED_DENIED')
        agg = blocks.setdefault(row.block_height, [0, 0])
        agg[0] += row.credit_atoms
        agg[1] += row.debit_atoms
    return tuple((h, *blocks[h]) for h in sorted(blocks)[-14:])


def _deny_unverified_snapshot(snapshot):
    if snapshot is None:
        return None
    if (type(snapshot) is not WalletReadSnapshot or snapshot.synthetic_rpc
            or snapshot.chain != 'regtest' or snapshot.mainnet_allowed):
        raise ValueError('FUSION_HISTORY_UNVERIFIED_DENIED')
    if type(snapshot.confirmed_atoms) is not int or snapshot.confirmed_atoms < 0:
        raise ValueError('FUSION_HISTORY_UNVERIFIED_DENIED')
    if type(snapshot.height) is not int or snapshot.height < 0:
        raise ValueError('FUSION_HISTORY_UNVERIFIED_DENIED')
    for row in snapshot.history:
        if (type(row.block_height) is not int or not 1 <= row.block_height <= snapshot.height
                or type(row.confirmations) is not int or row.confirmations <= 0
                or type(row.credit_atoms) is not int or row.credit_atoms < 0
                or type(row.debit_atoms) is not int or row.debit_atoms < 0):
            raise ValueError('FUSION_HISTORY_UNVERIFIED_DENIED')
    return snapshot


def confirmed_balance_history(snapshot):
    """Oldest-to-newest (height, confirmed_atoms) from complete verified history.

    Empty when pagination, missing rows or inconsistent nets would require invention.
    """
    snapshot = _deny_unverified_snapshot(snapshot)
    if snapshot is None:
        return ()
    if snapshot.history_complete is not True or snapshot.history_offset != 0:
        return ()
    if not snapshot.history:
        return ((snapshot.height, 0),) if snapshot.confirmed_atoms == 0 else ()
    net = 0
    blocks = {}
    for row in snapshot.history:
        delta = row.credit_atoms - row.debit_atoms
        net += delta
        blocks[row.block_height] = blocks.get(row.block_height, 0) + delta
    if snapshot.confirmed_atoms - net != 0:
        return ()
    running = 0
    points = []
    first = min(blocks)
    if first > 1:
        points.append((first - 1, 0))
    for height in sorted(blocks):
        running += blocks[height]
        if running < 0:
            return ()
        points.append((height, running))
    if not points or points[-1][1] != snapshot.confirmed_atoms:
        return ()
    if points[-1][0] != snapshot.height:
        points.append((snapshot.height, snapshot.confirmed_atoms))
    return tuple(points)


class ResponsiveRow(QWidget):
    def __init__(self, *children, weights=None, breakpoint=760, min_side=0):
        super().__init__()
        self.setObjectName('FusionTransparent')
        self.setMinimumWidth(0)
        self._break = breakpoint
        self._min_side = min_side
        self._children = children
        self._weights = weights or [1] * len(children)
        self._vertical = None
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(18)

    def addWidget(self, widget, row=0, column=0):
        self._grid.addWidget(widget, row, column)
        return widget

    def resizeEvent(self, event):
        needed = self._break
        if self._min_side:
            needed = max(needed, self._min_side)
        vertical = self.width() < needed
        if vertical != self._vertical:
            self._vertical = vertical
            for i, child in enumerate(self._children):
                self._grid.addWidget(child, i if vertical else 0, 0 if vertical else i)
            for i, w in enumerate(self._weights):
                self._grid.setColumnStretch(i, 0 if vertical else w)
                self._grid.setRowStretch(i, w if vertical else 0)
        super().resizeEvent(event)


class FlowGrid(QWidget):
    """1/2/4 columns from actual width vs minimum readable card size."""

    def __init__(self, *children, min_item=220, max_columns=4):
        super().__init__()
        self.setObjectName('FusionTransparent')
        self.setMinimumWidth(0)
        self._children = children
        self._min_item = min_item
        self._max_columns = max_columns
        self._columns = None
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(12)
        for child in children:
            child.setMinimumWidth(0)
            child.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    def resizeEvent(self, event):
        usable = max(1, self.width())
        raw = max(1, min(self._max_columns, usable // max(1, self._min_item)))
        columns = 4 if raw >= 4 else 2 if raw >= 2 else 1
        if columns != self._columns:
            self._columns = columns
            for i, child in enumerate(self._children):
                self._grid.addWidget(child, i // columns, i % columns)
            for column in range(self._max_columns):
                self._grid.setColumnStretch(column, 1 if column < columns else 0)
        super().resizeEvent(event)


class StatusCard(QFrame):
    def __init__(self, title, caption):
        super().__init__()
        self.setObjectName('FusionPanel')
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)
        top = QHBoxLayout(); top.setSpacing(8)
        self.glyph = StatusGlyph()
        heading = label(title, 'FusionCardTitle')
        heading.setMinimumWidth(0)
        top.addWidget(self.glyph, 0, Qt.AlignmentFlag.AlignTop)
        top.addWidget(heading, 1)
        layout.addLayout(top)
        self.value = label('Not verified', 'FusionCardValue')
        self.detail = label(caption)
        self.detail.setWordWrap(True)
        self.detail.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout.addWidget(self.value)
        layout.addWidget(self.detail)

    def apply(self, state, title, detail, *, animate=True):
        self.glyph.set_state(state, animate=animate)
        self.value.setText(title)
        self.detail.setText(detail)

    def set_theme(self, mode):
        self.glyph.set_theme(mode)


class Hero(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName('FusionHero')
        self.mode = 'dark'
        self.logo = QPixmap(str(brand_image()))
        self.setMinimumHeight(148)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    def resizeEvent(self, event):
        layout = self.layout()
        compact = self.width() < 640
        self.setMinimumHeight(148 if compact else 176)
        if layout is not None:
            layout.setContentsMargins(22, 16, 16 if compact else 28, 16)
        for child in self.findChildren(BalanceHistoryChart):
            child.setVisible(self.width() >= 720)
        super().resizeEvent(event)

    def paintEvent(self, event):
        c = fusion_palette(self.mode)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 20, 20)
        p.setClipPath(path)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0, QColor(c['surface']))
        gradient.setColorAt(1, QColor(c['hero_bottom']))
        p.fillPath(path, gradient)
        glow = QRadialGradient(rect.right() - 90, rect.center().y(), 140)
        gold = QColor(c['accent']); gold.setAlpha(40 if self.mode == 'dark' else 28)
        glow.setColorAt(0, gold); glow.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(rect, glow)
        if self.width() >= 720:
            p.setOpacity(0.18 if self.mode == 'dark' else 0.12)
            p.setPen(QPen(QColor(c['accent']), 1))
            cx, cy = self.width() - 108, self.height() / 2
            for radius in (48, 72, 96, 124):
                p.drawEllipse(QPointF(cx, cy), radius, radius * 0.62)
        if self.width() >= 720:
            size = min(148, max(96, self.height() - 28))
            p.setOpacity(0.96)
            coin = self.logo.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(int(self.width() - size - 22), int((self.height() - coin.height()) / 2), coin)
        p.setOpacity(0.9); p.setClipping(False)
        p.setPen(QPen(QColor(c['accent']), 1))
        p.drawRoundedRect(rect, 20, 20)
        p.end()


class ChainActivity(QWidget):
    """Gross confirmed credits/debits: discrete block columns, exact hover data."""
    def __init__(self):
        super().__init__()
        self._activity = ()
        self._mode = 'dark'
        self._hit = []
        self._hover = -1
        self.setMinimumHeight(196)
        self.setMouseTracking(True)
        self.setAccessibleName('Confirmed on-chain credit and debit activity')

    def render_snapshot(self, snapshot):
        self._activity = activity_by_block(snapshot)
        self._hover = -1
        self._hit = []
        QToolTip.hideText()
        self.update()

    def set_theme(self, mode):
        fusion_palette(mode)
        self._mode = mode
        self.update()

    def mouseMoveEvent(self, event):
        index = next((i for i, r in enumerate(self._hit) if r.contains(event.position())), -1)
        if index != self._hover:
            self._hover = index
            self.update()
        if index >= 0:
            h, credit, debit = self._activity[index]
            QToolTip.showText(event.globalPosition().toPoint(),
                              f'Confirmed block {h}\nCredits  {format_wam(credit)} WAM\nDebits   {format_wam(debit)} WAM', self)
        else:
            QToolTip.hideText()

    def leaveEvent(self, event):
        self._hover = -1
        QToolTip.hideText()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = fusion_palette(self._mode)
        p.setFont(QFont(p.font().family(), 10))
        if not self._activity:
            p.setPen(QColor(c['chart_empty']))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       'No confirmed activity\nSync the verified chain to see credits and debits.')
            p.end()
            return
        left, top, right, bottom = 66., 20., self.width() - 16., self.height() - 37.
        maximum = max(max(a, b) for _, a, b in self._activity)
        if maximum <= 0:
            p.end()
            return
        quantum = 10 ** max(0, len(str(maximum)) - 1)
        ceiling = ((maximum + quantum - 1) // quantum) * quantum
        for j in range(5):
            value = ceiling * j // 4
            y = bottom - (bottom - top) * j / 4
            p.setPen(QPen(QColor(c['grid']), 1, Qt.PenStyle.DotLine))
            p.drawLine(QPointF(left, y), QPointF(right, y))
            p.setPen(QColor(c['muted']))
            amount = format_wam(value).rstrip('0').rstrip('.')
            p.drawText(QRectF(0, y - 8, left - 12, 18), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, amount)
        count = len(self._activity)
        span = (right - left) / count
        width = min(22., span * .21)
        self._hit = []
        for i, (height, credit, debit) in enumerate(self._activity):
            center = left + span * (i + .5)
            hit = QRectF(left + i * span, top, span, bottom - top)
            self._hit.append(hit)
            if i == self._hover:
                p.fillRect(hit, QColor(c['panel']))
            for x, atoms, color in ((center - width * .62, credit, c['green']), (center + width * .62, debit, c['blue'])):
                if atoms <= 0:
                    continue
                bh = (bottom - top) * atoms / ceiling
                r = QRectF(x - width / 2, bottom - bh, width, bh)
                gradient = QLinearGradient(r.topLeft(), r.bottomLeft())
                gradient.setColorAt(0, QColor(color))
                faded = QColor(color); faded.setAlpha(75)
                gradient.setColorAt(1, faded)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(gradient)
                p.drawRoundedRect(r, 4, 4)
            p.setPen(QColor(c['muted']))
            if count < 9 or i % 2 == 0:
                p.drawText(QRectF(center - span / 2, bottom + 9, span, 20), Qt.AlignmentFlag.AlignHCenter, str(height))
        p.end()


class BalanceHistoryChart(QWidget):
    """Confirmed wallet balance over verified blocks. Never a price series."""

    def __init__(self):
        super().__init__()
        self._points = ()
        self._mode = 'dark'
        self._hover = -1
        self._hit = []
        self._reveal = 1.0
        self._reveal_anim = None
        self.setMinimumHeight(128)
        self.setMinimumWidth(132)
        self.setMouseTracking(True)
        self.setAccessibleName('Confirmed wallet balance history')
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def get_reveal(self):
        return self._reveal

    def set_reveal(self, value):
        self._reveal = max(0.0, min(1.0, float(value)))
        self.update()

    reveal = Property(float, get_reveal, set_reveal)

    def render_points(self, points):
        previous = self._points
        self._points = tuple(points)
        self._hover = -1
        QToolTip.hideText()
        if self._reveal_anim is not None:
            self._reveal_anim.stop()
            self._reveal_anim = None
        if self._points and self._points != previous and not motion_reduced(self):
            self._reveal = 0.12
            animation = QPropertyAnimation(self, b'reveal', self)
            animation.setDuration(CHART_MS)
            animation.setStartValue(0.12)
            animation.setEndValue(1.0)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._reveal_anim = animation
            animation.start()
        else:
            self._reveal = 1.0
        self.update()

    def set_theme(self, mode):
        fusion_palette(mode)
        self._mode = mode
        self.update()

    def _mapped(self, width, height):
        if not self._points:
            return ()
        left, top, right, bottom = 8.0, 18.0, width - 10.0, height - 22.0
        xs = [h for h, _ in self._points]
        ys = [v for _, v in self._points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max(1, max_x - min_x)
        span_y = max(1, max_y - min_y)
        mapped = []
        for height_value, atoms in self._points:
            x = left + (right - left) * (height_value - min_x) / span_x
            y = bottom - (bottom - top) * (atoms - min_y) / span_y
            mapped.append((x, y, height_value, atoms))
        return mapped

    def mouseMoveEvent(self, event):
        mapped = self._mapped(self.width(), self.height())
        index = -1
        nearest = 1e9
        for i, (x, y, _h, _v) in enumerate(mapped):
            distance = abs(event.position().x() - x)
            if distance < nearest and distance < 28:
                nearest, index = distance, i
        if index != self._hover:
            self._hover = index
            self.update()
        if index >= 0:
            _x, _y, height, atoms = mapped[index]
            QToolTip.showText(event.globalPosition().toPoint(),
                              f'Verified block {height}\nConfirmed {format_wam(atoms)} WAM', self)
        else:
            QToolTip.hideText()

    def leaveEvent(self, event):
        self._hover = -1
        QToolTip.hideText()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = fusion_palette(self._mode)
        if not self._points:
            p.setPen(QColor(c['chart_empty']))
            p.drawText(self.rect().adjusted(10, 10, -10, -10),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
                       'Balance history is not yet available.')
            p.end()
            return
        mapped = self._mapped(self.width(), self.height())
        clip_right = 8.0 + (self.width() - 18.0) * self._reveal
        p.setClipRect(QRectF(0, 0, clip_right, self.height()))
        if len(mapped) == 1:
            x, y, height, atoms = mapped[0]
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(c['accent']))
            p.drawEllipse(QPointF(x, y), 5.0, 5.0)
            p.setPen(QColor(c['muted']))
            p.drawText(self.rect().adjusted(8, 8, -8, -8),
                       Qt.AlignmentFlag.AlignCenter,
                       f'Confirmed {format_wam(atoms)} WAM\nat block {height}')
            p.end()
            return
        path = QPainterPath()
        path.moveTo(mapped[0][0], mapped[0][1])
        for i in range(1, len(mapped)):
            x0, y0 = mapped[i - 1][0], mapped[i - 1][1]
            x1, y1 = mapped[i][0], mapped[i][1]
            dx = x1 - x0
            path.cubicTo(x0 + dx / 3.0, y0, x1 - dx / 3.0, y1, x1, y1)
        fill = QPainterPath(path)
        fill.lineTo(mapped[-1][0], self.height() - 22)
        fill.lineTo(mapped[0][0], self.height() - 22)
        fill.closeSubpath()
        gradient = QLinearGradient(QPointF(0, 16), QPointF(0, self.height() - 18))
        gold = QColor(c['accent']); gold.setAlpha(90 if self._mode == 'dark' else 70)
        fade = QColor(c['accent']); fade.setAlpha(0)
        gradient.setColorAt(0, gold)
        gradient.setColorAt(1, fade)
        p.fillPath(fill, gradient)
        pen = QPen(QColor(c['accent']), 2.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        for i, (x, y, height, atoms) in enumerate(mapped):
            if i == self._hover or len(mapped) == 1:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(c['accent']))
                p.drawEllipse(QPointF(x, y), 4.2, 4.2)
                p.setPen(QColor(c['muted']))
                p.drawText(QRectF(x - 36, self.height() - 20, 72, 16),
                           Qt.AlignmentFlag.AlignHCenter, str(height))
        p.end()


class NetworkFlyout(QFrame):
    """Compact verified network facts. Not a second Network page."""
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('FusionFlyout')
        self.setAccessibleName('Network status drawer')
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)
        head = QHBoxLayout()
        head.addWidget(label('Network status', 'FusionCardTitle'))
        head.addStretch()
        self.close_button = action('Close', 'history')
        self.close_button.setAccessibleName('Close network status drawer')
        self.close_button.clicked.connect(self.closed.emit)
        head.addWidget(self.close_button)
        layout.addLayout(head)
        self.mode_value = label('Isolated or Shared REGTEST is shown after verification.')
        self.core_value = label('Owned Core process is not confirmed here.')
        self.peer_value = label('Peer count is shown only after a verified network check.')
        self.height_value = label('Chain height is shown only after a verified snapshot.')
        for widget in (self.mode_value, self.core_value, self.peer_value, self.height_value):
            widget.setWordWrap(True)
            widget.setMinimumWidth(0)
            layout.addWidget(widget)
        layout.addWidget(label('Open Network for peer controls and full diagnostics.'))
        layout.addStretch()
        self.setMinimumWidth(280)
        self.setMaximumWidth(360)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.closed.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def render(self, *, network=None, core_alive=None, height=None):
        network = network or {}
        self.mode_value.setText(network.get('mode', 'REGTEST mode is unknown until verified.'))
        if core_alive is True:
            self.core_value.setText('Owned Core process is running.')
        elif core_alive is False:
            self.core_value.setText('Owned Core process is not running.')
        else:
            self.core_value.setText('Owned Core process is not confirmed here.')
        if type(network.get('peer_count')) is int:
            self.peer_value.setText(str(network['peer_count']) + ' reported peer(s).')
        elif network.get('shared'):
            self.peer_value.setText('Shared REGTEST peer count is awaiting a verified check.')
        else:
            self.peer_value.setText('Zero-peer isolated REGTEST profile.')
        if type(height) is int:
            self.height_value.setText('Verified snapshot height ' + str(height) + '.')
        else:
            self.height_value.setText('Chain height is shown only after a verified snapshot.')


class FusionOverview(QScrollArea):
    transaction_selected = Signal(str)
    recovery_requested = Signal()
    network_requested = Signal()
    backup_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName('FusionScroll')
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root = QWidget(); root.setObjectName('FusionInner'); self.setWidget(root)
        root.setMinimumWidth(0)
        whole = QVBoxLayout(root)
        whole.setContentsMargins(4, 4, 8, 36)
        whole.setSpacing(14)
        head = QHBoxLayout()
        titles = QVBoxLayout(); titles.setSpacing(2)
        title_row = QHBoxLayout(); title_row.setSpacing(8)
        home = QLabel(); home.setProperty('fusion_icon_label', 'home'); home.setFixedSize(24, 24)
        title_row.addWidget(home); title_row.addWidget(label('Overview', 'PageTitle')); title_row.addStretch()
        titles.addLayout(title_row)
        titles.addWidget(label('Your WAM wallet at a glance'))
        head.addLayout(titles, 1)
        self.live_badge = label('Awaiting verification', 'FusionBadge')
        self.live_badge.hide()
        head.addWidget(self.live_badge, 0, Qt.AlignmentFlag.AlignTop)
        whole.addLayout(head)

        self.hero = Hero()
        hero_row = QHBoxLayout(self.hero)
        hero_row.setContentsMargins(22, 16, 22, 16)
        hero_row.setSpacing(12)
        hero = QVBoxLayout()
        hero.setSpacing(6)
        hero.addWidget(label('CONFIRMED BALANCE', 'FusionKicker'))
        self.balance_value = label('—', 'FusionBalance', True)
        self.balance_value.setMinimumWidth(0)
        self.balance_unit = label('WAM', 'FusionDenom')
        self.balance_unit.hide()
        hero.addWidget(self.balance_value)
        hero.addWidget(self.balance_unit)
        self.utxo_details = label('Awaiting verified Core / WSP state')
        hero.addWidget(self.utxo_details)
        self.fund_details = label('')
        self.fund_details.hide()
        hero.addWidget(self.fund_details)
        row = QHBoxLayout(); row.setSpacing(10)
        self.go_send = action('Send', 'send', True); self.go_send.setEnabled(False)
        self.go_receive = action('Receive', 'receive')
        row.addWidget(self.go_send); row.addWidget(self.go_receive); row.addStretch()
        hero.addLayout(row)
        hero.addStretch()
        hero_row.addLayout(hero, 5)
        self.balance_chart = BalanceHistoryChart()
        hero_row.addWidget(self.balance_chart, 3)

        self.core_card = StatusCard('WAM Core', 'Pinned binary identity')
        self.chain_card = StatusCard('Chain', 'Verified tip height')
        self.security_card = StatusCard('Security', 'Native custody state')
        self.network_card = StatusCard('Network', 'REGTEST connectivity')
        self.core_status = self.core_card.value
        self.chain_status = self.chain_card.value
        self.vault_status = self.security_card.value
        self.network_status = self.network_card.value
        self.scanner_status = self.chain_status
        self.custody_caption = self.security_card.value
        self.lock_details = self.security_card.detail
        self.custody_switch = StateSwitch('Locked')
        self.custody_switch.setAccessibleName('Wallet Lock / Unlock switch')
        self.custody_switch.setEnabled(False)
        self.security_card.layout().addWidget(self.custody_switch)
        self.status_cards = [self.core_status, self.chain_status, self.vault_status, self.network_status]
        self.status_icons = [self.core_card.glyph, self.chain_card.glyph,
                             self.security_card.glyph, self.network_card.glyph]
        self.status_board = FlowGrid(
            self.core_card, self.chain_card, self.security_card, self.network_card,
            min_item=210, max_columns=4)

        activity, alayout = panel()
        top = QHBoxLayout()
        top.addWidget(label('Recent transactions', 'FusionCardTitle')); top.addStretch()
        self.open_history = action('View all', 'history')
        top.addWidget(self.open_history); alayout.addLayout(top)
        self.activity_table = QTableWidget(0, 3)
        self.activity_table.setObjectName('FusionActivityTable')
        self.activity_table.setHorizontalHeaderLabels(('ACTIVITY', 'AMOUNT', 'STATUS'))
        self.activity_table.verticalHeader().hide()
        self.activity_table.setShowGrid(False)
        self.activity_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.activity_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.activity_table.horizontalHeader().setStretchLastSection(True)
        self.activity_table.setMinimumHeight(168)
        self.activity_table.setMinimumWidth(0)
        self.activity_table.setColumnWidth(0, 170)
        self.activity_table.cellClicked.connect(self._select_tx)
        self._txids = []
        alayout.addWidget(self.activity_table)
        self.empty = label('No recent transactions. Your confirmed activity will appear here.')
        alayout.addWidget(self.empty)
        environment, el = panel('Wallet environment')
        self.wallet_profile = label('REGTEST profile')
        self.environment_core = label('WAM Core identity is shown after verification')
        self.environment_stack = label('WSP-1  ·  BIP39 (12 words)')
        el.addWidget(self.wallet_profile)
        el.addWidget(self.environment_core)
        el.addWidget(self.environment_stack)

        rail, rl = panel('Quick actions')
        self.open_backup = quick_action('Backup Wallet', 'backup')
        self.open_recovery = quick_action('Verify Recovery', 'security')
        self.quick_lock = quick_action('Lock Wallet', 'lock')
        self.open_network = quick_action('Network Status', 'network')
        rl.addWidget(FlowGrid(
            self.open_backup, self.open_recovery, self.quick_lock, self.open_network,
            min_item=168, max_columns=2))
        rl.addStretch()

        whole.addWidget(ResponsiveRow(self.hero, rail, weights=[5, 2], breakpoint=840, min_side=780))
        whole.addWidget(self.status_board)
        whole.addWidget(ResponsiveRow(activity, environment, weights=[3, 2], breakpoint=720, min_side=640))

        self._compat = QWidget(); self._compat.hide()
        compat = QVBoxLayout(self._compat)
        self.network_summary = label('Shown after a verified Core snapshot.')
        self.health_value = label('Not verified', 'FusionCardValue')
        self.health_details = label('Core, chain, custody and network are reported only from verified backend state.')
        self.evidence_text = label('No verified blockchain snapshot')
        self.manual_sync = action('Refresh', 'sync')
        self.open_security = action('Security', 'security')
        self.open_security.setEnabled(False)
        for widget in (self.network_summary, self.health_value, self.health_details,
                       self.evidence_text, self.manual_sync, self.open_security):
            compat.addWidget(widget)
        whole.addWidget(self._compat)

        self._confirmed_atoms = None
        self.open_backup.clicked.connect(self.backup_requested.emit)
        self.open_recovery.clicked.connect(self.recovery_requested.emit)
        self.open_network.clicked.connect(self.network_requested.emit)
        self.quick_lock.clicked.connect(lambda: self.custody_switch.click() if self.custody_switch.isEnabled() else None)
        self.render_snapshot(None, locked=True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_balance_text()

    def _apply_balance_text(self):
        if self._confirmed_atoms is None:
            self.balance_value.setText('—')
            self.balance_unit.hide()
            return
        amount = format_wam(self._confirmed_atoms, grouped=True)
        compact = self.hero.width() > 0 and self.hero.width() < 640
        self.balance_unit.setVisible(compact)
        self.balance_value.setText(amount if compact else amount + ' WAM')

    def _select_tx(self, row, column):
        if 0 <= row < len(self._txids):
            self.transaction_selected.emit(self._txids[row])

    def set_theme(self, mode):
        self.hero.mode = mode
        self.hero.update()
        self.balance_chart.set_theme(mode)
        for card in (self.core_card, self.chain_card, self.security_card, self.network_card):
            card.set_theme(mode)
        self.custody_switch.setProperty('fusion_mode', mode)
        self.custody_switch.update()
        for row in range(self.activity_table.rowCount()):
            item = self.activity_table.item(row, 0)
            if item is not None:
                positive = item.data(Qt.ItemDataRole.UserRole) > 0
                item.setIcon(vector_icon('receive' if positive else 'send',
                                         fusion_palette(mode)['green' if positive else 'red']))

    def render_snapshot(self, snap, *, locked=False, operational=False, network=None,
                        faulted=False, available_atoms=None, reservation_count=None,
                        core_alive=None, busy=False):
        network = network or {}
        facts = dict(snap=None if (snap is None or locked) else snap, locked=locked,
                     operational=operational, faulted=faulted, core_alive=core_alive,
                     busy=busy, network=network)
        self.core_card.apply(*classify('core', **facts), animate=not locked)
        self.chain_card.apply(*classify('chain', **facts), animate=not locked)
        self.security_card.apply(*classify('security', **facts), animate=False)
        self.network_card.apply(*classify('network', **facts), animate=not locked)
        unlocked = not locked and operational and snap is not None
        self.custody_switch.blockSignals(True)
        self.custody_switch.setChecked(unlocked)
        self.custody_switch.setText('Unlocked' if unlocked else 'Locked')
        self.custody_switch.blockSignals(False)
        if snap is None or locked:
            self._confirmed_atoms = None
            self._apply_balance_text()
            self.utxo_details.setText('Unlock and verify the chain to display wallet values.')
            self.fund_details.hide()
            self.balance_chart.render_points(())
            self.live_badge.setText('Locked' if locked else 'Not verified')
            self.evidence_text.setText('No verified blockchain snapshot')
            self.evidence_text.setToolTip('')
            self.activity_table.setRowCount(0)
            self.activity_table.hide()
            self._txids = []
            self.empty.show()
            self.go_receive.setEnabled(False)
            self.health_value.setText('Faulted' if faulted else ('Locked' if locked else 'Not verified'))
            self.health_details.setText('Wallet values stay hidden until this original REGTEST profile is verified.')
            self.network_summary.setText(network.get('summary', 'Network status is shown only after a verified Core snapshot.'))
            self.wallet_profile.setText('REGTEST profile')
            self.environment_core.setText('WAM Core identity is shown after verification')
            return
        activity_by_block(snap)
        self.balance_chart.render_points(confirmed_balance_history(snap))
        self._confirmed_atoms = snap.confirmed_atoms
        self._apply_balance_text()
        self.utxo_details.setText(
            f'{snap.confirmed_utxos} confirmed UTXO(s)  ·  Verified block {snap.height}'
            + ('  ·  REGTEST (Shared)' if network.get('shared') else '  ·  REGTEST (Isolated)'))
        funds = []
        if type(available_atoms) is int and available_atoms >= 0:
            if available_atoms != snap.confirmed_atoms:
                funds.append('Spendable ' + format_wam(available_atoms, grouped=True) + ' WAM')
        if type(reservation_count) is int and reservation_count > 0:
            funds.append(str(reservation_count) + ' reserved input(s) stay unavailable')
        self.fund_details.setText('  ·  '.join(funds))
        self.fund_details.setVisible(bool(funds))
        self.live_badge.setText('REGTEST VERIFIED')
        self.go_receive.setEnabled(True)
        self.evidence_text.setText('Verified tip ' + snap.tip[:14] + '…  ·  No real funds')
        self.evidence_text.setToolTip('Core SHA-256: ' + snap.core_sha256 + '\nVerified tip: ' + snap.tip)
        self.network_summary.setText(network.get('summary') or (
            f"Mode  {'Shared REGTEST' if network.get('shared') else 'Isolated REGTEST'}\n"
            f"Height  {snap.height}"))
        self.health_value.setText('Operating normally' if not faulted else 'Faulted')
        self.health_details.setText(
            'Confirmed balance, custody and chain height come from this verified snapshot.'
            if not faulted else 'Original reservations are preserved. Do not retry uncertain payments.')
        self.wallet_profile.setText('Operational REGTEST wallet' if operational else 'Read-only REGTEST wallet')
        self.environment_core.setText('WAM Core v0.1.11  ·  SHA-256 ' + snap.core_sha256[:12] + '…')
        self.environment_core.setToolTip('Core SHA-256: ' + snap.core_sha256)
        rows = snap.history[:4]
        self._txids = [r.txid for r in rows]
        self.activity_table.setRowCount(len(rows))
        self.activity_table.setVisible(bool(rows))
        self.empty.setVisible(not rows)
        if rows:
            self.activity_table.setMinimumHeight(min(220, 48 + 58 * len(rows)))
        mode = self.hero.mode
        for i, tx in enumerate(rows):
            value = tx.credit_atoms - tx.debit_atoms
            direction = 'Received' if value > 0 else 'Sent' if value < 0 else 'Activity'
            amount = ('+' if value > 0 else '-' if value < 0 else '') + format_wam(abs(value)) + ' WAM'
            status = f'Confirmed ({tx.confirmations})'
            for j, text in enumerate((direction + '\n' + tx.txid[:10] + '…', amount, status)):
                item = QTableWidgetItem(text)
                item.setForeground(QColor(fusion_palette(mode)['text']))
                item.setToolTip(tx.txid + '\nClick to view exact transaction details')
                if j == 0:
                    item.setData(Qt.ItemDataRole.UserRole, value)
                    item.setIcon(vector_icon('receive' if value > 0 else 'send',
                                             fusion_palette(mode)['green' if value > 0 else 'red']))
                if j == 1:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.activity_table.setItem(i, j, item)
            self.activity_table.setRowHeight(i, 58)
