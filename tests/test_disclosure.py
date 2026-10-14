import unittest
from dataclasses import replace
from wam_regtest.disclosure import LocalDisclosureGate,DisclosureError
class DisclosureContracts(unittest.TestCase):
    def setUp(self):
        self.now=1.;self.g=LocalDisclosureGate('a'*32,clock=lambda:self.now)
        self.fact={'txid':'1'*64,'block_height':104,'credit_atoms':1000,'debit_atoms':0};self.anchor=(1,'2'*64)
    def tearDown(self): self.g.close()
    def ticket(self): return self.g.issue(self.fact,('block_height',),self.anchor,approved=True,authenticated=True)
    def test_projection_and_replay(self):
        t=self.ticket();result=self.g.release(t,self.fact,self.anchor)
        self.assertEqual(result['facts'],{'block_height':104});self.assertFalse(result['ownership_proof'])
        with self.assertRaises(DisclosureError):self.g.release(t,self.fact,self.anchor)
        self.assertNotIn(self.fact['txid'],str(self.g.audit))
    def test_scope_expiry_revocation_and_mutation(self):
        for mode in ('expire','revoke','anchor','session','fields','record','mac'):
            with self.subTest(mode=mode):
                self.now=1.;t=self.ticket();r=dict(self.fact);a=self.anchor
                if mode=='expire':self.now=31.
                elif mode=='revoke':self.g.revoke(t)
                elif mode=='anchor':a=(2,'3'*64)
                elif mode=='session':t=replace(t,session='b'*32)
                elif mode=='fields':t=replace(t,fields=('txid',))
                elif mode=='record':r['credit_atoms']=1001
                elif mode=='mac':t=replace(t,mac='0'*64)
                with self.assertRaises(DisclosureError):self.g.release(t,r,a)
    def test_auth_consent_and_private_fields(self):
        for fields,approved,auth in ((('private_key',),True,True),(('*',),True,True),(('txid',),False,True),(('txid',),True,False),(('txid',),1,True)):
            with self.assertRaises(DisclosureError):self.g.issue(self.fact,fields,self.anchor,approved=approved,authenticated=auth)
    def test_invalid_fact_rejects_with_redacted_audit(self):
        fact={**self.fact,'private_key':'not-a-real-key'}
        with self.assertRaises(DisclosureError):self.g.issue(fact,('txid',),self.anchor,approved=True,authenticated=True)
        self.assertEqual(self.g.audit,('DISCLOSE_DENIED',))
    def test_lock_and_new_session_reject_old_token(self):
        t=self.ticket();self.g.close()
        with self.assertRaises(DisclosureError):self.g.release(t,self.fact,self.anchor)
        new=LocalDisclosureGate('a'*32)
        try:
            with self.assertRaises(DisclosureError):new.release(t,self.fact,self.anchor)
        finally:new.close()
if __name__=='__main__':unittest.main()
