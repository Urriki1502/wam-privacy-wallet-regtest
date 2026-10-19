"""K-09 process-termination publication boundaries on disposable REGTEST-style files.

These are genuine OS-process kills against real filesystem calls, NOT physical
power-cut, native OS anchor, encrypted owner key, WAM Core or signer acceptance.
No real wallet, node or transaction is ever used.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from wam_regtest.crash_recovery import _candidate_inventory, CrashRecoveryRefusal
from wam_regtest.vault import CheckpointVault, VaultError


_CRASH_WORKER = r"""
import os
from pathlib import Path
import sys
import threading

directory=Path(sys.argv[1])
mode=sys.argv[2]
generation=int(sys.argv[3])
marker=Path(sys.argv[4])
stage=directory/(".stage-"+format(generation,"032x"))
snapshot=directory/("snapshot-%09d.enc"%generation)
payload=b"WAMSP02\x00"+(b"PUBLIC_DISPOSABLE_K09_FIXTURE_"*128)

def at_boundary():
    with open(marker,"xb",buffering=0) as notice:
        notice.write(b"ready")
        os.fsync(notice.fileno())
    # Only the controlling test process terminates this worker. No
    # graceful finally handlers may clear the interrupted stage/snapshot.
    threading.Event().wait()

with open(stage,"xb",buffering=0) as target:
    if os.name!="nt":
        os.fchmod(target.fileno(),0o600)
    target.write(payload[:64])
    if mode=="during_stage_write":
        at_boundary()  # not the complete ciphertext; no fsync
    target.write(payload[64:])
    os.fsync(target.fileno())
if mode=="after_stage_fsync":
    at_boundary()
if os.name=="nt":
    # Windows native storage uses an atomic same-directory handle rename;
    # it does NOT have the POSIX stage+hardlink window.
    os.rename(stage,snapshot)
else:
    os.link(stage,snapshot)
    if mode=="after_link_before_unlink":
        at_boundary()
    os.unlink(stage)
    dfd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(dfd)
    finally: os.close(dfd)
if mode=="after_publication_before_anchor":
    at_boundary()
