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

    def _prepare_q02_engineering(self):
        self.ledger['active_q']='Q02'
        self.ledger['questions'][0]['processing']='ENGINEERING_DONE'
        q02=self.ledger['questions'][1]
        q02['processing']='ACTIVE'
        q02['coverage_identified']=True
        q02['coverage_total']=1
        # A source-only *test fixture*. This does NOT certify Q02 in reality.
        q02['cases']=[{'id':'Q02-SOURCE-SCOPE-TODO','requirement':'enumerate all genuine Q02 cases',
            'requirement_refs':['https://github.com/Urriki1502/wam-privacy-wallet-regtest/issues/45'],
            'platform':'shared','layer':'SOURCE','gates':['G0'],'mandatory':True,
            'status':'PENDING','acceptance_evidence':[],'blocker':None}]

    def test_owner_authorized_engineering_handoff_does_not_accept_predecessor(self):
        self._prepare_q02_engineering()
        result=validate(self.ledger)
        self.assertEqual(result['engineering_active_q'],'Q02')
        self.assertEqual(result['prior_engineering_handoffs'],['Q01'])
        self.assertFalse(self.ledger['questions'][0]['accepted'])
        self.assertFalse(result['q_accepted'])

    def test_q02_without_authorized_complete_engineering_handoff_denied(self):
        self._prepare_q02_engineering()
        for change in ('no-handoff','no-owner','missing-merge','technical-fail',
                       'technical-stale','unlisted-blocker','gate-fail'):
            data=copy.deepcopy(self.ledger)
            q01=data['questions'][0]
            handoff=q01['engineering_handoff']
            if change=='no-handoff':q01.pop('engineering_handoff')
            elif change=='no-owner':handoff['owner_authorized_handoff']=False
            elif change=='missing-merge':handoff['merged_main_sha']='not-a-commit'
            elif change=='technical-fail':q01['cases'][0]['status']='FAIL';q01['status']='FAIL'
            elif change=='technical-stale':q01['cases'][0]['status']='STALE'
            elif change=='unlisted-blocker':handoff['unresolved_case_ids'].pop()
            elif change=='gate-fail':q01['gates']['G2']['status']='FAIL'
            with self.subTest(change=change),self.assertRaises(ValueError):validate(data)

    def test_owner_merge_authorization_not_fabricated_from_ci_receipt(self):
        for change in ('owner-decision','merge-receipt','full-q'):
            data=copy.deepcopy(self.ledger)
            if change=='owner-decision':data['questions'][0]['owner_merge_authorization']=None
            elif change=='merge-receipt':
                data['questions'][0]['cases'][next(i for i,c in enumerate(data['questions'][0]['cases'])
                    if c['id']=='Q01-MERGE-AUTH')]['acceptance_evidence'][0]['merged_main_sha']='missing'
            else:data['questions'][0]['accepted']=True
            with self.subTest(change=change),self.assertRaises(ValueError):validate(data)

    def test_false_acceptance_or_green_ci_without_evidence_is_denied(self):
        for change in ('case-pass','accepted','auto-merge','second-active'):
            data=copy.deepcopy(self.ledger)
            if change=='case-pass':
                # This case may already have valid evidence after a ledger
                # update. Deliberately remove it to exercise the same refusal.
                data['questions'][0]['cases'][0]['status']='PASS'
                data['questions'][0]['cases'][0]['acceptance_evidence']=[]
            elif change=='accepted':data['questions'][0]['accepted']=True
            elif change=='auto-merge':data['automatic_merge_allowed']=True
            else:data['questions'][1]['processing']='ACTIVE'
            with self.subTest(change=change),self.assertRaises(ValueError):validate(data)

    def test_unexplained_external_block_and_missing_case_are_denied(self):
        data=copy.deepcopy(self.ledger);case=next(c for c in data['questions'][0]['cases'] if c['status']=='BLOCKED');case['blocker']=None
        with self.assertRaises(ValueError):validate(data)
        data=copy.deepcopy(self.ledger);data['questions'][0]['cases'].pop()
        with self.assertRaises(ValueError):validate(data)
