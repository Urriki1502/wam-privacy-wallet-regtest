"""Phase 4.2 packaging/CI contracts (R1-R5). Build-time policy only; no wallet authority."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


policy = _load('phase42_packaging_policy', ROOT / 'scripts/production_packaging.py')
SOURCE = {p.stem for p in (ROOT / 'src/wam_regtest').glob('*.py')}


def _runtime(platform='macos'):
    getter = getattr(policy, 'runtime_modules', None)
    return getter(platform) if getter is not None else policy.RUNTIME


class _FakeArchive:
    """Exact allowlisted PYZ inventory, so only the loose-file policy decides."""
    def __init__(self, path):
        self.toc = {'PYZ.pyz': None, 'production_entry': None}

    def open_embedded_archive(self, name):
        names = {'wam_regtest'} | {'wam_regtest.' + n for n in _runtime() - {'__init__', 'production_entry'}}
        return type('PYZ', (), {'toc': dict.fromkeys(names)})()


def _app(root):
    app = Path(root) / 'WAM Privacy Wallet REGTEST.app'
    wsp = app / 'Contents/Resources/wsp-source'
    member = wsp / 'src/wam_sp/core.py'
    member.parent.mkdir(parents=True)
    member.write_text('# pinned public WSP data\n')
    (app / 'Contents/Frameworks').mkdir(parents=True)
    (app / 'Contents/MacOS').mkdir(parents=True)
    (wsp / 'SOURCE_SHA256.json').write_text(json.dumps({
        'source_commit': 'ac55f13423620252bdbf848c7e8a280c3b84721e',
        'files': {'src/wam_sp/core.py': hashlib.sha256(member.read_bytes()).hexdigest()}}))
    return app


class LooseModulePolicy(unittest.TestCase):
    """R2: loose wallet modules/bytecode outside the PYZ must fail the frozen audit."""

    def _audit(self, app):
        with mock.patch('PyInstaller.archive.readers.CArchiveReader', _FakeArchive):
            return policy.audit(app / 'Contents/MacOS/x', app)

    def test_pinned_wsp_data_only_passes(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self._audit(_app(d))['status'], 'PASS_EXACT_PRODUCTION_ALLOWLIST')

    def test_loose_python_or_bytecode_anywhere_else_is_denied(self):
        for relative in ('Contents/Resources/q02_probe.pyc', 'Contents/Frameworks/wallet_session.py',
                         'Contents/Resources/lib/package_entry.pyo', 'Contents/MacOS/cli.py',
                         'Contents/Resources/wsp-source/src/wam_sp/__pycache__/core.cpython-312.pyc',
                         'Contents/Resources/wsp-source/src/wam_sp/q06_spend_probe.py'):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as d:
                app = _app(d)
                (app / relative).parent.mkdir(parents=True, exist_ok=True)
                (app / relative).write_bytes(b'')
                with self.assertRaisesRegex(ValueError, 'PRODUCTION_LOOSE_MODULE_DENIED'):
                    self._audit(app)

    def test_modified_pinned_wsp_member_is_denied(self):
        with tempfile.TemporaryDirectory() as d:
            app = _app(d)
            (app / 'Contents/Resources/wsp-source/src/wam_sp/core.py').write_text('changed\n')
            with self.assertRaisesRegex(ValueError, 'PRODUCTION_LOOSE_MODULE_DENIED'):
                self._audit(app)


class MacAllowlistClosure(unittest.TestCase):
    """R3: every Mac allowlisted module imports with all excluded modules absent."""

    def test_windows_read_modules_are_not_shipped_on_macos_but_remain_in_source(self):
        for name in ('windows_read_gui', 'windows_wallet_read', 'windows_wsp_regtest'):
            self.assertIn(name, SOURCE)
            self.assertNotIn(name, _runtime('macos'))

    def test_import_closure_with_exclusions_blocked(self):
        runtime = _runtime('macos')
        excluded = sorted(SOURCE - runtime)
        child = (
            'import sys,importlib,importlib.abc\n'
            'EX=set(sys.argv[1].split(","));MODS=sys.argv[2].split(",")\n'
            'class B(importlib.abc.MetaPathFinder):\n'
            ' def find_spec(self,n,p=None,t=None):\n'
            '  if n.startswith("wam_regtest.") and n.split(".")[1] in EX:raise ModuleNotFoundError("EXCLUDED:"+n)\n'
            'sys.meta_path.insert(0,B());bad=[]\n'
            'for m in MODS:\n'
            ' try:importlib.import_module("wam_regtest."+m)\n'
            ' except BaseException as e:bad.append(m+":"+type(e).__name__)\n'
            'print(",".join(bad))\n')
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'), QT_QPA_PLATFORM='offscreen')
        out = subprocess.run([sys.executable, '-c', child, ','.join(excluded),
                              ','.join(sorted(runtime - {'__init__'}))],
                             env=env, capture_output=True, text=True, timeout=300)
        self.assertEqual(out.returncode, 0, out.stderr[-2000:])
        self.assertEqual(out.stdout.strip(), '')


class ResidualCiOnlyConfirm(unittest.TestCase):
    """R4: env-gated CI confirm has no production caller and refuses without full scope."""

    def test_no_shipped_gui_emits_ci_confirm(self):
        users = set()
        for name in _runtime('macos') - {'__init__'}:
            tree = ast.parse((ROOT / 'src/wam_regtest' / (name + '.py')).read_text())
            if any(isinstance(n, ast.Constant) and n.value == 'ci_confirm' for n in ast.walk(tree)):
                users.add(name)
        # Dispatcher and finite executor action list only; no GUI/entry emitter.
        self.assertEqual(users, {'bip39_owner_backend', 'wallet_executor'})

    def test_ci_confirm_refuses_unless_complete_ci_scope(self):
        from wam_regtest.bip39_owner_backend import Bip39ReadOnlyBackend, Q06ReadOnlyError
        backend = object.__new__(Bip39ReadOnlyBackend)
        backend._spend_session = object()
        backend._core = lambda: self.fail('Core must not be reached')
        for env in ({}, {'GITHUB_ACTIONS': 'true'}, {'WAM_Q06_CI_SPEND_QUALIFY': '1'},
                    {'CI': 'true', 'WAM_QUALIFICATION': '1'},
                    {'GITHUB_ACTIONS': 'false', 'WAM_Q06_CI_SPEND_QUALIFY': '1'}):
            with self.subTest(env=env), mock.patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(Q06ReadOnlyError, 'Q06_GUI_CONFIRM_CI_SCOPE_DENIED'):
                    backend._confirm_spend_ci()
        backend._spend_session = None
        with mock.patch.dict(os.environ, {'GITHUB_ACTIONS': 'true', 'WAM_Q06_CI_SPEND_QUALIFY': '1'}, clear=True):
            with self.assertRaisesRegex(Q06ReadOnlyError, 'Q06_GUI_CONFIRM_CI_SCOPE_DENIED'):
                backend._confirm_spend_ci()

    def test_production_entry_never_reads_ci_environment(self):
        text = (ROOT / 'src/wam_regtest/production_entry.py').read_text()
        self.assertNotIn('environ', text)
        self.assertNotIn('getenv', text)


class MacCiWorkflowContract(unittest.TestCase):
    """R1: hosted Mac jobs consume the split production/qualification layout."""

    WORKFLOWS = ('.github/workflows/macos-arm64-frozen-rc.yml', '.github/workflows/real-core-regtest.yml')

    def test_workflows_use_explicit_split_output_and_verifier(self):
        for workflow in self.WORKFLOWS:
            with self.subTest(workflow=workflow):
                text = (ROOT / workflow).read_text()
                self.assertIn('WAM_MACOS_OUTPUT_ROOT', text)
                self.assertIn('scripts/verify_macos_ci_outputs.py', text)
                self.assertNotIn('Path("package-output")', text)
                self.assertNotIn('package-output/WAM-Privacy-Wallet-REGTEST-macOS-ARM64.dmg', text)
                self.assertNotIn('qualification-only/package-output/WAM-Privacy-Wallet', text)

    def test_each_workflow_builds_once_with_unique_job_ids(self):
        import re
        for workflow in self.WORKFLOWS:
            with self.subTest(workflow=workflow):
                text = (ROOT / workflow).read_text()
                self.assertEqual(text.count('bash scripts/build_macos_bundle.sh'), 1)
                self.assertEqual(text.count('scripts/verify_macos_ci_outputs.py'), 1)
                jobs = re.findall(r'^  ([A-Za-z0-9_-]+):\s*$', text, re.M)
                self.assertEqual(len(jobs), len(set(jobs)))

    def test_production_builder_creates_its_private_stage_parent(self):
        text = (ROOT / 'scripts/build_macos_production.py').read_text()
        self.assertLess(text.index("(root/'bundle-input').mkdir("), text.index('tempfile.mkdtemp('))


class ArtifactIdentity(unittest.TestCase):
    """R5: qualification-only bytes never share the distributed identity."""

    def test_distinct_names_and_bundle_identifiers(self):
        legacy = (ROOT / 'scripts/build_macos_bundle.sh').read_text()
        production = (ROOT / 'scripts/build_macos_production.py').read_text()
        self.assertIn('org.wamcoin.privacywallet.regtest.qualification', legacy)
        self.assertIn('WAM Privacy Wallet REGTEST QUALIFICATION', legacy)
        self.assertIn('QUALIFICATION-ONLY', legacy)
        self.assertNotIn('--osx-bundle-identifier "org.wamcoin.privacywallet.regtest" ', legacy)
        self.assertIn("'org.wamcoin.privacywallet.regtest'", production)


@unittest.skipUnless((ROOT / 'scripts/verify_macos_ci_outputs.py').is_file(), 'verifier not present')
class MacCiOutputVerifier(unittest.TestCase):
    """R1: receipts from different executables or commits cannot be mixed."""

    SHA = 'a' * 40

    def setUp(self):
        self.verifier = _load('phase42_ci_verifier', ROOT / 'scripts/verify_macos_ci_outputs.py')

    def _tree(self, root):
        v = self.verifier
        root = Path(root)
        prod, qual = root / 'package-output', root / 'qualification-only/package-output'
        prod.mkdir(parents=True)
        qual.mkdir(parents=True)
        for directory, names, ident in ((root / 'dist', v.PRODUCTION_APP, v.PRODUCTION_BUNDLE_ID),
                                        (root / 'qualification-only/dist', v.QUALIFICATION_APP, v.QUALIFICATION_BUNDLE_ID)):
            contents = directory / names / 'Contents'
            (contents / 'MacOS').mkdir(parents=True)
            (contents / 'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier': ident}))
            (contents / 'MacOS' / names.removesuffix('.app')).write_bytes(ident.encode())
        files = {}
        for name in v.PRODUCTION_FILES:
            (prod / name).write_bytes(b'production ' + name.encode())
            files[name] = hashlib.sha256((prod / name).read_bytes()).hexdigest()
        (prod / 'PRODUCTION_BUILD_RECEIPT.json').write_text(json.dumps(dict(
            artifact_role='allowlisted-regtest-wallet', mainnet_allowed=False, production_qualified=False,
            source=dict(checkout_sha=self.SHA, source_head_sha=self.SHA, tracked_source_matches_head=True,
                        source_unchanged_across_build=True),
            core_sha256=v.CORE_PINS, wsp_source_commit=v.WSP_PIN, files_sha256=files,
            # The real builder always records it; binding requires it (CDX-AUD-008).
            executable_sha256=hashlib.sha256(v.PRODUCTION_BUNDLE_ID.encode()).hexdigest())))
        (prod / 'PRODUCTION_MODULE_INVENTORY.json').write_text(json.dumps(dict(
            status='PASS_EXACT_PRODUCTION_ALLOWLIST', developer_dispatch=False)))
        (prod / 'PRODUCTION_DISPATCH_NEGATIVES.json').write_text(json.dumps([dict(mode='smoke', returncode=64)]))
        (prod / 'SHA256SUMS.txt').write_bytes(''.join(
            f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n'
            for p in sorted(prod.iterdir()) if p.name != 'SHA256SUMS.txt').encode())
        qfiles = {}
        for name in v.QUALIFICATION_FILES:
            (qual / name).write_bytes(b'qualification ' + name.encode())
            qfiles[name] = dict(sha256=hashlib.sha256((qual / name).read_bytes()).hexdigest())
        (qual / 'q06-frozen-spend-evidence.json').write_text('{}')
        (qual / 'SHA256SUMS.json').write_text(json.dumps(dict(
            artifact_role='qualification-only', distribution_allowed=False, source_commit=self.SHA,
            qualification_scope='full', full_exact_commit_Q01_Q06_qualified=True, mainnet_allowed=False,
            wamd_sha256=v.CORE_PINS['wamd'], wam_cli_sha256=v.CORE_PINS['wam-cli'], files=qfiles)))
        (root / 'qualification-only/NOT_FOR_DISTRIBUTION.json').write_text(json.dumps(dict(
            artifact_role='qualification-only', production_binary_qualified=False)))
        return root

    def _verify(self, root, publish):
        # Synthetic fixtures exercise the BINDING stage only (CDX-AUD-008).
        return self.verifier.verify(Path(root), self.SHA, Path(publish), payload_audit=False)

    def test_default_verification_rejects_synthetic_non_payload_bytes(self):
        """CDX-AUD-008: self-consistent receipts no longer pass without real payloads."""
        with tempfile.TemporaryDirectory() as d:
            root = self._tree(Path(d) / 'b')
            self.verifier.verify(root, self.SHA, Path(d) / 'binding', payload_audit=False)
            with self.assertRaisesRegex(ValueError, 'MACOS_CI_OUTPUT_PAYLOAD_'):
                self.verifier.verify(root, self.SHA, Path(d) / 'p')
            self.assertFalse((Path(d) / 'p').exists())

    def test_split_outputs_publish_only_production_payloads(self):
        with tempfile.TemporaryDirectory() as d:
            root = self._tree(Path(d) / 'b')
            binding = self._verify(root, Path(d) / 'p')
            published = {p.name for p in (Path(d) / 'p/production').iterdir()}
            self.assertTrue(set(self.verifier.PRODUCTION_FILES) <= published)
            evidence = {p.name for p in (Path(d) / 'p/qualification-only-evidence').rglob('*') if p.is_file()}
            self.assertFalse(evidence & set(self.verifier.QUALIFICATION_FILES))
            self.assertIn('q06-frozen-spend-evidence.json', evidence)
            self.assertEqual(binding['source_commit'], self.SHA)
            self.assertFalse(binding['production_qualified'])

    def test_mixed_commit_role_or_bytes_are_denied(self):
        def other_commit(root):
            path = root / 'qualification-only/package-output/SHA256SUMS.json'
            data = json.loads(path.read_text()); data['source_commit'] = 'b' * 40
            path.write_text(json.dumps(data))

        def same_bytes(root):
            q = root / 'qualification-only/package-output'
            path = q / 'SHA256SUMS.json'
            data = json.loads(path.read_text())
            name = self.verifier.QUALIFICATION_FILES[0]
            (q / name).write_bytes((root / 'package-output' / self.verifier.PRODUCTION_FILES[0]).read_bytes())
            data['files'][name]['sha256'] = hashlib.sha256((q / name).read_bytes()).hexdigest()
            path.write_text(json.dumps(data))

        def legacy_role(root):
            path = root / 'qualification-only/package-output/SHA256SUMS.json'
            data = json.loads(path.read_text()); data.pop('artifact_role')
            path.write_text(json.dumps(data))

        def tampered_production(root):
            (root / 'package-output' / self.verifier.PRODUCTION_FILES[0]).write_bytes(b'changed')

        def shared_bundle_id(root):
            plist = root / 'qualification-only/dist' / self.verifier.QUALIFICATION_APP / 'Contents/Info.plist'
            plist.write_bytes(plistlib.dumps({'CFBundleIdentifier': self.verifier.PRODUCTION_BUNDLE_ID}))

        def production_claims_qualified(root):
            path = root / 'package-output/PRODUCTION_BUILD_RECEIPT.json'
            data = json.loads(path.read_text()); data['production_qualified'] = True
            path.write_text(json.dumps(data))

        for mutate in (other_commit, same_bytes, legacy_role, tampered_production,
                       shared_bundle_id, production_claims_qualified):
            with self.subTest(case=mutate.__name__), tempfile.TemporaryDirectory() as d:
                root = self._tree(Path(d) / 'b')
                mutate(root)
                with self.assertRaises(ValueError):
                    self._verify(root, Path(d) / 'p')
                self.assertFalse((Path(d) / 'p').exists())


if __name__ == '__main__':
    unittest.main()
