"""K-09 forensic checkpoint ledger contracts using ONLY disposable public WSP keys.

This is not a live-Core/rescan/orphan-discard approval. The native file reader
is mocked here; full native CI and Codex/physical QA remain separate gates.
"""
from contextlib import nullcontext
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from wam_sp.keystore import Keyring, seal
from wam_sp.store import Store
from wam_sp.watcher import GENESIS

from wam_regtest.crash_ledger import (
    LedgerEvidenceError, project_owner_ledger, compare_candidate_ledger,
)
from wam_regtest.crash_recovery import (
    inspect_owner_crash_residue, CrashRecoveryRefusal,
)
from wam_regtest.vault import CheckpointVault


class K09LedgerForensicContracts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="k09-ledger-public-fixture-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.directory=self.root/"vault"
        self.directory.mkdir(mode=0o700)
        self.password=b"PUBLIC_REGTEST_K09_LEDGER_TEST_PASSWORD"
        self.wallet_id="a"*32
        self.ring=Keyring(seed=bytes([0x12])*32)
        self.addCleanup(self.ring.close)
        accounts=[a.identity() for a in self.ring.accounts()]
        self.store=Store(self.root/"scanner.db",accounts)
        self.addCleanup(self.store.close)

    def payload(self, generation, ring=None):
        actual_ring=self.ring if ring is None else ring
        return {
            "version":1,"disposable_regtest":True,
            "network":GENESIS,"wallet_id":self.wallet_id,
            "generation":generation,
            "keys":self._b64(actual_ring.backup(self.password)),
            "checkpoint":self._b64(self.store.export_checkpoint(self.password)),
        }

    @staticmethod
    def _b64(value):
        import base64
        return base64.b64encode(value).decode("ascii")

    def outer(self, generation, ring=None):
        return seal(json.dumps(self.payload(generation,ring),sort_keys=True).encode(),
                    self.password,b"recovery")

    def make_vault(self, encrypted_by_generation):
        anchored=encrypted_by_generation[3]
        record=(3,sha256(anchored).hexdigest())
        vault=CheckpointVault.__new__(CheckpointVault)
        vault.directory=self.directory
        vault.anchor=Mock(wallet_id=self.wallet_id)
        vault.anchor.lease.return_value=nullcontext()
        vault.anchor.read.return_value=record
        vault._expected=record
        vault._storage=Mock()
        vault._storage.read.side_effect=lambda directory,name: encrypted_by_generation[
            int(name.split("-")[1].split(".")[0])]
        # Mock ONLY the platform's native custody reader in source-unit tests.
        # OS ACL/handle correctness is a separate native CI acceptance gate.
        vault._storage.read_crash_residue.side_effect=(
            lambda directory,name: (directory/name).read_bytes())
        for number,ciphertext in encrypted_by_generation.items():
            (self.directory/f"snapshot-{number:09d}.enc").write_bytes(ciphertext)
        return vault

    def preview(self, vault):
        with (patch("wam_regtest.custody.envelope_profile",
                    return_value={"version":1}),
              patch("wam_sp.file_lock.exclusive_file_lock",
                    return_value=nullcontext())):
            return inspect_owner_crash_residue(
                vault,self.password,authorized=True,audit_reservations=True)

    def test_sealed_owner_candidate_no_delta_does_not_authorize_discard(self):
        encrypted={3:self.outer(3),4:self.outer(4)}
        vault=self.make_vault(encrypted)
        receipt=self.preview(vault)
        self.assertEqual(receipt["future_snapshot_ledger_authenticated_count"],1)
        self.assertEqual(receipt["future_snapshot_ledger_unverifiable_count"],0)
        self.assertEqual(receipt["future_snapshot_irreversible_delta_count"],0)
        for key in ("safe_to_discard_proven","operator_discard_available",
                    "wallet_unlocked","signer_allowed","broadcast_allowed",
                    "core_reservation_or_reorg_reconciled"):
            self.assertIs(receipt[key],False,key)
        vault.anchor.advance.assert_not_called()
        vault._storage.publish.assert_not_called()
        self.assertEqual((self.directory/"snapshot-000000004.enc").read_bytes(),
                         encrypted[4])

    def test_signed_reservation_only_in_future_is_flagged_and_preserved(self):
        original=self.outer(3)
        txid="b"*64
        self.store.db.execute(
            "INSERT INTO reservations VALUES(?,?,?,?,?)",
            (txid,2,"public-test-token","signed",1))
        future=self.outer(4)
        vault=self.make_vault({3:original,4:future})
        receipt=self.preview(vault)
        self.assertEqual(receipt["future_snapshot_ledger_authenticated_count"],1)
        self.assertEqual(receipt["future_snapshot_reservation_set_changed_count"],1)
        self.assertEqual(receipt["future_snapshot_irreversible_delta_count"],1)
        self.assertFalse(receipt["operator_discard_available"])
        self.assertNotIn(txid,str(receipt))
        self.assertEqual((self.directory/"snapshot-000000004.enc").read_bytes(),
                         future)

    def test_truncated_future_orphan_is_unknown_never_harmless(self):
        vault=self.make_vault({3:self.outer(3),4:b"PUBLIC_TORN_CIPHERTEXT"})
        receipt=self.preview(vault)
        self.assertEqual(receipt["future_snapshot_ledger_authenticated_count"],0)
        self.assertEqual(receipt["future_snapshot_ledger_unverifiable_count"],1)
        self.assertFalse(receipt["safe_to_discard_proven"])

    def test_account_rotation_or_substitution_is_redacted_risk(self):
        other=Keyring(seed=bytes([0x33])*32)
        self.addCleanup(other.close)
        vault=self.make_vault({3:self.outer(3),4:self.outer(4,ring=other)})
        result=self.preview(vault)
        # Candidate scanner checkpoint remains bound to the original WSP
        # account; a different signer is not accepted as a verified ledger.
        self.assertEqual(result["future_snapshot_ledger_unverifiable_count"],1)
        self.assertFalse(result["operator_discard_available"])

    def test_malformed_audit_opt_in_never_reads_native_storage(self):
        vault=self.make_vault({3:self.outer(3)})
        with self.assertRaisesRegex(CrashRecoveryRefusal,
                                    "K09_FORENSIC_SCOPE_DENIED"):
            inspect_owner_crash_residue(vault,self.password,authorized=True,
                                        audit_reservations="yes")
        vault._storage.read.assert_not_called()

    def test_projection_rejects_malformed_backup_without_leaking_keys(self):
        payload=self.payload(3)
        payload["checkpoint"]="not base64!"
        with self.assertRaises(LedgerEvidenceError):
            project_owner_ledger(payload,self.password)


    def test_full_stage_signed_only_in_unanchored_checkpoint_is_unsafe(self):
        original=self.outer(3)
        txid="c"*64
        self.store.db.execute(
            "INSERT INTO reservations VALUES(?,?,?,?,?)",
            (txid,1,"public-stage-token","uncertain",2))
        stage_bytes=self.outer(4)
        vault=self.make_vault({3:original})
        stage=self.directory/(".stage-"+"a"*32)
        stage.write_bytes(stage_bytes)
        receipt=self.preview(vault)
        self.assertEqual(receipt["stage_content_authenticated_count"],1)
        self.assertEqual(receipt["stage_irreversible_delta_count"],1)
        self.assertEqual(receipt["stage_content_unverifiable_count"],0)
        self.assertFalse(receipt["safe_to_discard_proven"])
        self.assertFalse(receipt["operator_discard_available"])
        self.assertNotIn(txid,str(receipt))
        self.assertEqual(stage.read_bytes(),stage_bytes)

    def test_truncated_stage_refused_without_cleanup(self):
        vault=self.make_vault({3:self.outer(3)})
        stage=self.directory/(".stage-"+"b"*32)
        stage.write_bytes(b"PUBLIC_TORN_STAGE")
        receipt=self.preview(vault)
        self.assertEqual(receipt["stage_content_authenticated_count"],0)
        self.assertEqual(receipt["stage_content_unverifiable_count"],1)
        self.assertFalse(receipt["safe_to_discard_proven"])
        self.assertEqual(stage.read_bytes(),b"PUBLIC_TORN_STAGE")

    def test_posix_stage_hardlink_to_future_is_not_discard_permission(self):
        vault=self.make_vault({3:self.outer(3),4:self.outer(4)})
        stage=self.directory/(".stage-"+"c"*32)
        try:
            stage.hardlink_to(self.directory/"snapshot-000000004.enc")
        except (OSError,NotImplementedError):
            self.skipTest("test filesystem cannot create hardlinks")
        receipt=self.preview(vault)
        self.assertEqual(receipt["stage_content_authenticated_count"],1)
        self.assertEqual(receipt["future_snapshot_ledger_authenticated_count"],1)
        self.assertEqual(receipt["stage_future_snapshot_link_pairs"],1)
        self.assertFalse(receipt["operator_discard_available"])
        self.assertTrue(stage.exists())

    def test_status_only_reservation_delta_is_not_hidden(self):
        txid="d"*64
        self.store.db.execute(
            "INSERT INTO reservations VALUES(?,?,?,?,?)",
            (txid,0,"public-token","draft",1))
        original=self.outer(3)
        self.store.db.execute(
            "UPDATE reservations SET state='signed' WHERE txid=?",
            (txid,))
        vault=self.make_vault({3:original,4:self.outer(4)})
        receipt=self.preview(vault)
        self.assertEqual(receipt["future_snapshot_reservation_set_changed_count"],1)
        self.assertEqual(receipt["future_snapshot_irreversible_delta_count"],1)
        self.assertFalse(receipt["operator_discard_available"])
        self.assertNotIn(txid,str(receipt))



if __name__=="__main__":
    unittest.main()
