"""Supplemental entry contracts; no mock result is genuine-Core acceptance."""
import contextlib
import io
from pathlib import Path
import runpy
import symtable
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


class FrozenDispatchContracts(unittest.TestCase):
    def test_macos_script_entry_imports_without_package_parent(self):
        entry=runpy.run_path(str(ROOT/'src/wam_regtest/package_entry.py'))
        self.assertTrue(callable(entry['run_q04_scenario']))

    def test_windows_script_entry_has_runner_and_builder_re_is_global(self):
        entry=runpy.run_path(str(ROOT/'src/wam_regtest/windows_package_entry.py'))
        self.assertTrue(callable(entry['run_q04_scenario']))
        source=(ROOT/'scripts/build_windows_bundle.py').read_text()
        table=symtable.symtable(source,'build_windows_bundle.py','exec')
        main=next(c for c in table.get_children() if c.get_name()=='main')
        self.assertTrue(main.lookup('re').is_global())

    def test_macos_q04_dispatch_executes_runner(self):
        entry=runpy.run_path(str(ROOT/'src/wam_regtest/package_entry.py'))
        main=entry['main'];g=main.__globals__
        with patch.dict(g,{'_check_bundle':lambda:(ROOT/'core',ROOT/'wsp')}), \
             patch.dict(g,{'run_q04_scenario':lambda *a,**k:{'status':'Q04_MINER_COEXISTENCE_PASS'}}), \
             patch.object(sys,'argv',['wallet','--ci-q04-external-miner']), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(),0)

    def test_linux_q04_requires_explicit_trust_before_runner(self):
        from wam_regtest.cli import main
        with patch.object(sys,'platform','linux'), \
             patch.object(sys,'argv',['wallet','q04-external-miner','--core-dir',str(ROOT),'--confirm-disposable-regtest']), \
             patch('wam_regtest.cli.run_q04_scenario') as runner, \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(),2)
            runner.assert_not_called()

    def test_linux_q04_configures_current_process_before_runner(self):
        from wam_regtest.cli import main
        order=[]
        def configure(*args,**kw):
            self.assertEqual(args,(ROOT,'a'*64,ROOT/'anchor.sock'))
            self.assertTrue(kw['authorized']);order.append('trust')
        def run(*a,**k):
            order.append('run');return {'status':'supplemental-dispatch-only'}
        with patch.object(sys,'platform','linux'), \
             patch.object(sys,'argv',['wallet','q04-external-miner','--core-dir',str(ROOT),
                '--confirm-disposable-regtest','--manifest-sha256','a'*64,
                '--anchor-socket',str(ROOT/'anchor.sock'),'--confirm-experimental-developer-regtest']), \
             patch('wam_regtest.linux_runtime.configure',side_effect=configure), \
             patch('wam_regtest.cli.run_q04_scenario',side_effect=run), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(),0)
        self.assertEqual(order,['trust','run'])
