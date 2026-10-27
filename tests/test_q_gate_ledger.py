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
        self.assertEqual(result['active_q'],'Q04')
        self.assertEqual(sum(result['case_results'].values()),result['coverage_identified'])
        self.assertFalse(result['q_accepted'])
        self.assertEqual(result['prior_engineering_handoffs'],['Q01','Q02','Q03'])

    def test_q04_integrated_postmerge_evidence_is_explicitly_partial(self):
        q04=self.ledger['questions'][3]
        p=q04['postmerge_qualification']
        self.assertEqual(q04['processing'],'ACTIVE')
        self.assertEqual(q04['candidate_head_sha'],p['premerge_head_sha'])
        self.assertEqual(q04['post_merge_main_sha'],p['merged_main_sha'])
        self.assertEqual(q04['owner_merge_authorization'],
            'https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/133')
        self.assertEqual(p['status'],'PARTIAL_PASS')
        self.assertEqual(len(p['exact_main_runs']),4)
        self.assertEqual(p['latest_governance_main_sha'],
            'a0e4c0c2f48e92c7cd8ebfd38a062aa03d1aa15e')
        self.assertEqual({x['run_id'] for x in p['exact_main_runs']},
            {40446287827,40446287701,40450255431,40450255365})
        latest=[x for x in p['exact_main_runs'] if x.get('checkout_sha')]
        self.assertEqual(len(latest),2)
        self.assertTrue(all(x['checkout_sha']==p['latest_governance_main_sha'] for x in latest))
        mac_core=next(x for x in latest if x['run_id']==40450255431)
        self.assertEqual(len(mac_core['artifact_archives']),3)
        self.assertTrue(all(len(x['archive_sha256'])==64 for x in mac_core['artifact_archives']))
        self.assertEqual({x['required_ref_sha'] for x in p['pending_exact_main_runs']},
            {p['latest_governance_main_sha']})
        self.assertTrue(all(x['status']=='PASS' for x in p['exact_main_runs']))
        self.assertEqual({x['platform'] for x in p['pending_exact_main_runs']},
            {'windows-x64','linux-x86_64'})
        self.assertEqual(len(p['pending_exact_main_runs']),3)
        self.assertTrue(all(x['status']=='PENDING' for x in p['pending_exact_main_runs']))
        self.assertFalse(p['handoff_to_q05_authorized'])
        self.assertFalse(q04['accepted'])
        self.assertNotIn('engineering_handoff',q04)
        self.assertEqual(sum(x['status']=='BLOCKED' for x in q04['cases']),2)
        self.assertEqual(self.ledger['active_q'],'Q04')

    def _reset_to_q02_active(self):
        """Fixture: revert committed Q03 activation to exercise Q01->Q02 handoff."""
        self.ledger['active_q']='Q02'
        self.ledger['questions'][0]['processing']='ENGINEERING_DONE'
        q02=self.ledger['questions'][1]
        q02['processing']='ACTIVE'
        q02['coverage_identified']=True
        q02['coverage_total']=1
        q02['engineering_handoff_blocker']={
            'actor':'REPOSITORY_OWNER','missing_evidence':'fixture','next_action':'fixture'}
        q02.pop('engineering_handoff',None)
        q02['cases']=[{'id':'Q02-SOURCE-SCOPE-TODO','requirement':'enumerate all genuine Q02 cases',
            'requirement_refs':['https://github.com/Urriki1502/wam-privacy-wallet-regtest/issues/45'],
            'platform':'shared','layer':'SOURCE','gates':['G0'],'mandatory':True,
            'status':'PENDING','acceptance_evidence':[],'blocker':None}]
        q03=self.ledger['questions'][2]
        q03['processing']='QUEUED'
        q03['coverage_identified']=False
        q03['coverage_total']=None
        q03['cases']=[]
        q03.pop('engineering_handoff',None)
        q04=self.ledger['questions'][3]
        q04['processing']='QUEUED'
        q04['coverage_identified']=False
        q04['coverage_total']=None
        q04['cases']=[]

    def test_owner_authorized_engineering_handoff_does_not_accept_predecessor(self):
        self._reset_to_q02_active()
        result=validate(self.ledger)
        self.assertEqual(result['engineering_active_q'],'Q02')
        self.assertEqual(result['prior_engineering_handoffs'],['Q01'])
        self.assertFalse(self.ledger['questions'][0]['accepted'])
        self.assertFalse(result['q_accepted'])

    def test_q02_without_authorized_complete_engineering_handoff_denied(self):
        self._reset_to_q02_active()
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

    def test_handoff_owner_comment_requires_real_numeric_github_url_shape(self):
        # URL shape cannot authenticate a human decision; live GitHub review
        # remains mandatory. Reject nonnumeric placeholders.
        prefix='https://github.com/Urriki1502/wam-privacy-wallet-regtest/issues/45#issuecomment-'
        for suffix in ('Q02_OWNER_DECISION_20261025','','0','6379544993/extra',
                       '6379544993?approved=true','6379544993\n'):
            data=copy.deepcopy(self.ledger)
            # Target the Q02 handoff now present in the committed ledger.
            data['questions'][1]['engineering_handoff']['owner_decision_url']=prefix+suffix
            with self.subTest(suffix=suffix),self.assertRaises(ValueError):validate(data)

    def test_q03_handoff_preserves_release_and_next_q_boundaries(self):
        q03=self.ledger['questions'][2]
        q04=self.ledger['questions'][3]
        self.assertEqual(self.ledger['active_q'],'Q04')
        self.assertEqual(sum(c['status']=='PASS' for c in q03['cases']),24)
        self.assertFalse(q03['accepted'])
        self.assertIn('engineering_handoff',q03)
        self.assertEqual(q03['engineering_handoff']['next_q'],'Q04')
        self.assertEqual(q04['processing'],'ACTIVE')
        self.assertEqual({c['id'] for c in q03['cases'] if c['status']=='BLOCKED'},
            {'Q03-INDEPENDENT','Q03-WINDOWS-NO-FLICKER'})
        for case in q03['cases']:
            if case['status']=='PASS' and case['platform']=='linux-x86_64':
                for evidence in case['acceptance_evidence']:
                    if 'core_trust' in evidence:
                        self.assertEqual(evidence['core_trust'],'reviewed-developer-source-build')

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
            else:data['questions'][4]['processing']='ACTIVE'  # Q05 while Q04 active
            with self.subTest(change=change),self.assertRaises(ValueError):validate(data)

    def test_unexplained_external_block_and_missing_case_are_denied(self):
        data=copy.deepcopy(self.ledger);case=next(c for c in data['questions'][0]['cases'] if c['status']=='BLOCKED');case['blocker']=None
        with self.assertRaises(ValueError):validate(data)
        data=copy.deepcopy(self.ledger);data['questions'][0]['cases'].pop()
        with self.assertRaises(ValueError):validate(data)

    def test_q03_cannot_follow_unqualified_q02(self):
        data=copy.deepcopy(self.ledger)
        # Remove the authentic Q02 handoff; Q03 active must then fail validation.
        data['questions'][1].pop('engineering_handoff',None)
        data['questions'][1]['processing']='ENGINEERING_DONE'
        data['questions'][2]['processing']='ACTIVE'
        with self.assertRaises(ValueError):validate(data)

    def test_negative_injection_cannot_bypass_native_provenance_requirements(self):
        data=copy.deepcopy(self.ledger)
        case=next(c for c in data['questions'][1]['cases'] if c['layer']=='NEGATIVE_INJECTION')
        case['status']='PASS'
        case['acceptance_evidence']=[{'source_sha':'a'*40,'checkout_sha':'b'*40,
            'timestamp_utc':'2026-10-24T14:00:00Z','platform':case['platform'],
            'reference':'https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/129'}]
        # Source metadata alone must not qualify an OS/Core-backed fault case.
        with self.assertRaises(ValueError):validate(data)


if __name__=='__main__':
    unittest.main()
