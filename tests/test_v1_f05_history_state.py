"""F-05 synthetic public boundary tests only, NOT actual Core E2E."""
from dataclasses import replace
import unittest

from wam_regtest.f05_history_state import (
    KnownTransactionState,TxHistoryRefusal,classify_known_transaction,
)
from wam_regtest.wallet_read import HistoryRow
from wam_regtest.wsp_live import REGTEST_GENESIS


TXID='c'*64
def proof(*,height=105,confirmed=False,mempool=False,reservation='broadcast',prior=False):
    history=([HistoryRow(TXID,105,height-104,0,110000)]
             if confirmed else [])
    return dict(chain='regtest',genesis=REGTEST_GENESIS,height=height,
                txid=TXID,mempool_txids=[TXID] if mempool else [],
                history=history,reservation_state=reservation,
                prior_confirmed=prior,broadcast_submitted=True)


class F05TransactionObservations(unittest.TestCase):
    def test_broadcast_in_mempool_is_unconfirmed_without_authority(self):
        v=classify_known_transaction(**proof(height=104,mempool=True))
        self.assertEqual((v.classification,v.confirmation_depth),
                         ('mempool_observed',0))
        self.assertTrue(v.irreversible_reservation)
        for flag in ('automatic_rebroadcast_allowed','reservation_release_allowed',
                     'unconfirmed_silent_receive_detected','spend_authorized','mainnet_allowed'):
            self.assertFalse(getattr(v,flag))

    def test_verified_wsp_history_required_for_confirmation(self):
        for height,depth in ((105,1),(116,12),(204,100)):
            with self.subTest(height=height):
                state=classify_known_transaction(**proof(height=height,confirmed=True))
                self.assertEqual(state.classification,'confirmed')
                self.assertEqual(state.confirmation_depth,depth)
                self.assertTrue(state.verified_wsp_history)

    def test_reorg_mempool_resurrection_is_not_confirmation(self):
        for mempool,expected in ((True,'reorged_mempool_observed'),
                                 (False,'reorged_not_observed')):
            case=proof(height=104,mempool=mempool,prior=True)
            state=classify_known_transaction(**case)
            self.assertEqual(state.classification,expected)
            self.assertFalse(state.verified_wsp_history)
            self.assertTrue(state.irreversible_reservation)
            self.assertFalse(state.reservation_release_allowed)

    def test_uncertain_rpc_reply_stays_irreversible_regardless_of_mempool(self):
        for mempool,expected in ((True,'uncertain_mempool_observed'),
                                 (False,'uncertain_not_observed')):
            state=classify_known_transaction(**proof(
                height=104,mempool=mempool,reservation='uncertain'))
            self.assertEqual(state.classification,expected)
            self.assertTrue(state.irreversible_reservation)
            self.assertFalse(state.automatic_rebroadcast_allowed)

    def test_mempool_absence_cannot_be_called_dropped(self):
        case=proof(height=104,mempool=False)
        state=classify_known_transaction(**case)
        self.assertEqual(state.classification,'submitted_not_observed')
        self.assertFalse(state.verified_wsp_history)
        for reservation,expected in (('draft','draft'),
                                     ('signed','signed_not_broadcast')):
            state=classify_known_transaction(**proof(
                height=104,mempool=False,reservation=reservation))
            self.assertEqual(state.classification,expected)

    def test_inconsistent_wsp_history_and_mempool_fail_closed(self):
        for mode in ('both','wrong_depth','future_block','duplicate','unreconciled'):
            case=proof(confirmed=True)
            if mode=='both':
                case['mempool_txids']=[TXID]
            elif mode=='wrong_depth':
                case['history']=[replace(case['history'][0],confirmations=2)]
            elif mode=='future_block':
                case['history']=[replace(case['history'][0],block_height=106)]
            elif mode=='duplicate':
                case['history']*=2
            elif mode=='unreconciled':
                case['history']=[replace(case['history'][0],credit_atoms=-1)]
            with self.subTest(mode=mode):
                with self.assertRaises(TxHistoryRefusal):
                    classify_known_transaction(**case)

    def test_wrong_chain_duplicate_mempool_and_unknown_origin_denied(self):
        for kind in ('chain','genesis','boolheight','txid','duplicate','unknown','badstate'):
            case=proof(height=104,mempool=True)
            if kind=='chain':case['chain']='main'
            elif kind=='genesis':case['genesis']='a'*64
            elif kind=='boolheight':case['height']=True
            elif kind=='txid':case['txid']='zz'
            elif kind=='duplicate':case['mempool_txids']=[TXID,TXID]
            elif kind=='unknown':
                case['reservation_state']='none'
                case['broadcast_submitted']=False
            else:case['reservation_state']='released'
            with self.subTest(kind=kind):
                with self.assertRaises(TxHistoryRefusal):
                    classify_known_transaction(**case)


if __name__=='__main__':
    unittest.main()
