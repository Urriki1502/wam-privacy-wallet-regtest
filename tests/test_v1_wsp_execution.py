"""Actual pinned WSP/Git/subprocess import tests; no Core/key/anchor use."""
from pathlib import Path
from importlib._bootstrap_external import _code_to_timestamp_pyc
import hashlib
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest


class WspExecutionBoundary(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory(prefix='wam-public-wsp-exec-')
        self.addCleanup(self.folder.cleanup)
        self.root=Path(self.folder.name).resolve()/'wsp'
        original=Path(importlib.util.find_spec('wam_sp').origin).parent.parent.parent
        p=subprocess.run(['git','-c','advice.detachedHead=false','clone','--quiet',
                          '--local','--no-hardlinks',str(original),str(self.root)],
                         capture_output=True,timeout=20)
        self.assertEqual(p.returncode,0)
        self.source=self.root/'src'/'wam_sp'/'scanner.py'
        self.original=self.source.read_bytes()
        self.wallet=Path(__file__).resolve().parents[1]/'src'

    def run_child(self,code):
        env=dict(os.environ,PYTHONPATH=str(self.wallet)+os.pathsep+str(self.root/'src'))
        return subprocess.run([sys.executable,'-c',code,str(self.root)],env=env,
                              capture_output=True,text=True,timeout=30)

    def test_clean_native_wsp_import_executes_authenticated_source_loader(self):
        p=self.run_child("import wam_regtest;import wam_sp.scanner as m;print(type(m.__loader__).__name__)")
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('_VerifiedWspSourceLoader',p.stdout)

    def test_timestamp_valid_poisoned_cache_is_ignored_without_deleting_it(self):
        cache=Path(importlib.util.cache_from_source(str(self.source)))
        cache.parent.mkdir(mode=0o700)
        code=compile(self.original.decode('utf8')+'\nPUBLIC_EXECUTION_SENTINEL=True\n',str(self.source),'exec')
        info=self.source.stat()
        cache.write_bytes(_code_to_timestamp_pyc(code,int(info.st_mtime),info.st_size))
        before=hashlib.sha256(cache.read_bytes()).hexdigest()
        p=self.run_child("import wam_regtest;import wam_sp.scanner as m;assert not getattr(m,'PUBLIC_EXECUTION_SENTINEL',False);print('AUTHENTIC_SOURCE_EXECUTED')")
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('AUTHENTIC_SOURCE_EXECUTED',p.stdout)
        self.assertEqual(self.source.read_bytes(),self.original)
        self.assertEqual(hashlib.sha256(cache.read_bytes()).hexdigest(),before)

    def test_changed_tracked_source_never_executes_before_pin_refusal(self):
        marker=self.root/'PUBLIC_EXECUTION_MARKER'
        self.source.write_bytes(self.original+('\nfrom pathlib import Path\nPath('+repr(str(marker))+').write_text("public")\n').encode())
        p=self.run_child("import wam_regtest;import wam_sp.scanner")
        self.assertNotEqual(p.returncode,0)
        self.assertIn('WSP_SOURCE_WORKTREE_DENIED',p.stderr)
        self.assertFalse(marker.exists())

    def test_preimported_unverified_wsp_cannot_enter_wallet_runtime(self):
        p=self.run_child("import wam_sp.scanner;import wam_regtest")
        self.assertNotEqual(p.returncode,0)
        self.assertIn('WSP_PREIMPORTED_RUNTIME_DENIED',p.stderr)

    def test_source_absent_bytecode_only_package_cannot_replace_pinned_module(self):
        cache=Path(importlib.util.cache_from_source(str(self.source)))
        cache.parent.mkdir(mode=0o700)
        info=self.source.stat();code=compile(self.original,str(self.source),'exec')
        legacy=self.source.with_suffix('.pyc')
        legacy.write_bytes(_code_to_timestamp_pyc(code,int(info.st_mtime),info.st_size))
        self.source.unlink()
        p=self.run_child("import wam_regtest;import wam_sp.scanner")
        self.assertNotEqual(p.returncode,0)
        self.assertNotIn('AUTHENTIC_SOURCE_EXECUTED',p.stdout)
