"""F-06 adversarial invariant tests; PSBT decoder mocked in UNIT only.

Actual native Core/WSP wallet E2E exercises real PSBTv2 and genuine SQLite.
No mock success may qualify a native Core send/sign gate.
"""
from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from wam_regtest.f06_send_invariants import (
    SendInvariantRefusal, require_exact_send_reservation,
)
from wam_regtest.wallet_session import PaymentReview


A=('a'*64,0)
B=('b'*64,1)
TOKEN='7'*32
RAW=b'public-unit-psbt'
SIGNED=b'public-unit-signed-psbt'


def fixture(*,inputs=(A,B),state='draft',signed=False):
    coins=tuple(dict(txid=p[0],vout=p[1],atoms=100000) for p in inputs)
    proposal=SimpleNamespace(
        coins=coins,token=TOKEN,fee=10000,
        intents=(SimpleNamespace(code='public-fixture-recipient',atoms=100000),))
    prepared=SimpleNamespace(proposal=proposal,psbt=RAW)
    review=PaymentReview('public-fixture-recipient',100000,10000,
                         90000,2,sha256(RAW).hexdigest())
    rows=[(txid,vout,TOKEN,state) for txid,vout in inputs]
    return dict(prepared=prepared,review=review,rows=rows,
                mempool_spends=[],expected_state=state,
                signed_psbt=SIGNED if signed else None)


def fake_psbt(raw):
    if raw not in (RAW,SIGNED):
        raise ValueError('NOT_A_PUBLIC_FIXTURE')
    return SimpleNamespace(
        version=2,tx=SimpleNamespace(inputs=(A,B)),
        txid=lambda:'f'*64)


class F06ReservationContracts(unittest.TestCase):
    def guarded(self, args):
        with patch('wam_sp.psbt.PSBT.decode',side_effect=fake_psbt):
            return require_exact_send_reservation(**args)

    def test_anchored_draft_and_signed_exact_review_accepted(self):
        self.assertTrue(self.guarded(fixture()))
        self.assertTrue(self.guarded(fixture(state='signed',signed=True)))

    def test_mismatched_review_intent_or_fee_refused(self):
        for field,val in (
            ('code','different-recipient'),
            ('atoms',100001),
            ('fee',11000),
            ('input_count',1),
            ('change_atoms',89999),
            ('commitment','f'*64),
        ):
            with self.subTest(field=field):
                req=fixture();req['review']=replace(req['review'],**{field:val})
                with self.assertRaises(SendInvariantRefusal):
                    self.guarded(req)

    def test_duplicate_outpoint_or_second_reservation_refused(self):
        for case in ('duplicate','missing','wrong_token','second_lock',
                     'early_signed','wrong_state','duplicate_coin'):
            with self.subTest(case=case):
                req=fixture()
                if case=='duplicate':req['rows'].append(req['rows'][0])
                elif case=='missing':req['rows'].pop()
                elif case=='wrong_token':
                    a=list(req['rows'][0]);a[2]='e'*32;req['rows'][0]=tuple(a)
                elif case=='second_lock':req['mempool_spends']=[A]
                elif case=='early_signed':
                    a=list(req['rows'][0]);a[3]='signed';req['rows'][0]=tuple(a)
                elif case=='wrong_state':req['expected_state']='uncertain'
                else:
                    req['prepared'].proposal.coins=(
                        req['prepared'].proposal.coins[0],
                        req['prepared'].proposal.coins[0])
                with self.assertRaises(SendInvariantRefusal):
                    self.guarded(req)

    def test_signed_psbt_must_match_unsigned_exact_inputs(self):
        for case in ('not_signed','signed_in_draft','changed_psbt',
                     'wrong_inputs','wrong_txid','wrong_version'):
            with self.subTest(case=case):
                req=fixture(state='signed',signed=True)
                if case=='not_signed':req['signed_psbt']=None
                elif case=='signed_in_draft':req['expected_state']='draft'
                elif case=='changed_psbt':req['signed_psbt']=b'bad'
                if case in ('wrong_inputs','wrong_txid','wrong_version'):
                    def forged(raw):
                        p=fake_psbt(raw)
                        if raw==SIGNED:
                            if case=='wrong_inputs':
                                p.tx.inputs=(A,('d'*64,2))
                            if case=='wrong_txid':
                                p.txid=lambda:'e'*64
                            if case=='wrong_version':
                                p.version=0
                        return p
                    with patch('wam_sp.psbt.PSBT.decode',side_effect=forged):
                        with self.assertRaises(SendInvariantRefusal):
                            require_exact_send_reservation(**req)
                else:
                    with self.assertRaises(SendInvariantRefusal):
                        self.guarded(req)

    def test_unsigned_psbt_coin_selection_order_is_exact(self):
        req=fixture()
        def reverse(raw):
            p=fake_psbt(raw)
            p.tx.inputs=(B,A)
            return p
        with patch('wam_sp.psbt.PSBT.decode',side_effect=reverse):
            with self.assertRaises(SendInvariantRefusal):
                require_exact_send_reservation(**req)

    def test_change_dust_and_unbounded_value_refused(self):
        for change in (1,329,-1,90001,True):
            with self.subTest(change=change):
                req=fixture();req['review']=replace(req['review'],change_atoms=change)
                with self.assertRaises(SendInvariantRefusal):
                    self.guarded(req)

    def test_boolean_vout_bad_txid_or_false_fee_denied(self):
        for field,val in (('vout',True),('txid','z'*64),('atoms',True)):
            with self.subTest(field=field):
                req=fixture()
                req['prepared'].proposal.coins[0][field]=val
                with self.assertRaises(SendInvariantRefusal):
                    self.guarded(req)
        req=fixture();req['review']=replace(req['review'],fee=True)
        with self.assertRaises(SendInvariantRefusal):
            self.guarded(req)


if __name__=='__main__':
    unittest.main()
