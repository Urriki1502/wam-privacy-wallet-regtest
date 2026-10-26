"""Refusal contracts for Q03 provenance import; no Core E2E is simulated."""
from hashlib import sha256
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/update_q03_ledger.py'


def module():
    spec=importlib.util.spec_from_file_location('q03_ledger_update',SCRIPT)
    value=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class Q03EvidenceImportContracts(unittest.TestCase):
    def setUp(self):self.update=module()

    def test_import_does_not_capture_arbitrary_git_head_or_modify_ledger(self):
        with patch('subprocess.check_output',side_effect=AssertionError('import side effect')):
            module()

    def test_zero_digest_and_tampered_zip_are_refused(self):
        raw=io.BytesIO()
        with zipfile.ZipFile(raw,'w') as z:z.writestr('public-test-receipt.json','{}')
        original=raw.getvalue()
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'artifact.zip';path.write_bytes(original)
            for claimed in ('0'*64,'a'*64):
                with self.subTest(claimed=claimed),self.assertRaises(ValueError):
                    self.update.archive(path,{'expired':False,'digest':'sha256:'+claimed})
            metadata={'expired':False,'digest':'sha256:'+sha256(original).hexdigest()}
            with self.update.archive(path,metadata)[0] as z:
                self.assertEqual(z.read('public-test-receipt.json'),b'{}')
            path.write_bytes(original+b'tampered')
            with self.assertRaises(ValueError):self.update.archive(path,metadata)

    def test_expired_or_missing_api_digest_cannot_promote(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'artifact.zip';path.write_bytes(b'public fixture')
            for metadata in ({'expired':True,'digest':'sha256:'+sha256(path.read_bytes()).hexdigest()},
                             {'expired':False},{}):
                with self.subTest(metadata=metadata),self.assertRaises(ValueError):
                    self.update.archive(path,metadata)

    def test_cross_platform_core_and_official_signed_linux_are_refused(self):
        with self.assertRaises(ValueError):
            self.update.check_pins('windows-x64',self.update.PINS['macos-arm64'],'official-signed-v0.1.11')
        with self.assertRaises(ValueError):
            self.update.check_pins('linux-x86_64',self.update.PINS['linux-x86_64'],'official-signed-v0.1.11')
        self.update.check_pins('linux-x86_64',self.update.PINS['linux-x86_64'],'reviewed-developer-source-build')

    def test_cli_hash_socket_or_missing_measurement_cannot_claim_reuse(self):
        delta={key:0 for key in self.update.ZERO_COUNTERS};delta['http_request']=55
        self.update.check_reuse({'cycles':5,'delta':delta})
        for key in self.update.ZERO_COUNTERS:
            bad=dict(delta);bad[key]=1
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.update.check_reuse({'cycles':5,'delta':bad})
        delta.pop('http_socket_connect')
        with self.assertRaises(ValueError):self.update.check_reuse({'cycles':5,'delta':delta})
