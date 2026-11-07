"""Clipboard adapter may notify an ownership change during its current read."""
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from wam_regtest.bip39_owner_gui import Bip39RecoveryVerifyDialog
class ClipboardReadTransition(unittest.TestCase):
 def test_republished_same_text_during_final_read_is_not_cleared(self):
  app=QApplication.instance() or QApplication([]);dialog=Bip39RecoveryVerifyDialog();clip=app.clipboard()
  public='abandon '*11+'about';clip.setText(public)
  real=clip.text;reads=0
  def read(*args):
   nonlocal reads
   reads+=1
   if reads==2:
    clip.setText('public intermediate');clip.setText(public)
   return real(*args)
  try:
   with patch.object(clip,'text',read):dialog._on_paste()
   self.assertEqual(real(),public)
  finally:clip.clear();dialog.reject();dialog.deleteLater();app.processEvents()
