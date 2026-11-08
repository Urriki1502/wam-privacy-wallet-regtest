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
PLATFORMS = ('macos', 'windows', 'linux-desktop', 'linux-headless')
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
    'linux-desktop': _COMMON_LAZY | _NON_WINDOWS_SMOKE | {('linux_headless', 'linux_headless_probe'),
                                                          ('linux_headless', 'linux_qt_probe')},
    'linux-headless': _COMMON_LAZY | _NON_WINDOWS_SMOKE | {
        ('linux_headless', 'linux_headless_probe'), ('linux_headless', 'linux_qt_probe'),
        # Qt-only branches; the no-Qt package refuses them (fail closed).
        ('core', 'desktop'), ('core', 'operational_gui'), ('linux_headless', 'operational_gui'),
        ('linux_production_entry', 'desktop'), ('managed_onboarding', 'bip39_owner_gui'),
        ('managed_onboarding', 'desktop'), ('managed_onboarding', 'fusion_ui'),
        ('managed_onboarding', 'managed_gui'), ('shared_regtest_gui', 'fusion_ui')},
}


class PlatformAllowlists(unittest.TestCase):
    def test_macos_set_is_unchanged_and_others_add_only_reviewed_modules(self):
        self.assertIs(policy.runtime_modules('macos'), policy.RUNTIME)
        base = policy.RUNTIME - {'production_entry'}
        self.assertEqual(policy.runtime_modules('windows'), base | policy.WINDOWS_EXTRA)
        self.assertEqual(policy.runtime_modules('linux-desktop'), base | policy.LINUX_EXTRA)
        self.assertEqual(policy.runtime_modules('linux-headless'),
                         (base | policy.LINUX_EXTRA) - policy.QT_MODULES)
        with self.assertRaises(ValueError):
            policy.runtime_modules('android')

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
        self.assertFalse({n for n in policy.runtime_modules('linux-headless') if SCAN[n][2]})

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

    def test_strict_headless_parser(self):
        self.assertIsNotNone(self.entry.headless_arguments(self.VALID[1:]))
        self.assertIsNotNone(self.entry.headless_arguments(self.VALID[1:] + ['--recover-backup', '/b/x.enc']))
        for bad in (self.VALID[1:] + ['--confirm-experimental-developer-regtest'],
                    self.VALID[1:] + ['--recover-backup', 'relative.enc'],
                    self.VALID[1:3] + self.VALID[5:],
                    ['--manifest-sha256=' + 'a' * 64] + self.VALID[3:],
                    [t.upper() if t.startswith('a' * 8) else t for t in self.VALID[1:]],
                    self.VALID[1:] + ['--gui']):
            with self.subTest(bad=bad):
                self.assertIsNone(self.entry.headless_arguments(bad))

    def test_valid_headless_runs_existing_frontend_with_bundled_core_and_no_probe(self):
        with mock.patch.object(sys, 'argv', ['wam', *self.VALID]), \
                mock.patch.object(self.entry, 'checked_resources', return_value=(Path('/b/core'), Path('/b/wsp'))), \
                mock.patch('wam_regtest.linux_headless.run', return_value=0) as run:
            self.assertEqual(self.entry.main(), 0)
        args = run.call_args.args[0]
        self.assertEqual((args.core_dir, args.wsp_source_root), (Path('/b/core'), Path('/b/wsp')))
        self.assertEqual(args.manifest_sha256, 'a' * 64)
        self.assertEqual(args.anchor_socket, Path('/run/wam/anchor.sock'))
        self.assertFalse(args.confirm_headless_e2e or args.confirm_qt_e2e or args.gui)
        self.assertIsNone(args.report)
        self.assertIsNone(args.recover_backup)

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
        for needle in ("'--production'", "'linux-desktop' if args.desktop else 'linux-headless'",
                       'linux_production_entry.py', 'audit(binary,bundle,flavor)', 'DEVELOPER_ARGV',
                       "'production_qualified':False", 'linux-production-output', 'dist-production'):
            self.assertIn(needle, text)

    def test_ci_jobs_build_production_after_qualification(self):
        windows = (ROOT / '.github/workflows/windows-x64-credential-anchor.yml').read_text()
        linux = (ROOT / '.github/workflows/linux-experimental-regtest.yml').read_text()
        self.assertLess(windows.index('python -I scripts/build_windows_bundle.py\n'),
                        windows.index('python -I scripts/build_windows_bundle.py --production'))
        self.assertIn('path: windows-production-output/', windows)
        self.assertIn('--production', linux)
        self.assertIn('path: linux-production-output/', linux)
        for text in (windows, linux):
            self.assertIn('scripts/production_packaging.py', text)


if __name__ == '__main__':
    unittest.main()
