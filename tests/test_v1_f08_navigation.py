"""F-08 native-Qt guided managed onboarding contracts (UNIT/GUI only).

All cases use an isolated empty temporary root, authenticated status SHAPES
and no WAM daemon. They never create/restore keys, invoke a Core socket, or
qualify real-hardware appearance, wallet importing, or spending.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PySide6.QtWidgets import QScrollArea
from shiboken6 import delete,isValid

from wam_regtest.desktop import qt_application
from wam_regtest.managed_gui import ManagedCoreWindow
from wam_regtest.supervisor_protocol import public_status


class F08ManagedWelcomeContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=qt_application()

    def setUp(self):
        self.temp=TemporaryDirectory(prefix='f08-welcome-test-')
        self.root=Path(self.temp.name).resolve()
        self.win=ManagedCoreWindow(self.root)
        self.addCleanup(self._dispose)

    def _dispose(self):
        if self.win is not None:
            window=self.win
            self.assertTrue(window.close())
            delete(window)
            self.assertFalse(isValid(window))
            self.win=None
            self.app.processEvents()
        self.temp.cleanup()

    def test_welcome_is_scrolling_default_without_obscuring_verified_pages(self):
        self.assertEqual(self.win.navigation.count(),4)
        self.assertEqual(
            [self.win.navigation.item(i).text() for i in range(4)],
            ['Overview','Receive','History','Get Started'])
        self.assertEqual(self.win.stack.count(),4)
        self.assertEqual(self.win.navigation.currentRow(),3)
        self.assertIs(self.win.stack.currentWidget(),self.win.welcome_page)
        self.assertIsInstance(self.win.welcome_page.scroll,QScrollArea)
        self.assertTrue(self.win.welcome_page.scroll.widgetResizable())
        self.assertEqual(self.win.welcome_page.core_state.text(),'Core: Unverified')
        self.assertIsNone(self.win._snapshot)
        self.assertIsNone(self.win.session)

    def test_unverified_workflow_controls_fail_closed_no_backend_activity(self):
        page=self.win.welcome_page
        for guide,original in self.win._f08_welcome_sources:
            self.assertEqual(guide.isEnabled(),original.isEnabled())
        for attr in ('start','create','verify','view','sync','send'):
            self.assertFalse(getattr(page,attr).isEnabled())
        page.start.click();page.create.click();page.send.click()
        self.assertIsNone(self.win._worker)
        self.assertIsNone(self.win.session)
        self.assertIsNone(self.win._snapshot)
        self.assertFalse(self.win.dashboard.go_send.isEnabled())

    def test_ready_supervisor_is_not_wallet_custody_authority(self):
        self.win._apply_managed_status(
            public_status(state='ready',owned=True,chain_height=101))
        page=self.win.welcome_page
        self.assertIn('Ready',page.core_state.text())
        self.assertIn('101',page.height_state.text())
        self.assertTrue(page.refresh.isEnabled())
        self.assertFalse(page.start.isEnabled())
        self.assertFalse(page.create.isEnabled())
        self.assertFalse(page.verify.isEnabled())
        self.assertFalse(page.send.isEnabled())
        self.assertFalse(self.win.dashboard.go_send.isEnabled())
        self.assertIsNone(self.win._snapshot)

    def test_original_controls_alone_authorize_create_or_verify(self):
        # No real paths are opened: these are only previously vetted
        # supervisor UI predicates, not successful custody operations.
        self.win._wallet_core_dir=self.root/'qualified-core'
        self.win._wallet_wsp_source=self.root/'wsp-source'
        self.win._apply_managed_status(
            public_status(state='ready',owned=True,chain_height=101))
        p=self.win.welcome_page
        self.assertTrue(p.create.isEnabled())
        self.assertFalse(p.verify.isEnabled())
        self.assertFalse(p.send.isEnabled())
        vault=self.root/'chain'/'wallet-vault'
        vault.mkdir(parents=True)
        self.win._update_controls()
        self.assertFalse(p.create.isEnabled())
        self.assertTrue(p.verify.isEnabled())
        self.assertTrue(p.send.isEnabled())
        self.assertIsNone(self.win.session)
        self.assertFalse(self.win.dashboard.go_send.isEnabled())
        # On GUI-only fixture, a supervisor status loss must revoke all.
        self.win._apply_managed_status(
            public_status(state='busy',owned=True,chain_height=None))
        self.assertFalse(p.create.isEnabled())
        self.assertFalse(p.verify.isEnabled())
        self.assertFalse(p.send.isEnabled())
        self.assertIn('unavailable',p.height_state.text().lower())

    def test_busy_worker_cannot_be_bypassed_by_secondary_page(self):
        self.win._wallet_core_dir=self.root/'qualified-core'
        self.win._wallet_wsp_source=self.root/'wsp-source'
        self.win._apply_managed_status(
            public_status(state='ready',owned=True,chain_height=101))
        self.assertTrue(self.win.welcome_page.create.isEnabled())
        worker=object()
        self.win._worker=worker
        self.win._update_controls()
        self.assertFalse(self.win.welcome_page.create.isEnabled())
        self.assertFalse(self.win.welcome_page.refresh.isEnabled())
        self.assertFalse(self.win.welcome_page.inspect.isEnabled())
        self.win._worker=None
        self.win._update_controls()
        self.assertTrue(self.win.welcome_page.create.isEnabled())

    def test_status_renderer_rejects_unverified_or_invalid_state(self):
        page=self.win.welcome_page
        for bad in (
            dict(state='mainnet',authenticated=True,height=1,wallet_exists=False),
            dict(state='ready',authenticated=1,height=1,wallet_exists=False),
            dict(state='ready',authenticated=True,height=True,wallet_exists=False),
            dict(state='ready',authenticated=True,height=-1,wallet_exists=False),
            dict(state='ready',authenticated=True,height=1,wallet_exists='yes'),
        ):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                page.render_status(**bad)
        page.render_status(
            state='ready',authenticated=False,height=101,wallet_exists=True)
        self.assertEqual(page.core_state.text(),'Core: Unverified')
        self.assertIn('unavailable',page.height_state.text().lower())
        self.assertIn('verification required',page.wallet_state.text())

    def test_readonly_overview_receive_history_remain_navigable(self):
        for i in range(3):
            self.win.navigation.setCurrentRow(i)
            self.assertIs(self.win.stack.currentWidget(),
                          (self.win.dashboard,self.win.receive_page,
                           self.win.history_page)[i])
            self.assertIsNone(self.win._snapshot)
        self.win.navigation.setCurrentRow(3)
        self.assertIs(self.win.stack.currentWidget(),self.win.welcome_page)


if __name__=='__main__':
    unittest.main()
