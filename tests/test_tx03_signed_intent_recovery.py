"""TX-03: signed-intent recovery, Stage A (read-only) and Stage B (explicit resume).

Real pinned-WSP scanner/PSBT/signer/reservations and real encrypted
create-only payment evidence (macOS native storage); synthetic Core RPC and
anchored-vault doubles. Crash cuts use BaseException so no handler runs.
No path re-signs, retries automatically, or releases a signed/uncertain row.
"""
from contextlib import nullcontext
from hashlib import sha256
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from mnemonic import Mnemonic
from wam_regtest.bip39_12 import Bip39Regtest12Keys
from wam_sp.core import Input, pub, send
from wam_sp.psbt import PSBT
from wam_sp.scanner import Scanner
from wam_sp.transaction import p2wpkh
from wam_sp.wallet import Signer, Wallet
from wam_sp.watcher import GENESIS

SOURCE = Path(importlib.util.find_spec("wam_sp").origin).resolve().parents[2]
PASSWORD = b"tx03 disposable public test password"
RESUMABLE = ("SIGNED_NOT_SUBMITTED_RESUMABLE", "UNCERTAIN_NOT_OBSERVED_RESUMABLE")


class Crash(BaseException):
    pass


def _states(scanner):
    return {r[0] for r in scanner.store.db.execute("SELECT state FROM reservations")}


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
        raise ValueError("TX03_SYNTHETIC_RPC_METHOD_DENIED")


class _Core:
    """Synthetic Core: a mempool set, spent outpoints and a send behaviour."""

    def __init__(self, test):
        self.test, self.mempool, self.spent = test, set(), set()
        self.accept, self.send, self.calls = True, None, []

    def attest(self):
        return None

    def _call(self, method, params):
        if method == "getrawmempool":
            return sorted(self.mempool)
        raise ValueError("TX03_RPC_DENIED")

    def call(self, method, params=None):
        if method == "getbestblockhash":
            return self.test.tip
        if method == "gettxout":
            if (params[0], params[1]) in self.spent:
                return None
            return {"value": 0.001, "scriptPubKey": {"hex": "5120" + self.test.coin["public_key"]}}
        self.calls.append(method)
        if method == "testmempoolaccept":
            if isinstance(self.accept, BaseException):
                raise self.accept
            return [{"allowed": self.accept}]
        if method == "sendrawtransaction":
            raw = PSBT.decode(self.test.signed)
            if isinstance(self.send, BaseException):
                if getattr(self.send, "reached_core", False):
                    self.mempool.add(raw.txid())
                raise self.send
            self.mempool.add(raw.txid())
            return raw.txid()
        raise ValueError("TX03_RPC_DENIED")


class _Vault:
    def __init__(self, keys, crash_on=None):
        self.keys, self.crash_on, self.saved, self.cipher = keys, crash_on, [], None
        self.anchor = SimpleNamespace(wallet_id="d" * 32, value=(1, "a" * 64),
                                      lease=lambda: nullcontext())
        self.anchor.read = lambda: self.anchor.value
        self._expected = self.anchor.value

    def save(self, keys, scanner, password):
        if self.crash_on is not None and len(self.saved) + 1 == self.crash_on:
            raise Crash()
        self.saved.append(_states(scanner))
        self.cipher = scanner.checkpoint(password)
        self.anchor.value = (self.anchor.value[0] + 1, sha256(self.cipher).hexdigest())
        self._expected = self.anchor.value


