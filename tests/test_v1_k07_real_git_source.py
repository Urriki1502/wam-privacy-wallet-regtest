"""Actual disposable Git/FS guard tests; no WSP import or synthetic Core PASS."""
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wam_regtest.wsp_live import _pinned_source, RealWspScanError


class ActualGitSourceIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="wam-k07-public-git-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.package=self.root/"src"/"wam_sp"
        self.package.mkdir(parents=True)
        (self.package/"__init__.py").write_bytes(b"# inert public fixture\n")
        self.scanner=self.package/"scanner.py"
        self.original=b"# exact public scanner fixture\n"
        self.scanner.write_bytes(self.original)
        self.git("init","--quiet","--template=")
        (self.root/".git/info").mkdir(exist_ok=True)
        self.git("config","core.hooksPath",str(self.root/"no-hooks"))
        self.git("add","--","src")
        self.git("-c","user.name=Public Test","-c","user.email=public@example.invalid",
                 "-c","commit.gpgsign=false","commit","--quiet","-m","public fixture")
        self.pin=self.git("rev-parse","HEAD").decode().strip()

    def git(self,*args,input=None):
        return subprocess.check_output(["git","-C",str(self.root),*args],
                                       input=input,stderr=subprocess.DEVNULL,timeout=10)

    def verify(self):
        # Use a real public Git fixture, not 2nd copies of WSP algorithms.
        # Only the expected pin/import location are supplied; Git/FS run natively.
        with (patch("wam_regtest.wsp_live.PINNED_WSP_COMMIT",self.pin),
              patch("wam_regtest.wsp_live.importlib.util.find_spec",
                    return_value=SimpleNamespace(origin=str(self.package/"__init__.py")))):
            _pinned_source(self.root)

    def test_clean_real_git_then_both_index_flags_cannot_hide_tamper(self):
        self.verify()
        for flag,reset in (("--assume-unchanged","--no-assume-unchanged"),
                           ("--skip-worktree","--no-skip-worktree")):
            with self.subTest(flag=flag):
                self.git("update-index",flag,"src/wam_sp/scanner.py")
                self.scanner.write_bytes(b"# changed, never imported\n")
                try:
                    self.assertFalse(self.git("status","--porcelain").strip())
                    with self.assertRaisesRegex(RealWspScanError,"WSP_SOURCE_HASH_DENIED"):
                        self.verify()
                finally:
                    self.scanner.write_bytes(self.original)
                    self.git("update-index",reset,"src/wam_sp/scanner.py")
        self.verify()

    def test_real_git_replacement_cannot_substitute_pinned_tree(self):
        self.scanner.write_bytes(b"# replacement bytes never imported\n")
        self.git("add","--","src/wam_sp/scanner.py")
        tree=self.git("write-tree").decode().strip()
        commit=self.git("-c","user.name=Public Test","-c",
                        "user.email=public@example.invalid","-c","commit.gpgsign=false",
                        "commit-tree",tree,input=b"public replacement\n").decode().strip()
        self.git("replace",self.pin,commit)
        self.assertEqual(self.git("rev-parse","HEAD").decode().strip(),self.pin)
        self.assertFalse(self.git("status","--porcelain").strip())
        with self.assertRaisesRegex(RealWspScanError,"WSP_SOURCE_HASH_DENIED"):
            self.verify()

    def test_real_git_ignore_cannot_hide_native_module(self):
        (self.root/".git/info/exclude").write_text("src/wam_sp/ignored.so\n")
        (self.package/"ignored.so").write_bytes(b"inert not a library")
        self.assertFalse(self.git("status","--porcelain").strip())
        with self.assertRaisesRegex(RealWspScanError,"WSP_SOURCE_CLOSURE_DENIED"):
            self.verify()

    def test_native_extra_hardlink_refused(self):
        os.link(self.scanner,self.root/"public-hardlink")
        self.git("config","status.showUntrackedFiles","no")
        with self.assertRaises(RealWspScanError):
            self.verify()

    def test_symlinked_source_parent_refused(self):
        source=self.root/"src"
        target=self.root/"public-source"
        source.rename(target)
        try:
            source.symlink_to(target,target_is_directory=True)
        except OSError:
            self.skipTest("native test identity has no symlink capability")
        self.git("update-index","--assume-unchanged","src/wam_sp/scanner.py",
                 "src/wam_sp/__init__.py")
        with self.assertRaises(RealWspScanError):
            self.verify()


if __name__=="__main__":
    unittest.main()
