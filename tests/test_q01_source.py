"""Real disposable Git/filesystem negative tests; SOURCE only, never Core E2E."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from wam_regtest.build_provenance import capture, verify, BuildSourceError


class Q01BuildSourceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='wam-q01-public-source-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / 'src/public_example.py'
        self.source.parent.mkdir()
        self.source.write_bytes(b'# public inert build fixture\n')
        self.git('init', '--quiet', '--template=')
        self.git('config', 'core.hooksPath', str(self.root / 'absent-hooks'))
        self.git('add', '--', 'src')
        self.git('-c', 'user.name=Public Fixture', '-c', 'user.email=public@example.invalid',
                 '-c', 'commit.gpgsign=false', 'commit', '--quiet', '-m', 'public fixture')

    def git(self, *args, input=None):
        return subprocess.check_output(['git', '-C', str(self.root), *args],
            input=input, stderr=subprocess.DEVNULL, timeout=10)

    def test_clean_source_and_unchanged_build(self):
        stamp = capture(self.root)
        verify(self.root, stamp)
        self.assertEqual(stamp['checkout_sha'], self.git('rev-parse', 'HEAD').decode().strip())

    def test_dirty_source_hidden_by_index_flag_is_refused(self):
        self.git('update-index', '--assume-unchanged', 'src/public_example.py')
        self.source.write_bytes(b'# changed public bytes\n')
        self.assertFalse(self.git('status', '--porcelain').strip())
        with self.assertRaisesRegex(BuildSourceError, 'BUILD_SOURCE_DIRTY'):
            capture(self.root)

    def test_staged_source_is_refused(self):
        self.source.write_bytes(b'# staged public bytes\n')
        self.git('add', '--', 'src')
        with self.assertRaises(BuildSourceError):
            capture(self.root)

    def test_ignored_importable_shadow_is_refused(self):
        (self.root / '.git/info').mkdir(exist_ok=True)
        (self.root / '.git/info/exclude').write_text('src/shadow.py\n')
        (self.source.parent / 'shadow.py').write_bytes(b'# public shadow never executed\n')
        self.assertFalse(self.git('status', '--porcelain').strip())
        with self.assertRaisesRegex(BuildSourceError, 'BUILD_SOURCE_UNTRACKED_MODULE'):
            capture(self.root)

    def test_source_changed_during_build_is_refused(self):
        stamp = capture(self.root)
        self.source.write_bytes(b'# build-time change\n')
        with self.assertRaises(BuildSourceError):
            verify(self.root, stamp)

    def test_git_replacement_cannot_authenticate_modified_source(self):
        pin = self.git('rev-parse', 'HEAD').decode().strip()
        self.source.write_bytes(b'# substituted public source\n')
        self.git('add', '--', 'src')
        tree = self.git('write-tree').decode().strip()
        replacement = self.git('-c', 'user.name=Public Fixture', '-c',
            'user.email=public@example.invalid', 'commit-tree', tree,
            input=b'public replacement\n').decode().strip()
        self.git('replace', pin, replacement)
        self.assertFalse(self.git('status', '--porcelain').strip())
        with self.assertRaises(BuildSourceError):
            capture(self.root)

    def test_hardlinked_tracked_file_is_refused(self):
        os.link(self.source, self.root / 'public-hardlink')
        with self.assertRaises(BuildSourceError):
            capture(self.root)


class Q01EnvironmentContracts(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location('q01_environment', self.root / 'scripts/q01_environment.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_profiles_have_exact_backend_and_separate_qt_closure(self):
        headless = self.module.locked_versions(self.root, 'headless')
        gui = self.module.locked_versions(self.root, 'gui')
        self.assertEqual(headless['setuptools'], '84.0.0')
        self.assertEqual(headless['cryptography'], '50.0.0')
        self.assertEqual(headless['coincurve'], '21.0.0')
        self.assertNotIn('pyside6', headless)
        self.assertEqual(gui['pyside6'], '6.12.0')
        self.assertEqual(gui['qrcode'], '8.2')

    def test_bootstrap_rejects_hidden_python_environment_before_install(self):
        with tempfile.TemporaryDirectory(prefix='wam-q01-bootstrap-') as temporary:
            root = Path(temporary)
            result = subprocess.run([__import__('sys').executable, '-I',
                str(self.root / 'scripts/q01_environment.py'), '--profile', 'headless',
                '--environment', str(root / 'env'), '--receipt', str(root / 'receipt.json')],
                env={**os.environ, 'PYTHONPATH': str(root)}, capture_output=True, timeout=20)
            self.assertNotEqual(result.returncode, 0)
            expected = (3, 12, 15) if __import__('sys').platform == 'linux' else (3, 12, 10)
            code = b'Q01_HIDDEN_PYTHON_ENVIRONMENT_DENIED' if __import__('sys').version_info[:3] == expected else b'Q01_DECLARED_ISOLATED_CPYTHON_REQUIRED'
            self.assertIn(code, result.stderr)
            self.assertFalse((root / 'env').exists())
            self.assertFalse((root / 'receipt.json').exists())
