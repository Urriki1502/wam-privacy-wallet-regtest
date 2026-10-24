"""Actual Win32 ACL/owner/reparse/atomic publication; not real-Core E2E."""
from pathlib import Path
import os,secrets,subprocess,sys,tempfile,unittest
from wam_regtest import windows_private_storage as store

@unittest.skipUnless(sys.platform=='win32','Native Win64 custody only')
class NativeWindowsCustodyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='wam-win-custody-');self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.private=self.base/'private'
        store.create_private_directory(self.private)
        self.blob=b'WAMSP02\x00'+secrets.token_bytes(80)
    def test_owner_only_directory_and_create_only_ciphertext(self):
        store.validate_directory(self.private);store.publish(self.private,'test.enc',self.blob)
        self.assertEqual(store.read(self.private,'test.enc'),self.blob)
        with self.assertRaises(store.WindowsCustodyError):store.publish(self.private,'test.enc',self.blob)
        self.assertEqual(store.read(self.private,'test.enc'),self.blob)
        self.assertFalse(list(self.private.glob('.stage-*')))
    def test_default_public_inherited_directory_rejected_without_repair(self):
        with self.assertRaises(store.WindowsCustodyError):store.validate_directory(self.base)
    def test_junction_and_hardlink_denied(self):
        target=self.private/'real';store.create_private_directory(target)
        link=self.private/'junction'
        p=subprocess.run(['cmd','/c','mklink','/J',str(link),str(target)],capture_output=True)
        self.assertEqual(p.returncode,0)
        self.addCleanup(lambda:os.rmdir(link) if link.exists() else None)
        with self.assertRaises(store.WindowsCustodyError):store.validate_directory(link)
        with self.assertRaises(store.WindowsCustodyError):store.create_private_directory(link/'child')
        store.publish(self.private,'test.enc',self.blob)
        os.link(self.private/'test.enc',self.private/'alias.enc')
        with self.assertRaises(store.WindowsCustodyError):store.read(self.private,'test.enc')
    def test_world_acl_and_wrong_owner_denied(self):
        import ctypes
        for suffix,descriptor in (('world','O:'+store.owner_sid()+'D:P(A;OICI;FA;;;WD)'),
                                  ('wrong-owner','O:BAD:P(A;OICI;FA;;;'+store.owner_sid()+')')):
            path=self.base/suffix
            with store.security_attributes(directory=True,descriptor=descriptor) as sa:
                self.assertTrue(store.mkdir(str(path),sa))
            with self.assertRaises(store.WindowsCustodyError):store.validate_directory(path)
    def test_ancestor_and_private_directory_cannot_be_renamed_while_pinned(self):
        moved=self.base/'moved'
        with store.directory_guard(self.private):
            with self.assertRaises(OSError):os.rename(self.private,moved)
            with self.assertRaises(OSError):os.rename(self.base,self.base.with_name(self.base.name+'-moved'))
        os.rename(self.private,moved);os.rename(moved,self.private)
        store.validate_directory(self.private)
    def test_bad_names_and_envelopes_never_publish(self):
        for name in ('../escape.enc','con.enc','test.enc:stream','UPPER.enc','a.enc '):
            with self.assertRaises(store.WindowsCustodyError):store.publish(self.private,name,self.blob)
        for blob in (b'',b'not-a-ciphertext'*5):
            with self.assertRaises(store.WindowsCustodyError):store.publish(self.private,'bad.enc',blob)
    def test_spawned_reader_reopens_same_bytes(self):
        store.publish(self.private,'test.enc',self.blob)
        code='from pathlib import Path;import sys,hashlib;from wam_regtest.windows_private_storage import read;print(hashlib.sha256(read(Path(sys.argv[1]),"test.enc")).hexdigest())'
        p=subprocess.run([sys.executable,'-c',code,str(self.private)],capture_output=True,text=True,timeout=15)
        import hashlib
        self.assertEqual(p.returncode,0);self.assertEqual(p.stdout.strip(),hashlib.sha256(self.blob).hexdigest())

    def test_terminated_writer_leaves_only_unpublished_ciphertext(self):
        import time
        store.publish(self.private,'test.enc',self.blob)
        code = """
from pathlib import Path
import ctypes,time,sys
from wam_regtest import windows_private_storage as s
root=Path(sys.argv[1])
with s.directory_guard(root),s.security_attributes() as sa:
    h=s.create(str(root/'.stage-interrupted'),0xc0030000,1,sa,1,0x80200080,None)
    assert h not in (None,s.INVALID)
    blob=b'WAMSP02\\x00'+b'c'*80
    buf=ctypes.create_string_buffer(blob);count=s.w.DWORD()
    assert s.write(h,buf,len(blob),ctypes.byref(count),None) and count.value==len(blob)
    assert s.flush(h)
    s.publish(root,'ready.enc',blob)
    time.sleep(60)
"""
        p=subprocess.Popen([sys.executable,'-c',code,str(self.private)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            deadline=time.monotonic()+10
            while not (self.private/'ready.enc').exists() and p.poll() is None and time.monotonic()<deadline:
                time.sleep(.05)
            self.assertTrue((self.private/'ready.enc').exists(),'native writer did not reach flushed pre-publication phase')
            p.kill();p.wait(timeout=5)
            self.assertFalse((self.private/'snapshot-000000002.enc').exists())
            self.assertEqual(store.read(self.private,'test.enc'),self.blob)
            self.assertTrue((self.private/'.stage-interrupted').exists())
            with self.assertRaises(store.WindowsCustodyError):store.publish(self.private,'test.enc',self.blob)
            self.assertEqual(store.read(self.private,'test.enc'),self.blob)
        finally:
            if p.poll() is None:p.kill()
            p.wait(timeout=5)

class WindowsCustodyHostScope(unittest.TestCase):
    def test_native_scope_not_simulated_on_other_hosts(self):
        if sys.platform!='win32':
            with self.assertRaisesRegex(store.WindowsCustodyError,'WIN_CUSTODY_NATIVE_X64_REQUIRED'):
                store.create_private_directory(Path('/not-a-windows-datadir'))
        else:store.require_native()
