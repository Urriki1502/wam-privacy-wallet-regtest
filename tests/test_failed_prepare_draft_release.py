"""CUR-001: a failed Signer.prepare must not leave its new draft reserved.

Only the exact token created by this prepare is released, only while every
row is still 'draft', and never after an uncertain persistence failure.
Real pinned-WSP scanner/wallet/reservations; synthetic RPC and vault.
"""
from contextlib import nullcontext
from hashlib import sha256
import importlib.util
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from mnemonic import Mnemonic
from wam_regtest.bip39_12 import Bip39Regtest12Keys
from wam_sp.core import Input, pub, send
from wam_sp.scanner import Scanner
from wam_sp.transaction import p2wpkh
from wam_sp.wallet import Signer, Wallet
from wam_sp.watcher import GENESIS

SOURCE = Path(importlib.util.find_spec("wam_sp").origin).resolve().parents[2]
PASSWORD = b"cur-001 disposable public test password"
FOREIGN = ("ee" * 32, 7, "f" * 32, "signed", 1)


def _rows(scanner):
    return sorted(tuple(r) for r in scanner.store.db.execute(
        "SELECT txid,vout,token,state,created FROM reservations"))


class _Chain:
    def __init__(self, block):
        self.block = block

    def attest(self):
        return None

    def call(self, method, params=None):
        if method == "getbestblockhash":
            return self.block["hash"]
        if method == "getblockcount":
            return 1
        if method == "getblockhash":
            return GENESIS if params[0] == 0 else self.block["hash"]
        if method == "getblock":
            return self.block
        raise ValueError("CUR001_SYNTHETIC_RPC_METHOD_DENIED")


class _Vault:
    def __init__(self, keys, fail=False):
        self.keys, self.fail, self.saved = keys, fail, []
        self.anchor = SimpleNamespace(wallet_id="d" * 32, value=(1, "a" * 64),
                                      lease=lambda: nullcontext())
        self.anchor.read = lambda: self.anchor.value
        self._expected = self.anchor.value

    def save(self, keys, scanner, password):
        if self.fail:
            raise OSError("CUR001_PUBLIC_SAVE_FAULT")
        self.saved.append(_rows(scanner))
        self.anchor.value = (self.anchor.value[0] + 1,
                             sha256(scanner.checkpoint(password)).hexdigest())
        self._expected = self.anchor.value


