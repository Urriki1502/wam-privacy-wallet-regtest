"""Lightweight Qt presentation motion. Never wallet authority or Core progress."""
from __future__ import annotations

import os

from PySide6.QtCore import (
    QEasingCurve, QEvent, QObject, QParallelAnimationGroup, QPropertyAnimation,
    Qt, QTimer, Property,
)
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath
from PySide6.QtWidgets import (
    QAbstractButton, QGraphicsOpacityEffect, QStackedWidget, QWidget, QVBoxLayout,
)

FAST_MS = 140
STANDARD_MS = 220
PAGE_MS = 320
EMPHASIS_MS = 360
THEME_MS = 190
BUTTON_MS = 140
CHART_MS = 220
STAGGER_MS = 45
SLIDE_PX = 18
PAGE_MS_LEGACY = PAGE_MS
CARD_MS = STANDARD_MS


def motion_reduced(widget=None):
    if os.environ.get("QT_REDUCE_MOTION") == "1":
        return True
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return True
    current = widget
    while isinstance(current, QWidget):
        if current.property("fusion_reduce_motion") is True:
            return True
        current = current.parentWidget()
    return False


def clear_effect(widget):
    if widget is not None and widget.graphicsEffect() is not None:
        widget.setGraphicsEffect(None)


def fade_widget(widget, *, start=0.84, end=1.0, duration=STANDARD_MS, parent=None):
    """Non-blocking opacity fade. Never used to imply Core or payment progress."""
    if widget is None:
        return None
    if motion_reduced(widget):
        clear_effect(widget)
        return None
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    effect.setOpacity(start)
    animation = QPropertyAnimation(effect, b"opacity", parent or widget)
    animation.setDuration(max(100, min(420, duration)))
    animation.setStartValue(start)
    animation.setEndValue(end)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.finished.connect(lambda w=widget: clear_effect(w))
    animation.start()
    return animation


def slide_geometry(target, rect, *, duration=THEME_MS, parent=None):
    if target is None:
        return None
    if motion_reduced(target):
        target.setGeometry(rect)
        return None
    animation = QPropertyAnimation(target, b"geometry", parent or target)
    animation.setDuration(max(160, min(380, duration)))
    animation.setStartValue(target.geometry())
    animation.setEndValue(rect)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.start()
    return animation


class PressFeedback(QObject):
    """Short press dimming for buttons; skipped when Reduced Motion is on."""

    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.attach(host)

    def attach(self, root):
        for button in root.findChildren(QAbstractButton):
            button.installEventFilter(self)

    def eventFilter(self, watched, event):
        if not isinstance(watched, QAbstractButton) or motion_reduced(watched):
            return False
        if event.type() == QEvent.Type.MouseButtonPress and watched.isEnabled():
            effect = watched.graphicsEffect()
            if not isinstance(effect, QGraphicsOpacityEffect):
                effect = QGraphicsOpacityEffect(watched)
                watched.setGraphicsEffect(effect)
            effect.setOpacity(0.88)
        elif event.type() in (QEvent.Type.MouseButtonRelease, QEvent.Type.Leave):
            effect = watched.graphicsEffect()
            if isinstance(effect, QGraphicsOpacityEffect):
                animation = QPropertyAnimation(effect, b"opacity", watched)
                animation.setDuration(FAST_MS)
                animation.setStartValue(effect.opacity())
                animation.setEndValue(1.0)
                animation.setEasingCurve(QEasingCurve.Type.OutCubic)
                animation.finished.connect(lambda w=watched: clear_effect(w))
                animation.start()
                watched._fusion_press = animation
        return False


