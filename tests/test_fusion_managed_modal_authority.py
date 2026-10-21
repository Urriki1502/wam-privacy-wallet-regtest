"""Actual Qt nested-loop authority regression; worker fixtures, not Core E2E."""
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QMessageBox
from shiboken6 import delete
from wam_regtest.desktop import qt_application
from wam_regtest.managed_gui import ManagedCoreWindow
from wam_regtest.supervisor_protocol import public_status


class ManagedModalAuthority(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=qt_application()

    def setUp(self):
        self.folder=tempfile.TemporaryDirectory(prefix='wam-modal-public-unit-')
        self.root=Path(self.folder.name).resolve()
        self.win=ManagedCoreWindow(self.root,core_dir=self.root/'unit-core',
                                   wsp_source=self.root/'unit-wsp')
        self.win._sync_timer.stop()
        self.ready()

    def tearDown(self):
        self.win._worker=None
        self.win._spend_window=None
        self.assertFalse(self.win._managed_dialog_open)
        self.win.close();delete(self.win);self.app.processEvents()
        self.folder.cleanup()

    def ready(self):
        self.win._apply_managed_status(
            public_status(state='ready',owned=True,chain_height=101))

    def nested(self,action):
        # Deliver a genuine Qt timer inside a modal-style nested event loop.
        # Exceptions are retained for unittest, never raised through Qt C++.
        loop=QEventLoop();errors=[]
        def tick():
            try:action()
            except BaseException as error:errors.append(error)
            finally:loop.quit()
        QTimer.singleShot(0,tick);loop.exec()
        if errors:raise errors[0]

    def password(self,*args,**kwargs):
        return 'public-disposable-unit-password',True

    def vault(self):
        (self.root/'chain'/'wallet-vault').mkdir(parents=True,exist_ok=True)

    def test_denial_during_password_never_constructs_worker(self):
        operations=[('_verify_wallet','_LockedWalletWorker'),
                    ('_view_wallet','_ManagedWalletSnapshotWorker'),
                    ('_create_wallet','_ManagedWalletCreateWorker'),
                    ('_create_bip39_wallet','_ManagedWalletCreateWorker'),
                    ('_open_spending_wallet','_ManagedSpendSessionWorker'),
                    ('_inspect_crash_preview','_CrashPreviewWorker')]
        for operation,name in operations:
            with self.subTest(operation=operation):
                if operation in ('_open_spending_wallet','_inspect_crash_preview'):self.vault()
                self.ready()
                def denied(*args,**kwargs):
                    self.nested(lambda:self.win._managed_denied('PUBLIC_TEST_DENIAL'))
                    return self.password()
                with (patch('wam_regtest.managed_gui.QMessageBox.question',return_value=QMessageBox.StandardButton.Yes),
                      patch('wam_regtest.managed_gui.QInputDialog.getText',side_effect=denied),
                      patch('wam_regtest.managed_gui.'+name) as worker):
                    getattr(self.win,operation)()
                    worker.assert_not_called()
                self.assertIsNone(self.win._worker)

    def test_ready_after_denial_cannot_revive_old_password_approval(self):
        def changed(*args,**kwargs):
            def tick():
                self.win._managed_denied('PUBLIC_TEST_DENIAL');self.ready()
            self.nested(tick)
            return self.password()
        with (patch('wam_regtest.managed_gui.QInputDialog.getText',side_effect=changed),
              patch('wam_regtest.managed_gui._LockedWalletWorker') as worker):
            self.win._verify_wallet();worker.assert_not_called()
        self.assertTrue(self.win._managed_authenticated)

    def test_timer_nested_actions_file_drop_and_close_cannot_occupy_modal_worker(self):
        names=['_ManagedStatusWorker','_ManagedWalletSnapshotWorker',
               '_ManagedWalletCreateWorker','_ManagedSpendSessionWorker',
               '_CrashPreviewWorker','_CoreSqliteInspectionWorker']
        def prompt(*args,**kwargs):
            def tick():
                self.assertFalse(self.win.refresh_button.isEnabled())
                self.assertFalse(self.win.verify_wallet_button.isEnabled())
                self.win.request_sync()
                self.win._verify_wallet();self.win._view_wallet()
                self.win._create_wallet();self.win._create_bip39_wallet()
                self.win._open_spending_wallet();self.win._inspect_crash_preview()
                self.win._inspect_core_sqlite(str(self.root/'public.dat'))
                self.win._choose_core_sqlite();self.win._create_bip39_phrase()
                self.win._confirm_stop()
                self.assertFalse(self.win.close())
                self.assertIsNone(self.win._worker)
            self.nested(tick)
            return self.password()
        with ExitStack() as stack:
            blocked=[stack.enter_context(patch('wam_regtest.managed_gui.'+n)) for n in names]
            locked=stack.enter_context(patch('wam_regtest.managed_gui._LockedWalletWorker'))
            stack.enter_context(patch('wam_regtest.managed_gui.QInputDialog.getText',side_effect=prompt))
            self.win._verify_wallet()
            locked.assert_called_once();locked.return_value.start.assert_called_once()
            for worker in blocked:worker.assert_not_called()

    def test_worker_or_paths_changed_during_prompt_are_not_overwritten(self):
        for change in ('worker','path'):
            with self.subTest(change=change):
                occupied=object()
                original=self.win._wallet_core_dir
                def changed(*args,**kwargs):
                    if change=='worker':self.win._worker=occupied
                    else:self.win._wallet_core_dir=self.root/'other-core'
                    return self.password()
                try:
                    with (patch('wam_regtest.managed_gui.QInputDialog.getText',side_effect=changed),
                          patch('wam_regtest.managed_gui._LockedWalletWorker') as worker):
                        self.win._verify_wallet();worker.assert_not_called()
                    if change=='worker':self.assertIs(self.win._worker,occupied)
                finally:
                    self.win._worker=None;self.win._wallet_core_dir=original

    def test_cancel_and_exception_restore_exclusion_without_starting(self):
        for failure in (False,True):
            with self.subTest(failure=failure):
                with (patch('wam_regtest.managed_gui.QInputDialog.getText',
                            side_effect=RuntimeError('PUBLIC_TEST') if failure else None,
                            return_value=('',False)),
                      patch('wam_regtest.managed_gui._LockedWalletWorker') as worker):
                    if failure:
                        with self.assertRaises(RuntimeError):self.win._verify_wallet()
                    else:self.win._verify_wallet()
                    worker.assert_not_called()
                self.assertFalse(self.win._managed_dialog_open)
                self.assertTrue(self.win.verify_wallet_button.isEnabled())

    def test_stable_approved_wallet_actions_still_start_once(self):
        for operation,name in [('_verify_wallet','_LockedWalletWorker'),
                               ('_view_wallet','_ManagedWalletSnapshotWorker'),
                               ('_create_wallet','_ManagedWalletCreateWorker'),
                               ('_open_spending_wallet','_ManagedSpendSessionWorker')]:
            with self.subTest(operation=operation):
                if operation=='_open_spending_wallet':self.vault()
                with (patch('wam_regtest.managed_gui.QMessageBox.question',return_value=QMessageBox.StandardButton.Yes),
                      patch('wam_regtest.managed_gui.QInputDialog.getText',side_effect=self.password),
                      patch('wam_regtest.managed_gui.'+name) as worker):
                    getattr(self.win,operation)()
                    worker.assert_called_once();worker.return_value.start.assert_called_once()
                self.win._worker=None

    def test_bip39_confirmation_loss_clears_material_without_worker(self):
        from wam_regtest.bip39_gui import Bip39CreationDialog
        accepted=Bip39CreationDialog.DialogCode.Accepted
        with (patch('wam_regtest.managed_gui.QMessageBox.question',return_value=QMessageBox.StandardButton.Yes),
              patch('wam_regtest.managed_gui.QInputDialog.getText',side_effect=self.password),
              patch('wam_regtest.bip39_gui.Bip39CreationDialog') as dialog,
              patch('wam_regtest.managed_gui._ManagedWalletCreateWorker') as worker):
            dialog.DialogCode.Accepted=accepted
            dialog.return_value.confirmed=True
            def lose():
                self.nested(lambda:self.win._managed_denied('PUBLIC_TEST_DENIAL'))
                return accepted
            dialog.return_value.exec.side_effect=lose
            self.win._create_bip39_wallet()
            worker.assert_not_called()
            dialog.return_value.take_wallet_material.assert_not_called()
            dialog.return_value._clear_sensitive.assert_called_once()

    def test_approved_stop_and_offline_file_inspection_handoff_without_queued_approval(self):
        with (patch('wam_regtest.managed_gui.QMessageBox.question',return_value=QMessageBox.StandardButton.Yes),
              patch('wam_regtest.managed_gui._ManagedStatusWorker') as worker):
            self.win._confirm_stop()
            worker.assert_called_once_with(self.root,'shutdown')
            worker.return_value.start.assert_called_once()
        self.win._worker=None
        self.win._managed_denied('PUBLIC_TEST_OFFLINE')
        filename=str(self.root/'public.dat')
        with (patch('wam_regtest.managed_gui.QFileDialog.getOpenFileName',return_value=(filename,'')),
              patch('wam_regtest.managed_gui._CoreSqliteInspectionWorker') as worker):
            self.win._choose_core_sqlite()
            worker.assert_called_once_with(Path(filename))
            worker.return_value.start.assert_called_once()
