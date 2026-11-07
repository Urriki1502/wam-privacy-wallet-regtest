"""Production argv must deny before resources; policy fails closed on new modules."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from wam_regtest import production_entry
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('packaging_policy',ROOT/'scripts/production_packaging.py')
policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)

class ProductionPackaging(unittest.TestCase):
 def test_all_developer_entrypoints_denied_before_resources_even_ci_environment(self):
  for args in (['--ci-q06-bip39-spend'],['--ci-q05-managed-wallet','native'],['smoke'],['-m','wam_regtest.cli'],['--check-bundle','--ci-ui-layout'],['--core-dir=/tmp'],['--ci-v1-net-shared-regtest']):
   with self.subTest(args=args),patch.object(sys,'argv',['wallet',*args]),patch.dict('os.environ',{'CI':'true','WAM_QUALIFICATION':'1'}),patch.object(production_entry,'checked_resources') as check:
    self.assertEqual(production_entry.main(),64);check.assert_not_called()
 def test_positive_allowlist_excludes_every_probe_and_legacy_dispatch(self):
  available={p.stem for p in (ROOT/'src/wam_regtest').glob('*.py')}
  excluded=available-policy.RUNTIME
  for name in available:
   if name.endswith(('_probe','_scenario')):self.assertIn(name,excluded)
  for name in ('cli','__main__','package_entry','windows_package_entry','linux_package_entry','bip39_reconcile','q05_packaged','q04_runner','q04_miner_loop','q04_fixture'):
   self.assertIn(name,excluded)
  args=policy.arguments(ROOT)
  self.assertEqual(set(args[1::2]),{'wam_regtest.'+n for n in available-{'__init__','production_entry'}})
 def test_readonly_self_check_cannot_launch_wallet(self):
  with patch.object(sys,'argv',['wallet','--check-bundle']),patch.object(production_entry,'checked_resources',return_value=(None,None)) as check:
   self.assertEqual(production_entry.main(),0);check.assert_called_once()
 def test_frozen_audit_is_mandatory_in_production_builder(self):
  text=(ROOT/'scripts/build_macos_production.py').read_text()
  self.assertIn('inventory=audit(binary,app)',text)
  self.assertNotIn("'--collect-submodules','wam_regtest'",text)
  self.assertIn("production_qualified=False",text)
