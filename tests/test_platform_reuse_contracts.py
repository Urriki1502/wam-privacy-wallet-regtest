"""Existing OS ports must stay the V2.2 freeze path. No native Win/Linux claim."""
from pathlib import Path
import unittest

from wam_regtest.linux_developer_core import inspect_elf, LinuxCoreError
from wam_regtest.q05_platforms import DarwinArm64Adapter, LinuxX64Adapter, WindowsX64Adapter
from wam_regtest.windows_release_preflight import BINARY_SHA256, ARCHIVE_SHA256

from test_linux_developer_core import elf

ROOT = Path(__file__).resolve().parents[1]


class PlatformReuseContracts(unittest.TestCase):
    def test_single_existing_builders_and_entries(self):
        scripts = ROOT / 'scripts'
        src = ROOT / 'src' / 'wam_regtest'
        self.assertTrue((scripts / 'build_windows_bundle.py').is_file())
        self.assertTrue((scripts / 'build_linux_wallet.py').is_file())
        self.assertTrue((scripts / 'build_linux_developer_core.sh').is_file())
        self.assertTrue((scripts / 'build_macos_bundle.sh').is_file())
        extras = list(scripts.glob('build_windows_*.py')) + list(scripts.glob('build_linux_wallet_*.py'))
        self.assertEqual(extras, [scripts / 'build_windows_bundle.py'])
        for name in ('windows_package_entry.py', 'linux_package_entry.py', 'package_entry.py'):
            self.assertTrue((src / name).is_file())

    def test_pyinstaller_still_collects_the_shared_fusion_package(self):
        mac = (ROOT / 'scripts' / 'build_macos_bundle.sh').read_text()
        win = (ROOT / 'scripts' / 'build_windows_bundle.py').read_text()
        linux = (ROOT / 'scripts' / 'build_linux_wallet.py').read_text()
        for text in (mac, win, linux):
            self.assertIn('--collect-submodules', text)
            self.assertIn('wam_regtest', text)
        onboarding = (ROOT / 'src' / 'wam_regtest' / 'managed_onboarding.py').read_text()
        self.assertIn('launch_bip39_trial', onboarding)
        owner = (ROOT / 'src' / 'wam_regtest' / 'bip39_owner_gui.py').read_text()
        self.assertIn('Bip39FusionWindow', owner)

    def test_q06_frozen_denials_keep_q06_tokens_on_existing_entries(self):
        linux = (ROOT / 'src' / 'wam_regtest' / 'linux_package_entry.py').read_text()
        windows = (ROOT / 'src' / 'wam_regtest' / 'windows_package_entry.py').read_text()
        self.assertIn('Q06PlatformQualificationError', linux)
        self.assertIn('Q06PlatformQualificationError', windows)
        self.assertIn(r'(?:LINUX|Q04|EXTERNAL_ATTACHMENT|Q06)_', linux)
        from wam_regtest.windows_package_entry import _public_denial
        for code in ('Q06_NATIVE_SCOPE_DENIED','Q02_ACCEPTANCE_CONFIG_AUTH_FAILED'):
            self.assertEqual(_public_denial(ValueError(code))['reason_code'],code)

    def test_v1_net_frozen_lab_stays_cocoa_and_v19_blocked(self):
        probe = (ROOT / 'src' / 'wam_regtest' / 'shared_network_probe.py').read_text()
        self.assertIn("SHARED_NATIVE_COCOA_REQUIRED", probe)
        self.assertIn("report['cases']['V19'] = 'BLOCKED'", probe)
        self.assertIn('--ci-v1-net-shared-regtest', (ROOT / 'src' / 'wam_regtest' / 'package_entry.py').read_text())
        self.assertNotIn('--ci-v1-net-shared-regtest', (ROOT / 'src' / 'wam_regtest' / 'windows_package_entry.py').read_text())
        self.assertNotIn('--ci-v1-net-shared-regtest', (ROOT / 'src' / 'wam_regtest' / 'linux_package_entry.py').read_text())

    def test_core_trust_labels_and_official_pe_pins(self):
        self.assertTrue(DarwinArm64Adapter.official_signed)
        self.assertTrue(WindowsX64Adapter.official_signed)
        self.assertTrue(LinuxX64Adapter.official_signed)
        self.assertEqual(LinuxX64Adapter.core_trust, 'official-signed-v0.1.13-reviewed-loader')
        self.assertEqual(ARCHIVE_SHA256, 'db6bcb58e909a72a69ab7bb74a95ab3837298c12fd847dc83fdb37fca10732b4')
        self.assertEqual(BINARY_SHA256['wamd.exe'],
                         '5fbeb6e07a83b337209edf0efbe342201bc3bf2e0c113dea8fdf7bf0e07d49e3')
        self.assertEqual(BINARY_SHA256['wam-cli.exe'],
                         'a6171ed6cddfeea58b9a6a8b722f2c07c0d332f0f1a7263f52193e4ef9f6f326')

    def test_q06_owner_probe_uses_current_fusion_nav(self):
        from wam_regtest.fusion_ui import FUSION_NAV_PAGES
        text = (ROOT / 'src' / 'wam_regtest' / 'q06_owner_probe.py').read_text()
        self.assertIn('FUSION_NAV_PAGES', text)
        self.assertNotIn('navigation.count() != 6', text)
        self.assertGreaterEqual(len(FUSION_NAV_PAGES), 6)
        spend = (ROOT / 'src' / 'wam_regtest' / 'q06_spend_probe.py').read_text()
        platform = (ROOT / 'src' / 'wam_regtest' / 'q06_platform_probe.py').read_text()
        self.assertIn('FUSION_NAV_PAGES', spend)
        self.assertIn('FUSION_NAV_PAGES', platform)

    def test_macos_frozen_qt_probe_reads_v22_overview_chart(self):
        probe = (ROOT / 'src' / 'wam_regtest' / 'desktop_probe.py').read_text()
        self.assertIn('balance_chart._points', probe)
        self.assertNotIn('dashboard.chart._activity', probe)

    def test_linux_gnu_stack_rw_required_rwe_denied(self):
        self.assertEqual(inspect_elf(bytes(elf(6)))['gnu_stack'], 'RW')
        with self.assertRaisesRegex(LinuxCoreError, 'GNU_STACK'):
            inspect_elf(bytes(elf(7)))