@unittest.skipUnless(sys.platform == "darwin", "native macOS encrypted evidence storage")
class SignedIntentRecovery(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="tx03-")
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name).resolve()
        self.keys = Bip39Regtest12Keys(Mnemonic("english").to_mnemonic(bytes(16)),
                                       source=SOURCE, authorized_disposable=True)
        recipient = Bip39Regtest12Keys(Mnemonic("english").to_mnemonic(bytes([1] * 16)),
                                       source=SOURCE, authorized_disposable=True)
        self.addCleanup(self.keys.close)
        self.addCleanup(recipient.close)
        self.code = recipient.accounts()[0].payment_code()
        funding = Input("05" * 32, 0, p2wpkh(91), witness=(bytes(72), pub(91)), secret=91)
        output = send([funding], [self.keys.accounts()[0].payment_code()])[0]
        self.block = {"height": 1, "hash": sha256(b"tx03 synthetic chain").hexdigest(),
                      "previousblockhash": GENESIS, "tx": [{
                          "txid": "ab" * 32,
                          "vin": [{"txid": funding.txid, "vout": 0, "scriptSig": {"hex": ""},
                                   "txinwitness": [v.hex() for v in funding.witness],
                                   "prevout": {"scriptPubKey": {"hex": funding.script.hex()}}}],
                          "vout": [{"n": 0, "value": 0.001,
                                    "scriptPubKey": {"hex": (b"\x51\x20" + output).hex()}}]}]}
        self.scanner = self._scanner("runtime.sqlite")
        self.coin = self.scanner.coins()[0]
        self.tip = self.scanner.store.tip()[1]
        self.core = _Core(self)
        for p in (patch("wam_regtest.bip39_spend_session._owned"),
                  patch("wam_regtest.bip39_spend_session._owner_binding",
                        return_value="public-test-owner-binding")):
            p.start()
            self.addCleanup(p.stop)

    def _scanner(self, name, cipher=None):
        scanner = Scanner(self.path / name, self.keys.accounts())
        self.addCleanup(scanner.close)
        if cipher is not None:
            scanner.restore(cipher, PASSWORD)
        scanner.sync(_Chain(self.block))
        scanner.assert_current()
        return scanner

    def _session(self, scanner, vault):
        from wam_regtest.bip39_spend_session import Q06OwnedSpendSession
        from wam_regtest.wallet_session import WalletSession
        owner = SimpleNamespace(core=self.path, directory=self.path, cli=self.path,
                                receipt={"wamd_sha256": "0" * 64})
        guard = SimpleNamespace(check=lambda: None, close=lambda: None)
        session = Q06OwnedSpendSession(owner, SOURCE, self.keys, scanner, guard, vault, PASSWORD)
        p = patch.object(WalletSession, "_rpc", lambda _self: self.core)
        p.start()
        self.addCleanup(p.stop)
        session.snapshot = lambda *a, **k: SimpleNamespace(height=1, tip=self.tip)
        return session

    def _signed_session(self, crash_on=None):
        self.vault = _Vault(self.keys, crash_on)
        session = self._session(self.scanner, self.vault)
        review = session.prepare(self.code, 50_000, 1000)
        session.sign(review.commitment)
        self.signed = session._signed
        self.txid = PSBT.decode(self.signed).txid()
        self.token = session._prepared.proposal.token
        return session, review

    def _restart(self):
        """Crash recovery: fresh runtime restored from the last anchored checkpoint."""
        scanner = self._scanner("restart-%d.sqlite" % len(self.vault.saved), self.vault.cipher)
        self.vault.crash_on = None
        return self._session(scanner, self.vault)

    def _item(self, session):
        status = session.signed_intent_status()
        self.assertFalse(status["write_attempted"] or status["automatic_resume"]
                         or status["abandon_available"])
        return status["intents"]

    # ---- crash-cut matrix -------------------------------------------------
    def test_crash_before_signed_publication_leaves_only_a_draft(self):
        self.vault = _Vault(self.keys, crash_on=2)  # 1=draft save, 2=signed save
        session = self._session(self.scanner, self.vault)
        review = session.prepare(self.code, 50_000, 1000)
        with self.assertRaises(Crash):
            session.sign(review.commitment)
        restarted = self._restart()
        self.assertEqual(self.vault.saved[-1], {"draft"})
        self.assertEqual(self._item(restarted), [])  # nothing irreversible to recover

    def test_crash_after_signed_publication_before_crypto_needs_operator_review(self):
        session, review = None, None
        self.vault = _Vault(self.keys)
        session = self._session(self.scanner, self.vault)
        review = session.prepare(self.code, 50_000, 1000)
        with patch.object(Signer, "sign", side_effect=Crash()), self.assertRaises(Crash):
            session.sign(review.commitment)
        restarted = self._restart()
        [item] = self._item(restarted)
        self.assertEqual((item["state"], item["classification"]),
                         ("signed", "OPERATOR_REVIEW_SIGNED_EVIDENCE_MISSING"))
        from wam_regtest.bip39_spend_session import Q06SpendSessionError
        with self.assertRaisesRegex(Q06SpendSessionError, "NOT_ELIGIBLE"):
            restarted.resume_signed_intent(item["token"], "0" * 64, approved=True)
        self.assertEqual(self.core.calls, [])

    def test_crash_after_signing_before_evidence_needs_operator_review(self):
        self.vault = _Vault(self.keys)
        session = self._session(self.scanner, self.vault)
        review = session.prepare(self.code, 50_000, 1000)
        with patch.object(type(session), "_retain_signed_payment", side_effect=Crash()), \
                self.assertRaises(Crash):
            session.sign(review.commitment)
        [item] = self._item(self._restart())
        self.assertEqual(item["classification"], "OPERATOR_REVIEW_SIGNED_EVIDENCE_MISSING")

    def test_after_evidence_signed_not_submitted_resumes_exact_tx_once(self):
        self._signed_session()
        restarted = self._restart()
        [item] = self._item(restarted)
        self.assertEqual((item["classification"], item["txid"], item["atoms"], item["fee"]),
                         ("SIGNED_NOT_SUBMITTED_RESUMABLE", self.txid, 50_000, 1000))
        result = restarted.resume_signed_intent(self.token, self.txid, approved=True)
        self.assertEqual((result["txid"], result["resigned"], result["automatic"]),
                         (self.txid, False, False))
        self.assertEqual(self.vault.saved[-2:], [{"uncertain"}, {"broadcast"}])
        self.assertEqual(self.core.calls.count("sendrawtransaction"), 1)
        self.assertEqual(restarted._q06_pending_confirm, self.txid)
        # Repeated resume is refused; nothing is sent again.
        restarted._q06_pending_confirm = None
        from wam_regtest.bip39_spend_session import Q06SpendSessionError
        with self.assertRaisesRegex(Q06SpendSessionError, "NOT_ELIGIBLE"):
            restarted.resume_signed_intent(self.token, self.txid, approved=True)
        self.assertEqual(self.core.calls.count("sendrawtransaction"), 1)

    def test_crash_before_broadcast_preflight_is_still_resumable(self):
        session, review = self._signed_session()
        self.core.accept = Crash()
        with self.assertRaises(Crash):
            session.broadcast(review.commitment)
        self.core.accept = True
        restarted = self._restart()
        self.assertEqual(self.vault.saved[-1], {"signed"})
        [item] = self._item(restarted)
        self.assertEqual(item["classification"], "SIGNED_NOT_SUBMITTED_RESUMABLE")

    def test_crash_during_submission_before_core_is_uncertain_and_resumable(self):
        session, review = self._signed_session()
        self.core.send = Crash()
        with self.assertRaises(Crash):
            session.broadcast(review.commitment)
        self.core.send = None
        restarted = self._restart()
        self.assertEqual(self.vault.saved[-1], {"uncertain"})
        [item] = self._item(restarted)
        self.assertEqual(item["classification"], "UNCERTAIN_NOT_OBSERVED_RESUMABLE")
        restarted.resume_signed_intent(self.token, self.txid, approved=True)
        self.assertEqual(self.vault.saved[-1], {"broadcast"})

    def test_response_lost_after_submission_is_observed_not_resent(self):
        session, review = self._signed_session()
        lost = RuntimeError("PUBLIC_RESPONSE_LOST")
        lost.reached_core = True
        self.core.send = lost
        from wam_regtest.wallet_session import WalletSessionError
        with self.assertRaisesRegex(WalletSessionError, "UNCERTAIN"):
            session.broadcast(review.commitment)
        restarted = self._restart()
        [item] = self._item(restarted)
        self.assertEqual(item["classification"], "IN_MEMPOOL_AWAITING_CONFIRMATION")
        from wam_regtest.bip39_spend_session import Q06SpendSessionError
        with self.assertRaisesRegex(Q06SpendSessionError, "NOT_ELIGIBLE"):
            restarted.resume_signed_intent(self.token, self.txid, approved=True)
        self.assertEqual(self.core.calls.count("sendrawtransaction"), 1)
        self.assertEqual(_states(restarted.scanner), {"uncertain"})

    def test_reorg_or_conflict_spending_an_input_is_never_resumable(self):
        session, review = self._signed_session()
        self.core.spent.add((self.coin["txid"], self.coin["vout"]))
        restarted = self._restart()
        [item] = self._item(restarted)
        self.assertEqual(item["classification"], "OPERATOR_REVIEW_INPUT_SPENT_OR_CONFLICTED")
        from wam_regtest.bip39_spend_session import Q06SpendSessionError
        with self.assertRaisesRegex(Q06SpendSessionError, "NOT_ELIGIBLE"):
            restarted.resume_signed_intent(self.token, self.txid, approved=True)
        self.assertEqual(_states(restarted.scanner), {"signed"})

    def test_definitive_rejection_on_resume_keeps_signed_and_sends_nothing(self):
        self._signed_session()
        restarted = self._restart()
        self.core.accept = False
        from wam_regtest.wallet_session import WalletSessionError
        with self.assertRaisesRegex(WalletSessionError, "BROADCAST_REJECTED_LOCK_RETAINED"):
            restarted.resume_signed_intent(self.token, self.txid, approved=True)
        self.assertNotIn("sendrawtransaction", self.core.calls)
        self.assertEqual(self.vault.saved[-1], {"signed"})
        with self.assertRaisesRegex(ValueError, "RESERVATION_NOT_DRAFT"):
            Wallet(restarted.scanner).release_draft(self.token)

    def test_unauthorized_or_mismatched_resume_is_refused_without_rpc_writes(self):
        session, review = self._signed_session()
        from wam_regtest.bip39_spend_session import Q06SpendSessionError
        # Active in-memory payment: refused (use the normal Broadcast instead).
        with self.assertRaisesRegex(Q06SpendSessionError, "SESSION_NOT_IDLE"):
            session.resume_signed_intent(self.token, self.txid, approved=True)
        restarted = self._restart()
        for args, kwargs, code in (
                ((self.token, self.txid), {}, "EXPLICIT_APPROVAL_REQUIRED"),
                ((self.token, self.txid), {"approved": "yes"}, "EXPLICIT_APPROVAL_REQUIRED"),
                ((self.token, "f" * 64), {"approved": True}, "NOT_ELIGIBLE"),
                (("e" * 32, self.txid), {"approved": True}, "NOT_ELIGIBLE"),
                ((self.token.upper(), self.txid), {"approved": True}, "EXPLICIT_APPROVAL_REQUIRED")):
            with self.subTest(code=code, args=args):
                with self.assertRaisesRegex(Q06SpendSessionError, code):
                    restarted.resume_signed_intent(*args, **kwargs)
        restarted.faulted = True
        with self.assertRaisesRegex(Q06SpendSessionError, "SESSION_NOT_IDLE"):
            restarted.resume_signed_intent(self.token, self.txid, approved=True)
        self.assertEqual(self.core.calls, [])
        self.assertEqual(_states(restarted.scanner), {"signed"})

    def test_tampered_evidence_is_not_an_authority(self):
        self._signed_session()
        evidence = self.path / "q06-payment-evidence" / (self.token + "-signed.enc")
        data = bytearray(evidence.read_bytes())
        data[-1] ^= 1
        evidence.unlink()
        evidence.write_bytes(bytes(data))
        evidence.chmod(0o600)
        [item] = self._item(self._restart())
        self.assertEqual(item["classification"], "OPERATOR_REVIEW_EVIDENCE_INVALID")

    def test_no_abandon_or_release_api_exists(self):
        from wam_regtest.bip39_spend_session import Q06OwnedSpendSession
        # Only the CUR-001 never-reviewed DRAFT release exists; nothing for signed rows.
        self.assertEqual([n for n in dir(Q06OwnedSpendSession)
                          if "abandon" in n or "release" in n], ["_release_unreviewed_draft"])


class BackendWiring(unittest.TestCase):
    def test_executor_and_backend_accept_only_exact_arguments(self):
        from wam_regtest.wallet_executor import COMMANDS
        from wam_regtest.bip39_owner_backend import Bip39ReadOnlyBackend, Q06ReadOnlyError
        self.assertTrue({"intent_status", "resume_intent"} <= COMMANDS)
        backend = object.__new__(Bip39ReadOnlyBackend)
        backend._spend_session = None
        backend.shared_profile = None
        backend.public_state = lambda: {"faulted": False}
        for action, args in (("intent_status", ()), ("resume_intent", ("a" * 32, "b" * 64, True)),
                             ("resume_intent", ("a" * 32, "b" * 64, False)),
                             ("resume_intent", ("a" * 32, "b" * 64))):
            with self.subTest(action=action, args=args), self.assertRaises(Q06ReadOnlyError):
                Bip39ReadOnlyBackend.execute(backend, action, args, {})


if __name__ == "__main__":
    unittest.main()
