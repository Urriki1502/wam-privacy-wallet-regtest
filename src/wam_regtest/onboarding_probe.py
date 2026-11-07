"""Bounded real-Qt password input qualification; no wallet/backend or secrets."""
import time


def qualify_password_dialogs():
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox, QDialog
    from .bip39_owner_gui import _onboarding_password
    app = QApplication.instance()
    if app is None:
        raise ValueError('ONBOARDING_QT_APPLICATION_REQUIRED')
    responses = iter(('short', 'public-disposable-password',
                      'different-disposable-password', 'public-disposable-password',
                      'public-disposable-password'))
    state = {'inputs': 0, 'warnings': 0, 'timeout': False}
    deadline = time.monotonic() + 10
    timer = QTimer()
    timer.setInterval(50)
    def advance():
        dialog = app.activeModalWidget()
        if time.monotonic() >= deadline:
            state['timeout'] = True
            if isinstance(dialog, QDialog):
                dialog.reject()
            return
        if isinstance(dialog, QInputDialog):
            value = next(responses, None)
            if value is None:
                state['timeout'] = True
                dialog.reject()
            else:
                state['inputs'] += 1
                dialog.setTextValue(value)
                dialog.accept()
        elif isinstance(dialog, QMessageBox):
            state['warnings'] += 1
            dialog.accept()
    timer.timeout.connect(advance)
    timer.start()
    try:
        password, ok = _onboarding_password(None, 'create')
        passed = (ok and password == 'public-disposable-password'
                  and state == {'inputs': 5, 'warnings': 2, 'timeout': False})
        password = ''
        if not passed:
            raise ValueError('ONBOARDING_NATIVE_PASSWORD_RECOVERY_DENIED')
    finally:
        timer.stop()
    return {'invalid_length_recovered': True, 'confirmation_mismatch_recovered': True,
            'valid_confirmation_accepted': True, 'backend_created': False}