raise RuntimeError("unexpected test worker completion")
"""


class K09NativeProcessKillBoundaries(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="k09-kill-fixture-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.vault=self.root/"vault"
        self.vault.mkdir(mode=0o700)
        # A sentinel only. This is NOT a Keychain/Credential/root-witness anchor.
        self.anchor_sentinel=self.root/"surrogate-anchor.txt"
        self.anchor_sentinel.write_text("generation=3\n",encoding="utf-8")

    def stage(self,generation):
        return self.vault/(".stage-"+format(generation,"032x"))

    def snap(self,generation):
        return self.vault/("snapshot-%09d.enc"%generation)

    def kill_at(self, mode, generation):
        marker=self.root/("ready-%s-%s"%(generation,mode))
        proc=subprocess.Popen(
            [sys.executable,"-u","-c",_CRASH_WORKER,
             str(self.vault),mode,str(generation),str(marker)],
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, text=True,
        )
        try:
            deadline=time.monotonic()+15
            while not marker.is_file() and time.monotonic()<deadline:
                if proc.poll() is not None:
                    output=proc.stderr.read()
                    self.fail("crash worker exited before boundary: "+output[-1000:])
                time.sleep(0.025)
            self.assertTrue(marker.is_file(),"crash worker boundary timeout")
        finally:
            if proc.poll() is None:
                proc.kill()   # SIGKILL on POSIX; TerminateProcess on Windows
            try: proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate(timeout=10)
        self.assertNotEqual(proc.returncode,0)
        self.assertEqual(self.anchor_sentinel.read_text(encoding="utf-8"),
                         "generation=3\n")

    def preview(self):
        return _candidate_inventory(self.vault,3)

    def assert_restore_locked(self, code):
        vault=CheckpointVault.__new__(CheckpointVault)
        vault.directory=self.vault
        with self.assertRaisesRegex(VaultError,code):
            vault._reject_unanchored_publication((3,"a"*64))

    def test_kill_during_partial_stage_write(self):
        self.kill_at("during_stage_write",4)
        self.assertTrue(self.stage(4).is_file())
        self.assertFalse(self.snap(4).exists())
        view=self.preview()
        self.assertEqual((view["stage_count"],view["future_snapshot_count"]),(1,0))
        self.assertFalse(view["operator_discard_available"])
        self.assert_restore_locked("VAULT_INTERRUPTED_PUBLICATION_DENIED")

    def test_kill_after_stage_fsync_before_publication(self):
        self.kill_at("after_stage_fsync",4)
        self.assertEqual(self.preview()["candidate_count"],1)
        self.assertTrue(self.stage(4).is_file())
        self.assert_restore_locked("VAULT_INTERRUPTED_PUBLICATION_DENIED")

    @unittest.skipIf(os.name=="nt","Windows uses rename, not POSIX link/unlink")
    def test_kill_after_hardlink_before_unlink(self):
        self.kill_at("after_link_before_unlink",4)
        self.assertEqual(self.stage(4).stat().st_ino,self.snap(4).stat().st_ino)
        view=self.preview()
        self.assertEqual(view["stage_future_snapshot_link_pairs"],1)
        self.assertEqual(view["candidate_count"],2)
        self.assertFalse(view["safe_to_discard_proven"])
        self.assert_restore_locked("VAULT_INTERRUPTED_PUBLICATION_DENIED")

    def test_stage_refusal_is_independent_of_directory_iteration_order(self):
        # Filesystems may enumerate the future hardlink before its stage.
        # The interrupted stage must still receive the deterministic refusal.
        from types import SimpleNamespace
        vault=CheckpointVault.__new__(CheckpointVault)
        stage_name=".stage-"+"4".zfill(32)
        snapshot_name="snapshot-000000004.enc"
        vault.directory=SimpleNamespace(iterdir=lambda: [
            SimpleNamespace(name=snapshot_name), SimpleNamespace(name=stage_name)])
        with self.assertRaisesRegex(
                VaultError,"VAULT_INTERRUPTED_PUBLICATION_DENIED"):
            vault._reject_unanchored_publication((3,"a"*64))

    def test_kill_after_publication_before_anchor(self):
        self.kill_at("after_publication_before_anchor",4)
        self.assertTrue(self.snap(4).is_file())
        self.assertFalse(self.stage(4).exists())
        view=self.preview()
        self.assertEqual((view["stage_count"],view["future_snapshot_count"]),(0,1))
        self.assert_restore_locked("VAULT_UNANCHORED_GENERATION_DENIED")

    def test_two_successive_interruptions_preserve_entire_orphan_set(self):
        self.kill_at("after_publication_before_anchor",4)
        first=self.snap(4).read_bytes()
        self.kill_at("after_publication_before_anchor",5)
        self.assertEqual(self.snap(4).read_bytes(),first)
        view=self.preview()
        self.assertEqual(view["future_snapshot_count"],2)
        self.assertTrue(view["multiple_future_generations"])
        self.assertFalse(view["signed_or_uncertain_reservations_reconciled"])
        self.assertFalse(view["operator_discard_available"])
        self.assert_restore_locked("VAULT_UNANCHORED_GENERATION_DENIED")

    def test_malformed_reserved_names_are_never_treated_as_clean(self):
        for name in (".stage-short","snapshot-00000004.enc",
                     "snapshot-000000000.enc","snapshot-000000004.enc.tmp",
                     ".stage-"+"A"*32):
            with self.subTest(name=name):
                path=self.vault/name
                path.write_bytes(b"PUBLIC_AMBIGUOUS_FIXTURE")
                with self.assertRaisesRegex(
                        CrashRecoveryRefusal,
                        "K09_AMBIGUOUS_PUBLICATION_NAME_DENIED"):
                    self.preview()
                self.assert_restore_locked("VAULT_AMBIGUOUS_PUBLICATION_DENIED")
                self.assertEqual(path.read_bytes(),b"PUBLIC_AMBIGUOUS_FIXTURE")
                path.unlink()  # fixture teardown only; never application cleanup


if __name__=="__main__":
    unittest.main()
