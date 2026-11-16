"""REGTEST funding must reach Core ownership guard without a developer scenario."""
import builtins
from pathlib import Path
import unittest
from unittest.mock import patch
from wam_regtest.bip39_owner_backend import Bip39ReadOnlyBackend

class OwnershipGuardReached(Exception):pass

class RuntimeWithoutDeveloperScenario(unittest.TestCase):
 def test_funding_has_no_scenario_import_before_original_owner_guard(self):
  backend=object.__new__(Bip39ReadOnlyBackend)
  backend._secret=bytearray(b'public synthetic placeholder');backend._public={}
  backend._seed_folder=Path('/never-opened-public-test-path')
  def guard():raise OwnershipGuardReached()
  backend._core=guard
  original=builtins.__import__
  def without_scenario(name,*args,**kwargs):
   if name in ('q05_checkpoint_scenario','wam_regtest.q05_checkpoint_scenario'):
    raise ModuleNotFoundError('EXCLUDED_PRODUCTION_DEVELOPER_MODULE')
   return original(name,*args,**kwargs)
  with patch('builtins.__import__',without_scenario):
   with self.assertRaises(OwnershipGuardReached):backend._fund_q06()
