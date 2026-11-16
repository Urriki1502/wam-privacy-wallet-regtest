"""Native qualification-only button observation; no Core or wallet authority."""

def click_visible_approval(app, caption):
    """Click an explicit approval on any visible dialog, not only the active modal.

    Two Fusion windows make a WindowModal Sign/Broadcast dialog easy to miss via
    activeModalWidget(); the operator action is still the labeled QPushButton.
    """
    from PySide6.QtWidgets import QDialog, QPushButton
    for widget in app.allWidgets():
        if not isinstance(widget, QDialog) or not widget.isVisible():
            continue
        for control in widget.findChildren(QPushButton):
            if control.text() == caption and control.isEnabled():
                # QPushButton.click() can be delivered while the dialog is
                # still showing. Emit the same clicked signal the button uses
                # so Accept runs on the main loop that opened the dialog.
                control.clicked.emit()
                return True
    return False

