"""Actual Qt shutdown contracts, SOURCE only; no Core acceptance substituted."""
import unittest
from pathlib import Path
import tempfile
try:
    from PySide6.QtCore import QThread
    from PySide6.QtWidgets import QWidget
    from wam_regtest.desktop import qt_application,RegtestWalletWindow
    from wam_regtest.managed_lifecycle_probe import close_gui
    QT=True
except ImportError:
    QT=False


@unittest.skipUnless(QT,'native Qt component unavailable; genuine GUI CI mandatory')
class NormalCloseContracts(unittest.TestCase):
    def test_actual_worker_refusal_then_normal_close(self):
        class Worker(QThread):
            def run(self): self.msleep(100)
        app=qt_application(); worker=Worker()
        temporary=tempfile.TemporaryDirectory(prefix='wam-q05-close-contract-')
        root=Path(temporary.name).resolve()
        window=RegtestWalletWindow(root,root,root)
        window._worker=worker
        worker.finished.connect(window._worker_finished)
        window.show()
        try:
            worker.start()
            self.assertFalse(window.close())
            self.assertTrue(window.isVisible())
            close_gui(window,app,timeout=3)
            self.assertFalse(worker.isRunning())
            self.assertFalse(window.isVisible())
        finally:
            worker.wait(3000); app.processEvents(); window.close()
            window.deleteLater(); worker.deleteLater(); app.processEvents(); temporary.cleanup()

    def test_permanent_refusal_is_not_success_or_force_deleted(self):
        class Refusing(QWidget):
            allow=False
            def closeEvent(self,event):
                if self.allow: event.accept()
                else: event.ignore()
        app=qt_application(); window=Refusing(); window.show()
        try:
            with self.assertRaisesRegex(ValueError,'Q05_NORMAL_GUI_CLOSE_NOT_COMPLETED'):
                close_gui(window,app,timeout=.05)
            self.assertTrue(window.isVisible())
        finally:
            window.allow=True; window.close(); window.deleteLater(); app.processEvents()


if __name__=='__main__': unittest.main()
