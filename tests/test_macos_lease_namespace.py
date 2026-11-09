"""CDX-AUD-001: macOS wallet lease namespace must not depend on TMPDIR.

Public random wallet ids and a disposable keychain created by the test only.
The user's real Keychain and any existing wallet lock are never touched.
"""
import os
from pathlib import Path
import secrets
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

HOLD = (
    "import sys;sys.dont_write_bytecode=True\n"
    "from wam_regtest.vault import KeychainAnchor\n"
    "a=KeychainAnchor(sys.argv[1])\n"
    "try:\n"
    " with a.lease():\n"
    "  print('HELD',flush=True);sys.stdin.readline()\n"
    "except Exception as e:\n"
    " print(type(e).__name__,*e.args,flush=True);sys.exit(73)\n")
# The pre-CDX-AUD-001 algorithm, verbatim in effect: lock <gettempdir()>/
# wam-regtest-wallet-leases/<id>.lock only (an "old build" process).
OLD = (
    "import sys,os,fcntl,tempfile;from pathlib import Path\n"
    "root=Path(tempfile.gettempdir()).resolve(strict=True)/'wam-regtest-wallet-leases'\n"
    "root.mkdir(mode=0o700,exist_ok=True)\n"
    "fd=os.open(str(root/(sys.argv[1]+'.lock')),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)\n"
    "try:\n fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)\n"
    "except OSError:\n print('VaultError VAULT_SESSION_BUSY',flush=True);sys.exit(73)\n"
    "print('HELD',flush=True);sys.stdin.readline()\n")


def _default_tmp():
    return os.confstr(65537)


