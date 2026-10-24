"""Qt SOURCE layout contracts, never a substitute for Windows frozen evidence."""
from pathlib import Path
import unittest
from shiboken6 import delete
from wam_regtest.desktop import qt_application
from wam_regtest.managed_gui import ManagedCoreWindow
from wam_regtest.q17_layout import inspect_window,widget_geometry
from wam_regtest.supervisor_protocol import public_status


class Q17LayoutContracts(unittest.TestCase):
    def setUp(self):
        self.app=qt_application()
        self.window=ManagedCoreWindow(Path('C:/q17-layout-no-node') if __import__('sys').platform=='win32' else Path('/tmp/q17-layout-no-node'))
        self.window.show();self.app.processEvents()

    def tearDown(self):
        self.assertTrue(self.window.close());delete(self.window);self.app.processEvents()

    def test_minimum_and_normal_layout_full_text_in_each_display_state(self):
        window=self.window
        for state in ('error','stopped','ready','recovery-needed'):
            window._apply_managed_status(public_status(state=state,owned=True,chain_height=104 if state=='ready' else None))
            for mode in (0,1,2):
                window.appearance.setCurrentIndex(mode)
                for width,height in ((820,600),(900,650),(1280,800)):
                    with self.subTest(state=state,mode=mode,width=width):
                        window.resize(width,height)
                        for _ in range(3):self.app.processEvents()
                        proof=inspect_window(window,self.app)
                        self.assertEqual(len(proof['controls']),8)
                        self.assertEqual(len(proof['welcome_actions']),9)
                        self.assertIsNone(window.session)
                        self.assertIsNone(window._snapshot)
                        self.assertIsNone(window._spend_window)

    def test_detector_rejects_real_clipped_or_hidden_controls(self):
        window=self.window;window.resize(820,600);self.app.processEvents()
        window.start_core.setFixedWidth(20);self.app.processEvents()
        with self.assertRaisesRegex(ValueError,'Q17_TEXT_CLIPPED'):
            widget_geometry(window.start_core,window,'start_core')
        window.stop_core.hide()
        with self.assertRaisesRegex(ValueError,'Q17_ESSENTIAL_CONTROL_HIDDEN'):
            widget_geometry(window.stop_core,window,'stop_core')

    def test_observer_does_not_reveal_deliberately_hidden_mining_item(self):
        from PySide6.QtWidgets import QListWidgetItem,QWidget
        item=QListWidgetItem('Mining Account');self.window.navigation.addItem(item)
        self.window.stack.addWidget(QWidget());item.setHidden(True)
        self.window.resize(820,600);self.app.processEvents()
        proof=inspect_window(self.window,self.app)
        self.assertEqual(proof['hidden_navigation'],['Mining Account'])
        self.assertTrue(item.isHidden())
        self.assertNotIn('Mining Account',[r['text'] for r in proof['navigation']])
