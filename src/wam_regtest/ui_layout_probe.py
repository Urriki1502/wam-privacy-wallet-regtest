"""Real Qt layout checks only; no backend, secrets, Core or wallet operations.

The disabled executor is a presentation fixture, never transaction evidence.
Used by focused source tests and the exact frozen macOS executable.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace


def check_layouts(output=None):
    from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QRect, Qt
    from PySide6.QtWidgets import QScrollArea
    from .desktop import qt_application
    from .bip39_fusion_gui import Bip39FusionWindow
    from .wallet_executor import ExecutorState

    app = qt_application()
    window = Bip39FusionWindow(SimpleNamespace(state=ExecutorState(), busy=False, closed=False))
    window._poll.stop()  # No executor operations, timers or real wallet state.
    window.reduce_motion.setChecked(True)
    records = []
    destination = Path(output) if output is not None else None
    if destination:
        destination.mkdir(parents=True, exist_ok=False)

    def settle():
        for _ in range(8):
            app.processEvents()
            time.sleep(.01)

    def snapshot(name):
        if destination:
            assert window.grab().save(str(destination / (name + '.png')))

    def text_fits(widget, scene):
        r = widget.contentsRect()
        needed = widget.fontMetrics().boundingRect(
            QRect(0, 0, max(1, r.width()), 10000),
            int(Qt.TextFlag.TextWordWrap), widget.text()).height()
        assert r.height() >= needed, (scene, r.height(), needed)
        # WordWrap alone may report a wide unbreakable line as one row.
        bounds = widget.fontMetrics().boundingRect(
            QRect(0, 0, max(1, r.width()), 10000),
            int(Qt.TextFlag.TextWordWrap), widget.text())
        assert bounds.width() <= r.width(), (scene, bounds.width(), r.width())
        records.append(dict(scene=scene, size=[window.width(), window.height()],
                            theme=theme, width=r.width(), height=r.height(),
                            needed_height=needed))

    try:
        window.show()
        for width, height in ((900, 630), (1260, 810)):
            window.resize(width, height)
            for theme in (1, 2):
                window.appearance_buttons[theme].click()
                settle()
                window.status.setText('Native Core not opened — layout inspection only')
                window.stack.setCurrentWidget(window.backup_page)
                window.page_title.setText('Wallet Backup')
                window.navigation.clearSelection()
                window.backup_page._stack.setCurrentWidget(window.backup_page._success_page)
                settle()
                description = window.backup_page._success_description
                text_fits(description, 'backup')
                scroll = window.backup_page.findChild(QScrollArea)
                assert scroll.horizontalScrollBar().maximum() == 0
                assert scroll.viewport().rect().contains(description.mapTo(scroll.viewport(), QPoint(0, 0)))
                snapshot(f'backup-{width}-{theme}')
                original = description.text()
                description.setText((original + ' ') * 5)
                settle()
                text_fits(description, 'backup-wrapped')
                snapshot(f'backup-wrapped-{width}-{theme}')
                description.setText(original)
                # Policy must restore on other backup pages; verification logic is untouched.
                window.backup_page._stack.setCurrentWidget(window.backup_page._verify_page)
                assert window.backup_page._stack.sizePolicy() == window.backup_page._normal_stack_policy
                window.navigation.setCurrentRow(5)
                window.stack.setCurrentIndex(5)
                settle()
                for expanded in (False, True, False):
                    window.advanced_toggle.setChecked(expanded)
                    settle()
                    button = window.advanced_toggle
                    scroll = window.stack.widget(5)
                    scroll.ensureWidgetVisible(button)
                    settle()
                    assert button.height() >= button.sizeHint().height(), ('advanced', button.height(), button.sizeHint().height())
                    assert button.width() >= button.sizeHint().width()
                    assert window.advanced_container.isVisible() == expanded
                    assert button.parentWidget().rect().contains(button.geometry())
                    records.append(dict(scene='advanced', size=[width, height], theme=theme,
                                        expanded=expanded, height=button.height(),
                                        needed_height=button.sizeHint().height()))
                    snapshot(f'advanced-{width}-{theme}-{expanded}')
                for number, message in enumerate((
                    'Operation could not complete safely. Wallet state and reservations are retained. '
                    'Verify the original REGTEST profile, native checkpoint and pending transaction before continuing. '
                    'Do not reset custody or automatically retry the previous signed payment.',
                    'Checkpoint: ' + 'a' * 128,
                    '\n'.join(['Retained state — verify the original profile before continuing.'] * 6),
                )):
                    window.status.setText(message)
                    settle()
                    text_fits(window.status, f'footer-{number}')
                    assert window.status.text().replace('\u200b', '') == message
                    assert window.status.toolTip() == message
                    assert not window.status.geometry().intersects(window.stack.geometry())
                    assert window.status.parentWidget().rect().contains(window.status.geometry())
                    snapshot(f'footer-{width}-{theme}-{number}')
        return dict(status='UI_LAYOUT_PASS', qt_platform=app.platformName(),
                    device_pixel_ratio=window.devicePixelRatioF(),
                    frozen=bool(getattr(sys, 'frozen', False)),
                    backend_or_core_started=False, wallet_or_transaction_acceptance=False,
                    owner_window_size_confirmed=False, measurements=records)
    finally:
        window._closed = True
        window.hide()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def run():
    from .desktop import shutdown_qt
    try:
        report = check_layouts('ui-layout-review')
        assert report['qt_platform'] == 'cocoa'
        Path('ui-layout-evidence.json').write_text(json.dumps(report, indent=2) + '\n')
        print('NATIVE_UI_LAYOUT_PASS_FROZEN=' + str(report['frozen']), flush=True)
        return 0
    finally:
        shutdown_qt()
