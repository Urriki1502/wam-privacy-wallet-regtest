"""K-09 native read-only stage evidence contracts with disposable ciphertext.

Linux/macOS run OS descriptor, owner/mode, ACL, and POSIX link verification.
Windows native positive NTFS DACL/handle qualification remains a separate
workflow and independent acceptance gate; never substitute POSIX fixtures.
"""
import os
from pathlib import Path
import sys
import tempfile
import unittest

from wam_sp.keystore import seal
from wam_regtest import custody


class K09NativeResidueReader(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="k09-stage-native-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.vault=self.root/"vault"
        if sys.platform in ("darwin","linux"):
            self.vault.mkdir(mode=0o700)
        self.storage=custody.storage()
        self.payload=seal(
            b"PUBLIC_DISPOSABLE_REGTEST_FORENSIC_STAGE",
            b"PUBLIC_16_BYTE_PASSWORD",b"recovery"
        )

    def create(self,name,raw=None):
        target=self.vault/name
        fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        try:
            data=self.payload if raw is None else raw
            while data:
                n=os.write(fd,data)
                if n<=0:raise OSError
                data=data[n:]
            os.fsync(fd)
        finally:
            os.close(fd)
        return target

    def test_reject_malformed_residue_names_before_native_io(self):
        for name in ("bad.enc",".stage-X","snapshot-123.enc",
                     "../snapshot-000000004.enc","snapshot-000000004.enc.tmp"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    self.storage.read_crash_residue(self.vault,name)

    @unittest.skipIf(sys.platform=="win32",
                     "Windows needs separately provisioned native NTFS owner-only DACL")
    def test_native_read_full_stage_does_not_unlock_or_delete(self):
        stage=self.create(".stage-"+"a"*32)
        result=self.storage.read_crash_residue(self.vault,stage.name)
        self.assertEqual(result,self.payload)
        self.assertEqual(stage.read_bytes(),self.payload)
        self.assertEqual(len(list(self.vault.iterdir())),1)
        with self.assertRaises(ValueError):
            self.storage.read(self.vault,stage.name)

    @unittest.skipIf(sys.platform=="win32",
                     "Windows publication uses rename not POSIX hardlink")
    def test_native_read_link_unlink_window_without_weakening_normal_reader(self):
        stage=self.create(".stage-"+"b"*32)
        snapshot=self.vault/"snapshot-000000004.enc"
        try:
            snapshot.hardlink_to(stage)
        except (OSError,NotImplementedError):
            self.skipTest("filesystem does not support POSIX hardlinks")
        self.assertEqual(stage.stat().st_nlink,2)
        self.assertEqual(self.storage.read_crash_residue(self.vault,stage.name),
                         self.payload)
        self.assertEqual(self.storage.read_crash_residue(self.vault,snapshot.name),
                         self.payload)
        with self.assertRaises(ValueError):
            self.storage.read(self.vault,snapshot.name)
        self.assertTrue(stage.exists())
        self.assertTrue(snapshot.exists())

    @unittest.skipIf(sys.platform=="win32",
                     "Windows ACL/handle negative testing uses dedicated native gate")
    def test_symlink_torn_stage_and_permissions_fail_closed(self):
        stage=self.create(".stage-"+"c"*32,b"WAMSP02\x00INCOMPLETE")
        with self.assertRaises(ValueError):
            self.storage.read_crash_residue(self.vault,stage.name)
        stage.unlink()
        source=self.create("snapshot-000000004.enc")
        stage.symlink_to(source)
        with self.assertRaises(ValueError):
            self.storage.read_crash_residue(self.vault,stage.name)
        stage.unlink()
        mode=self.create(".stage-"+"d"*32)
        mode.chmod(0o644)
        with self.assertRaises(ValueError):
            self.storage.read_crash_residue(self.vault,mode.name)
        self.assertEqual(source.read_bytes(),self.payload)


if __name__=="__main__":
    unittest.main()
