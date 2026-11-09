"""Real Qt clipboard ownership regression; public synthetic BIP39 only."""
import contextlib
import io
import os
import unittest
from unittest.mock import patch
try:
 from PySide6.QtWidgets import QApplication
 from wam_regtest.bip39_owner_gui import Bip39RecoveryVerifyDialog
except ImportError:
 QApplication = None

@unittest.skipIf(QApplication is None, 'PySide6 required')
class ClipboardOwnership(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.app=QApplication.instance() or QApplication([])
 def setUp(self):
  self.dialog=Bip39RecoveryVerifyDialog()
  self.clip=self.app.clipboard()
  self.words='abandon '*11+'about'
 def tearDown(self):
  self.dialog.reject();self.dialog.deleteLater();self.clip.clear();self.app.processEvents()
 def test_newer_clipboard_during_consumption_is_preserved(self):
  original=self.dialog._apply_paste
  def consume(text):
   original(text);self.clip.setText('new public address')
  self.clip.setText(self.words)
  with patch.object(self.dialog,'_apply_paste',consume):self.dialog._on_paste()
  self.assertEqual(self.clip.text(),'new public address')
 def test_same_text_republished_by_new_owner_is_preserved(self):
  original=self.dialog._apply_paste
  def consume(text):
   original(text);self.clip.setText('intermediate public content');self.clip.setText(text)
  self.clip.setText(self.words)
  with patch.object(self.dialog,'_apply_paste',consume):self.dialog._on_paste()
  self.assertEqual(self.clip.text(),self.words)
 def test_failed_consume_is_redacted_and_clears_unchanged_clipboard_and_fields(self):
  self.clip.setText(self.words);out=io.StringIO();signals=[]
  self.dialog.verify_requested.connect(signals.append)
  with patch.object(self.dialog,'_apply_paste',side_effect=ValueError(self.words)):
   with contextlib.redirect_stdout(out),contextlib.redirect_stderr(out):self.dialog._on_paste()
  self.assertEqual(self.clip.text(),'');self.assertEqual(signals,[])
  self.assertNotIn(self.words,out.getvalue())
  self.assertTrue(all(not x.text() for x in self.dialog._fields))
 def test_paste_cancel_emits_no_phrase_and_does_not_clear_newer_public_clipboard(self):
  signals=[];self.dialog.verify_requested.connect(signals.append)
  self.clip.setText(self.words);self.dialog._on_paste();self.clip.setText('public TXID')
  self.dialog._on_cancel()
  self.assertEqual(signals,[]);self.assertEqual(self.clip.text(),'public TXID')
  self.assertTrue(all(not x.text() for x in self.dialog._fields))

 def _assert_cleanup_error_redacted(self,operation,adapter):
  self.clip.setText(self.words);output=io.StringIO();signals=[];escaped=None
  self.dialog.verify_requested.connect(signals.append)
  with patch.object(self.clip,operation,adapter),contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
   try:self.dialog._on_paste()
   except Exception as error:escaped=(type(error).__name__,'PRIVATE_ADAPTER_ERROR_SENTINEL' in str(error))
  self.assertIsNone(escaped,'Cleanup adapter exceptions must not escape a Qt slot')
  self.assertEqual(signals,[])
  self.assertNotIn('PRIVATE_ADAPTER_ERROR_SENTINEL',output.getvalue())
  self.assertNotIn(self.words,output.getvalue())
  self.assertTrue(all(not field.text() for field in self.dialog._fields))
  self.assertFalse(self.dialog._verify_error.isHidden())
 def test_final_clipboard_read_error_is_redacted_and_fields_cleared(self):
  original=self.clip.text;reads=0
  def read(*args):
   nonlocal reads
   reads+=1
   if reads==2:raise RuntimeError('PRIVATE_ADAPTER_ERROR_SENTINEL')
   return original(*args)
  self._assert_cleanup_error_redacted('text',read)
 def test_clipboard_clear_error_is_redacted_and_fields_cleared(self):
  def clear(*args):raise RuntimeError('PRIVATE_ADAPTER_ERROR_SENTINEL')
  self._assert_cleanup_error_redacted('clear',clear)