class StatusGlyph(QWidget):
    """Verified / pending / warning / error / unknown. Pending spinner stops on terminal state."""

    def __init__(self):
        super().__init__()
        self._state = 'unknown'
        self._progress = 1.0
        self._angle = 0
        self._mode = 'dark'
        self._spin = QTimer(self)
        self._spin.setInterval(16)
        self._spin.timeout.connect(self._tick)
        self._reveal = None
        self.setFixedSize(22, 22)
        self.setAccessibleName('Status indicator')

    def get_progress(self):
        return self._progress

    def set_progress(self, value):
        self._progress = max(0.0, min(1.0, float(value)))
        self.update()

    progress = Property(float, get_progress, set_progress)

    def state(self):
        return self._state

    def set_theme(self, mode):
        self._mode = mode
        self.update()

    def set_state(self, state, *, animate=True):
        if state not in ('unknown', 'pending', 'verified', 'warning', 'error'):
            raise ValueError('FUSION_STATUS_STATE_DENIED')
        previous = self._state
        self._state = state
        if self._reveal is not None:
            self._reveal.stop()
            self._reveal = None
        if state == 'pending':
            self._progress = 1.0
            if motion_reduced(self):
                self._spin.stop()
            elif not self._spin.isActive():
                self._spin.start()
            self.update()
            return
        self._spin.stop()
        self._angle = 0
        if (animate and previous != state and state in ('verified', 'warning', 'error')
                and not motion_reduced(self)):
            self._progress = 0.0
            animation = QPropertyAnimation(self, b'progress', self)
            animation.setDuration(EMPHASIS_MS if state == 'verified' else STANDARD_MS)
            animation.setStartValue(0.0)
            animation.setEndValue(1.0)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._reveal = animation
            animation.start()
        else:
            self._progress = 1.0
            self.update()

    def _tick(self):
        if self._state != 'pending':
            self._spin.stop()
            return
        self._angle = (self._angle + 8) % 360
        self.update()

    def paintEvent(self, event):
        from wam_regtest.fusion_ui import fusion_palette
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = fusion_palette(self._mode if self._mode in ('dark', 'light') else 'dark')
        tone = {
            'verified': c['green'], 'pending': c['accent'], 'warning': c['warning_text'],
            'error': c['red'], 'unknown': c['muted'],
        }[self._state]
        rect = self.rect().adjusted(2, 2, -2, -2)
        if self._state == 'pending':
            p.setPen(QPen(QColor(c['border']), 2))
            p.drawEllipse(rect)
            if not motion_reduced(self):
                pen = QPen(QColor(tone), 2)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.drawArc(rect, int(-self._angle * 16), 110 * 16)
            else:
                p.setPen(QPen(QColor(tone), 2))
                p.drawEllipse(rect.adjusted(4, 4, -4, -4))
            p.end()
            return
        p.setPen(QPen(QColor(tone), 1.7))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(rect)
        t = self._progress
        if self._state == 'verified':
            path = QPainterPath()
            path.moveTo(6, 12)
            path.lineTo(10, 16)
            path.lineTo(16, 7)
            pen = QPen(QColor(tone), 1.8)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawPath(path)
            if t < 1:
                p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
                fade = QColor(0, 0, 0, int(255 * t))
                p.fillRect(self.rect(), fade)
        elif self._state == 'warning':
            p.setPen(QPen(QColor(tone), 1.6))
            p.drawLine(11, 6, 6, 16)
            p.drawLine(11, 6, 16, 16)
            p.drawLine(6, 16, 16, 16)
            p.drawPoint(11, 10)
            p.drawPoint(11, 14)
        elif self._state == 'error':
            p.setPen(QPen(QColor(tone), 1.8))
            p.drawLine(7, 7, 15, 15)
            p.drawLine(15, 7, 7, 15)
        else:
            p.setPen(QPen(QColor(tone), 1.6))
            p.drawEllipse(10, 6, 2, 2)
            p.drawLine(11, 10, 11, 16)
        p.end()


class TransitionHost(QWidget):
    """Stacked pages with opacity + short translation. Layouts keep final geometry."""

    def __init__(self):
        super().__init__()
        self.setObjectName('FusionTransparent')
        self.stack = QStackedWidget(self)
        self._motion = None
        self._shift = 0
        self._pending = None
        self._effect = None

    def get_shift(self):
        return self._shift

    def set_shift(self, value):
        self._shift = int(value)
        self._place()

    shift = Property(int, get_shift, set_shift)

    def addWidget(self, widget):
        return self.stack.addWidget(widget)

    def widget(self, index):
        return self.stack.widget(index)

    def currentWidget(self):
        return self.stack.currentWidget()

    def currentIndex(self):
        return self.stack.currentIndex()

    def count(self):
        return self.stack.count()

    def indexOf(self, widget):
        return self.stack.indexOf(widget)

    def setCurrentIndex(self, index):
        self.set_current(index, reduced=True)

    def setCurrentWidget(self, widget):
        index = self.stack.indexOf(widget)
        if index >= 0:
            self.set_current(index, reduced=True)

    def _place(self):
        self.stack.setGeometry(self._shift, 0, self.width(), self.height())

    def resizeEvent(self, event):
        self._place()
        super().resizeEvent(event)

    def set_current(self, index, *, reduced=False):
        if not 0 <= index < self.stack.count():
            return
        self._pending = index
        if self._motion is not None:
            self._motion.stop()
            self._motion = None
        if self._effect is not None:
            clear_effect(self.stack)
            self._effect = None
        self.stack.setCurrentIndex(index)
        self._shift = 0
        self._place()
        if reduced or motion_reduced(self):
            self._pending = None
            return
        direction = 1
        self._shift = SLIDE_PX * direction
        self._place()
        self._effect = QGraphicsOpacityEffect(self.stack)
        self.stack.setGraphicsEffect(self._effect)
        self._effect.setOpacity(0.72)
        group = QParallelAnimationGroup(self)
        slide = QPropertyAnimation(self, b'shift', self)
        slide.setDuration(PAGE_MS)
        slide.setStartValue(self._shift)
        slide.setEndValue(0)
        slide.setEasingCurve(QEasingCurve.Type.OutCubic)
        fade = QPropertyAnimation(self._effect, b'opacity', self)
        fade.setDuration(PAGE_MS)
        fade.setStartValue(0.72)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        group.addAnimation(slide)
        group.addAnimation(fade)
        group.finished.connect(self._finished)
        self._motion = group
        group.start()

    def _finished(self):
        clear_effect(self.stack)
        self._effect = None
        self._motion = None
        self._shift = 0
        self._place()
        self._pending = None
