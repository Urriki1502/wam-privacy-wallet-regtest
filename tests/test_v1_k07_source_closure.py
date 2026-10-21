"""K-07 source-vs-frozen provenance closure, no synthetic Core evidence."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import unittest

from wam_regtest.wsp_live import _pinned_source,PINNED_WSP_COMMIT,RealWspScanError
from wam_regtest.build_provenance import _blob


class WspPinnedSourceClosureContracts(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(prefix="k07-pinned-tree-")
        self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name).resolve()
        self.package=self.root/"src"/"wam_sp"
        self.package.mkdir(parents=True)
        (self.package/"__init__.py").write_text("# publicly disposable source\n")
        (self.package/"scanner.py").write_text("# pinned-checkout fixture\n")
        self.tree=b"".join(
            b"100644 blob "+_blob(p.read_bytes()).encode()+b"\t"+
            p.relative_to(self.root).as_posix().encode()+b"\x00"
            for p in sorted(self.package.glob("*.py")))
        self.dirty=b""

    def _git(self,cmd,*,capture_output,text=False,timeout,check):
        self.assertTrue(capture_output and check and timeout<=6)
        if cmd[:4] == ["git","--no-replace-objects","-C",str(self.root)]:
            self.assertEqual(cmd[4:],["ls-tree","-r","-z",PINNED_WSP_COMMIT,
                                      "--","src/wam_sp"])
            return SimpleNamespace(stdout=self.tree)
        self.assertEqual(cmd[:3],["git","-C",str(self.root)])
        if cmd[3:] == ["rev-parse","HEAD"]:
            return SimpleNamespace(stdout=PINNED_WSP_COMMIT)
        if cmd[3:5] == ["status","--porcelain"]:
            self.assertEqual(cmd[5], "--untracked-files=all")
            self.assertEqual(cmd[6:],["--","src/wam_sp"])
            return SimpleNamespace(stdout=self.dirty)
        raise AssertionError("K07_UNEXPECTED_GIT_COMMAND")

    def verify(self):
        with (patch("wam_regtest.wsp_live.subprocess.run",
                    side_effect=self._git),
              patch("wam_regtest.wsp_live.importlib.util.find_spec",
                    return_value=SimpleNamespace(
                        origin=str(self.package/"__init__.py")))):
            _pinned_source(self.root)

    def test_positive_exact_python_source_closure(self):
        self.verify()

    def test_new_untracked_python_file_refused(self):
        (self.package/"evildoer.py").write_text("raise RuntimeError('test only')\n")
        with self.assertRaisesRegex(RealWspScanError,"WSP_SOURCE_CLOSURE_DENIED"):
            self.verify()

    def test_ignored_python_file_refused_not_just_git_status(self):
        # A .gitignore rule can hide this file from porcelain status; the
        # HEAD-tree-to-actual-source closure still must reject it.
        directory=self.package/"adapters"
        directory.mkdir()
        (directory/"ignored_helper.py").write_text("# ignored test-only code\n")
        self.dirty=b""
        with self.assertRaisesRegex(RealWspScanError,"WSP_SOURCE_CLOSURE_DENIED"):
            self.verify()

    def test_git_untracked_metadata_refused_even_for_nonpy_file(self):
        (self.package/"foreign.txt").write_text("public test only")
        self.dirty=b"?? src/wam_sp/foreign.txt\x00"
        with self.assertRaisesRegex(RealWspScanError,"WSP_SOURCE_WORKTREE_DENIED"):
            self.verify()

    def test_tracked_python_modification_refused(self):
        (self.package/"scanner.py").write_text("# altered file\n")
        self.dirty=b" M src/wam_sp/scanner.py\n"
        with self.assertRaisesRegex(RealWspScanError,"WSP_SOURCE_WORKTREE_DENIED"):
            self.verify()

    def test_missing_tracked_source_refused(self):
        (self.package/"scanner.py").unlink()
        # Existing PIN guard already refuses missing scanner.py BEFORE
        # K-07's exact tree-closure guard. Both are fail-closed and correct.
        with self.assertRaisesRegex(RealWspScanError,"WSP_SOURCE_PIN_DENIED"):
            self.verify()

    def test_unexpected_tree_manifest_refused(self):
        self.tree=b"src/wam_sp/scanner.py\x00"
        with self.assertRaisesRegex(RealWspScanError,"WSP_SOURCE_CLOSURE_DENIED"):
            self.verify()

    def test_symlinked_scanner_refused_even_if_git_metadata_claims_clean(self):
        original=self.package/"scanner.py"
        original.unlink()
        target=self.package/"payload.txt"
        target.write_text("# public test\n")
        try: original.symlink_to(target)
        except (NotImplementedError,OSError):
            self.skipTest("native Windows test identity lacks symlink privilege")
        with self.assertRaisesRegex(RealWspScanError,"WSP_SOURCE_CLOSURE_DENIED"):
            self.verify()

    def test_ordinary_pycache_does_not_inject_python_source(self):
        cache=self.package/"__pycache__"
        cache.mkdir()
        (cache/"scanner.cpython-312.pyc").write_bytes(b"public-bytecode-fixture")
        self.verify()

    def test_clean_status_cannot_hide_changed_source_bytes(self):
        (self.package/"scanner.py").write_text("# altered behind clean status\n")
        with self.assertRaisesRegex(RealWspScanError,"WSP_SOURCE_HASH_DENIED"):
            self.verify()

    def test_ignored_native_modules_and_legacy_bytecode_refused(self):
        for suffix in (".so", ".pyd", ".dll", ".dylib", ".pyw", ".pyo", ".pyc"):
            with self.subTest(suffix=suffix):
                member=self.package/("ignored"+suffix)
                member.write_bytes(b"inert public fixture")
                try:
                    with self.assertRaisesRegex(RealWspScanError,"WSP_SOURCE_CLOSURE_DENIED"):
                        self.verify()
                finally:
                    member.unlink()

    def test_crlf_only_checkout_still_matches_exact_pinned_blob(self):
        scanner=self.package/"scanner.py"
        scanner.write_bytes(scanner.read_bytes().replace(b"\n",b"\r\n"))
        self.verify()


if __name__=="__main__":
    unittest.main()
