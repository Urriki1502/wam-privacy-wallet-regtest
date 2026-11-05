"""Lightweight Qt presentation motion. Never wallet authority or Core progress."""
from __future__ import annotations

import os

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation
from PySide6.QtWidgets import QAbstractButton, QGraphicsOpacityEffect, QWidget

PAGE_MS = 200
CARD_MS = 180
BUTTON_MS = 140
THEME_MS = 190
CHART_MS = 220


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


def fade_widget(widget, *, start=0.84, end=1.0, duration=PAGE_MS, parent=None):
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
    animation.setDuration(max(100, min(240, duration)))
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
    animation.setDuration(max(160, min(220, duration)))
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
            effect.setOpacity(0.86)
        elif event.type() in (QEvent.Type.MouseButtonRelease, QEvent.Type.Leave):
            effect = watched.graphicsEffect()
            if isinstance(effect, QGraphicsOpacityEffect):
                animation = QPropertyAnimation(effect, b"opacity", watched)
                animation.setDuration(BUTTON_MS)
                animation.setStartValue(effect.opacity())
                animation.setEndValue(1.0)
                animation.setEasingCurve(QEasingCurve.Type.OutCubic)
                animation.finished.connect(lambda w=watched: clear_effect(w))
                animation.start()
                watched._fusion_press = animation
        return False
