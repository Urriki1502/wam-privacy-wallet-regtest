"""Governance contracts only; no Core or external acceptance inferred."""
import copy
import json
from pathlib import Path
import unittest
from wam_regtest.q_gate import validate


class SequentialQGateContracts(unittest.TestCase):
    def setUp(self):
        self.ledger=json.loads((Path(__file__).resolve().parent/'acceptance/issue45.json').read_text())

    def test_committed_ledger_has_one_active_q_and_explicit_cases(self):
        result=validate(self.ledger)
        self.assertEqual(result['active_q'],'Q01')
        self.assertEqual(sum(result['case_results'].values()),result['coverage_identified'])
        self.assertFalse(result['q_accepted'])

    def test_cannot_activate_next_q_without_accepted_predecessor(self):
        self.ledger['active_q']='Q02';self.ledger['questions'][0]['processing']='QUEUED';self.ledger['questions'][1]['processing']='ACTIVE'
        with self.assertRaises(ValueError):validate(self.ledger)

    def test_false_acceptance_or_green_ci_without_evidence_is_denied(self):
        for change in ('case-pass','accepted','auto-merge','second-active'):
            data=copy.deepcopy(self.ledger)
            if change=='case-pass':data['questions'][0]['cases'][0]['status']='PASS'
            elif change=='accepted':data['questions'][0]['accepted']=True
            elif change=='auto-merge':data['automatic_merge_allowed']=True
            else:data['questions'][1]['processing']='ACTIVE'
            with self.subTest(change=change),self.assertRaises(ValueError):validate(data)

    def test_unexplained_external_block_and_missing_case_are_denied(self):
        data=copy.deepcopy(self.ledger);case=next(c for c in data['questions'][0]['cases'] if c['status']=='BLOCKED');case['blocker']=None
        with self.assertRaises(ValueError):validate(data)
        data=copy.deepcopy(self.ledger);data['questions'][0]['cases'].pop()
        with self.assertRaises(ValueError):validate(data)
