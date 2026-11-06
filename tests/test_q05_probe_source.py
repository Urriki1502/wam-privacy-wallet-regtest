"""Literal runtime bytes cannot be waived by CI artifact/index status."""
from hashlib import sha1
from pathlib import Path
import tempfile
import unittest
import os

from wam_regtest.probe_source import verify_python_tree,ProbeSourceError,local_audit_documents


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

    def test_retained_owner_audit_is_hashed_without_staging_or_changing_it(self):
        name='docs/INDEPENDENT_RC_AUDIT_56ea3618.md'
        path=self.root/name;path.parent.mkdir();path.write_bytes(b'public retained audit\n')
        before=path.stat()
        from hashlib import sha256
        self.assertEqual(local_audit_documents(self.root,b'?? '+name.encode()+b'\n'),
                         {name:sha256(path.read_bytes()).hexdigest()})
        self.assertEqual(path.stat(),before)

    def test_untracked_code_unknown_docs_and_tracked_edits_still_refuse(self):
        for status in (b'?? src/extra.py\n',b'?? docs/unknown.md\n',
                       b' M src/wam_regtest/test.py\n',b'A  scripts/other.py\n'):
            with self.assertRaisesRegex(ProbeSourceError,'CLEAN_SOURCE_REQUIRED'):
                local_audit_documents(self.root,status)

    def test_named_owner_security_instructions_are_hashed_as_non_runtime(self):
        from hashlib import sha256
        names = (
            'docs/security-audit/WAM_Fusion_PreMainnet_Security_Audit_Charter_2026-11-06.md',
            'docs/security-audit/WAM_Fusion_Security_Remediation_Design_Review_2026-11-06.md')
        expected = {}
        for name in names:
            path = self.root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'public owner instructions\n')
            expected[name] = sha256(path.read_bytes()).hexdigest()
        status = b''.join(b'?? '+name.encode()+b'\n' for name in names)
        self.assertEqual(local_audit_documents(self.root, status), expected)
        for name in names:
            self.assertEqual((self.root/name).read_bytes(), b'public owner instructions\n')

    @unittest.skipIf(os.name=='nt','POSIX metadata; native Windows reparse/custody has separate contracts')
    def test_retained_audit_cannot_be_executable_symlink_or_hardlink(self):
        name='docs/INDEPENDENT_RC_AUDIT_56ea3618.md'
        path=self.root/name;path.parent.mkdir();path.write_bytes(b'audit\n')
        status=b'?? '+name.encode()+b'\n'
        path.chmod(0o700)
        with self.assertRaises(ProbeSourceError):local_audit_documents(self.root,status)
        path.chmod(0o600)
        link=path.with_name('second');os.link(path,link)
        with self.assertRaises(ProbeSourceError):local_audit_documents(self.root,status)
        link.unlink();path.unlink();path.symlink_to(self.file)
        with self.assertRaises(ProbeSourceError):local_audit_documents(self.root,status)
