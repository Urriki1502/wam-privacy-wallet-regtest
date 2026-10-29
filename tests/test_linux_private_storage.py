"""Native Linux custody contracts, supplementary to genuine wallet E2E."""
import os
from pathlib import Path
import platform
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from wam_regtest import linux_private_storage as store


@unittest.skipUnless(sys.platform=='linux' and platform.machine()=='x86_64','native Linux custody only')
class LinuxCustodyContracts(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='wam-linux-custody-')
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name).resolve();self.root.chmod(0o700)
        from wam_sp.keystore import seal
        self.password=b'public-regtest-custody-passphrase'
        self.ciphertext=seal(b'public test payload',self.password,b'recovery')
    def test_actual_wsp_envelope_unique_and_authenticated(self):
        from wam_sp.keystore import seal,unseal
        second=seal(b'public test payload',self.password,b'recovery')
        self.assertNotEqual(second[8:24],self.ciphertext[8:24])
        self.assertNotEqual(second[24:36],self.ciphertext[24:36])
        store.publish(self.root,'backup.enc',self.ciphertext)
        raw=store.read(self.root,'backup.enc')
        self.assertEqual(unseal(raw,self.password,b'recovery'),b'public test payload')
        for password,purpose in ((b'wrong-test-password',b'recovery'),(self.password,b'keys')):
            with self.assertRaises(ValueError):unseal(raw,password,purpose)
    def test_create_only_and_private_modes(self):
        child=self.root/'vault';store.create_private_directory(child)
        self.assertEqual(child.stat().st_mode&0o777,0o700)
        store.publish(child,'snapshot.enc',self.ciphertext)
        self.assertEqual((child/'snapshot.enc').stat().st_mode&0o777,0o600)
        with self.assertRaises(store.LinuxStorageError):store.publish(child,'snapshot.enc',self.ciphertext)
        with self.assertRaises(store.LinuxStorageError):store.create_private_directory(child)
        self.assertEqual(store.read(child,'snapshot.enc'),self.ciphertext)
        self.assertEqual(sorted(p.name for p in child.iterdir()),['snapshot.enc'])
    def test_symlink_ancestor_and_final_denied(self):
        child=self.root/'vault';store.create_private_directory(child)
        (self.root/'alias').symlink_to(child,target_is_directory=True)
        with self.assertRaises(store.LinuxStorageError):store.validate_directory(self.root/'alias')
        (child/'deeper').mkdir(mode=0o700)
        with self.assertRaises(store.LinuxStorageError):store.validate_directory(self.root/'alias/deeper')
        store.publish(child,'original.enc',self.ciphertext)
        (child/'linked.enc').symlink_to(child/'original.enc')
        with self.assertRaises(store.LinuxStorageError):store.read(child,'linked.enc')
    def test_hardlink_fifo_and_unsafe_mode_denied(self):
        store.publish(self.root,'original.enc',self.ciphertext)
        os.link(self.root/'original.enc',self.root/'linked.enc')
        with self.assertRaises(store.LinuxStorageError):store.read(self.root,'original.enc')
        os.mkfifo(self.root/'fifo.enc',0o600)
        with self.assertRaises(store.LinuxStorageError):store.read(self.root,'fifo.enc')
        self.root.chmod(0o750)
        with self.assertRaises(store.LinuxStorageError):store.validate_directory(self.root)
        self.root.chmod(0o700)
    def test_actual_default_acl_denied_without_permission_repair(self):
        # POSIX ACL creation is an actual kernel operation on our disposable dir.
        result=subprocess.run(['setfacl','-m','d:u:65534:r-x',str(self.root)],capture_output=True)
        self.assertEqual(result.returncode,0)
        with self.assertRaises(store.LinuxStorageError):store.validate_directory(self.root)
        self.assertIn('system.posix_acl_default',os.listxattr(self.root))
    def test_os_lease_same_wallet_across_objects_and_processes(self):
        lease=store.LinuxWalletLease(self.root,'a'*32)
        with lease.hold(),lease.hold():
            with self.assertRaises(store.LinuxStorageError):
                with store.LinuxWalletLease(self.root,'a'*32).hold():pass
            code="from pathlib import Path;from wam_regtest.linux_private_storage import LinuxWalletLease;import sys\ntry:\n with LinuxWalletLease(Path(sys.argv[1]),'a'*32).hold():pass\nexcept ValueError:sys.exit(73)"
            result=subprocess.run([sys.executable,'-c',code,str(self.root)],capture_output=True,timeout=10)
            self.assertEqual(result.returncode,73)
        with store.LinuxWalletLease(self.root,'a'*32).hold():pass
    def test_killed_process_releases_native_lease(self):
        code="from pathlib import Path;from wam_regtest.linux_private_storage import LinuxWalletLease;import sys,time\nwith LinuxWalletLease(Path(sys.argv[1]),'b'*32).hold():\n print('HELD',flush=True);time.sleep(30)"
        child=subprocess.Popen([sys.executable,'-c',code,str(self.root)],stdout=subprocess.PIPE,text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(),'HELD')
            with self.assertRaises(store.LinuxStorageError):
                with store.LinuxWalletLease(self.root,'b'*32).hold():pass
        finally:
            child.kill();child.wait(timeout=10);child.stdout.close()
        with store.LinuxWalletLease(self.root,'b'*32).hold():pass
    def test_failed_publication_cleanup_and_conservative_final_file(self):
        actual=os.fsync;calls=[]
        def fail_directory(fd):
            calls.append(fd)
            if len(calls)==2:raise OSError('supplementary fault injection')
            return actual(fd)
        with patch.object(os,'fsync',side_effect=fail_directory):
            with self.assertRaises(store.LinuxStorageError):store.publish(self.root,'ambiguous.enc',self.ciphertext)
        self.assertEqual(store.read(self.root,'ambiguous.enc'),self.ciphertext)
        with self.assertRaises(store.LinuxStorageError):store.publish(self.root,'ambiguous.enc',self.ciphertext)
        self.assertFalse(any(p.name.startswith('.stage-') for p in self.root.iterdir()))
    def test_no_software_only_spending_anchor(self):
        with self.assertRaisesRegex(store.LinuxStorageError,'ANTI_ROLLBACK'):
            store.require_trusted_anchor_for_spending()
        from wam_regtest import custody
        with self.assertRaises(ValueError):custody.storage()


