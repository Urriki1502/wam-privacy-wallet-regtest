"""Native Win32 Credential Manager + global mutex anti-rollback contracts."""
import ctypes
from ctypes import wintypes
import secrets
import subprocess
import sys
import unittest
import queue
import threading

from wam_regtest.windows_checkpoint_anchor import (
    WindowsCredentialAnchor, WindowsAnchorError,
)

if sys.platform == "win32":
    _advapi = ctypes.WinDLL("Advapi32", use_last_error=True)
    _delete = _advapi.CredDeleteW
    _delete.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD)
    _delete.restype = wintypes.BOOL
else:
    _delete = None


@unittest.skipUnless(sys.platform == "win32", "Native Win32-only credential tests")
class NativeWindowsAnchorTests(unittest.TestCase):
    def setUp(self):
        self.wallet_id = secrets.token_hex(16)
        self.anchor = WindowsCredentialAnchor(self.wallet_id)
        self.addCleanup(self._cleanup_public_fixture)

    def _cleanup_public_fixture(self):
        # Test-generated random target only. No destructive production API.
        if not _delete(self.anchor._target, 1, 0):
            if ctypes.get_last_error() != 1168:
                raise AssertionError("WIN_TEST_CREDENTIAL_CLEANUP_DENIED")

    def test_create_reopen_increment_and_stale_writer_denied(self):
        self.assertIsNone(self.anchor.read())
        one = (1, "a"*64)
        two = (2, "b"*64)
        self.anchor.advance(None, one)
        another = WindowsCredentialAnchor(self.wallet_id)
        self.assertEqual(another.read(), one)
        with self.assertRaisesRegex(WindowsAnchorError, "^WIN_ANCHOR_STALE_WRITER_DENIED$"):
            another.advance(None, one)
        another.advance(one, two)
        self.assertEqual(self.anchor.read(), two)
        with self.assertRaisesRegex(WindowsAnchorError, "^WIN_ANCHOR_STALE_WRITER_DENIED$"):
            self.anchor.advance(one, (3, "c"*64))
        self.assertEqual(self.anchor.read(), two)

    def test_invalid_generation_rejected_without_change(self):
        for record in ((0, "a"*64), (1, "A"*64), (2, "a"*64),
                       (True, "a"*64), (1, "a"*63), [1, "a"*64]):
            with self.subTest(record=repr(record)), self.assertRaises(WindowsAnchorError):
                self.anchor.advance(None, record)
        self.assertIsNone(self.anchor.read())

    def test_second_object_same_thread_cannot_override_wallet_lease(self):
        other = WindowsCredentialAnchor(self.wallet_id)
        with self.anchor.lease():
            with self.assertRaisesRegex(WindowsAnchorError, "^WIN_ANCHOR_SESSION_BUSY$"):
                with other.lease():
                    self.fail("second owner acquired global lease")

    def test_competing_process_cannot_enter_and_release_recovers(self):
        child_program = (
            "import sys;"
            "from wam_regtest.windows_checkpoint_anchor import WindowsCredentialAnchor;"
            "a=WindowsCredentialAnchor(sys.argv[1]);"
            "with a.lease():\n"
            " print('READY',flush=True)\n"
            " sys.stdin.readline()\n"
        )
        # with-statements require compound context at start of a new line.
        child_program = (
            "import sys\n"
            "from wam_regtest.windows_checkpoint_anchor import WindowsCredentialAnchor\n"
            "a=WindowsCredentialAnchor(sys.argv[1])\n"
            "with a.lease():\n"
            " print('READY',flush=True)\n"
            " sys.stdin.readline()\n"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", child_program, self.wallet_id],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        )
        def close():
            if proc.poll() is None:
                proc.kill()
            proc.communicate(timeout=8)
        self.addCleanup(close)
        ready=queue.Queue()
        threading.Thread(target=lambda:ready.put(proc.stdout.readline().strip()),daemon=True).start()
        self.assertEqual(ready.get(timeout=8), "READY")
        with self.assertRaisesRegex(WindowsAnchorError, "^WIN_ANCHOR_SESSION_BUSY$"):
            with self.anchor.lease():
                self.fail("entered conflicting process lease")
        proc.stdin.write("\n")
        proc.stdin.flush()
        proc.wait(timeout=8)
        self.assertEqual(proc.returncode, 0)
        with self.anchor.lease():
            self.assertIsNone(self.anchor.read())

    def test_precreated_public_mutex_denied_without_repair(self):
        from wam_regtest import windows_checkpoint_anchor as native
        from wam_regtest.windows_private_storage import security_attributes, owner_sid
        with security_attributes(kernel=True,descriptor='O:'+owner_sid()+'D:P(A;;GA;;;WD)') as sa:
            handle=native._mutex(sa,False,self.anchor._mutex_name)
        self.assertTrue(handle)
        try:
            with self.assertRaisesRegex(WindowsAnchorError,'WIN_ANCHOR_MUTEX_CUSTODY_DENIED'):
                with self.anchor.lease():self.fail('entered public mutex')
        finally:native._close(handle)

    def test_killed_writer_abandonment_denied_then_lease_recovers(self):
        from wam_regtest import windows_checkpoint_anchor as native
        from wam_regtest.windows_private_storage import security_attributes
        # Retain a non-owned handle so the object survives killed child's exit.
        with security_attributes(kernel=True) as sa:
            handle=native._mutex(sa,False,self.anchor._mutex_name)
        self.assertTrue(handle)
        code="import sys,time\nfrom wam_regtest.windows_checkpoint_anchor import WindowsCredentialAnchor\nwith WindowsCredentialAnchor(sys.argv[1]).lease():\n print('READY',flush=True)\n time.sleep(60)\n"
        p=subprocess.Popen([sys.executable,'-c',code,self.wallet_id],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
        try:
            ready=queue.Queue()
            threading.Thread(target=lambda:ready.put(p.stdout.readline().strip()),daemon=True).start()
            self.assertEqual(ready.get(timeout=8),'READY')
            p.kill();p.wait(timeout=8)
            with self.assertRaisesRegex(WindowsAnchorError,'WIN_ANCHOR_ABANDONED_WRITER_DENIED'):
                with self.anchor.lease():self.fail('accepted abandoned writer')
            with self.anchor.lease():self.assertIsNone(self.anchor.read())
        finally:
            if p.poll() is None:p.kill()
            p.wait(timeout=8);p.stdout.close();native._close(handle)


if __name__ == "__main__":
    unittest.main()
