"""Proposed recovery ordering model; explicitly no runtime qualification."""
import importlib.util
from pathlib import Path
import unittest


class RecoveryDesignModelContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=Path(__file__).resolve().parents[1]/'scripts/model_q05_checkpoint_recovery.py'
        spec=importlib.util.spec_from_file_location('q05_recovery_design_model',path)
        cls.model=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.model)

    def test_all_fault_boundaries_deny_or_preserve_authoritative_state(self):
        traces=self.model.explore()
        self.assertEqual(len(traces),9)
        self.assertTrue(all(not row['violations'] for row in traces))
        self.assertFalse(traces[4]['balance_visible'])
        self.assertTrue(traces[-1]['balance_visible'])

    def test_unsafe_alternatives_have_counterexamples_without_acceptance_claim(self):
        result=self.model.evaluate()
        self.assertEqual(len(result['counterexamples']),8)
        self.assertFalse(result['runtime_recovery_implemented'])
        self.assertFalse(result['q05_acceptance'])
        self.assertFalse(result['independent_approval'])
