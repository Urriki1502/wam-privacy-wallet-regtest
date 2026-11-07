"""Actual Qt surface contracts; genuine Core proof is separate native/frozen."""
from types import SimpleNamespace
import importlib.util,os,sys,unittest
if sys.platform=='linux' and not os.environ.get('DISPLAY'):
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

@unittest.skipUnless(importlib.util.find_spec('PySide6') is not None,'Qt controls only; native/frozen proof separate')
class UnsignedDraftControls(unittest.TestCase):
    def setUp(self):
        from PySide6.QtWidgets import QApplication
        from wam_regtest.wallet_executor import ExecutorState
        from wam_regtest.bip39_fusion_gui import Bip39FusionWindow
        self.app=QApplication.instance() or QApplication([])
        self.owner=SimpleNamespace(state=ExecutorState(locked=False,core_alive=True),busy=False,closed=False)
        self.window=Bip39FusionWindow(self.owner)
        self.window._ready=self.window._spend_enabled=True
        self.calls=[]
        self.window._command=lambda *args:self.calls.append(args)
    def tearDown(self):
        self.window._poll.stop();self.window.hide();self.window.deleteLater();self.app.processEvents()
    def test_unsigned_cancel_eligibility_and_irreversible_denial(self):
        from wam_regtest.wallet_executor import ExecutorState
        w=self.window
        for name,commit,signed,busy,state,expected in [
            ('empty',None,False,False,ExecutorState(locked=False,core_alive=True),False),
            ('preparing',None,False,True,ExecutorState(locked=False,core_alive=True),False),
            ('review','a'*64,False,False,ExecutorState(locked=False,core_alive=True),True),
            ('signing','a'*64,False,True,ExecutorState(locked=False,core_alive=True),False),
            ('signed','a'*64,True,False,ExecutorState(locked=False,core_alive=True),False),
            ('uncertain','a'*64,False,False,ExecutorState(locked=False,core_alive=True,faulted=True),False),
            ('locked','a'*64,False,False,ExecutorState(locked=True,core_alive=True),False),
            ('reauth','a'*64,False,False,ExecutorState(locked=False,core_alive=True,reauthentication_required=True),False),
            ('confirmed',None,False,False,ExecutorState(locked=False,core_alive=True),False)]:
            with self.subTest(state=name):
                w._approved_commitment=commit;w._signed_ready=signed;self.owner.busy=busy;self.owner.state=state
                w._set_actions();self.assertEqual(w.cancel.isEnabled(),expected)
        self.owner.busy=False;self.owner.state=ExecutorState(locked=False,core_alive=True)
        w._approved_commitment='a'*64;w._signed_ready=False;w._set_actions();w.cancel.click()
        self.assertEqual(self.calls,[('cancel',)])
    def test_real_qt_approval_rejection_cancels_without_sign_or_broadcast(self):
        from wam_regtest.wallet_session import PaymentReview
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        w=self.window
        review=PaymentReview('wamrtsp1public',123456789,10000,100000000,1,'b'*64)
        w._completed_result=('prepare',review)
        w._finished();self.app.processEvents()
        dialog=QApplication.activeModalWidget()
        self.assertIsNotNone(dialog);self.assertTrue(dialog.cancel.isDefault())
        self.assertTrue(w.cancel.isEnabled())
        dialog.cancel.click();self.app.processEvents()
        self.assertEqual(self.calls,[('cancel',)])
        self.assertFalse(w._signed_ready)
    def test_recovered_unsigned_draft_explicit_cancel_controls(self):
        from wam_regtest.wallet_executor import ExecutorState
        w=self.window;ok=ExecutorState(locked=False,core_alive=True)
        snap=lambda flag:{'recovered_unsigned_cancel_available':flag,'signer_allowed':True,
                          'payment_review':None,'payment_signed':False,'pending_confirm_txid':None,
                          'receive_code':'wamrtsp1public','confirmed_atoms':5,'available_atoms':0 if flag else 5,
                          'height':1,'tip':'c'*64,'history':(),'reservation_count':1 if flag else 0}
        # Presentation flag comes only from the backend's verified snapshot,
        # through the real production handler.
        from wam_regtest.bip39_owner_gui import Bip39TrialWindow
        Bip39TrialWindow._on_ready(w,'snapshot',snap(True));w._set_actions()
        self.assertTrue(w._recovered_unsigned_cancel)
        self.assertTrue(w.cancel.isEnabled());self.assertFalse(w.send.isEnabled())
        w.recipient_input.setText('wamrtsp1public');w.amount_input.setText('1');w.fee_input.setText('0.0001')
        w._prepare_send();self.assertEqual(self.calls,[])  # New payment waits.
        for name,state,busy in [('faulted',ExecutorState(locked=False,core_alive=True,faulted=True),False),
                                ('locked',ExecutorState(locked=True,core_alive=True),False),
                                ('reauth',ExecutorState(locked=False,core_alive=True,reauthentication_required=True),False),
                                ('busy',ok,True)]:
            with self.subTest(state=name):
                self.owner.state=state;self.owner.busy=busy;w._set_actions()
                self.assertFalse(w.cancel.isEnabled())
        self.owner.state=ok;self.owner.busy=False;w._set_actions()
        w._signed_ready=True;w._set_actions();self.assertFalse(w.cancel.isEnabled())
        w._signed_ready=False;w._set_actions();w.cancel.click()
        self.assertEqual(self.calls,[('cancel',)])
        Bip39TrialWindow._on_ready(w,'cancel',{'recovered_unsigned_cancelled':True,
                                              'signer_allowed':False,'broadcast_allowed':False})
        self.assertFalse(w._recovered_unsigned_cancel)
        self.assertEqual(w._pending_action,('snapshot',))  # Read only; never a write retry.
        Bip39TrialWindow._on_ready(w,'snapshot',snap(False));w._set_actions()
        self.assertFalse(w.cancel.isEnabled());self.assertTrue(w.send.isEnabled())
        # Lock/quit/open clear the cached flag; it never survives authority loss.
        for action in ('lock','open'):
            w._recovered_unsigned_cancel=True
            try:Bip39TrialWindow._on_ready(w,action,{})
            except Exception:pass
            self.assertFalse(w._recovered_unsigned_cancel)
    def test_fee_and_amount_validation_never_dispatch_invalid_values(self):
        w=self.window;w.recipient_input.setText('wamrtsp1public');w.amount_input.setText('1.23456789')
        for fee in ['0','-1','0.000000001','0.01000001','NaN','1e-8']:
            w.fee_input.setText(fee);w._prepare_send();self.assertEqual(self.calls,[])
        for raw,fee in [('0.00000001',1),('0.000001',100),('0.01',1000000)]:
            w.fee_input.setText(raw);w._prepare_send();self.assertEqual(self.calls.pop(),('prepare','wamrtsp1public',123456789,fee))

if __name__=='__main__':unittest.main(verbosity=2)
