"""Policy/mutation contracts ONLY; actual three-OS native/frozen CI is separate."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from wam_regtest.a06_acceptance import require_components
from wam_regtest.a06_artifact_gate import assess_artifacts

ROOT=Path(__file__).resolve().parents[1]


class RecoveryAcceptanceContracts(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((ROOT/'tests/data/a06_mac_policy_fixture.json').read_text())

    def assess(self,data=None,frozen=False):
        d=self.data if data is None else data
        return require_components(d['graceful_shutdown_component'],d['index_recovery_component'],
            d['bip39_index_recovery_component'],d['frozen_operator_recovery_component'],
            platform='macos-arm64',frozen=frozen)

    def test_actual_component_policy_fixture_validates_without_full_release_claim(self):
        r=self.assess()
        self.assertEqual([r[k] for k in ('A06-A','A06-B','A06-C')],['PASS']*3)
        self.assertFalse(r['automatic_release_authorized'])
        self.assertFalse(r['full_q05_qualified']);self.assertFalse(r['full_v1_qualified'])

    def test_each_graceful_method_and_exact_chain_required(self):
        for key,value in [('exact_tip_preserved',False),('clean_exit_code',1),
                          ('reindex_performed',True),('core_wallet_address_and_balance_preserved',False)]:
            d=copy.deepcopy(self.data);d['graceful_shutdown_component']['cases'][0][key]=value
            with self.assertRaises(ValueError):self.assess(d)
        self.data['graceful_shutdown_component']['cases'].pop()
        with self.assertRaises(ValueError):self.assess()

    def test_reindex_cannot_accept_different_chain_or_changed_core(self):
        for field,value in [('tip','0'*64),('height',0),('wam_cli_sha256','0'*64),
                            ('operator_reindex_approved',False),('automatic_broadcast',True)]:
            d=copy.deepcopy(self.data);d['bip39_index_recovery_component']['cases'][0]['explicit_reindex'][field]=value
            with self.assertRaises(ValueError):self.assess(d)

    def test_any_unproven_interruption_continuation_is_nonpassing(self):
        c=self.data['bip39_index_recovery_component']['cases'][0]['interrupted_recovery']
        for key,value in c.items():
            if value is not True:continue
            d=copy.deepcopy(self.data);d['bip39_index_recovery_component']['cases'][0]['interrupted_recovery'][key]=False
            with self.subTest(field=key),self.assertRaises(ValueError):self.assess(d)
        del c['status']
        with self.assertRaises((ValueError,KeyError)):self.assess()

    def test_wallet_and_irreversible_state_cannot_be_optional(self):
        for key in ('exact_original_64_byte_seed_and_identity','signed_and_uncertain_reservations_preserved',
                    'native_anchor_vault_unchanged_by_reindex','confirmed_scanner_history_preserved','cleanup_verified'):
            d=copy.deepcopy(self.data);d['bip39_index_recovery_component']['cases'][1][key]=False
            with self.assertRaises(ValueError):self.assess(d)

    def test_source_receipt_cannot_substitute_for_frozen_or_missing_operator(self):
        with self.assertRaises(ValueError):self.assess(frozen=True)
        self.data['bip39_index_recovery_component']['execution']='FROZEN'
        with self.assertRaises((ValueError,TypeError)):self.assess(frozen=True)

    def test_missing_artifacts_cannot_pass_even_with_synthetic_success_jobs(self):
        with self.assertRaises((ValueError,OSError)):
            assess_artifacts(ROOT/'not-an-artifact-set','macos-arm64','a'*40,'b'*40)

    def test_actual_gate_cli_publishes_fail_for_missing_evidence_and_for_omitted_jobs(self):
        required=['real-wamd','native-app-dmg','a06-core-crash']
        env={**os.environ,'JOB_RESULTS':json.dumps({n:{'result':'success'} for n in required}),
             'WAM_SOURCE_HEAD':'a'*40,'WAM_CHECKOUT_SHA':'b'*40}
        with tempfile.TemporaryDirectory() as folder:
            for i,names in enumerate((required,['a06-core-crash'])):
                output=Path(folder)/f'{i}.json'
                run=subprocess.run([sys.executable,str(ROOT/'scripts/ci_platform_release_gate.py'),
                    '--platform','macos-arm64','--required-jobs',json.dumps(names),
                    '--evidence-root',folder,'--output',str(output)],env=env,capture_output=True)
                self.assertEqual(run.returncode,1)
                receipt=json.loads(output.read_text())
                self.assertEqual(receipt['status'],'FAIL')
                self.assertFalse(receipt['automatic_release_authorized'])


class HistoricalObservationContracts(unittest.TestCase):
    def test_unclassified_error_or_bad_exit_does_not_become_recorded(self):
        spec=importlib.util.spec_from_file_location('a06_observation',ROOT/'scripts/ci_a06_observation.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        # A classified raw failure must contain the ENTIRE native receipt;
        # an error plus a success job result can never manufacture evidence.
        for status in ('ERROR','FAIL','PASS'):
            with self.assertRaises((ValueError,KeyError)):
                m.record({'status':status},0,source='a'*40,checkout='b'*40)


if __name__=='__main__':unittest.main()
