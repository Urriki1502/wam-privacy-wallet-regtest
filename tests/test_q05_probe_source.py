"""Literal runtime bytes cannot be waived by CI artifact/index status."""
from hashlib import sha1
from pathlib import Path
import tempfile
import unittest

from wam_regtest.probe_source import verify_python_tree,ProbeSourceError


class NativeProbeSourceContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.file=self.root/'src/wam_regtest/test.py'
        self.file.parent.mkdir(parents=True);self.file.write_bytes(b'value = 1\n')
        raw=self.file.read_bytes()
        self.tree={'src/wam_regtest/test.py':sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()}

    def test_exact_source_and_non_code_artifacts_are_distinct(self):
        (self.root/'public-receipt.json').write_text('{}')
        digests,normalized=verify_python_tree(self.root,self.tree,self.tree)
        self.assertEqual(len(digests),1);self.assertFalse(normalized)

    def test_tracked_byte_change_cannot_hide_behind_clean_index_status(self):
        self.file.write_bytes(b'value = 2\n')
        with self.assertRaisesRegex(ProbeSourceError,'LITERAL_SOURCE_BYTES_DENIED'):
            verify_python_tree(self.root,self.tree,self.tree)

    def test_untracked_python_and_different_candidate_checkout_are_denied(self):
        extra=self.file.with_name('untracked.py');extra.write_bytes(b'value = 1\n')
        with self.assertRaises(ProbeSourceError):verify_python_tree(self.root,self.tree,self.tree)
        extra.unlink()
        with self.assertRaisesRegex(ProbeSourceError,'CANDIDATE_CHECKOUT_PYTHON_DIFFERS'):
            verify_python_tree(self.root,self.tree,{**self.tree,'scripts/other.py':'a'*40})

    def test_python_crlf_records_raw_digest_but_other_byte_changes_refuse(self):
        self.file.write_bytes(b'value = 1\r\n')
        _,normalized=verify_python_tree(self.root,self.tree,self.tree)
        self.assertTrue(normalized)
        self.file.write_bytes(b'value = 9\r\n')
        with self.assertRaises(ProbeSourceError):verify_python_tree(self.root,self.tree,self.tree)
