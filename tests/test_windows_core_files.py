"""Native token-owner inheritance without relaxing private custody policy."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from wam_regtest import windows_core_files as files
from wam_regtest import windows_private_storage as store


class HostScope(unittest.TestCase):
    def test_foreign_host_cannot_simulate_native_owner(self):
        if sys.platform == 'win32':return
        with self.assertRaisesRegex(ValueError,'WIN_CUSTODY_NATIVE_X64_REQUIRED'):
            with files.child_user_owner():self.fail('entered Windows context')


@unittest.skipUnless(sys.platform=='win32','requires genuine Windows token/NTFS')
class NativeOwner(unittest.TestCase):
    def owner(self):
        token=store.w.HANDLE()
        self.assertTrue(store.token_open(store.current(),8,store.c.byref(token)))
        try:
            data=files._token_buffer(token,4)
            return store._sid_text(store.c.cast(data,store.c.POINTER(store.c.c_void_p))[0])
        finally:store.close(token)

    def test_default_owner_restored_after_failed_creation(self):
        before=self.owner()
        with self.assertRaisesRegex(RuntimeError,'fixture-creation-failed'):
            with files.child_user_owner():
                self.assertEqual(self.owner(),store.owner_sid())
                raise RuntimeError('fixture-creation-failed')
        self.assertEqual(self.owner(),before)

    def test_original_child_creates_only_user_owned_inherited_file(self):
        with tempfile.TemporaryDirectory(prefix='wam-core-owner-') as temp:
            root=Path(temp)/'private'
            store.create_private_directory(root)
            before=self.owner()
            with files.child_user_owner():
                child=subprocess.Popen([sys.executable,'-c',
                    'from pathlib import Path;import sys;Path(sys.argv[1]).write_bytes(b"public")',
                    str(root/'public.dat')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            self.assertEqual(self.owner(),before)
            self.assertEqual(child.wait(timeout=15),0)
            with store.directory_guard(root):
                handle=store.create(str(root/'public.dat'),0x20000,1,None,3,0x00200080,None)
                self.assertNotIn(handle,(None,store.INVALID))
                try:
                    store._metadata(handle)
                    store.verify_security(handle,protected=False)
                    with self.assertRaises(store.WindowsCustodyError):
                        store.verify_security(handle,protected=True)
                finally:store.close(handle)
            with self.assertRaisesRegex(ValueError,'WIN_CORE_PUBLIC_PREFIX_OWNER_REQUIRED'):
                files.public_block_prefix(root,'xor.dat',8)
            with self.assertRaisesRegex(ValueError,'WIN_CORE_PUBLIC_PREFIX_SCOPE_DENIED'):
                files.public_block_prefix(root,'wallet.dat',8)
