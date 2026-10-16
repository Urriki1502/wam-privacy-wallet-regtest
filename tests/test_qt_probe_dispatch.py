"""Qt event ordering regression only; never a blockchain acceptance substitute."""
import unittest
from PySide6.QtCore import QObject,Signal,QTimer
from wam_regtest.desktop import qt_application
from wam_regtest.wallet_probe import _operation


class ProbeDispatch(unittest.TestCase):
    def test_queued_sync_finishes_before_fixture_action_is_dispatched_once(self):
        class Window(QObject):
            operation_completed=Signal(str,object)
            operation_failed=Signal(str)
            _worker=None
        app=qt_application();window=Window();entered=[]
        def queued_sync():
            window._worker=object()
            QTimer.singleShot(40,lambda:setattr(window,'_worker',None))
        def action():
            entered.append(window._worker is None)
            if window._worker is not None:window.operation_failed.emit('WALLET_SYNC_UNVERIFIED')
            else:window.operation_completed.emit('network','CONTROL_SCHEDULING_ONLY')
        # The idle check sees no worker, but a previously queued native event
        # starts sync before the fixture's first action-dispatch opportunity.
        QTimer.singleShot(0,queued_sync)
        result=_operation(app,window,'network',action)
        self.assertEqual(result,'CONTROL_SCHEDULING_ONLY')
        self.assertEqual(entered,[True])

    def test_acceptance_window_lifetime_restores_interactive_policy_on_failure(self):
        from wam_regtest.qt_probe_lifetime import acceptance_application
        app=qt_application();prior=app.quitOnLastWindowClosed()
        try:
            app.setQuitOnLastWindowClosed(True)
            with self.assertRaisesRegex(ValueError,'FIXTURE_FAILURE'):
                with acceptance_application():
                    self.assertFalse(app.quitOnLastWindowClosed())
                    with acceptance_application():
                        self.assertFalse(app.quitOnLastWindowClosed())
                    self.assertFalse(app.quitOnLastWindowClosed())
                    raise ValueError('FIXTURE_FAILURE')
            self.assertTrue(app.quitOnLastWindowClosed())
        finally:app.setQuitOnLastWindowClosed(prior)
