"""Presentation unit fixtures only; real acceptance uses Core-backed native probes."""
from dataclasses import replace
import ast
from pathlib import Path
import unittest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication,QDialog
from wam_regtest.desktop import qt_application
from wam_regtest.fusion_ui import fusion_palette,ReadableText
from wam_regtest.fusion_pages import ReceivePage,HistoryPage,PaymentApproval
from wam_regtest.wallet_read import WalletReadSnapshot,HistoryRow
from wam_regtest.wallet_session import PaymentReview
from wam_sp.keystore import ScanAccount
from wam_sp.core import pub


def fixture():
 return WalletReadSnapshot('regtest',105,'a'*64,ScanAccount(0,1,pub(2),birthday=1).payment_code(),125000000,1,
  (HistoryRow('b'*64,104,2,150000000,0),HistoryRow('c'*64,105,1,1000000,26000000)),'d'*64)

class FusionV2Widgets(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=qt_application()
 def test_receive_copy_exact_and_clear_qr_after_lock(self):
  page=ReceivePage();self.addCleanup(page.deleteLater);snap=fixture();page.render_snapshot(snap)
  self.assertIsNotNone(page.qr.matrix);page.copy_button.click();self.assertEqual(self.app.clipboard().text(),snap.receive_code)
  self.assertEqual(page.receive_code.text(),snap.receive_code)
  page.render_snapshot(None);self.assertIsNone(page.qr.matrix);self.assertIsNone(page.code);self.assertFalse(page.copy_button.isEnabled())
 def test_invalid_receive_address_never_produces_a_qr(self):
  page=ReceivePage();self.addCleanup(page.deleteLater)
  page.render_snapshot(fixture())
  with self.assertRaises(ValueError):page.render_snapshot(replace(fixture(),receive_code='wamrtsp1-invalid'))
  self.assertIsNone(page.qr.matrix);self.assertIsNone(page.code);self.assertFalse(page.copy_button.isEnabled())
 def test_history_filter_detail_copy_and_failure_clear(self):
  page=HistoryPage();self.addCleanup(page.deleteLater);snap=fixture();page.render_snapshot(snap)
  page.select_txid('b'*64);self.assertEqual(page.detail_id.text(),'b'*64);page.copy_button.click();self.assertEqual(self.app.clipboard().text(),'b'*64)
  page.filter.setCurrentIndex(2);self.assertTrue(page.table.isRowHidden(0));self.assertFalse(page.table.isRowHidden(1))
  page.search.setText('missing');self.assertTrue(page.table.isRowHidden(1));self.assertFalse(page.copy_button.isEnabled())
  page.render_snapshot(None);self.assertEqual(page.rows,());self.assertEqual(page.table.rowCount(),0);self.assertNotIn('b'*64,page.detail_id.text())
 def test_confirmation_defaults_to_cancel_and_cannot_approve_itself(self):
  review=PaymentReview(fixture().receive_code,100000,10000,400000,1,'e'*64)
  for kind in ('sign','broadcast'):
   dialog=PaymentApproval(review,kind,None);self.addCleanup(dialog.deleteLater)
   self.assertTrue(dialog.cancel.isDefault());self.assertFalse(dialog.approve.isDefault());self.assertEqual(dialog.result(),QDialog.DialogCode.Rejected)
   dialog.cancel.click();self.assertEqual(dialog.result(),QDialog.DialogCode.Rejected)
 def test_selectable_wrap_never_changes_hash_or_payment_code(self):
  text=ReadableText(fixture().receive_code);self.addCleanup(text.deleteLater);text.resize(250,120);text.show();self.app.processEvents()
  self.assertEqual(text.toPlainText(),fixture().receive_code);self.assertEqual(text.text(),fixture().receive_code)
  self.assertTrue(text.isReadOnly());self.assertLess(text.minimumSizeHint().width(),100)
 def test_semantic_text_contrast_on_cards(self):
  def luminance(hexcolor):
   parts=[int(hexcolor[i:i+2],16)/255 for i in (1,3,5)]
   return sum(weight*(x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4) for weight,x in zip((.2126,.7152,.0722),parts))
  for mode in ('dark','light'):
   colors=fusion_palette(mode)
   for text in ('text','muted','accent','green','red'):
    for surface in ('bg','surface','panel'):
     values=sorted((luminance(colors[text]),luminance(colors[surface])))
     self.assertGreaterEqual((values[1]+.05)/(values[0]+.05),4.5,(mode,text,surface))
 def test_presentation_has_no_signer_or_rpc_authority(self):
  source=Path(__file__).resolve().parents[1]/'src/wam_regtest'
  for name in ('fusion_ui.py','fusion_pages.py'):
   tree=ast.parse((source/name).read_text())
   for item in ast.walk(tree):
    if isinstance(item,ast.Call) and isinstance(item.func,ast.Attribute):
     self.assertNotIn(item.func.attr,('sign','broadcast','prepare','advance','sendrawtransaction','snapshot'))
