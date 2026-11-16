"""CUR-003 + CDX-AUD-003 (one finding): backup-ack sidecar publication.

Disposable public fixtures only: no seed, wallet, Core or retained profile.
Hardened storage only; the JSON/HMAC format and onboarding authority are
unchanged and there is no bypass of backup confirmation.
"""
import hmac
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(importlib.util.find_spec("wam_sp").origin).resolve().parents[2]
SEED = "bip39-12-" + "a" * 32
SECRET = b"public-test-ack-key-not-a-seed"


@unittest.skipUnless(sys.platform == "darwin", "native macOS no-follow private directories")
class BackupAckSidecarStorage(unittest.TestCase):
    def setUp(self):
        from wam_regtest.bip39_owner_backend import Bip39ReadOnlyBackend
        from wam_regtest.custody import private_temporary_directory
        temp = private_temporary_directory("ack-")  # runner-safe private root
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.root = self.base / "profile"
        self.root.mkdir(mode=0o700)
        import subprocess
        subprocess.run(["/bin/chmod", "-N", str(self.base)], check=True)  # runner temp ACL
        subprocess.run(["/bin/chmod", "-N", str(self.root)], check=True)
        self.backend = Bip39ReadOnlyBackend(self.root, Path("/synthetic-core"), SOURCE)
        self.folder = self.root / SEED
        self.ack_dir = self.root / "q06-gui-state" / "ack"
        self.path = self.ack_dir / (SEED + ".json")
        self.victim = self.base / "outside-public-dummy.txt"
        self.victim.write_text("PUBLIC_DUMMY_PRESERVE")

    def _legacy_dirs(self, mode=0o700):
        self.ack_dir.mkdir(mode=0o700, parents=True)
        os.chmod(self.ack_dir, mode)

    def _write_raw(self, data, mode=0o600):
        if not self.ack_dir.exists():
            self._legacy_dirs()
        self.path.write_bytes(data if type(data) is bytes else json.dumps(data).encode())
        os.chmod(self.path, mode)

    def _mac(self):
        return hmac.new(SECRET, f"{SEED}:acknowledged".encode(), "sha256").hexdigest()

    def _denied_write(self):
        from wam_regtest.bip39_owner_backend import Q06ReadOnlyError
        with self.assertRaises(Q06ReadOnlyError) as caught:
            self.backend._q06_write_ack(self.folder, True, secret=SECRET)
        self.assertEqual(caught.exception.args, ("Q06_GUI_BACKUP_ACK_STORAGE_DENIED",))

    def _no_stage(self):
        self.assertEqual([p.name for p in self.ack_dir.iterdir() if p.name != SEED + ".json"], [])

    def test_fixed_temporary_name_symlink_cannot_redirect_the_write(self):
        self._legacy_dirs()
        (self.ack_dir / (SEED + ".tmp")).symlink_to(self.victim)
        self.backend._q06_write_ack(self.folder, False, deferred=True)
        self.assertEqual(self.victim.read_text(), "PUBLIC_DUMMY_PRESERVE")
        self.assertFalse(self.path.is_symlink())
        self.assertTrue((self.ack_dir / (SEED + ".tmp")).is_symlink())  # untouched evidence
        self.assertEqual(self.backend._q06_read_ack(self.folder), (False, True, True))

    def test_symlink_target_is_refused_and_preserved(self):
        self._legacy_dirs()
        self.path.symlink_to(self.victim)
        self._denied_write()
        self.assertTrue(self.path.is_symlink())
        self.assertEqual(self.victim.read_text(), "PUBLIC_DUMMY_PRESERVE")
        self.assertEqual(self.backend._q06_read_ack(self.folder), (False, True, False))

    def test_hardlinked_target_is_refused(self):
        self._write_raw({"version": 1, "acknowledged": False, "deferred": True, "seed_id": SEED})
        os.link(self.path, self.base / "second-link")
        self.assertEqual(self.backend._q06_read_ack(self.folder)[2], False)
        self._denied_write()
        self.assertEqual(json.loads((self.base / "second-link").read_text())["deferred"], True)

    def test_group_or_other_writable_file_is_refused(self):
        self._write_raw({"version": 1, "acknowledged": False, "deferred": True,
                         "seed_id": SEED}, mode=0o666)
        self.assertEqual(self.backend._q06_read_ack(self.folder)[2], False)
        self._denied_write()

    def test_symlinked_ack_directory_is_refused(self):
        (self.root / "q06-gui-state").mkdir(mode=0o700)
        outside = self.base / "outside-dir"
        outside.mkdir(mode=0o700)
        self.ack_dir.symlink_to(outside)
        self._denied_write()
        self.assertEqual(list(outside.iterdir()), [])
        self.assertEqual(self.backend._q06_read_ack(self.folder)[2], False)

    def test_non_private_ack_directory_with_a_record_is_not_trusted(self):
        self._legacy_dirs(0o755)
        self._write_raw({"version": 1, "acknowledged": False, "deferred": True, "seed_id": SEED})
        self.assertEqual(self.backend._q06_read_ack(self.folder)[2], False)
        self._denied_write()

    def test_missing_record_is_unknown_not_tampered(self):
        self.assertEqual(self.backend._q06_read_ack(self.folder), (None, None, True))
        self.assertFalse((self.root / "q06-gui-state").exists())  # read never creates
        self._legacy_dirs(0o755)
        self.assertEqual(self.backend._q06_read_ack(self.folder), (None, None, True))

    def test_new_publication_is_private_and_leaves_no_stage(self):
        self.backend._q06_write_ack(self.folder, False, deferred=True)
        self.backend._q06_write_ack(self.folder, True, secret=SECRET)
        for directory in (self.root / "q06-gui-state", self.ack_dir):
            self.assertEqual(stat.S_IMODE(directory.lstat().st_mode), 0o700)
        info = self.path.lstat()
        self.assertTrue(stat.S_ISREG(info.st_mode))
        self.assertEqual((stat.S_IMODE(info.st_mode), info.st_nlink), (0o600, 1))
        self._no_stage()
        self.assertEqual(json.loads(self.path.read_text()),
                         {"version": 1, "acknowledged": True, "deferred": False,
                          "seed_id": SEED, "mac": self._mac()})

    def test_write_fsync_and_replace_errors_keep_previous_record(self):
        import wam_regtest.bip39_owner_backend as backend_module
        self.backend._q06_write_ack(self.folder, False, deferred=True)
        previous = self.path.read_bytes()
        for name in ("write", "fsync", "rename"):
            with self.subTest(fault=name):
                with patch.object(backend_module.os, name, side_effect=OSError("PUBLIC_FAULT")):
                    self._denied_write()
                self.assertEqual(self.path.read_bytes(), previous)
                self._no_stage()

    def test_file_fsync_before_rename_then_directory_fsync(self):
        import wam_regtest.bip39_owner_backend as backend_module
        events, real_fsync, real_rename = [], os.fsync, os.rename

        def fsync(fd):
            events.append("fsync-dir" if stat.S_ISDIR(os.fstat(fd).st_mode) else "fsync-file")
            return real_fsync(fd)

        def rename(*a, **k):
            events.append("rename")
            return real_rename(*a, **k)
        self.backend._q06_write_ack(self.folder, False, deferred=True)
        with patch.object(backend_module.os, "fsync", fsync), \
                patch.object(backend_module.os, "rename", rename):
            self.backend._q06_write_ack(self.folder, True, secret=SECRET)
        self.assertEqual(events, ["fsync-file", "rename", "fsync-dir"])

    def test_restart_reads_authenticated_acknowledgement(self):
        from wam_regtest.bip39_owner_backend import Bip39ReadOnlyBackend
        self.backend._q06_write_ack(self.folder, False, deferred=True)
        self.backend._q06_write_ack(self.folder, True, secret=SECRET)
        restarted = Bip39ReadOnlyBackend(self.root, Path("/synthetic-core"), SOURCE)
        self.assertEqual(restarted._q06_read_ack(self.folder, SECRET), (True, False, True))
        self.assertEqual(restarted._q06_read_ack(self.folder, b"wrong-public-key")[2], False)

    def test_malformed_records_fail_integrity(self):
        good = {"version": 1, "acknowledged": False, "deferred": True, "seed_id": SEED}
        cases = {
            "not-json": b"not json",
            "not-utf8": b"\xff\xfe\x00",
            "empty": b"",
            "oversize": json.dumps(dict(good, pad="x" * 5000)).encode(),
            "extra-key": dict(good, extra=1),
            "missing-key": {k: v for k, v in good.items() if k != "deferred"},
            "version-string": dict(good, version="1"),
            "version-bool": dict(good, version=True),
            "ack-string": dict(good, acknowledged="false"),
            "both-true": dict(good, acknowledged=True, deferred=True, mac=self._mac()),
            "wrong-seed": dict(good, seed_id="bip39-12-" + "b" * 32),
            "mac-on-unacknowledged": dict(good, mac=self._mac()),
            "mac-not-hex": dict(good, acknowledged=True, deferred=False, mac="Z" * 64),
            "list": [good],
        }
        for name, data in cases.items():
            with self.subTest(case=name):
                if self.path.exists():
                    self.path.unlink()
                self._write_raw(data)
                self.assertEqual(self.backend._q06_read_ack(self.folder, SECRET)[2], False)

    def test_legacy_writer_record_still_reads_without_modification(self):
        self._legacy_dirs()
        self.path.write_text(json.dumps({"version": 1, "acknowledged": True, "deferred": False,
                                         "seed_id": SEED, "mac": self._mac()},
                                        separators=(",", ":")))
        os.chmod(self.path, 0o644)  # Path.write_text with the default umask
        before = self.path.lstat()
        self.assertEqual(self.backend._q06_read_ack(self.folder, SECRET), (True, False, True))
        after = self.path.lstat()
        self.assertEqual((before.st_mtime_ns, before.st_mode), (after.st_mtime_ns, after.st_mode))
        # An explicit legacy refusal marker keeps its existing meaning.
        self.path.unlink()
        self._write_raw({"version": 1, "acknowledged": False, "deferred": False, "seed_id": SEED})
        self.assertEqual(self.backend._q06_read_ack(self.folder), (False, False, True))

    def test_invalid_seed_folder_name_is_refused(self):
        from wam_regtest.bip39_owner_backend import Q06ReadOnlyError
        with self.assertRaises(Q06ReadOnlyError):
            self.backend._q06_write_ack(self.root / "../escape", False, deferred=True)
        self.assertEqual(self.backend._q06_read_ack(self.root / "not-a-seed")[2], False)


    def test_inherited_acl_profile_directory_is_refused(self):
        """Hosted-runner condition: an inheritable ACL makes new ack dirs non-private."""
        import subprocess
        subprocess.run(["/bin/chmod", "+a", "everyone allow read,list,search,file_inherit,"
                        "directory_inherit", str(self.root)], check=True)
        self._denied_write()
        subprocess.run(["/bin/chmod", "-N", str(self.root)], check=True)
        if (self.root / "q06-gui-state").exists():
            subprocess.run(["/bin/chmod", "-RN", str(self.root / "q06-gui-state")], check=True)
        self.assertEqual(self.backend._q06_read_ack(self.folder)[2], False if self.path.exists() else True)

if __name__ == "__main__":
    unittest.main()
