"""K-09 N+1 adoption contracts with synthetic, disposable WSP REGTEST keys.

SOURCE tests only. They do NOT establish OS-native anchor or real-Core E2E;
the outer owner/anchor/storage mocks are intentionally explicit here.
"""
from contextlib import nullcontext
from hashlib import sha256
import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from wam_sp.keystore import Keyring, seal
from wam_sp.store import Store
from wam_sp.watcher import GENESIS

from wam_regtest.crash_ledger import (
    project_owner_ledger, require_irreversible_continuity,
    LedgerEvidenceError,
)
from wam_regtest.k09_adoption import (
    _adopt_published_next, _authenticated_payload, K09AdoptionRefusal,
)
from wam_regtest.vault import CheckpointVault


class K09AuthenticatedAdoptionContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="k09-adoption-public-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.folder = self.root / "vault"
        self.folder.mkdir(mode=0o700)
        self.password = b"PUBLIC_DISPOSABLE_K09_PASSWORD_2026"
        self.wallet_id = "c" * 32
        self.ring = Keyring(seed=bytes([0x34]) * 32)
        self.addCleanup(self.ring.close)
        self.store = Store(
            self.root / "scanner.db", [a.identity() for a in self.ring.accounts()])
        self.addCleanup(self.store.close)

    def payload(self, generation):
        return {
            "version": 1,
            "disposable_regtest": True,
            "network": GENESIS,
            "wallet_id": self.wallet_id,
            "generation": generation,
            "keys": base64.b64encode(
                self.ring.backup(self.password)).decode("ascii"),
            "checkpoint": base64.b64encode(
                self.store.export_checkpoint(self.password)).decode("ascii"),
        }

    def sealed(self, payload):
        return seal(json.dumps(
            payload, sort_keys=True, separators=(",", ":")).encode(),
            self.password, b"recovery")

    def reserve(self, state, outpoint="d"*64, token="public-reservation"):
        self.store.db.execute(
            "INSERT INTO reservations VALUES(?,?,?,?,?)",
            (outpoint, 2, token, state, 1234))

    def attach(self, old, candidates):
        (self.folder / "snapshot-000000003.enc").write_bytes(old)
        for generation, content in candidates.items():
            (self.folder / f"snapshot-{generation:09d}.enc").write_bytes(content)
        current = [(3, sha256(old).hexdigest())]
        vault = CheckpointVault.__new__(CheckpointVault)
        vault.directory = self.folder
        vault.anchor = Mock(wallet_id=self.wallet_id)
        vault.anchor.lease.return_value = nullcontext()
        vault.anchor.read.side_effect = lambda: current[0]

        def advance(before, after):
            if current[0] != before:
                raise ValueError("synthetic stale anchor")
            current[0] = after
        vault.anchor._advance_unlocked.side_effect = advance
        vault._expected = current[0]
        vault._storage = Mock()
        vault._storage.read.side_effect = (
            lambda directory, name: (directory / name).read_bytes())
        vault._storage.validate_directory.return_value = None
        return vault, current

    def run_adoption(self, vault, *, consent=True, locked=True):
        with (patch("wam_regtest.custody.envelope_profile",
                    return_value={"version": 1}),
              patch("wam_sp.file_lock.exclusive_file_lock",
                    return_value=nullcontext())):
            return _adopt_published_next(
                vault, self.password, authorized=consent,
                confirm_anchor_advance=consent,
                locked_guard=lambda: locked)

    def test_only_n_plus_one_published_snapshot_is_adopted_and_stays_locked(self):
        old = self.sealed(self.payload(3))
        # The only copy of this irreversible reservation will be in N+1.
        self.reserve("signed")
        next_bytes = self.sealed(self.payload(4))
        vault, anchor = self.attach(old, {4: next_bytes})
        receipt = self.run_adoption(vault)
        self.assertEqual(
            receipt["status"], "K09_OWNER_AUTHENTICATED_NEXT_SNAPSHOT_ADOPTED")
        self.assertEqual(anchor[0], (4, sha256(next_bytes).hexdigest()))
        self.assertEqual(vault._expected, anchor[0])
        for key in ("wallet_unlocked", "signer_allowed", "broadcast_allowed",
                    "reservation_release_allowed", "automatic_cleanup_allowed",
                    "mainnet_allowed"):
            self.assertIs(receipt[key], False)
        self.assertEqual(
            (self.folder/"snapshot-000000003.enc").read_bytes(), old)
        self.assertEqual(
            (self.folder/"snapshot-000000004.enc").read_bytes(), next_bytes)
        vault._storage.publish.assert_not_called()

    def test_missing_consent_or_locked_state_does_not_mutate_anchor(self):
        old = self.sealed(self.payload(3))
        future = self.sealed(self.payload(4))
        vault, anchor = self.attach(old, {4: future})
        with self.assertRaisesRegex(
                K09AdoptionRefusal, "K09_ADOPTION_OPERATOR_CONSENT_DENIED"):
            self.run_adoption(vault, consent=False)
        with self.assertRaisesRegex(
                K09AdoptionRefusal, "K09_ADOPTION_MANAGED_STATE_CHANGED"):
            self.run_adoption(vault, locked=False)
        self.assertEqual(anchor[0][0], 3)
        vault.anchor._advance_unlocked.assert_not_called()

    def test_resealed_missing_self_identity_fields_are_all_refused(self):
        for field in ("wallet_id", "generation", "network", "version",
                      "disposable_regtest", "keys", "checkpoint"):
            with self.subTest(field=field):
                malformed = self.payload(4)
                del malformed[field]
                bad = self.sealed(malformed)
                vault, anchor = self.attach(
                    self.sealed(self.payload(3)), {4: bad})
                with self.assertRaises(K09AdoptionRefusal):
                    self.run_adoption(vault)
                self.assertEqual(anchor[0][0], 3)
                vault.anchor._advance_unlocked.assert_not_called()

    def test_resealed_wrong_self_identity_is_refused(self):
        for field, replacement in (
                ("wallet_id", "a"*32),
                ("generation", 5),
                ("network", "mainnet"),
                ("version", 2)):
            with self.subTest(field=field):
                malformed = self.payload(4)
                malformed[field] = replacement
                vault, anchor = self.attach(
                    self.sealed(self.payload(3)),
                    {4: self.sealed(malformed)})
                with self.assertRaises(K09AdoptionRefusal):
                    self.run_adoption(vault)
                self.assertEqual(anchor[0][0], 3)

    def test_prior_signed_record_cannot_disappear(self):
        self.reserve("signed")
        old = self.sealed(self.payload(3))
        self.store.db.execute("DELETE FROM reservations")
        future = self.sealed(self.payload(4))
        vault, anchor = self.attach(old, {4: future})
        with self.assertRaises(K09AdoptionRefusal):
            self.run_adoption(vault)
        self.assertEqual(anchor[0][0], 3)
        vault.anchor._advance_unlocked.assert_not_called()

    def test_signed_cannot_revert_to_draft_or_change_token(self):
        self.reserve("signed")
        old = self.sealed(self.payload(3))
        for sql in (
                "UPDATE reservations SET state='draft'",
                "UPDATE reservations SET token='different'"):
            with self.subTest(sql=sql):
                self.store.db.execute(sql)
                future = self.sealed(self.payload(4))
                vault, anchor = self.attach(old, {4: future})
                with self.assertRaises(K09AdoptionRefusal):
                    self.run_adoption(vault)
                self.assertEqual(anchor[0][0], 3)
                self.store.db.execute(
                    "UPDATE reservations SET state='signed', "
                    "token='public-reservation'")

    def test_forward_signed_to_uncertain_is_allowed(self):
        self.reserve("signed")
        original = self.payload(3)
        self.store.db.execute(
            "UPDATE reservations SET state='uncertain'")
        future = self.payload(4)
        old_ledger = project_owner_ledger(original, self.password)
        next_ledger = project_owner_ledger(future, self.password)
        self.assertTrue(require_irreversible_continuity(
            old_ledger, next_ledger))

    def test_staged_or_ambiguous_residue_remains_blocked(self):
        old = self.sealed(self.payload(3))
        future = self.sealed(self.payload(4))
        vault, anchor = self.attach(old, {4: future})
        stage = self.folder / (".stage-" + "a"*32)
        stage.write_bytes(future)
        with self.assertRaisesRegex(
                K09AdoptionRefusal, "K09_ADOPTION_AMBIGUOUS_RESIDUE_DENIED"):
            self.run_adoption(vault)
        self.assertEqual(anchor[0][0], 3)
        self.assertTrue(stage.exists())
        vault.anchor._advance_unlocked.assert_not_called()

    def test_jump_generation_and_multi_orphan_refuse(self):
        old = self.sealed(self.payload(3))
        next_bytes = self.sealed(self.payload(4))
        later_bytes = self.sealed(self.payload(5))
        vault, anchor = self.attach(old, {4: next_bytes, 5: later_bytes})
        with self.assertRaises(K09AdoptionRefusal):
            self.run_adoption(vault)
        self.assertEqual(anchor[0][0], 3)
        vault.anchor._advance_unlocked.assert_not_called()

    def test_truncated_or_wrong_password_residue_refuse(self):
        old = self.sealed(self.payload(3))
        vault, anchor = self.attach(old, {4: b"WAMSP02\x00torn"})
        with self.assertRaises(K09AdoptionRefusal):
            self.run_adoption(vault)
        self.assertEqual(anchor[0][0], 3)
        vault.anchor._advance_unlocked.assert_not_called()

    def test_competing_anchor_or_metadata_mutation_refuses(self):
        old = self.sealed(self.payload(3))
        future = self.sealed(self.payload(4))
        vault, anchor = self.attach(old, {4: future})
        vault._expected = (3, "0"*64)
        with self.assertRaises(K09AdoptionRefusal):
            self.run_adoption(vault)
        self.assertEqual(anchor[0][0], 3)
        vault.anchor._advance_unlocked.assert_not_called()


if __name__ == "__main__":
    unittest.main()