@unittest.skipUnless(sys.platform == "darwin", "native macOS lease")
class MacosLeaseNamespace(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="lease-ns-")
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.one, self.two = self.base / "one", self.base / "two"
        self.one.mkdir(mode=0o700)
        self.two.mkdir(mode=0o700)
        self.wallet = secrets.token_hex(16)
        self.children = []

    def tearDown(self):
        for child in self.children:
            if child.poll() is None:
                try:
                    child.communicate("\n", timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.communicate()

    def _env(self, tmpdir):
        return dict(os.environ, TMPDIR=str(tmpdir), PYTHONDONTWRITEBYTECODE="1")

    def _hold(self, tmpdir, code=HOLD, wallet=None):
        child = subprocess.Popen([sys.executable, "-I", "-B", "-c", code, wallet or self.wallet],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, env=self._env(tmpdir))
        self.children.append(child)
        self.assertEqual(child.stdout.readline().strip(), "HELD")
        return child

    def _try(self, tmpdir, code=HOLD, wallet=None):
        result = subprocess.run([sys.executable, "-I", "-B", "-c", code, wallet or self.wallet],
                                input="\n", capture_output=True, text=True, timeout=30,
                                env=self._env(tmpdir))
        return result.returncode, result.stdout.strip()

    def test_same_tmpdir_second_process_refused(self):
        self._hold(self.one)
        self.assertEqual(self._try(self.one), (73, "VaultError VAULT_SESSION_BUSY"))

    def test_different_tmpdir_second_process_refused(self):
        self._hold(self.one)
        self.assertEqual(self._try(self.two), (73, "VaultError VAULT_SESSION_BUSY"))

    def test_old_build_default_namespace_and_new_build_exclude_each_other(self):
        default = _default_tmp()
        old = self._hold(default, OLD)
        self.assertEqual(self._try(self.one), (73, "VaultError VAULT_SESSION_BUSY"))
        old.communicate("\n", timeout=10)
        self._hold(self.one)
        self.assertEqual(self._try(default, OLD), (73, "VaultError VAULT_SESSION_BUSY"))

    def test_old_build_with_same_custom_tmpdir_is_excluded(self):
        self._hold(self.one, OLD)
        self.assertEqual(self._try(self.one), (73, "VaultError VAULT_SESSION_BUSY"))

    def test_different_wallet_ids_do_not_contend(self):
        self._hold(self.one)
        self.assertEqual(self._try(self.two, wallet=secrets.token_hex(16))[0], 0)

    def test_reentrancy_only_for_same_object_and_thread(self):
        from concurrent.futures import ThreadPoolExecutor
        from wam_regtest.vault import KeychainAnchor, VaultError
        anchor = KeychainAnchor(self.wallet)

        def other_thread():
            with self.assertRaisesRegex(VaultError, "VAULT_SESSION_BUSY"):
                with anchor.lease():
                    self.fail("thread bypassed lease")
        with anchor.lease():
            with anchor.lease():
                pass
            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(other_thread).result(timeout=5)
            with self.assertRaisesRegex(VaultError, "VAULT_SESSION_BUSY"):
                with KeychainAnchor(self.wallet).lease():
                    self.fail("copy bypassed lease")
        with KeychainAnchor(self.wallet).lease():
            pass

    def test_crash_releases_without_unlinking_and_normal_shutdown_keeps_inode(self):
        from wam_regtest.vault import stable_lease_root
        path = stable_lease_root() / (self.wallet + ".lock")
        child = self._hold(self.one)
        inode = path.stat().st_ino
        child.send_signal(signal.SIGKILL)
        child.wait(timeout=10)
        self.assertEqual(self._try(self.two)[0], 0)
        self.assertEqual(path.stat().st_ino, inode)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)

    def test_stable_root_is_environment_independent(self):
        from wam_regtest.vault import _lease_roots, stable_lease_root
        with patch.dict(os.environ, {"TMPDIR": str(self.one), "HOME": str(self.two)}):
            tempfile.tempdir = None
            try:
                roots = _lease_roots()
            finally:
                tempfile.tempdir = None
        self.assertEqual(roots[0], stable_lease_root())
        self.assertNotIn(str(self.two), str(roots[0]))
        self.assertEqual(roots[1], Path(_default_tmp()).resolve() / "wam-regtest-wallet-leases")
        self.assertEqual(roots[2], self.one / "wam-regtest-wallet-leases")

    def _with_stable(self, root):
        return patch("wam_regtest.vault.stable_lease_root", return_value=root)

    def _denied(self, root):
        from wam_regtest.vault import KeychainAnchor, VaultError
        with self._with_stable(root), self.assertRaisesRegex(VaultError, "VAULT_GLOBAL_LEASE_DENIED"):
            with KeychainAnchor(self.wallet).lease():
                self.fail("invalid lease root accepted")

    def test_invalid_root_or_lock_metadata_fails_closed(self):
        target = self.base / "real"
        target.mkdir(mode=0o700)
        link = self.base / "link"
        link.symlink_to(target)
        self._denied(link)
        loose = self.base / "loose"
        loose.mkdir(mode=0o755)
        os.chmod(loose, 0o755)
        self._denied(loose)
        acl = self.base / "acl"
        acl.mkdir(mode=0o700)
        subprocess.run(["/bin/chmod", "+a", "everyone allow read", str(acl)], check=True)
        self._denied(acl)
        hard = self.base / "hard"
        hard.mkdir(mode=0o700)
        (hard / (self.wallet + ".lock")).touch(mode=0o600)
        os.link(hard / (self.wallet + ".lock"), self.base / "second")
        self._denied(hard)
        mode = self.base / "mode"
        mode.mkdir(mode=0o700)
        (mode / (self.wallet + ".lock")).touch()
        os.chmod(mode / (self.wallet + ".lock"), 0o644)
        self._denied(mode)
        symlock = self.base / "symlock"
        symlock.mkdir(mode=0o700)
        (symlock / (self.wallet + ".lock")).symlink_to(self.base / "outside")
        self._denied(symlock)
        self.assertFalse((self.base / "outside").exists())

    def test_name_replaced_during_lock_is_refused(self):
        import fcntl
        from wam_regtest.vault import KeychainAnchor
        root = self.base / "race"
        root.mkdir(mode=0o700)
        real = fcntl.flock

        def racing(fd, op):
            if op & fcntl.LOCK_EX:
                os.unlink(root / (self.wallet + ".lock"))
                (root / (self.wallet + ".lock")).touch(mode=0o600)
            return real(fd, op)
        with patch("fcntl.flock", racing):
            self._denied(root)
        with self._with_stable(root), KeychainAnchor(self.wallet).lease():
            pass


