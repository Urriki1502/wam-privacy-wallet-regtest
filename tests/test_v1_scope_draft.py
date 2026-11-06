"""Scope proposals cannot manufacture acceptance or suppress technical failures."""
import copy
import json
from pathlib import Path
import unittest
from wam_regtest.q_gate import ORDER, validate
from wam_regtest.v1_scope import review_scope_draft

ROOT = Path(__file__).resolve().parents[1]


class ScopeDraftContracts(unittest.TestCase):
    def setUp(self):
        self.ledger = json.loads((ROOT/'tests/acceptance/issue45.json').read_text())
        self.draft = json.loads((ROOT/'docs/V1_OWNER_SCOPE_DRAFT_20261106.json').read_text())

    def test_legacy_ledger_unchanged_and_q06_stays_blocked(self):
        before = copy.deepcopy(self.ledger)
        result = review_scope_draft(self.ledger, self.draft)
        self.assertEqual(self.ledger, before)
        self.assertEqual(result['active_q'], 'Q06')
        self.assertEqual(ORDER, [f'Q{i:02}' for i in range(1,21)])
        self.assertFalse(validate(self.ledger)['q_accepted'])
        self.assertFalse(result['engineering_transition_allowed'])
        self.assertFalse(result['acceptance_granted'])
        self.assertFalse(result['mainnet_allowed'])

    def test_no_activation_via_draft_or_fabricated_link(self):
        for key, value in [('status','ACTIVE'), ('owner_decision_url','owner said yes'),
                           ('owner_decision_url','https://github.com/Urriki1502/wam-privacy-wallet-regtest/issues/45#issuecomment-1'),
                           ('owner_de_scoped',['Q06','Q07','Q08','Q09','Q17']),
                           ('future_engineering_order',['Q10'])]:
            draft = copy.deepcopy(self.draft); draft[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                review_scope_draft(self.ledger, draft)
        self.ledger['active_q'] = 'Q10'
        with self.assertRaises(ValueError): review_scope_draft(self.ledger, self.draft)

    def test_queued_in_scope_failures_and_descoped_history_remain_visible(self):
        for qid in ('Q07','Q10','Q20'):
            q = next(q for q in self.ledger['questions'] if q['id']==qid)
            q['status'] = 'FAIL'
            q['cases'] = [{'id':qid+'-FIXTURE-FAIL','status':'FAIL','mandatory':True,
                           'requirement_refs':['fixture-only'],'gates':['G4'],
                           'acceptance_evidence':[], 'layer':'SOURCE'}]
        result = review_scope_draft(self.ledger, self.draft)
        self.assertEqual(result['historical_failures'], ['Q07-FIXTURE-FAIL','Q10-FIXTURE-FAIL','Q20-FIXTURE-FAIL'])
        self.assertEqual(result['in_scope_failures'], ['Q10-FIXTURE-FAIL','Q20-FIXTURE-FAIL'])
        self.assertFalse(result['acceptance_granted'])


if __name__ == '__main__': unittest.main()
