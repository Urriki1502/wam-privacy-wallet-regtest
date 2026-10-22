"""Supplemental artifact semantics, never genuine-Core acceptance substitutes."""
import copy
import unittest
from wam_regtest.a06_acceptance import core_pair
from wam_regtest.q05_artifact_gate import check_component, REQUIRED_CASES


class Q05GateContracts(unittest.TestCase):
    def proof(self, *, frozen=False):
        pair = core_pair('macos-arm64')
        return {'schema': 'wam-q05-managed-gui-lifecycle/v1', 'status': 'PASS',
            'platform': 'macos-arm64', 'execution': 'FROZEN' if frozen else 'SOURCE_NATIVE',
            'core_version': 'v0.1.11', 'wamd_sha256': pair[0], 'wam_cli_sha256': pair[1],
            'frozen_binary_sha256': 'a'*64, 'owner_data_accessed': False,
            'synthetic_rpc': False, 'mainnet_allowed': False, 'automatic_rebroadcast': False,
            'full_v1_qualified': False, 'cases': {name: {'status': 'DENIED' if name in
                ('normal-wrong-password', 'normal-decline') else 'PASS'} for name in REQUIRED_CASES}}

    def test_every_required_scenario_mandatory(self):
        for case in REQUIRED_CASES:
            proof = self.proof(); del proof['cases'][case]
            with self.assertRaises(ValueError): check_component(proof, 'macos-arm64', False)

    def test_safe_refusal_to_restore_is_failure_to_complete_lifecycle(self):
        proof = self.proof(); proof['status'] = 'FAIL'
        proof['cases']['unlocked-gui-kill-authenticated-reopen'] = {'status': 'FAIL', 'safe_refusal': True}
        result = check_component(proof, 'macos-arm64', False)
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('unlocked-gui-kill-authenticated-reopen', result['nonpassing_cases'])
        self.assertFalse(result['full_q05_qualified'])

    def test_pending_or_skipped_cannot_be_pass(self):
        for status in ('PENDING', 'SKIP', 'FAIL', None):
            proof = self.proof(); proof['cases']['wrong-version-gui']['status'] = status
            with self.assertRaises(ValueError): check_component(proof, 'macos-arm64', False)
            proof['status'] = 'FAIL'
            self.assertEqual(check_component(proof, 'macos-arm64', False)['status'], 'FAIL')

    def test_source_is_not_final_frozen(self):
        with self.assertRaises(ValueError): check_component(self.proof(), 'macos-arm64', True, ['a'*64])
        with self.assertRaises(ValueError): check_component(self.proof(frozen=True), 'macos-arm64', True, ['b'*64])
        self.assertEqual(check_component(self.proof(frozen=True), 'macos-arm64', True, ['a'*64])['status'], 'PASS')

    def test_core_pair_network_and_synthetic_scope_cannot_change(self):
        for field, value in [('wam_cli_sha256', 'a'*64), ('wamd_sha256', 'a'*64),
                ('core_version', 'v0.1.12'), ('mainnet_allowed', True),
                ('synthetic_rpc', True), ('owner_data_accessed', True), ('automatic_rebroadcast', True)]:
            proof = self.proof(); proof[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                check_component(proof, 'macos-arm64', False)


if __name__ == '__main__': unittest.main()