@unittest.skipUnless(sys.platform == "darwin", "native macOS Keychain")
class DisposableKeychainCasContention(unittest.TestCase):
    """Real Keychain CAS on a keychain file created and deleted by this test."""

    ADVANCE = (
        "import sys;sys.dont_write_bytecode=True;from pathlib import Path\n"
        "from wam_regtest.vault import KeychainAnchor\n"
        "a=KeychainAnchor(sys.argv[1],Path(sys.argv[2]))\n"
        "sys.stdin.readline()\n"
        "try:\n a.advance(None,(1,sys.argv[3]));print('ADVANCED',flush=True)\n"
        "except Exception as e:\n print(type(e).__name__,*e.args,flush=True);sys.exit(73)\n")

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="lease-kc-")
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.keychain = self.base / "disposable-public-test.keychain-db"
        subprocess.run(["/usr/bin/security", "create-keychain", "-p", "public-test-only",
                        str(self.keychain)], check=True, capture_output=True)
        self.addCleanup(subprocess.run, ["/usr/bin/security", "delete-keychain", str(self.keychain)],
                        capture_output=True)
        subprocess.run(["/usr/bin/security", "unlock-keychain", "-p", "public-test-only",
                        str(self.keychain)], check=True, capture_output=True)
        for name in ("one", "two"):
            (self.base / name).mkdir(mode=0o700)

    def test_cross_tmpdir_concurrent_cas_has_exactly_one_winner(self):
        from wam_regtest.vault import KeychainAnchor
        for round_ in range(3):
            wallet = secrets.token_hex(16)
            digests = [secrets.token_hex(32), secrets.token_hex(32)]
            children = [subprocess.Popen(
                [sys.executable, "-I", "-B", "-c", self.ADVANCE, wallet, str(self.keychain), digest],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                env=dict(os.environ, TMPDIR=str(self.base / name)))
                for name, digest in zip(("one", "two"), digests)]
            time.sleep(1.0)
            for child in children:
                child.stdin.write("\n")
                child.stdin.flush()
            outputs = [child.communicate(timeout=60)[0].strip() for child in children]
            winners = [d for d, out in zip(digests, outputs) if out == "ADVANCED"]
            with self.subTest(round=round_, outputs=outputs):
                self.assertEqual(len(winners), 1)
                loser = [o for o in outputs if o != "ADVANCED"][0]
                self.assertIn(loser, ("VaultError VAULT_SESSION_BUSY",
                                      "VaultError VAULT_ANCHOR_CHANGED"))
                self.assertEqual(KeychainAnchor(wallet, self.keychain).read(), (1, winners[0]))


    def test_cas_refused_while_other_tmpdir_process_holds_lease(self):
        from wam_regtest.vault import KeychainAnchor
        wallet = secrets.token_hex(16)
        holder = subprocess.Popen([sys.executable, "-I", "-B", "-c", HOLD, wallet],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True,
                                  env=dict(os.environ, TMPDIR=str(self.base / "one")))
        try:
            self.assertEqual(holder.stdout.readline().strip(), "HELD")
            result = subprocess.run(
                [sys.executable, "-I", "-B", "-c", self.ADVANCE, wallet, str(self.keychain),
                 secrets.token_hex(32)], input="\n", capture_output=True, text=True, timeout=60,
                env=dict(os.environ, TMPDIR=str(self.base / "two")))
            self.assertEqual(result.stdout.strip(), "VaultError VAULT_SESSION_BUSY")
            self.assertIsNone(KeychainAnchor(wallet, self.keychain).read())
        finally:
            holder.communicate("\n", timeout=10)

if __name__ == "__main__":
    unittest.main()
