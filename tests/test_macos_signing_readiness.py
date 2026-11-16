"""Workstream 5: Developer ID signing/notarization readiness (no credentials used).

Preflight must refuse: the qualification identity, a receipt not bound to the
exact executable, a missing Developer ID identity, and notarization while the
pinned official Core is only ad-hoc signed (re-signing would break its pins).
"""
import importlib.util
import json
from pathlib import Path
import plistlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / 'bundle-input/post-phase5-unified-remediation-20261108/final-1aa21e2/qualification/build'


def _load():
    spec = importlib.util.spec_from_file_location('sign_release', ROOT / 'scripts/sign_macos_release.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SigningPolicy(unittest.TestCase):
    def test_production_entitlements_grant_no_runtime_exception(self):
        data = plistlib.loads((ROOT / 'assets/macos-hardened-runtime.entitlements').read_bytes())
        self.assertEqual(data, {})

    def test_core_is_never_resigned_and_dry_run_waiver_is_dry_run_only(self):
        text = (ROOT / 'scripts/sign_macos_release.py').read_text()
        self.assertIn('set(cores.values())', text)  # Core excluded from nested signing
        self.assertIn('CORE_PIN_CONFLICT_PUBLISHER_DEVELOPER_ID_REQUIRED', text)
        self.assertIn("if dry_run:\n        # Ad-hoc code has no Team ID", text)


@unittest.skipUnless(sys.platform == 'darwin' and REAL.is_dir(), 'needs the real local production build')
class SigningPreflight(unittest.TestCase):
    def setUp(self):
        self.s = _load()
        self.app = REAL / 'dist' / self.s.APP_NAME
        self.receipt = REAL / 'package-output/PRODUCTION_BUILD_RECEIPT.json'

    def _denied(self, code, **kw):
        args = dict(app=self.app, receipt=self.receipt, identity='Developer ID Application: X (TEAMID1234)',
                    dry_run=False, notarize=True, profile='wam-notary')
        args.update(kw)
        with self.assertRaises(SystemExit) as caught:
            self.s.preflight(args['app'], args['receipt'], args['identity'], args['dry_run'],
                             args['notarize'], args['profile'])
        self.assertEqual(str(caught.exception), 'MACOS_SIGNING_' + code + '_DENIED')

    def test_qualification_identity_is_refused(self):
        qual = REAL / 'qualification-only/dist/WAM Privacy Wallet REGTEST QUALIFICATION.app'
        self._denied('APP_SHAPE', app=qual)

    def test_receipt_must_bind_the_exact_executable(self):
        with tempfile.TemporaryDirectory() as d:
            data = json.loads(self.receipt.read_text())
            data['executable_sha256'] = '0' * 64
            bad = Path(d) / 'r.json'
            bad.write_text(json.dumps(data))
            self._denied('RECEIPT_BINDING', receipt=bad)

    def test_missing_developer_id_identity_is_blocked(self):
        with mock.patch.object(self.s, 'codesigning_identities', return_value=[]):
            self._denied('DEVELOPER_ID_IDENTITY_UNAVAILABLE')

    def test_notarization_blocked_while_core_is_adhoc(self):
        fake = [('A' * 40, 'Developer ID Application: X (TEAMID1234)')]
        with mock.patch.object(self.s, 'codesigning_identities', return_value=fake):
            self._denied('CORE_PIN_CONFLICT_PUBLISHER_DEVELOPER_ID_REQUIRED')
            facts, cores = self.s.preflight(self.app, self.receipt, fake[0][1], False, False, None)
        self.assertEqual(facts['core_developer_id_runtime'], {'wamd': False, 'wam-cli': False})

    def test_dry_run_scope(self):
        self._denied('DRY_RUN_SCOPE', identity='-', dry_run=True, notarize=True)


if __name__ == '__main__':
    unittest.main()
