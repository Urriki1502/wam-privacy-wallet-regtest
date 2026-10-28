"""Native storage tests; zero real keys, no Core and no synthetic E2E claims."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from wam_regtest.supervisor_store import (
    create_once,read_exact,exclusive_lease,SupervisorStorageError,
)

PUBLIC=b"public-disposable-control"
TOKEN=b"x"*32


class SupervisorStoreContracts(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(prefix="wam-supervisor-unit-")
        self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name).resolve()/"wam-fusion-core-1234567890abcdef"
        if sys.platform=="win32":
            from wam_regtest.windows_private_storage import create_private_directory
            create_private_directory(self.root)
        else:
            self.root.mkdir(mode=0o700)

    def test_owner_only_create_once_and_read(self):
        create_once(self.root,"supervisor.token",TOKEN)
        self.assertEqual(read_exact(self.root,"supervisor.token",length=32),TOKEN)
        with self.assertRaises(SupervisorStorageError):
            create_once(self.root,"supervisor.token",TOKEN)
        self.assertEqual(read_exact(self.root,"supervisor.token"),TOKEN)

    def test_out_of_stage_scope_tokens_denied(self):
        for name in ('supervisor.scan.token', 'supervisor.spend.token'):
            with self.assertRaises(SupervisorStorageError):
                create_once(self.root, name, TOKEN)

    def test_invalid_name_and_public_root_refused_without_mutation(self):
        for name in ("../private-key","wallet.dat","supervisor.lock","../../wam.conf"):
            with self.assertRaises(SupervisorStorageError):
                create_once(self.root,name,PUBLIC)
        with self.assertRaises(SupervisorStorageError):
            create_once(self.root.parent/"unknown", "supervisor.token",TOKEN)
        self.assertEqual(list(self.root.iterdir()),[])

    def test_one_active_owner_lease(self):
        with exclusive_lease(self.root):
            with self.assertRaises(SupervisorStorageError):
                with exclusive_lease(self.root):pass
        with exclusive_lease(self.root):pass
        self.assertTrue((self.root/"supervisor.lock").exists())

    def test_untrusted_file_or_link_denied(self):
        if sys.platform=="win32":
            # Exercise this control-file boundary itself, not a POSIX chmod
            # surrogate or a skipped claim about another test suite.
            import ctypes
            from wam_regtest import windows_private_storage as native
            file=self.root/'supervisor.token'
            descriptor='O:'+native.owner_sid()+'D:P(A;;FA;;;'+native.owner_sid()+')(A;;FR;;;WD)'
            with native.security_attributes(descriptor=descriptor) as attributes:
                handle=native.create(str(file),0xc0000000,0,attributes,1,0x200080,None)
            self.assertNotIn(handle,(None,native.INVALID))
            try:
                raw=ctypes.create_string_buffer(TOKEN);count=native.w.DWORD()
                self.assertTrue(native.write(handle,raw,len(TOKEN),ctypes.byref(count),None))
                self.assertEqual(count.value,len(TOKEN));self.assertTrue(native.flush(handle))
            finally:native.close(handle)
            with self.assertRaises(SupervisorStorageError):read_exact(self.root,'supervisor.token')
            file.unlink()
            create_once(self.root,'supervisor.token',TOKEN)
            os.link(file,self.root/'hardlink-fixture')
            with self.assertRaises(SupervisorStorageError):read_exact(self.root,'supervisor.token')
            return
        file=self.root/"supervisor.token"
        file.symlink_to(self.root/"supervisor.lock")
        with self.assertRaises(SupervisorStorageError):
            read_exact(self.root,"supervisor.token")
        file.unlink()
        create_once(self.root,"supervisor.token",TOKEN)
        file.chmod(0o644)
        with self.assertRaises(SupervisorStorageError):
            read_exact(self.root,"supervisor.token")

    def test_wrong_size_and_unknown_root_refused(self):
        create_once(self.root,"supervisor.token",TOKEN)
        with self.assertRaisesRegex(SupervisorStorageError,"SUPERVISOR_STORAGE_LENGTH_DENIED"):
            read_exact(self.root,"supervisor.token",length=31)
        with self.assertRaises(SupervisorStorageError):
            read_exact(self.root,"supervisor.profile")
