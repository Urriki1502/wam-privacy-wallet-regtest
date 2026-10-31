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
 def test_receive_count_uses_complete_fingerprint_not_window(self):
  page=ReceivePage();self.addCleanup(page.deleteLater)
  snap=replace(fixture(),history=(HistoryRow('b'*64,104,2,0,1),),receive_count=12)
  page.render_snapshot(snap)
  self.assertIn('12 confirmed',page.received.text())
 def test_operational_window_pages_the_same_session_without_a_privileged_call(self):
  from time import monotonic,sleep
  from wam_regtest.history_pages import GUI_HISTORY_LIMIT
  from wam_regtest.operational_gui import OperationalWalletWindow
  limit=GUI_HISTORY_LIMIT
  def row(i):
   return HistoryRow(f'{i:064x}',100,2,1,0)
  newest=tuple(row(i) for i in range(limit,0,-1))
  older=tuple(row(i) for i in range(limit+3,limit,-1))
  base=fixture()
  def page(rows,offset,complete):
   return replace(base,history=rows,history_count=limit+3,history_complete=complete,
                  history_offset=offset,receive_count=limit+3,signer_allowed=True,
                  broadcast_allowed=True,height=400,confirmed_atoms=limit+3,confirmed_utxos=1)
  pages={0:page(newest,0,False),limit:page(older,limit,False)}
  class Session:
   locked=False;faulted=False
   core_dir=Path('/tmp/wam-q05-page-core');datadir=Path('/tmp/wam-q05-page-data');source=Path('/tmp/wam-q05-page-wsp')
   def __init__(self):self.calls=[]
   def snapshot(self,history_offset=0):
    self.calls.append(history_offset)
    return pages[history_offset]
   def prepare(self,*_a,**_k):raise AssertionError('prepare')
   def sign(self,*_a,**_k):raise AssertionError('sign')
   def broadcast(self,*_a,**_k):raise AssertionError('broadcast')
   def mine(self,*_a,**_k):raise AssertionError('mine')
   def lock(self,*_a,**_k):raise AssertionError('lock')
  session=Session()
  window=OperationalWalletWindow(session);self.addCleanup(window.deleteLater)
  window._sync_timer.stop();window._theme_timer.stop()
  window.apply_snapshot(pages[0]);self.app.processEvents()
  history=window.history_page
  self.assertTrue(history.older.isEnabled());self.assertFalse(history.newer.isEnabled())
  self.assertEqual(tuple(row.txid for row in history.rows),tuple(row.txid for row in newest))
  def idle():
   deadline=monotonic()+10
   while window._worker is not None:
    self.app.processEvents()
    if monotonic()>deadline:self.fail('history read worker did not finish')
    sleep(0.01)
  history.older.click();idle()
  self.assertEqual(session.calls,[limit])
  self.assertEqual(tuple(item.txid for item in history.rows),tuple(item.txid for item in older))
  self.assertEqual(history._offset,limit);self.assertTrue(history.newer.isEnabled());self.assertFalse(history.older.isEnabled())
  history.newer.click();idle()
  self.assertEqual(session.calls,[limit,0])
  self.assertEqual(tuple(item.txid for item in history.rows),tuple(item.txid for item in newest))
  self.assertEqual(window._history_offset,0);self.assertIsNone(window._worker)
  complete=replace(pages[0],history=newest[:2],history_count=2,history_complete=True,history_offset=0,receive_count=2)
  before=list(session.calls)
  window.apply_snapshot(complete);history.older.click();self.app.processEvents()
  self.assertFalse(history.older.isEnabled());self.assertEqual(session.calls,before)
  self.assertEqual(tuple(item.txid for item in history.rows),tuple(item.txid for item in newest[:2]))
 def test_older_history_control_emits_offset_without_signing(self):
  from wam_regtest.history_pages import GUI_HISTORY_LIMIT
  page=HistoryPage();self.addCleanup(page.deleteLater)
  rows=tuple(HistoryRow(f'{i:064x}',100+i,2,1,0) for i in range(GUI_HISTORY_LIMIT))
  snap=replace(fixture(),history=rows,history_count=GUI_HISTORY_LIMIT+40,history_complete=False,
               history_offset=0,receive_count=40)
  seen=[]
  page.page_requested.connect(seen.append)
  page.render_snapshot(snap)
  self.assertTrue(page.older.isEnabled());self.assertFalse(page.newer.isEnabled())
  page.older.click();self.assertEqual(seen,[GUI_HISTORY_LIMIT])
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
