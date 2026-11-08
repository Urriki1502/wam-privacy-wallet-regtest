"""Phase 5: Windows/Linux production allowlists and strict entries (build-time policy).

Runs on any host: static closure, argv refusal before resources, builder
contracts. Native Windows/Linux frozen execution is a separate CI gate.
"""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src/wam_regtest'


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


policy = _load('phase5_packaging_policy', ROOT / 'scripts/production_packaging.py')
AVAILABLE = {p.stem for p in SRC.glob('*.py')}
PLATFORMS = ('macos', 'windows', 'linux-desktop')
HOSTILE = {'CI': 'true', 'GITHUB_ACTIONS': 'true', 'WAM_Q06_CI_SPEND_QUALIFY': '1', 'WAM_QUALIFICATION': '1'}


def _scan(name):
    tree = ast.parse((SRC / (name + '.py')).read_text())
    parents = {c: n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
    module, lazy, qt = set(), set(), False
    for node in ast.walk(tree):
        targets, external = [], None
        if isinstance(node, ast.ImportFrom):
            if node.level == 1:
                targets = [node.module.split('.')[0]] if node.module else [a.name for a in node.names]
            elif node.module and node.module.startswith('wam_regtest.'):
                targets = [node.module.split('.')[1]]
            elif node.module == 'wam_regtest':
                targets = [a.name for a in node.names]
            else:
                external = (node.module or '').split('.')[0]
        elif isinstance(node, ast.Import):
            targets = [a.name.split('.')[1] for a in node.names if a.name.startswith('wam_regtest.')]
            external = node.names[0].name.split('.')[0]
        else:
            continue
        inside, cursor = False, node
        while cursor in parents:
            cursor = parents[cursor]
            if isinstance(cursor, (ast.FunctionDef, ast.AsyncFunctionDef)):
                inside = True
                break
        (lazy if inside else module).update(t for t in targets if t in AVAILABLE)
        if not inside and external in ('PySide6', 'shiboken6'):
            qt = True
    return module, lazy, qt


SCAN = {name: _scan(name) for name in AVAILABLE}

# Reviewed function-level edges from shipped modules to excluded modules. Each
# is a developer/acceptance branch or another platform's sys.platform branch;
# a new edge must be reviewed here (fails closed at runtime if reached).
_COMMON_LAZY = {('core', 'desktop_probe'), ('core', 'q02_probe'), ('core', 'reopen_probe'),
                ('core', 'security_probe'), ('core', 'wallet_probe'), ('core', 'windows_vault_probe'),
                ('managed_onboarding', 'onboarding_probe')}
_NON_WINDOWS_SMOKE = {('core', 'windows_core_regtest_smoke'), ('core_process', 'windows_core_regtest_smoke'),
                      ('core_supervisor', 'windows_core_regtest_smoke'), ('rpc_scope', 'windows_core_regtest_smoke'),
                      ('windows_core_transport', 'windows_core_regtest_smoke')}
REVIEWED_LAZY = {
    'macos': _COMMON_LAZY | _NON_WINDOWS_SMOKE,
    'windows': _COMMON_LAZY | {('windows_core_regtest_smoke', 'windows_read_gui'),
                               ('windows_core_regtest_smoke', 'windows_vault_probe'),
                               ('windows_core_regtest_smoke', 'windows_wsp_regtest')},
    'linux-desktop': _COMMON_LAZY | _NON_WINDOWS_SMOKE,
}


class PlatformAllowlists(unittest.TestCase):
    def test_macos_set_is_unchanged_and_others_add_only_reviewed_modules(self):
        self.assertIs(policy.runtime_modules('macos'), policy.RUNTIME)
        base = policy.RUNTIME - {'production_entry'}
        self.assertEqual(policy.runtime_modules('windows'), base | policy.WINDOWS_EXTRA)
        self.assertEqual(policy.runtime_modules('linux-desktop'), base | policy.LINUX_EXTRA)
        self.assertNotIn('linux_headless', policy.runtime_modules('linux-desktop'))
        for retired in ('android', 'linux-headless'):
            with self.assertRaises(ValueError):
                policy.runtime_modules(retired)

    def test_no_platform_ships_developer_entries_probes_or_scenarios(self):
        for platform in PLATFORMS:
            runtime = policy.runtime_modules(platform)
            with self.subTest(platform=platform):
                self.assertTrue(runtime <= AVAILABLE)
                self.assertFalse({n for n in runtime if n.endswith(('_probe', '_scenario', '_fixture'))})
                self.assertFalse(runtime & {'cli', '__main__', 'package_entry', 'windows_package_entry',
                                            'linux_package_entry', 'bip39_reconcile', 'q05_packaged',
                                            'q04_runner', 'q04_miner_loop', 'q04_fixture',
                                            'windows_read_gui', 'windows_wallet_read', 'windows_wsp_regtest'})
                self.assertIn(policy.ENTRY[platform], runtime)
                others = set(policy.ENTRY.values()) - {policy.ENTRY[platform]}
                self.assertFalse(runtime & others)

    def test_qt_module_set_matches_static_module_level_imports(self):
        desktop = policy.runtime_modules('linux-desktop')
        self.assertEqual({n for n in desktop if SCAN[n][2]}, set(policy.QT_MODULES))

    def test_module_level_closure_is_complete_for_every_platform(self):
        for platform in PLATFORMS:
            runtime = policy.runtime_modules(platform)
            with self.subTest(platform=platform):
                missing = {(n, t) for n in runtime for t in SCAN[n][0] if t not in runtime}
                self.assertEqual(missing, set())

    def test_lazy_edges_to_excluded_modules_are_exactly_the_reviewed_set(self):
        for platform in PLATFORMS:
            runtime = policy.runtime_modules(platform)
            with self.subTest(platform=platform):
                lazy = {(n, t) for n in runtime for t in SCAN[n][1] if t not in runtime}
                self.assertEqual(lazy, REVIEWED_LAZY[platform])

    def test_arguments_cover_every_module_once_per_platform(self):
        for platform in PLATFORMS:
            with self.subTest(platform=platform):
                args = policy.arguments(ROOT, platform)
                hidden = {args[i + 1] for i in range(0, len(args), 2) if args[i] == '--hidden-import'}
                excluded = {args[i + 1] for i in range(0, len(args), 2) if args[i] == '--exclude-module'}
                runtime = policy.runtime_modules(platform)
                self.assertEqual(hidden, {'wam_regtest.' + n for n in runtime - {'__init__', policy.ENTRY[platform]}})
                self.assertEqual(excluded, {'wam_regtest.' + n for n in AVAILABLE - runtime})

    def test_ci_confirm_has_no_emitter_in_any_production_set(self):
        for platform in PLATFORMS:
            users = {n for n in policy.runtime_modules(platform) - {'__init__'}
                     if any(isinstance(x, ast.Constant) and x.value == 'ci_confirm'
                            for x in ast.walk(ast.parse((SRC / (n + '.py')).read_text())))}
            with self.subTest(platform=platform):
                self.assertEqual(users, {'bip39_owner_backend', 'wallet_executor'})


class OnedirLooseFilePolicy(unittest.TestCase):
    def _bundle(self, root):
        bundle = Path(root) / 'WAM-Privacy-Wallet-REGTEST'
        wsp = bundle / '_internal/wsp-source'
        member = wsp / 'src/wam_sp/core.py'
        member.parent.mkdir(parents=True)
        member.write_text('# pinned\n')
        (wsp / 'SOURCE_SHA256.json').write_text(json.dumps({
            'source_commit': 'ac55f13423620252bdbf848c7e8a280c3b84721e',
            'files': {'src/wam_sp/core.py': hashlib.sha256(member.read_bytes()).hexdigest()}}))
        return bundle

    def test_pinned_onedir_wsp_passes_and_loose_wallet_code_is_denied(self):
        with tempfile.TemporaryDirectory() as d:
            policy.audit_loose_files(self._bundle(d))
        for relative in ('_internal/cli.pyc', '_internal/wam_regtest/q06_spend_probe.py',
                         'linux_package_entry.py', '_internal/lib/windows_package_entry.pyd'):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as d:
                bundle = self._bundle(d)
                (bundle / relative).parent.mkdir(parents=True, exist_ok=True)
                (bundle / relative).write_bytes(b'')
                with self.assertRaisesRegex(ValueError, 'PRODUCTION_LOOSE_MODULE_DENIED'):
                    policy.audit_loose_files(bundle)

    def test_windows_native_extension_modules_are_allowed_but_not_wallet_named(self):
        # Windows-CI 42486018402: .pyd files are compiled extension modules
        # (like .so on macOS/Linux), not loose Python source.
        for relative in ('_internal/_ssl.pyd', '_internal/_cffi_backend.cp312-win_amd64.pyd',
                         '_internal/PySide6/QtCore.pyd', '_internal/coincurve/_libsecp256k1.cp312-win_amd64.pyd'):
            with self.subTest(allowed=relative), tempfile.TemporaryDirectory() as d:
                bundle = self._bundle(d)
                (bundle / relative).parent.mkdir(parents=True, exist_ok=True)
                (bundle / relative).write_bytes(b'MZ')
                policy.audit_loose_files(bundle)
        for relative in ('_internal/wallet_session.cp312-win_amd64.pyd', '_internal/wam_regtest/x.pyd',
                         '_internal/wam_sp/core.so', '_internal/scanner.cpython-312-darwin.so'):
            with self.subTest(denied=relative), tempfile.TemporaryDirectory() as d:
                bundle = self._bundle(d)
                (bundle / relative).parent.mkdir(parents=True, exist_ok=True)
                (bundle / relative).write_bytes(b'MZ')
                with self.assertRaisesRegex(ValueError, 'PRODUCTION_LOOSE_MODULE_DENIED'):
                    policy.audit_loose_files(bundle)

    def test_second_wsp_source_directory_is_denied(self):
        with tempfile.TemporaryDirectory() as d:
            bundle = self._bundle(d)
            (bundle / 'wsp-source').mkdir()
            with self.assertRaisesRegex(ValueError, 'PRODUCTION_LOOSE_MODULE_DENIED'):
                policy.audit_loose_files(bundle)


class WindowsProductionEntry(unittest.TestCase):
    def setUp(self):
        from wam_regtest import windows_production_entry
        self.entry = windows_production_entry

    def test_every_developer_argv_is_refused_before_resources(self):
        for argv in policy.DEVELOPER_ARGV:
            with self.subTest(argv=argv), mock.patch.object(sys, 'argv', ['wallet', *argv]), \
                    mock.patch.dict(os.environ, HOSTILE), \
                    mock.patch.object(self.entry, 'checked_resources') as check:
                self.assertEqual(self.entry.main(), 64)
                check.assert_not_called()

    def test_check_bundle_stages_pinned_core_and_never_launches_wallet(self):
        from wam_regtest import windows_core_stage
        with mock.patch.object(sys, 'argv', ['wallet', '--check-bundle']), \
                mock.patch.object(self.entry, 'checked_resources', return_value=(Path('/core'), Path('/wsp'))), \
                mock.patch.object(windows_core_stage, '_stage_original_core') as stage, \
                mock.patch('wam_regtest.managed_onboarding.launch') as launch:
            self.assertEqual(self.entry.main(), 0)
            stage.assert_called_once()
            launch.assert_not_called()

    def test_unfrozen_host_is_denied_without_exception_text(self):
        with mock.patch.object(sys, 'argv', ['wallet', '--check-bundle']):
            self.assertEqual(self.entry.main(), 2)

    def test_entry_never_reads_environment(self):
        text = (SRC / 'windows_production_entry.py').read_text()
        self.assertNotIn('environ', text)
        self.assertNotIn('getenv', text)

    def test_stage_helper_moved_not_duplicated(self):
        qualification = ast.parse((SRC / 'windows_package_entry.py').read_text())
        self.assertFalse([n for n in qualification.body
                          if isinstance(n, ast.FunctionDef) and n.name == '_stage_original_core'])
        from wam_regtest import windows_core_stage, windows_package_entry
        self.assertIs(windows_package_entry._stage_original_core, windows_core_stage._stage_original_core)


class LinuxProductionEntry(unittest.TestCase):
    VALID = ['wallet', '--manifest-sha256', 'a' * 64, '--anchor-socket', '/run/wam/anchor.sock',
             '--confirm-experimental-developer-regtest']

    def setUp(self):
        from wam_regtest import linux_production_entry
        self.entry = linux_production_entry

    def test_every_developer_argv_is_refused_before_resources(self):
        for argv in policy.DEVELOPER_ARGV:
            with self.subTest(argv=argv), mock.patch.object(sys, 'argv', ['wam', *argv]), \
                    mock.patch.dict(os.environ, HOSTILE), \
                    mock.patch.object(self.entry, 'checked_resources') as check:
                self.assertEqual(self.entry.main(), 64)
                check.assert_not_called()

    def test_headless_cli_is_not_a_production_route(self):
        """Six-gate decision B: legacy-custody headless is refused like any developer argv."""
        self.assertFalse(hasattr(self.entry, 'headless_arguments'))
        for argv in (self.VALID, self.VALID + ['--recover-backup', '/b/x.enc'], ['wallet']):
            with self.subTest(argv=argv), mock.patch.object(sys, 'argv', ['wam', *argv]), \
                    mock.patch.object(self.entry, 'checked_resources') as check, \
                    mock.patch('wam_regtest.linux_headless.run') as run:
                self.assertEqual(self.entry.main(), 64)
                check.assert_not_called()
                run.assert_not_called()
        formerly_accepted = ['wallet', '--manifest-sha256', '0' * 64, '--anchor-socket',
                             '/nonexistent/anchor.sock', '--confirm-experimental-developer-regtest']
        self.assertIn(formerly_accepted, [list(a) for a in policy.DEVELOPER_ARGV])
        self.assertNotIn('linux_headless', (SRC / 'linux_production_entry.py').read_text())

    def test_check_bundle_and_unfrozen_host(self):
        with mock.patch.object(sys, 'argv', ['wam', '--check-bundle']), \
                mock.patch.object(self.entry, 'checked_resources', return_value=(Path('/c'), Path('/w'))), \
                mock.patch('wam_regtest.linux_headless.run') as run:
            self.assertEqual(self.entry.main(), 0)
            run.assert_not_called()
        with mock.patch.object(sys, 'argv', ['wam', '--check-bundle']):
            self.assertEqual(self.entry.main(), 2)

    def test_entry_never_reads_environment_or_imports_cli(self):
        text = (SRC / 'linux_production_entry.py').read_text()
        self.assertNotIn('environ', text)
        self.assertNotIn('wam_regtest.cli', text)


class BuilderContracts(unittest.TestCase):
    def test_windows_builder_production_mode(self):
        builder = _load('phase5_windows_builder', ROOT / 'scripts/build_windows_bundle.py')
        self.assertFalse(builder._production_mode([]))
        self.assertTrue(builder._production_mode(['--production']))
        for argv in (['--production', '--production'], ['--ci'], ['production']):
            with self.subTest(argv=argv), self.assertRaises(SystemExit) as raised:
                builder._production_mode(argv)
            self.assertEqual(raised.exception.code, 64)
        text = (ROOT / 'scripts/build_windows_bundle.py').read_text()
        for needle in ("production_arguments(source_root,'windows')", 'windows_production_entry.py',
                       "audit(executable,bundle,'windows')", 'DEVELOPER_ARGV', "'production_qualified':False",
                       'windows-production-output', 'dist-production'):
            self.assertIn(needle, text)

    def test_linux_builder_production_mode(self):
        text = (ROOT / 'scripts/build_linux_wallet.py').read_text()
        for needle in ("'--production'", "production_arguments(source_root,'linux-desktop')",
                       'LINUX_HEADLESS_PRODUCTION_OUT_OF_SCOPE',
                       'linux_production_entry.py', 'audit(binary,bundle,flavor)', 'DEVELOPER_ARGV',
                       "'production_qualified':False", 'linux-production-output', 'dist-production'):
            self.assertIn(needle, text)

    def test_ci_jobs_build_production_after_qualification(self):
        windows = (ROOT / '.github/workflows/windows-x64-credential-anchor.yml').read_text()
        linux = (ROOT / '.github/workflows/linux-experimental-regtest.yml').read_text()
        self.assertLess(windows.index('python -I scripts/build_windows_bundle.py\n'),
                        windows.index('python -I scripts/build_windows_bundle.py --production'))
        self.assertIn('path: windows-production-output/', windows)
        self.assertIn('--production --desktop', linux)
        self.assertNotIn("matrix.frontend == 'desktop' && '--desktop' || ''", linux)
        self.assertIn('path: linux-production-output/', linux)
        for text in (windows, linux):
            self.assertIn('scripts/production_packaging.py', text)


if __name__ == '__main__':
    unittest.main()
