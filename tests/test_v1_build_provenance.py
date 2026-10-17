"""Disposable Git fixtures only; not blockchain/frozen acceptance."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from wam_regtest.build_provenance import capture,verify,public_receipt,BuildSourceError


class BuildSourceContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='wam-build-source-test-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();(self.root/'src').mkdir()
        self.file=self.root/'src/module.py';self.file.write_text('VALUE=1\n')
        (self.root/'.gitignore').write_text('*.pyc\nignored.py\n__pycache__/\n')
        self.git('init','-q','--object-format=sha1');(self.root/'.git/no-hooks').mkdir();self.git('add','.');self.commit()
    def git(self,*args):
        return subprocess.check_output(['git','-C',str(self.root),*args],stderr=subprocess.DEVNULL)
    def commit(self):
        self.git('-c','commit.gpgsign=false','-c','core.hooksPath='+str(self.root/'.git/no-hooks'),'-c','user.name=Public fixture','-c','user.email=fixture@example.invalid','commit','-qm','public fixture')
    def test_clean_head_and_public_digest_have_no_host_paths(self):
        stamp=capture(self.root);verify(self.root,stamp);receipt=public_receipt(stamp)
        self.assertEqual(receipt['tracked_files'],2)
        self.assertEqual(receipt['checkout_sha'],self.git('rev-parse','HEAD').decode().strip())
        self.assertNotIn(str(self.root),str(receipt));self.assertNotIn('metadata',str(receipt))
    def test_declared_source_must_be_checkout_or_actual_merge_parent(self):
        snapshot=capture(self.root)
        with self.assertRaisesRegex(BuildSourceError,'^BUILD_SOURCE_HEAD_CHECKOUT_DENIED$'):
            public_receipt(snapshot,source_head='a'*40)
        # Supplemental metadata-only negatives, not a real build/chain claim.
        merge={**snapshot,'parents':['a'*40,'b'*40]}
        self.assertEqual(public_receipt(merge,source_head='a'*40)['source_head_sha'],'a'*40)
        for altered in ({**merge,'parents':['a'*40]},snapshot):
            with self.assertRaises(BuildSourceError):public_receipt(altered,source_head='a'*40)
        with self.assertRaises(BuildSourceError):public_receipt(merge,source_head='a'*40,dispatch=True)
    def test_uncommitted_or_assume_unchanged_source_never_claims_head(self):
        self.git('update-index','--assume-unchanged','src/module.py')
        self.file.write_text('VALUE=2\n')
        with self.assertRaisesRegex(BuildSourceError,'^BUILD_SOURCE_DIRTY$'):capture(self.root)
        self.assertEqual(self.file.read_text(),'VALUE=2\n')
    def test_staged_changes_and_changed_checkout_refuse(self):
        stamp=capture(self.root);self.file.write_text('VALUE=2\n');self.git('add','.')
        with self.assertRaises(BuildSourceError):capture(self.root)
        self.commit()
        with self.assertRaisesRegex(BuildSourceError,'^BUILD_SOURCE_CHANGED$'):verify(self.root,stamp)
    def test_ignored_extra_importable_modules_refused_without_deleting_them(self):
        for name in ('ignored.py','extra.PY','old.pyc','extension.so'):
            path=self.root/'src'/name;path.write_bytes(b'PUBLIC_EXTRA_MODULE')
            with self.assertRaisesRegex(BuildSourceError,'^BUILD_SOURCE_UNTRACKED_MODULE$'):capture(self.root)
            self.assertTrue(path.exists());path.unlink()
    @unittest.skipIf(os.name=='nt','native link privilege is not assumed; native build gate still checks reparse metadata')
    def test_source_links_refused_before_following_target(self):
        self.file.unlink();self.file.symlink_to(self.root/'.gitignore')
        with self.assertRaisesRegex(BuildSourceError,'^BUILD_SOURCE_FILE_DENIED$'):capture(self.root)
    def test_rewrite_to_original_bytes_is_still_detected_at_build_boundary(self):
        stamp=capture(self.root);raw=self.file.read_bytes()
        self.file.unlink();self.file.write_bytes(raw)
        # Native file identity/ctime is part of the private stamp.
        with self.assertRaisesRegex(BuildSourceError,'^BUILD_SOURCE_CHANGED$'):verify(self.root,stamp)
    def test_windows_text_checkout_can_normalize_but_original_pinned_cpp_cannot(self):
        from unittest.mock import patch
        pinned=self.root/'tests/source_contract/v0.1.11/example.cpp';pinned.parent.mkdir(parents=True)
        pinned.write_bytes(b'// PUBLIC_PINNED_SOURCE\n');self.git('add','.');self.commit()
        self.file.write_bytes(b'VALUE=1\r\n')
        with patch('wam_regtest.build_provenance.sys.platform','win32'):
            capture(self.root)
            pinned.write_bytes(b'// PUBLIC_PINNED_SOURCE\r\n')
            with self.assertRaisesRegex(BuildSourceError,'^BUILD_SOURCE_DIRTY$'):capture(self.root)
    @unittest.skipUnless(os.name=='nt','Windows native handle sharing contract')
    def test_windows_source_handle_denies_writer_during_read(self):
        from unittest.mock import patch
        from wam_regtest import windows_private_storage as native
        from wam_regtest.build_provenance import _windows_file
        read=native.readfile;attempts=[]
        def observed(*args):
            with self.assertRaises(PermissionError):
                with self.file.open('wb'):pass
            attempts.append(True)
            return read(*args)
        with patch.object(native,'readfile',side_effect=observed):raw,metadata=_windows_file(self.file)
        self.assertTrue(attempts);self.assertEqual(raw.replace(b'\r\n',b'\n'),b'VALUE=1\n')
