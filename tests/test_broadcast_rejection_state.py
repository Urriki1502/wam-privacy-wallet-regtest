"""CUR-004: a definitive pre-send mempool rejection must stay 'signed'.

Real pinned-WSP scanner, PSBT, signer and reservations; synthetic RPC and
anchored-vault doubles only.  A transaction this wallet never handed to
sendrawtransaction must not be recorded as network-uncertain, while every
outcome after the send boundary stays 'uncertain'.  Nothing is released,
retried or rebroadcast automatically.
"""
from contextlib import nullcontext
from hashlib import sha256
import importlib.util
from pathlib import Path
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
from wam_sp.wallet import Intent, Wallet
from wam_sp.watcher import GENESIS

SOURCE = Path(importlib.util.find_spec("wam_sp").origin).resolve().parents[2]
PASSWORD = b"cur-004 disposable public test password"


class Crash(BaseException):
    """Process death at a cut point: no except-Exception handler may run."""


def _states(rows):
    return {value[1] for value in rows.values()}


def _reservations(scanner):
    return {(t, v): (token, state, created) for t, v, token, state, created in
            scanner.store.db.execute("SELECT txid,vout,token,state,created FROM reservations")}


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
        raise ValueError("CUR004_SYNTHETIC_RPC_METHOD_DENIED")


class _Vault:
    """Anchored checkpoint double: `saved` is the durable state sequence."""

    def __init__(self, keys, crash_on=None):
        self.keys, self.crash_on, self.saved = keys, crash_on, []
        self.anchor = SimpleNamespace(wallet_id="d" * 32, value=(1, "a" * 64),
                                      lease=lambda: nullcontext())
        self.anchor.read = lambda: self.anchor.value
        self._expected = self.anchor.value

    def save(self, keys, scanner, password):
        if password != PASSWORD or keys is not self.keys:
            raise ValueError("CUR004_BAD_CUSTODY")
        if self.crash_on is not None and len(self.saved) + 1 == self.crash_on:
            raise Crash()
        self.saved.append(_reservations(scanner))
        self.anchor.value = (self.anchor.value[0] + 1,
                             sha256(scanner.checkpoint(password)).hexdigest())
        self._expected = self.anchor.value


