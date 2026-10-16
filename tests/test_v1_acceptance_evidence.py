import unittest
from wam_regtest.acceptance_evidence import effective_status

class EvidenceLayers(unittest.TestCase):
    def setUp(self):
        self.identity=dict(code_sha='a'*40,os='macOS',architecture='arm64',core_version='v0.1.11',wamd_sha256='b'*64,wam_cli_sha256='c'*64,wsp_commit='d'*40)
        self.record=dict(status='PASS',kind='SOURCE',identity=self.identity.copy(),tested_utc='2026-10-16T09:55:00Z',test_ref='public-test-receipt')

    def test_dependency_changes_invalidate_only_recorded_pass(self):
        self.assertEqual(effective_status(self.record,self.identity),'PASS')
        for field in self.identity:
            changed={**self.identity,field:'changed'}
            self.assertEqual(effective_status(self.record,changed),'STALE')

    def test_missing_skip_and_unperformed_layers_cannot_be_promoted(self):
        for state in ('PENDING','SKIP',None):self.assertEqual(effective_status({**self.record,'status':state},self.identity),'PENDING')
        for kind in ('CORE_E2E','FROZEN','PHYSICAL','DEV_REVIEWED'):
            self.assertEqual(effective_status({**self.record,'kind':kind},self.identity),'PENDING')
        self.assertEqual(effective_status({**self.record,'tested_utc':None},self.identity),'PENDING')
        self.assertEqual(effective_status({**self.record,'kind':'FROZEN','genuine_core':True},self.identity),'PENDING')

    def test_matching_but_malformed_hash_or_non_utc_time_is_not_proof(self):
        bad={**self.identity,'code_sha':'not-a-source-sha'}
        self.assertEqual(effective_status({**self.record,'identity':bad},bad),'PENDING')
        self.assertEqual(effective_status({**self.record,'tested_utc':'2026-10-16T10:00:00+07:00'},self.identity),'PENDING')
