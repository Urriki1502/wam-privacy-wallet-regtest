"""Existing Q06 history controls must request bounded, read-only pages."""
import unittest
import importlib.util
import os
import sys
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
from wam_regtest.bip39_owner_backend import Bip39ReadOnlyBackend,Q06ReadOnlyError

class PagingBackend(unittest.TestCase):
    def test_valid_existing_snapshot_offset_reaches_reader(self):
        backend=Bip39ReadOnlyBackend(Path('/unused'),Path('/unused'),Path('/unused'))
        with patch.object(backend,'_scan_q06',return_value={'read_only':True}) as scan:
            self.assertEqual(backend.execute('snapshot',(250,),{}),{'read_only':True})
            scan.assert_called_once_with(250)
        self.assertIsNone(backend.owner)

    def test_invalid_offsets_never_open_core(self):
        for offset in (True,-1,1_000_001,1.5,'250',None):
            backend=Bip39ReadOnlyBackend(Path('/unused'),Path('/unused'),Path('/unused'))
            with self.assertRaises(Q06ReadOnlyError):backend.execute('snapshot',(offset,),{})
            self.assertIsNone(backend.owner)

if sys.platform=='linux' and not os.environ.get('DISPLAY'):
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

@unittest.skipUnless(importlib.util.find_spec('PySide6') is not None, 'Requires native Qt-capable runner')
class PagingWidgets(unittest.TestCase):
    def test_older_existing_control_requests_page_without_payment(self):
        from wam_regtest.desktop import qt_application
        from wam_regtest.wallet_executor import ExecutorState
        from wam_regtest.bip39_fusion_gui import Bip39FusionWindow
        from wam_regtest.wallet_read import WalletReadSnapshot,HistoryRow
        app=qt_application();owner=SimpleNamespace(state=ExecutorState(locked=False),busy=False,closed=False)
        window=Bip39FusionWindow(owner);calls=[]
        try:
            window._ready=True
            row=HistoryRow('a'*64,1,1,1000,0)
            snapshot=WalletReadSnapshot('regtest',1,'b'*64,'public-test-only',1000,1,(row,), 'c'*64,
                history_count=251,history_complete=False,history_offset=0)
            window.history_page.render_snapshot(snapshot)
            self.assertNotIn('fingerprinted in custody',window.history_page.scope.text())
            with patch.object(window,'_command',side_effect=lambda *a:calls.append(a)):
                window.history_page.older.click()
            self.assertEqual(calls,[('snapshot',250)])
        finally:
            window._poll.stop();window.hide();window.deleteLater();app.processEvents()

    def test_locked_faulted_or_unready_page_never_dispatches(self):
        from wam_regtest.desktop import qt_application
        from wam_regtest.wallet_executor import ExecutorState
        from wam_regtest.bip39_fusion_gui import Bip39FusionWindow
        app=qt_application()
        for state,ready in ((ExecutorState(locked=True),True),
                            (ExecutorState(locked=False,faulted=True),True),
                            (ExecutorState(locked=False),False)):
            owner=SimpleNamespace(state=state,busy=False,closed=False)
            window=Bip39FusionWindow(owner);window._ready=ready
            try:
                with patch.object(window,'_command') as command:
                    self.assertFalse(window._request_history_page(250))
                    command.assert_not_called()
            finally:
                window._poll.stop();window.hide();window.deleteLater();app.processEvents()

if __name__=='__main__':unittest.main()