class BroadcastRejectionState(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="cur004-")
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
        block = {"height": 1, "hash": sha256(b"cur004 synthetic chain").hexdigest(),
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
        self.coin = self.scanner.coins()[0]
        self.tip = self.scanner.store.tip()[1]
        self.calls = []

    def _rpc(self, accept=(True,), send=None):
        test, accepts = self, list(accept)

        class Rpc:
            def attest(self):
                return None

            def call(self, method, params=None):
                if method == "getbestblockhash":
                    return test.tip
                if method == "gettxout":
                    return {"value": 0.001,
                            "scriptPubKey": {"hex": "5120" + test.coin["public_key"]}}
                test.calls.append((method, len(test.vault.saved),
                                   _states(_reservations(test.scanner))))
                if method == "testmempoolaccept":
                    result = accepts.pop(0) if len(accepts) > 1 else accepts[0]
                    if isinstance(result, BaseException):
                        raise result
                    return [{"allowed": result, "reject-reason": "min relay fee not met"}]
                if method == "sendrawtransaction":
                    if send is None:
                        return PSBT.decode(test.signed).txid()
                    if isinstance(send, BaseException):
                        raise send
                    return send
                raise ValueError("CUR004_RPC_METHOD_DENIED")
        return Rpc()

    def _q06(self, rpc, crash_on=None):
        from wam_regtest.bip39_spend_session import Q06OwnedSpendSession
        from wam_regtest.wallet_session import WalletSession
        self.vault = _Vault(self.keys, crash_on)
        owner = SimpleNamespace(core=self.path, directory=self.path, cli=self.path,
                                receipt={"wamd_sha256": "0" * 64})
        guard = SimpleNamespace(check=lambda: None, close=lambda: None)
        session = Q06OwnedSpendSession(owner, SOURCE, self.keys, self.scanner, guard,
                                       self.vault, PASSWORD)
        retained = patch.object(session, "_retain_signed_payment")
        self.retained = retained.start()
        self.addCleanup(retained.stop)
        for p in (patch("wam_regtest.bip39_spend_session._owned"),
                  patch.object(WalletSession, "_rpc", lambda _self: rpc)):
            p.start()
            self.addCleanup(p.stop)
        session.snapshot = lambda *a: None
        review = session.prepare(self.code, 50_000, 1000)
        session.sign(review.commitment)
        self.signed = session._signed
        self.token = session._prepared.proposal.token
        self.assertEqual(_states(self.vault.saved[-1]), {"signed"})
        return session, review

    def _stages(self):
        return [c.args[0] for c in self.retained.call_args_list]

    def test_definitive_pre_send_rejection_stays_signed_and_is_never_sent(self):
        from wam_regtest.wallet_session import WalletSessionError
        session, review = self._q06(self._rpc(accept=(False,)))
        with self.assertRaises(WalletSessionError) as caught:
            session.broadcast(review.commitment)
        self.assertEqual(caught.exception.args, ("WALLET_BROADCAST_REJECTED_LOCK_RETAINED",))
        self.assertNotIn("sendrawtransaction", [c[0] for c in self.calls])
        self.assertEqual(_states(_reservations(self.scanner)), {"signed"})
        self.assertEqual(len(self.vault.saved), 2)  # draft, signed; never 'uncertain'
        self.assertEqual(_states(self.vault.saved[-1]), {"signed"})
        self.assertEqual(self._stages(), ["signed"])  # no 'uncertain' evidence
        self.assertTrue(session.faulted)
        self.assertIsNone(session._signed)
        with self.assertRaisesRegex(ValueError, "RESERVATION_NOT_DRAFT"):
            Wallet(self.scanner).release_draft(self.token)
        before = list(self.calls)
        with self.assertRaises(WalletSessionError):
            session.broadcast(review.commitment)  # no automatic or repeated submission
        self.assertEqual(self.calls, before)

    def test_post_accept_transport_loss_is_uncertain_and_durable_before_send(self):
        from wam_regtest.wallet_session import WalletSessionError
        session, review = self._q06(self._rpc(send=RuntimeError("PUBLIC_TRANSPORT_LOSS")))
        with self.assertRaises(WalletSessionError) as caught:
            session.broadcast(review.commitment)
        self.assertEqual(caught.exception.args, ("WALLET_BROADCAST_UNCERTAIN_LOCK_RETAINED",))
        sends = [c for c in self.calls if c[0] == "sendrawtransaction"]
        self.assertEqual(len(sends), 1)
        # The durable anchored state was already 'uncertain' when send ran.
        self.assertEqual(sends[0][1], 3)
        self.assertEqual(_states(self.vault.saved[2]), {"uncertain"})
        self.assertEqual(_states(_reservations(self.scanner)), {"uncertain"})
        self.assertEqual(self._stages(), ["signed", "uncertain"])
        self.assertTrue(session.faulted)

    def test_wrong_txid_reply_after_send_is_uncertain(self):
        from wam_regtest.wallet_session import WalletSessionError
        session, review = self._q06(self._rpc(send="ff" * 32))
        with self.assertRaisesRegex(WalletSessionError, "BROADCAST_UNCERTAIN_LOCK_RETAINED"):
            session.broadcast(review.commitment)
        self.assertEqual(_states(self.vault.saved[-1]), {"uncertain"})

    def test_pre_send_verification_failure_is_not_submitted_and_stays_signed(self):
        from wam_regtest.wallet_session import WalletSessionError
        session, review = self._q06(self._rpc(accept=(RuntimeError("PUBLIC_RPC_LOSS"),)))
        with self.assertRaises(WalletSessionError) as caught:
            session.broadcast(review.commitment)
        self.assertEqual(caught.exception.args,
                         ("WALLET_BROADCAST_NOT_SUBMITTED_LOCK_RETAINED",))
        self.assertNotIn("sendrawtransaction", [c[0] for c in self.calls])
        self.assertEqual(_states(self.vault.saved[-1]), {"signed"})
        self.assertEqual(len(self.vault.saved), 2)
        self.assertTrue(session.faulted)

    def test_rejection_observed_only_after_uncertain_save_stays_uncertain(self):
        """A later race inside WSP is never relabelled after durable uncertainty."""
        from wam_regtest.wallet_session import WalletSessionError
        session, review = self._q06(self._rpc(accept=(True, False)))
        with self.assertRaisesRegex(WalletSessionError, "BROADCAST_UNCERTAIN_LOCK_RETAINED"):
            session.broadcast(review.commitment)
        self.assertNotIn("sendrawtransaction", [c[0] for c in self.calls])
        self.assertEqual(_states(self.vault.saved[-1]), {"uncertain"})

    def test_successful_broadcast_unchanged(self):
        session, review = self._q06(self._rpc())
        txid = session.broadcast(review.commitment)
        self.assertEqual(txid, PSBT.decode(self.signed).txid())
        self.assertEqual([_states(s) for s in self.vault.saved],
                         [{"draft"}, {"signed"}, {"uncertain"}, {"broadcast"}])
        self.assertEqual(self._stages(), ["signed", "uncertain", "broadcast"])
        self.assertFalse(session.faulted)

    def test_crash_cuts_leave_a_conservative_durable_state(self):
        cases = (
            ("preflight", dict(accept=(Crash(),)), None, {"signed"}, 0),
            ("send", dict(send=Crash()), None, {"uncertain"}, 1),
            ("final-save", {}, 4, {"uncertain"}, 1),
            ("uncertain-save", {}, 3, {"signed"}, 0),
        )
        for name, rpc, crash_on, durable, sends in cases:
            with self.subTest(cut=name):
                self.setUp()
                session, review = self._q06(self._rpc(**rpc), crash_on=crash_on)
                with self.assertRaises(Crash):
                    session.broadcast(review.commitment)
                self.assertEqual(_states(self.vault.saved[-1]), durable)
                self.assertEqual(
                    len([c for c in self.calls if c[0] == "sendrawtransaction"]), sends)

    def test_base_session_rejection_stays_signed(self):
        """Linux headless/base frontend uses the same WalletSession engine."""
        from wam_regtest.wallet_session import WalletSession, WalletSessionError
        rpc = self._rpc(accept=(False,))
        self.vault = _Vault(self.keys)
        session = WalletSession(self.path, self.path, SOURCE, self.keys, self.scanner,
                                self.vault, PASSWORD, None)
        with patch.object(WalletSession, "_rpc", lambda _self: rpc):
            session.snapshot = lambda *a: None
            review = session.prepare(self.code, 50_000, 1000)
            session.sign(review.commitment)
            self.signed = session._signed
            with self.assertRaisesRegex(WalletSessionError, "BROADCAST_REJECTED_LOCK_RETAINED"):
                session.broadcast(review.commitment)
        self.assertEqual(_states(self.vault.saved[-1]), {"signed"})
        self.assertNotIn("sendrawtransaction", [c[0] for c in self.calls])

    def test_gui_maps_new_codes_to_fixed_public_text(self):
        from wam_regtest.gui_errors import error_text, operation_error
        from wam_regtest.wallet_session import WalletSessionError
        for code in ("WALLET_BROADCAST_REJECTED_LOCK_RETAINED",
                     "WALLET_BROADCAST_NOT_SUBMITTED_LOCK_RETAINED"):
            self.assertEqual(operation_error("broadcast", WalletSessionError(code)), code)
            text = error_text(code)
            self.assertIn("not", text.lower())
            self.assertNotIn("may have accepted", text)


if __name__ == "__main__":
    unittest.main()
