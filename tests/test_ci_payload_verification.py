"""CDX-AUD-008: the macOS CI gate must open the actual payloads.

Positive: the REAL Phase 5 exact-HEAD build output (5fee594), if present in
this workspace's git-ignored evidence (skipped otherwise, e.g. hosted CI).
Negative: APFS clones of that real output, mutated into self-consistent but
payload-contradicted fixtures (every self-declared hash/sum recomputed).
No production_qualified promotion; nothing here dispatches CI.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / 'bundle-input/phase5-20261108/final-5fee594/qualification/build'
REAL_SHA = '5fee5948f457b708a7bce0f9cce95bfa1078d7c6'


def _load():
    spec = importlib.util.spec_from_file_location(
        'cdx008_verifier', ROOT / 'scripts/verify_macos_ci_outputs.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@unittest.skipUnless(sys.platform == 'darwin' and REAL.is_dir(),
                     'needs the real exact-HEAD macOS build output (local evidence)')
class CiPayloadVerification(unittest.TestCase):
    def setUp(self):
        self.v = _load()
        temp = tempfile.TemporaryDirectory(prefix='cdx008-', dir=ROOT / 'bundle-input'
                                           / 'post-phase5-unified-remediation-20261108' / 'temp')
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name)

    def _clone(self):
        target = self.tmp / 'build'
        subprocess.run(['cp', '-cR', str(REAL), str(target)], check=True)
        return target

    def _reseal(self, build, *, receipt=None):
        """Recompute every self-declared hash so the binding stage passes."""
        prod = build / 'package-output'
        path = prod / 'PRODUCTION_BUILD_RECEIPT.json'
        data = json.loads(path.read_text())
        data['files_sha256'] = {n: _sha(prod / n) for n in self.v.PRODUCTION_FILES}
        data['executable_sha256'] = _sha(build / 'dist' / self.v.PRODUCTION_APP / 'Contents/MacOS'
                                         / self.v.PRODUCTION_APP.removesuffix('.app'))
        if receipt is not None:
            receipt(data)
        path.write_text(json.dumps(data))
        (prod / 'SHA256SUMS.txt').write_bytes(''.join(
            f'{_sha(p)}  {p.name}\n' for p in sorted(prod.iterdir())
            if p.is_file() and p.name != 'SHA256SUMS.txt').encode())

    def _denied(self, build, code):
        publish = self.tmp / 'publish'
        with self.assertRaises(ValueError) as caught:
            self.v.verify(build, REAL_SHA, publish)
        self.assertEqual(caught.exception.args, ('MACOS_CI_OUTPUT_' + code + '_DENIED',))
        self.assertFalse(publish.exists())
        self.assertFalse(publish.with_name('publish.staging').exists())

    def test_real_exact_head_artifact_passes_payload_verification(self):
        publish = self.tmp / 'publish'
        binding = self.v.verify(REAL, REAL_SHA, publish)
        payload = binding['payload_verification']
        self.assertEqual(payload['status'], 'PASS_ACTUAL_PAYLOAD_AGREES_WITH_RECEIPTS')
        self.assertEqual(payload['pyz_modules'], 74)
        self.assertEqual(payload['developer_argv_executed'], len(self.v._packaging().DEVELOPER_ARGV))
        self.assertFalse(binding['production_qualified'])
        self.assertEqual(binding['production']['executable_sha256'],
                         '2d55711d1f250f1b02d78656f34b100707237729e6eedc66c39b3360126530c4')
        published = {p.name for p in (publish / 'production').iterdir()}
        self.assertFalse(published & set(self.v.QUALIFICATION_FILES))

    def test_plain_text_executable_with_consistent_receipts_is_denied(self):
        build = self._clone()
        exe = build / 'dist' / self.v.PRODUCTION_APP / 'Contents/MacOS' / 'WAM Privacy Wallet REGTEST'
        exe.unlink()
        exe.write_bytes(b'#!/bin/sh\nexit 64\n')
        self._reseal(build)
        self._denied(build, 'PAYLOAD_PYZ_AUDIT')

    def test_non_archive_zip_with_consistent_hashes_is_denied(self):
        build = self._clone()
        zip_path = build / 'package-output' / self.v.PRODUCTION_FILES[1]
        zip_path.unlink()
        zip_path.write_bytes(b'not a zip archive')
        self._reseal(build)
        self._denied(build, 'PAYLOAD_ZIP_SHAPE')

    def test_non_image_dmg_with_consistent_hashes_is_denied(self):
        build = self._clone()
        dmg = build / 'package-output' / self.v.PRODUCTION_FILES[0]
        dmg.unlink()
        dmg.write_bytes(b'not a disk image')
        self._reseal(build)
        self._denied(build, 'PAYLOAD_DMG_SHAPE')

    def test_inventory_claim_contradicting_actual_pyz_is_denied(self):
        for name, mutate in (
                ('missing-module-list', lambda d: d.pop('modules')),
                ('one-module-removed', lambda d: d['modules'].pop()),
                ('extra-module', lambda d: d['modules'].append('cli'))):
            with self.subTest(case=name):
                build = self._clone()
                path = build / 'package-output/PRODUCTION_MODULE_INVENTORY.json'
                data = json.loads(path.read_text())
                mutate(data)
                path.write_text(json.dumps(data))
                self._reseal(build)
                self._denied(build, 'PAYLOAD_INVENTORY_MISMATCH')
                shutil.rmtree(build)

    def test_dispatch_receipt_outside_reviewed_policy_is_denied(self):
        build = self._clone()
        path = build / 'package-output/PRODUCTION_DISPATCH_NEGATIVES.json'
        path.write_text(json.dumps([dict(mode='--not-a-reviewed-argv', returncode=64)]))
        self._reseal(build)
        self._denied(build, 'PAYLOAD_DISPATCH_RECEIPT')

    def test_missing_executable_binding_is_denied(self):
        build = self._clone()
        self._reseal(build, receipt=lambda d: d.pop('executable_sha256'))
        self._denied(build, 'PRODUCTION_EXECUTABLE')

    def test_core_bytes_differing_from_pin_are_denied(self):
        build = self._clone()
        wamd = build / 'dist' / self.v.PRODUCTION_APP / 'Contents/Resources/core/wamd'
        data = bytearray(wamd.read_bytes())
        data[-1] ^= 1
        wamd.unlink()
        wamd.write_bytes(bytes(data))
        self._reseal(build)
        self._denied(build, 'PAYLOAD_CORE_PIN')

    def test_wsp_manifest_naming_another_commit_is_denied(self):
        build = self._clone()
        manifest = (build / 'dist' / self.v.PRODUCTION_APP
                    / 'Contents/Resources/wsp-source/SOURCE_SHA256.json')
        data = json.loads(manifest.read_text())
        data['source_commit'] = 'b' * 40
        manifest.unlink()
        manifest.write_text(json.dumps(data))
        self._reseal(build)
        self._denied(build, 'PAYLOAD_WSP_PIN')

    def test_production_zip_holding_the_qualification_app_is_denied(self):
        import zipfile
        build = self._clone()
        zip_path = build / 'package-output' / self.v.PRODUCTION_FILES[1]
        with zipfile.ZipFile(zip_path, 'a') as archive:
            archive.writestr(self.v.QUALIFICATION_APP + '/Contents/Info.plist', b'public')
        self._reseal(build)
        self._denied(build, 'PAYLOAD_ZIP_MEMBER')

if __name__ == '__main__':
    unittest.main()
