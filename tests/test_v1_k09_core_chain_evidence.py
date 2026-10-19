"""K-09 recent-chain read-only reconciliation negative contracts.

Synthetic RPC responses exercise the parser ONLY; no fake observation can
authorize recovery. Real pinned Core/native IPC acceptance belongs to Codex.
"""
import unittest
from unittest.mock import Mock

from wam_regtest.crash_chain_evidence import (
    CrashChainEvidenceError,_observe_rpc,observe_recent_core_spends
)


TXID="a"*64
BLOCK="b"*64
TIP="c"*64
OTHER="d"*64


def fake_chain(*,spent=False,height=2,changed=False,malformed=None):
    def read(method,params):
        if method=="getblockcount":
            return height
        if method=="getbestblockhash":
            return OTHER if changed else TIP
        if method=="getblockhash":
            if params[0]==height:
                return TIP
            if params[0]==height-1:
                return BLOCK
            raise ValueError("unexpected block")
        if method=="getblock":
            digest=params[0]
            blockheight=height if digest==TIP else height-1
            vin=[{"coinbase":"00"}]
            if spent and blockheight==height:
                vin=[{"txid":TXID,"vout":1}]
            if malformed=="vin":
                vin=[{"txid":TXID,"vout":True}]
            return {
                "hash":digest,"height":blockheight,
                "tx":[{"vin":vin}],
            }
        raise AssertionError("unexpected RPC method")
    return read


class K09ReadOnlyCoreEvidence(unittest.TestCase):
    def setUp(self):
        self.target=frozenset({(TXID,1)})

    def test_spend_seen_on_live_chain_is_risk_not_discard_permission(self):
        report=_observe_rpc(fake_chain(spent=True),self.target,limit=2)
        self.assertEqual(report["onchain_spent_outpoints_observed"],1)
        self.assertEqual(report["blocks_scanned"],2)
        self.assertEqual(report["outpoints_checked"],1)
        self.assertFalse(report["full_chain_reconciled"])
        self.assertFalse(report["mempool_evidence_available"])
        for field in ("operator_discard_available","safe_to_discard_proven",
                      "wallet_unlocked","signer_allowed","broadcast_allowed",
                      "signed_or_uncertain_reservations_reconciled"):
            self.assertIs(report[field],False,field)
        self.assertNotIn(TXID,str(report))

    def test_absent_spend_is_unknown_not_proof_of_safety(self):
        report=_observe_rpc(fake_chain(spent=False),self.target,limit=2)
        self.assertEqual(report["onchain_spent_outpoints_observed"],0)
        self.assertFalse(report["safe_to_discard_proven"])
        self.assertFalse(report["mempool_evidence_available"])

    def test_changed_tip_fails_closed(self):
        with self.assertRaises(CrashChainEvidenceError):
            _observe_rpc(fake_chain(changed=True),self.target,limit=2)

    def test_malformed_outpoint_and_boolean_vout_are_denied(self):
        with self.assertRaisesRegex(CrashChainEvidenceError,
                                    "K09_CORE_OUTPOINT_FORMAT_DENIED"):
            _observe_rpc(fake_chain(),frozenset({(TXID,True)}),limit=2)
        with self.assertRaisesRegex(CrashChainEvidenceError,
                                    "K09_CORE_INPUT_SHAPE_DENIED"):
            _observe_rpc(fake_chain(malformed="vin"),self.target,limit=2)

    def test_denies_out_of_range_and_unbounded_observations(self):
        for n in (0,9,True,None):
            with self.subTest(n=n):
                with self.assertRaises(CrashChainEvidenceError):
                    _observe_rpc(fake_chain(),self.target,limit=n)
        with self.assertRaisesRegex(CrashChainEvidenceError,
                                    "K09_CORE_OUTPOINT_SET_LIMIT"):
            big=frozenset({(f"{i:064x}",0) for i in range(2049)})
            _observe_rpc(fake_chain(),big,limit=2)

    def test_public_api_rejects_mock_rpc_even_with_consent(self):
        for rpc,authorized in ((Mock(),True),(None,True),(Mock(),False)):
            with self.subTest(authorized=authorized):
                with self.assertRaises(CrashChainEvidenceError):
                    observe_recent_core_spends(
                        rpc,self.target,authorized=authorized)


if __name__=="__main__":
    unittest.main()