class FailedPrepareDraftRelease(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="cur001-")
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name)
        self.keys = Bip39Regtest12Keys(Mnemonic("english").to_mnemonic(bytes(16)),
                                       source=SOURCE, authorized_disposable=True)
        recipient = Bip39Regtest12Keys(Mnemonic("english").to_mnemonic(bytes([1] * 16)),
                                       source=SOURCE, authorized_disposable=True)
        self.addCleanup(self.keys.close)
        self.addCleanup(recipient.close)
        self.code = recipient.accounts()[0].payment_code()
        funding = Input("05" * 32, 0, p2wpkh(91), witness=(bytes(72), pub(91)), secret=91)
        output = send([funding], [self.keys.accounts()[0].payment_code()])[0]
        block = {"height": 1, "hash": sha256(b"cur001 synthetic chain").hexdigest(),
                 "previousblockhash": GENESIS, "tx": [{
                     "txid": "ab" * 32,
                     "vin": [{"txid": funding.txid, "vout": 0, "scriptSig": {"hex": ""},
                              "txinwitness": [v.hex() for v in funding.witness],
                              "prevout": {"scriptPubKey": {"hex": funding.script.hex()}}}],
                     "vout": [{"n": 0, "value": 0.001,
                               "scriptPubKey": {"hex": (b"\x51\x20" + output).hex()}}]}]}
        self.scanner = Scanner(self.path / "runtime.sqlite", self.keys.accounts())
        self.addCleanup(self.scanner.close)
        self.scanner.sync(_Chain(block))
        self.scanner.assert_current()
        # An unrelated irreversible reservation must never be touched.
        self.scanner.store.db.execute("INSERT INTO reservations VALUES(?,?,?,?,?)", FOREIGN)

    def _session(self, q06=True, fail_save=False):
        from wam_regtest.bip39_spend_session import Q06OwnedSpendSession
        from wam_regtest.wallet_session import WalletSession
        self.vault = _Vault(self.keys, fail_save)
        if q06:
            owner = SimpleNamespace(core=self.path, directory=self.path, cli=self.path,
                                    receipt={"wamd_sha256": "0" * 64})
            guard = SimpleNamespace(check=lambda: None, close=lambda: None)
            session = Q06OwnedSpendSession(owner, SOURCE, self.keys, self.scanner, guard,
                                           self.vault, PASSWORD)
            p = patch("wam_regtest.bip39_spend_session._owned")
            p.start()
            self.addCleanup(p.stop)
        else:
            session = WalletSession(self.path, self.path, SOURCE, self.keys, self.scanner,
                                    self.vault, PASSWORD, None)
        session.snapshot = lambda *a: None
        session._rpc = lambda: None
        return session

    def _prepare_fails(self, session, side_effect=ValueError("CHANGE_POLICY")):
        from wam_regtest.wallet_session import WalletSessionError
        with patch.object(Signer, "prepare", side_effect=side_effect):
            with self.assertRaises(WalletSessionError) as caught:
                session.prepare(self.code, 50_000, 1000)
        self.assertEqual(caught.exception.args, ("WALLET_PREPARE_DENIED",))

    def test_signer_prepare_failure_releases_only_its_new_draft(self):
        for q06 in (True, False):
            with self.subTest(q06=q06):
                self.setUp()
                session = self._session(q06)
                self._prepare_fails(session)
                self.assertEqual(_rows(self.scanner), [FOREIGN])
                self.assertEqual(self.vault.saved, [])  # durable state never had it
                self.assertIsNone(session._prepared)
                self.assertFalse(session.faulted)
                # The released coin can be prepared again normally.
                review = session.prepare(self.code, 50_000, 1000)
                self.assertEqual(review.input_count, 1)
                self.assertEqual({r[3] for r in _rows(self.scanner)}, {"draft", "signed"})

    def test_no_signature_or_irreversible_state_after_failed_prepare(self):
        session = self._session()
        with patch.object(Signer, "sign") as sign, patch.object(Wallet, "mark_signed") as mark:
            self._prepare_fails(session)
        sign.assert_not_called()
        mark.assert_not_called()
        self.assertIsNone(session._signed)

    def test_persistence_failure_after_prepare_retains_draft_and_latches(self):
        from wam_regtest.wallet_session import WalletSessionError
        session = self._session(fail_save=True)
        with self.assertRaisesRegex(WalletSessionError, "WALLET_PREPARE_DENIED"):
            session.prepare(self.code, 50_000, 1000)
        self.assertTrue(session.faulted)
        self.assertEqual({r[3] for r in _rows(self.scanner)}, {"draft", "signed"})

    def test_release_failure_latches_and_keeps_rows(self):
        session = self._session()
        with patch.object(Wallet, "release_draft",
                          side_effect=sqlite3.OperationalError("database is locked")):
            self._prepare_fails(session)
        self.assertTrue(session.faulted)
        self.assertEqual({r[3] for r in _rows(self.scanner)}, {"draft", "signed"})

    def test_rows_no_longer_all_draft_are_never_released(self):
        db = self.scanner.store.db

        def concurrent_change(proposal):
            db.execute("UPDATE reservations SET state='signed' WHERE token=?", (proposal.token,))
            raise ValueError("ACCOUNT_MISMATCH")
        session = self._session()
        self._prepare_fails(session, concurrent_change)
        self.assertTrue(session.faulted)
        self.assertEqual({r[3] for r in _rows(self.scanner)}, {"signed"})
        self.assertEqual(len(_rows(self.scanner)), 2)

    def test_concurrent_writer_lock_refuses_release_and_latches(self):
        other = sqlite3.connect(self.scanner.store.path, timeout=0, isolation_level=None)
        self.addCleanup(other.close)

        def locked(proposal):
            other.execute("BEGIN IMMEDIATE")
            raise ValueError("CHANGE_POLICY")
        session = self._session()
        self.scanner.store.db.execute("PRAGMA busy_timeout=50")
        try:
            self._prepare_fails(session, locked)
        finally:
            other.execute("ROLLBACK")
        self.assertTrue(session.faulted)
        self.assertEqual({r[3] for r in _rows(self.scanner)}, {"draft", "signed"})

    def test_duplicate_cancel_after_automatic_release_is_refused(self):
        from wam_regtest.wallet_session import WalletSessionError
        session = self._session(q06=False)
        self._prepare_fails(session)
        with self.assertRaisesRegex(WalletSessionError, "ONLY_UNSIGNED_DRAFT_CAN_CANCEL"):
            session.cancel()
        self.assertEqual(_rows(self.scanner), [FOREIGN])

    def test_restart_from_checkpoint_shows_no_orphan_draft(self):
        session = self._session()
        session.snapshot = lambda *a: None
        session._save()  # durable checkpoint before the failing prepare
        self._prepare_fails(session)
        restored = Scanner(self.path / "restored.sqlite", self.keys.accounts())
        self.addCleanup(restored.close)
        restored.restore(self.scanner.checkpoint(PASSWORD), PASSWORD)
        self.assertEqual(_rows(restored), [FOREIGN])
        self.assertEqual(self.vault.saved, [[FOREIGN]])


if __name__ == "__main__":
    unittest.main()
