"""Native Qt UNIT negatives only. No Core, real keys, wallets or anchors.

Run with PYTHONPATH pointing at an exact reviewed source snapshot and installed
project dependencies. Exit1 means a worker started after GUI authority was lost.
The mocked worker/dialog authority is NOT genuine-Core/frozen acceptance.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QEventLoop,QTimer
from shiboken6 import delete
from wam_regtest.desktop import qt_application,shutdown_qt
from wam_regtest.managed_gui import ManagedCoreWindow
from wam_regtest.supervisor_protocol import public_status

class ModalAuthority(unittest.TestCase):
    def test_authority_lost_during_dialog_never_creates_wallet_worker(self):
        app=qt_application()
        operations=[('_verify_wallet','_LockedWalletWorker'),
                    ('_view_wallet','_ManagedWalletSnapshotWorker'),
                    ('_create_wallet','_ManagedWalletCreateWorker'),
                    ('_open_spending_wallet','_ManagedSpendSessionWorker')]
        for operation,worker_name in operations:
            with self.subTest(operation=operation),TemporaryDirectory(prefix='wam-public-qt-unit-') as folder:
                root=Path(folder)
                if operation=='_open_spending_wallet':
                    (root/'chain'/'wallet-vault').mkdir(parents=True)
                win=ManagedCoreWindow(root,core_dir=root/'unit-core',wsp_source=root/'unit-wsp')
                win._apply_managed_status(public_status(state='ready',owned=True,chain_height=101))
                def password(*args,**kwargs):
                    loop=QEventLoop()
                    def tick():
                        win._managed_denied('public-unit-authority-lost')
                        loop.quit()
                    QTimer.singleShot(0,tick);loop.exec()
                    return 'public-disposable-unit-password',True
                try:
                    with (patch('wam_regtest.managed_gui.QMessageBox.question',return_value=QMessageBox.StandardButton.Yes),
                          patch('wam_regtest.managed_gui.QInputDialog.getText',side_effect=password),
                          patch('wam_regtest.managed_gui.'+worker_name) as worker):
                        getattr(win,operation)()
                        self.assertFalse(win._managed_authenticated)
                        worker.assert_not_called()
                finally:
                    win._worker=None
                    win.close();delete(win);app.processEvents()

if __name__=='__main__':
    try: result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ModalAuthority))
    finally: shutdown_qt()
    raise SystemExit(0 if result.wasSuccessful() else 1)