class LinuxDirectoryStability(unittest.TestCase):
    @unittest.skipUnless(sys.platform=='linux' and platform.machine()=='x86_64','native Linux custody only')
    def test_child_metadata_is_not_replacement_and_mode_change_is(self):
        temporary=tempfile.TemporaryDirectory(prefix='wam-linux-dir-stability-')
        self.addCleanup(temporary.cleanup)
        root=Path(temporary.name).resolve()
        root.chmod(0o700)
        child=root/'churn'
        store.create_private_directory(child)
        fd=os.open(child,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
        self.addCleanup(os.close,fd)
        real=os.fstat
        state={'n':0,'mode':None}
        def fstat(target):
            info=real(target)
            state['n']+=1
            mode=info.st_mode if state['mode'] is None or state['n']==1 else state['mode']
            return SimpleNamespace(st_dev=info.st_dev,st_ino=info.st_ino,st_mode=mode,
                st_uid=info.st_uid,st_gid=info.st_gid,
                st_nlink=info.st_nlink+(0 if state['n']==1 else 1),
                st_size=info.st_size,
                st_mtime_ns=info.st_mtime_ns+(0 if state['n']==1 else 1),
                st_ctime_ns=info.st_ctime_ns+(0 if state['n']==1 else 1))
        with patch('wam_regtest.linux_private_storage.os.fstat',fstat):
            store._validate_directory_fd(fd)
            state['n']=0
            state['mode']=stat.S_IFDIR|0o750
            with self.assertRaisesRegex(store.LinuxStorageError,'LINUX_PRIVATE_DIRECTORY_CHANGED'):
                store._validate_directory_fd(fd)


class ForeignLinuxCustody(unittest.TestCase):
    @unittest.skipIf(sys.platform=='linux','foreign-platform guard only')
    def test_foreign_platform_denied(self):
        with self.assertRaises(store.LinuxStorageError):store.require_native()
