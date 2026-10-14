"""Native filesystem security contracts; distinct from real-Core E2E."""
import os
from pathlib import Path
import tempfile
import unittest
from wam_regtest.encrypted_storage import publish, read, EncryptedStorageError
from wam_regtest.private_directory import MacosPrivateDirectoryError
from wam_regtest.core import smoke_real_core, CoreSmokeError


class NativeEncryptedStorageContracts(unittest.TestCase):
    def test_create_only_and_private_regular_file(self):
        with tempfile.TemporaryDirectory() as t:
            directory=Path(t).resolve()
            envelope=b"WAMSP02\x00"+bytes(64)
            publish(directory,"test.enc",envelope)
            self.assertEqual(read(directory,"test.enc"),envelope)
            self.assertEqual((directory/"test.enc").stat().st_mode & 0o777,0o600)
            with self.assertRaises(EncryptedStorageError):
                publish(directory,"test.enc",envelope)
            self.assertEqual(read(directory,"test.enc"),envelope)
            os.chmod(directory/"test.enc",0o640)
            with self.assertRaises(EncryptedStorageError):
                read(directory,"test.enc")

    def test_symlink_hardlink_and_public_directory_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            directory=Path(t).resolve()
            publish(directory,"test.enc",b"WAMSP02\x00"+bytes(64))
            os.link(directory/"test.enc",directory/"other.enc")
            with self.assertRaises(EncryptedStorageError):
                read(directory,"test.enc")
            (directory/"other.enc").unlink()
            (directory/"link.enc").symlink_to(directory/"test.enc")
            with self.assertRaises(EncryptedStorageError):
                read(directory,"link.enc")
            os.chmod(directory,0o750)
            with self.assertRaises(MacosPrivateDirectoryError):
                read(directory,"test.enc")

    def test_security_probe_requires_real_payment_and_disposable_consent(self):
        with self.assertRaisesRegex(CoreSmokeError,"CORE_SECURITY_SCOPE_DENIED"):
            smoke_real_core(Path("/unknown"),explicit_consent=True,security_e2e=True)


if __name__ == "__main__":
    unittest.main()
