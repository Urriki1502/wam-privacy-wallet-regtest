"""Disposable test keychains must not auto-lock mid-qualification.

Verified root cause: a fresh `security create-keychain` defaults to
lock-on-sleep timeout=300s; after >300 s idle, find-generic-password returned
status 128, which the anchor reports as VAULT_KEYCHAIN_READ_DENIED (the
intermittent frozen REOPEN ANCHOR failure). Fixtures only; the user's own
Keychain is never touched.
"""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DisposableKeychainFixtures(unittest.TestCase):
    def test_every_fixture_creator_disables_auto_lock(self):
        for relative in ('src/wam_regtest/q05_platforms.py', 'src/wam_regtest/wallet_probe.py',
                         'src/wam_regtest/security_probe.py', 'scripts/owner_acceptance.py',
                         'scripts/measure_q03_reuse.py'):
            text = (ROOT / relative).read_text()
            with self.subTest(file=relative):
                self.assertIn('create-keychain', text)
                self.assertIn('set-keychain-settings', text)
                self.assertGreater(text.index('set-keychain-settings'), text.index('create-keychain'))

    @unittest.skipUnless(sys.platform == 'darwin', 'native macOS keychain')
    def test_adapter_fixture_reports_no_timeout(self):
        from wam_regtest.q05_platforms import DarwinArm64Adapter
        with tempfile.TemporaryDirectory(prefix='kc-fixture-') as d:
            keychain = DarwinArm64Adapter().make_anchor(Path(d))
            try:
                info = subprocess.run(['/usr/bin/security', 'show-keychain-info', str(keychain)],
                                      capture_output=True, text=True, timeout=15)
                self.assertIn('no-timeout', info.stdout + info.stderr)
                self.assertNotIn('lock-on-sleep', info.stdout + info.stderr)
            finally:
                subprocess.run(['/usr/bin/security', 'delete-keychain', str(keychain)],
                               capture_output=True, timeout=15)


if __name__ == '__main__':
    unittest.main()
