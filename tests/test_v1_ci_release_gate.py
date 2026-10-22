"""Supplemental scheduling/result contracts, not genuine Core E2E."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('ci_release_gate',
    Path(__file__).resolve().parents[1]/'scripts'/'ci_platform_release_gate.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReleaseGateContracts(unittest.TestCase):
    required = ['native', 'frozen', 'a06-core-crash']

    def needs(self):
        return {name: {'result': 'success'} for name in self.required}

    def test_a06_failure_blocks_release_even_if_other_acceptance_passes(self):
        needs = self.needs()
        needs['a06-core-crash']['result'] = 'failure'
        proof = module.assess(needs, self.required)
        self.assertEqual(proof['status'], 'FAIL')
        self.assertEqual(proof['nonpassing_required_jobs'], ['a06-core-crash'])

    def test_all_required_ci_components_pass_without_release_authority(self):
        self.assertEqual(module.assess(self.needs(), self.required)['status'], 'PASS')

    def test_missing_cancelled_skipped_or_unknown_required_never_passes(self):
        for state in ('failure', 'cancelled', 'skipped', 'unknown', ''):
            for name in self.required:
                with self.subTest(state=state, name=name):
                    needs = self.needs()
                    needs[name]['result'] = state
                    self.assertEqual(module.assess(needs, self.required)['status'], 'FAIL')
        needs = self.needs()
        del needs['a06-core-crash']
        self.assertEqual(module.assess(needs, self.required)['status'], 'FAIL')

    def test_a06_cannot_be_accidentally_omitted_from_required_set(self):
        for required in ([], ['native', 'frozen'], ['a06-core-crash']*2):
            with self.assertRaises(ValueError):
                module.assess(self.needs(), required)

    def test_native_or_frozen_failure_blocks_even_with_a06_success(self):
        for name in ('native', 'frozen'):
            needs = self.needs()
            needs[name]['result'] = 'failure'
            self.assertEqual(module.assess(needs, self.required)['status'], 'FAIL')

    def test_optional_rebuild_skip_is_explicit_not_required_job_success(self):
        needs = self.needs()
        needs['native-contracts'] = {'result': 'success', 'outputs': {'core_changed': 'false'}}
        needs['developer-core'] = {'result': 'skipped'}
        proof = module.assess(needs, self.required, conditional_core_build=True)
        self.assertTrue(proof['reviewed_immutable_core_reused_without_optional_rebuild'])
        self.assertNotIn('developer-core', proof['required_job_results'])
        needs['native-contracts']['outputs']['core_changed'] = 'true'
        self.assertEqual(module.assess(needs, self.required, conditional_core_build=True)['status'], 'FAIL')

    def test_requested_or_failed_core_build_never_silently_ignored(self):
        for state in ('failure', 'cancelled', 'skipped', 'missing'):
            needs = self.needs()
            needs['native-contracts'] = {'outputs': {'core_changed': 'true'}}
            needs['developer-core'] = {'result': state}
            self.assertEqual(module.assess(needs, self.required, conditional_core_build=True)['status'], 'FAIL')
        needs['native-contracts']['outputs'] = {}
        with self.assertRaises(ValueError):
            module.assess(needs, self.required, conditional_core_build=True)


if __name__ == '__main__':
    unittest.main()
