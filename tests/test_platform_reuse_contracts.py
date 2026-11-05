"""Existing OS ports must stay the V2.2 freeze path. No native Win/Linux claim."""
from pathlib import Path
import unittest

from wam_regtest.linux_developer_core import inspect_elf, LinuxCoreError
from wam_regtest.q05_platforms import DarwinArm64Adapter, LinuxX64Adapter, WindowsX64Adapter
from wam_regtest.windows_release_preflight import BINARY_SHA256, ARCHIVE_SHA256

from tests.test_linux_developer_core import elf

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
        self.assertIn(r'(?:CORE|WIN|WALLET|WSP|Q04|Q06)_', windows)

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
        self.assertFalse(LinuxX64Adapter.official_signed)
        self.assertEqual(LinuxX64Adapter.core_trust, 'qualified-developer-core-reviewed-manifest')
        self.assertEqual(ARCHIVE_SHA256, 'ece622fa7ec3072c4e8b0d32e2c3749397d66260f2b0cf22b3636346873d15c5')
        self.assertEqual(BINARY_SHA256['wamd.exe'],
                         '31717319535c5b784b2bed3b4d3c9a727f5c062e9534b4d27c59d2ffd04e95a1')
        self.assertEqual(BINARY_SHA256['wam-cli.exe'],
                         '538a6d1b918b698ce76a949dda982fdda6776e33ba057efaac59b1af59e59d21')

    def test_linux_gnu_stack_rw_required_rwe_denied(self):
        self.assertEqual(inspect_elf(bytes(elf(6)))['gnu_stack'], 'RW')
        with self.assertRaisesRegex(LinuxCoreError, 'GNU_STACK'):
            inspect_elf(bytes(elf(7)))
