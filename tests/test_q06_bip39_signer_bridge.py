"""Q06: pinned WSP BIP39 signer/PSBT compatibility, source-only.

No signed WAM Core, no packaged GUI, no Send authorization and no claim of
release acceptance. An irreversible reservation must remain locked across
a scanner checkpoint, including an ambiguous network broadcast.
"""
import importlib.util
from pathlib import Path
from hashlib import sha256
import tempfile
import unittest

from mnemonic import Mnemonic
from wam_regtest.bip39_12 import Bip39Regtest12Keys
from wam_regtest.bip39_scanner_checkpoint import require_irreversible_preserved
from wam_sp.core import Input, pub, send
from wam_sp.transaction import p2wpkh
from wam_sp.scanner import Scanner
from wam_sp.wallet import Wallet, Signer, Intent
from wam_sp.psbt import PSBT
from wam_sp.watcher import GENESIS

SOURCE = Path(importlib.util.find_spec("wam_sp").origin).resolve().parents[2]
PASSWORD = b"q06 disposable source scan checkpoint test"


def _reservations(scanner):
    return {(txid, vout): (token, state, created)
            for txid, vout, token, state, created in scanner.store.db.execute(
                "SELECT txid,vout,token,state,created FROM reservations")}


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
        raise ValueError("Q06_SYNTHETIC_RPC_METHOD_DENIED")


class Q06Bip39SignerBridgeContracts(unittest.TestCase):
    @unittest.skipUnless(__import__('sys').platform == 'darwin', 'native macOS private storage')
    def test_signed_evidence_is_encrypted_create_only_and_password_authenticated(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from wam_regtest.bip39_spend_session import Q06OwnedSpendSession
        from wam_regtest.wallet_session import PaymentReview
        from wam_regtest import custody
        from wam_sp.keystore import unseal
        import json
        prepared = self.signer.prepare(self.proposal)
        signed = self.signer.sign(prepared, (self.intent,), 1000)
        session = object.__new__(Q06OwnedSpendSession)
        session._q06_owner = SimpleNamespace(directory=self.path.resolve())
        session._q06_guard = SimpleNamespace(check=lambda: None)
        session._prepared = prepared
        session._signed = signed
        session._review = PaymentReview(self.intent.code, 50000, 1000, 49000, 1, 'a'*64)
        session.ring = self.keys
        session._password = PASSWORD
        session.faulted = session._q06_uncertain = False
        with (patch('wam_regtest.bip39_spend_session._owned'),
              patch('wam_regtest.bip39_spend_session._owner_binding', return_value='public-test-binding')):
            session._retain_signed_payment('signed')
            directory = self.path.resolve() / 'q06-payment-evidence'
            name = prepared.proposal.token+'-signed.enc'
            ciphertext = custody.storage().read(directory, name)
            data = json.loads(unseal(ciphertext, PASSWORD, b'recovery'))
            self.assertTrue(data['signed_psbt'] == signed.hex())
            self.assertTrue(data['txid'] == PSBT.decode(signed).txid())
            with self.assertRaises(ValueError):
                unseal(ciphertext, b'wrong-disposable-password', b'recovery')
            with self.assertRaises(ValueError):
                session._retain_signed_payment('signed')
            self.assertTrue(session.faulted)
            self.assertTrue(custody.storage().read(directory, name) == ciphertext)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="q06-signer-source-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.keys = Bip39Regtest12Keys(
            Mnemonic("english").to_mnemonic(bytes(16)),
            source=SOURCE, authorized_disposable=True)
        self.recipient = Bip39Regtest12Keys(
            Mnemonic("english").to_mnemonic(bytes([1] * 16)),
            source=SOURCE, authorized_disposable=True)
        self.addCleanup(self.keys.close)
        self.addCleanup(self.recipient.close)
        account = self.keys.accounts()[0]
        funding_input = Input(
            "05" * 32, 0, p2wpkh(91),
            witness=(bytes(72), pub(91)), secret=91)
        output = send([funding_input], [account.payment_code()])[0]
        tx = {
            "txid": "ab" * 32,
            "vin": [{
                "txid": funding_input.txid, "vout": 0,
                "scriptSig": {"hex": ""},
                "txinwitness": [v.hex() for v in funding_input.witness],
                "prevout": {"scriptPubKey": {"hex": funding_input.script.hex()}},
            }],
            "vout": [{
                "n": 0, "value": 0.001,
                "scriptPubKey": {"hex": (b"\x51\x20" + output).hex()},
            }],
        }
        self.block = {
            "height": 1,
            "hash": sha256(b"q06 synthetic signer chain").hexdigest(),
            "previousblockhash": GENESIS,
            "tx": [tx],
        }
        self.chain = _Chain(self.block)
        self.scanner = Scanner(self.path / "current.sqlite", self.keys.accounts())
        self.addCleanup(self.scanner.close)
        self.scanner.sync(self.chain)
        self.scanner.assert_current()
        self.wallet = Wallet(self.scanner)
        self.intent = Intent(self.recipient.accounts()[0].payment_code(), 50_000)
        self.proposal = self.wallet.propose((self.intent,), 1000)
        self.signer = Signer(self.keys)

    def _sign_after_irreversible_mark(self):
        prepared = self.signer.prepare(self.proposal)
        self.wallet.mark_signed(self.proposal.token)
        before = _reservations(self.scanner)
        self.assertEqual(set(row[1] for row in before.values()), {"signed"})
        encrypted = self.scanner.checkpoint(PASSWORD)
        restored = Scanner(self.path / "restored.sqlite", self.keys.accounts())
        self.addCleanup(restored.close)
        restored.restore(encrypted, PASSWORD)
        restored.sync(self.chain)
        restored.assert_current()
        require_irreversible_preserved(before, _reservations(restored))
        self.assertEqual(_reservations(restored), before)
        with self.assertRaises(ValueError):
            Wallet(restored).release_draft(self.proposal.token)
        signed = self.signer.sign(prepared, (self.intent,), 1000)
        PSBT.decode(signed).finalize()
        return prepared, signed

    def test_bip39_12_word_source_signs_intent_verified_wsp_psbt(self):
        prepared, signed = self._sign_after_irreversible_mark()
        self.assertIsInstance(signed, bytes)
        self.assertNotEqual(signed, prepared.psbt)
        with self.assertRaises(ValueError):
            self.signer.sign(prepared, (self.intent,), 999)
        with self.assertRaises(ValueError):
            self.signer.sign(
                prepared, (Intent(self.intent.code, 49_999),), 1000)

    def test_q05_payment_engine_can_use_q06_key_adapter_without_rewriting_signer(self):
        """Synthetic transport, but production Q05 prepare/sign/broadcast methods."""
        from contextlib import nullcontext
        from types import SimpleNamespace
        from unittest.mock import patch
        from wam_regtest.wallet_session import WalletSession, WalletSessionError
        from wam_regtest.bip39_spend_session import Q06OwnedSpendSession

        # The per-fixture draft is explicitly released before calling the
        # existing engine; real sessions never discard irreversible locks.
        self.wallet.release_draft(self.proposal.token)
        coin = self.scanner.coins()[0]
        class FakeRpc:
            def call(self, method, params=None):
                if method == "getbestblockhash":
                    return self_tip
                if method == "gettxout":
                    return {"value": 0.001, "scriptPubKey": {
                        "hex": "5120" + coin["public_key"]}}
                if method == "testmempoolaccept":
                    return [{"allowed": True}]
                if method == "sendrawtransaction":
                    raise RuntimeError("Q06_TEST_NETWORK_UNCERTAIN")
                raise ValueError("Q06_TEST_RPC_METHOD_DENIED")
            def attest(self):
                pass
        class FakeAnchor:
            wallet_id = "d" * 32
            def __init__(self):
                self.value = (1, "a" * 64)
            def read(self):
                return self.value
            def lease(self):
                return nullcontext()
        class FakeVault:
            def __init__(self):
                self.anchor = FakeAnchor()
                self._expected = self.anchor.read()
                self.saved = []
            def save(self, keys, scanner, password):
                if password != PASSWORD or keys is not self_keys:
                    raise ValueError("Q06_TEST_BAD_CUSTODY")
                self.saved.append(_reservations(scanner).copy())
                self.anchor.value = (
                    self.anchor.value[0] + 1, sha256(scanner.checkpoint(password)).hexdigest())
                self._expected = self.anchor.value
        class FakeGuard:
            def check(self):pass
            def close(self):pass
        self_keys = self.keys
        self_tip = self.scanner.store.tip()[1]
        owner = SimpleNamespace(
            core=self.path, directory=self.path, cli=self.path,
            receipt={"wamd_sha256":"0"*64})
        vault = FakeVault()
        session = Q06OwnedSpendSession(
            owner, SOURCE, self.keys, self.scanner, FakeGuard(), vault, PASSWORD)
        # This fixture has no native owned directory: retain the synthetic
        # transport test's scope. Native encrypted evidence is exercised by
        # the actual Core/Keychain GUI qualification.
        with patch.object(session, '_retain_signed_payment') as retained, patch("wam_regtest.bip39_spend_session._owned"), patch.object(
                WalletSession, "_rpc", lambda _self: FakeRpc()):
            session.snapshot = lambda: None
            review = session.prepare(self.intent.code, self.intent.atoms, 1000)
            self.assertEqual(len(vault.saved), 1)
            self.assertEqual(set(x[1] for x in vault.saved[-1].values()), {"draft"})
            self.assertEqual(review.atoms, 50000)
            session.sign(review.commitment)
            self.assertEqual(len(vault.saved), 2)
            self.assertEqual(set(x[1] for x in vault.saved[-1].values()), {"signed"})
            with self.assertRaises(WalletSessionError):
                session.broadcast(review.commitment)
            # The source engine turns uncertain; Q06 journal adapter persisted
            # it BEFORE the RPC and cannot cancel it as an unsigned draft.
            self.assertEqual(len(vault.saved), 3)
            self.assertEqual(set(x[1] for x in vault.saved[-1].values()), {"uncertain"})
            with self.assertRaises(ValueError):
                self.wallet.release_draft(session._prepared.proposal.token)

    def test_q12_unsigned_cancel_cannot_release_irreversible_rows(self):
        from wam_regtest.wallet_session import WalletSession
        import threading
        session = object.__new__(WalletSession)
        session._lock = threading.RLock()
        session.scanner = self.scanner
        session._prepared = self.signer.prepare(self.proposal)
        session._signed = None  # Crash can lose transient bytes; row remains authoritative.
        session._review = session._tip = object()
        session._rpc = lambda: None
        saved = []
        session._save = lambda: saved.append(_reservations(self.scanner))
        for state in ('signed', 'uncertain', 'broadcast'):
            self.scanner.store.db.execute('UPDATE reservations SET state=?', (state,))
            before = _reservations(self.scanner)
            with self.subTest(state=state), self.assertRaises(ValueError):
                session.cancel()
            self.assertEqual(_reservations(self.scanner), before)
            self.assertEqual(saved, [])
        self.scanner.store.db.execute("UPDATE reservations SET state='draft'")
        session.cancel()
        self.assertEqual(saved, [{}])
        self.assertIsNone(session._prepared)
        self.assertIsNone(session._review)

    def test_q12_sign_fault_occurs_after_irreversible_save(self):
        from wam_regtest.wallet_session import WalletSession, WalletSessionError, PaymentReview
        from unittest.mock import patch
        from types import SimpleNamespace
        from contextlib import nullcontext
        import threading
        session = object.__new__(WalletSession)
        session._lock = threading.RLock()
        session.scanner, session.ring = self.scanner, self.keys
        session._prepared = self.signer.prepare(self.proposal)
        session._review = PaymentReview(self.intent.code,50000,1000,49000,1,'c'*64)
        session._signed = None
        session.faulted = False
        session.vault = SimpleNamespace(anchor=SimpleNamespace(lease=lambda:nullcontext()))
        session._rpc = lambda: None
        session._unchanged_inputs = lambda rpc: None
        saved = []
        session._save = lambda: saved.append(_reservations(self.scanner))
        with patch('wam_sp.wallet.Signer.sign',side_effect=RuntimeError('PUBLIC_TEST_CRYPTO_CUT')) as sign:
            with self.assertRaisesRegex(WalletSessionError,'SIGN_UNCERTAIN_LOCK_RETAINED'):
                session.sign('c'*64)
        self.assertEqual(sign.call_count,1)
        self.assertEqual(len(saved),1)
        self.assertEqual({value[1] for value in saved[0].values()},{'signed'})
        self.assertEqual(_reservations(self.scanner),saved[0])
        self.assertTrue(session.faulted)
        with self.assertRaises(ValueError):
            self.wallet.release_draft(self.proposal.token)

    def test_q12_changed_amount_recipient_or_fee_cannot_sign_prepared_psbt(self):
        prepared = self.signer.prepare(self.proposal)
        for intent, fee in ((Intent(self.intent.code,50001),1000),
                            (Intent(self.keys.accounts()[0].payment_code(),50000),1000),
                            (self.intent,999)):
            with self.subTest(fee=fee),self.assertRaises(ValueError):
                self.signer.sign(prepared,(intent,),fee)
        from dataclasses import replace
        altered = replace(prepared,proposal=replace(prepared.proposal,fee=1001))
        with self.assertRaises(ValueError):
            self.signer.sign(altered,(self.intent,),1001)

    def test_post_reopen_full_history_txid_read_only_and_ambiguous(self):
        from contextlib import nullcontext
        from threading import RLock
        from types import SimpleNamespace
        import sqlite3
        from wam_regtest.bip39_spend_session import (
            Q06OwnedSpendSession, Q06SpendSessionError)
        db=sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        db.execute("CREATE TABLE history(txid TEXT, height INTEGER)")
        old="b"*64
        db.execute("INSERT INTO history(txid,height) VALUES (?,?)",(old,103))
        store=SimpleNamespace(db=db,transaction=lambda:nullcontext())
        session=object.__new__(Q06OwnedSpendSession)
        session._lock=RLock()
        session._q06_uncertain=False
        session.faulted=False
        session.scanner=SimpleNamespace(store=store)
        session.snapshot=lambda:SimpleNamespace(height=108,tip="a"*64)
        methods=[]
        mempool=[]
        def rpc_call(method,params=None):
            methods.append(('call',method))
            if method=="getbestblockhash":
                return "a"*64
            raise AssertionError(method)
        def rpc_raw(method,args):
            methods.append(('_call',method,tuple(args)))
            if method=="getrawmempool" and list(args)==[]:
                return list(mempool)
            raise AssertionError(method)
        session._rpc=lambda:SimpleNamespace(call=rpc_call,_call=rpc_raw)
        count=db.total_changes
        found=session.inspect_confirmed(old)
        self.assertEqual(found["status"],"Q06_CONFIRMED_IN_VERIFIED_HISTORY")
        self.assertFalse(found["in_mempool"])
        self.assertTrue(found["complete_anchored_history"])
        self.assertFalse(found["write_attempted"])
        missing=session.inspect_confirmed("c"*64)
        self.assertEqual(missing["status"],"Q06_TX_NOT_IN_CONFIRMED_HISTORY")
        self.assertFalse(missing["in_mempool"])
        mempool.append("c"*64)
        pending=session.inspect_confirmed("c"*64)
        self.assertEqual(pending["status"],"Q06_TX_NOT_IN_CONFIRMED_HISTORY")
        self.assertTrue(pending["in_mempool"])
        self.assertEqual(db.total_changes,count)
        self.assertEqual(methods,[
            ("call","getbestblockhash"),("_call","getrawmempool",()),
            ("call","getbestblockhash"),("_call","getrawmempool",()),
            ("call","getbestblockhash"),("_call","getrawmempool",())])
        with self.assertRaises(Q06SpendSessionError):
            session.inspect_confirmed("mainnet")
        session._q06_uncertain=True
        with self.assertRaises(Q06SpendSessionError):
            session.inspect_confirmed(old)
        self.assertEqual(db.total_changes,count)

    def test_human_regtest_confirm_mines_exactly_one_block_for_exact_tx(self):
        from threading import RLock
        from types import SimpleNamespace
        from unittest.mock import patch
        from wam_regtest.bip39_spend_session import (
            Q06OwnedSpendSession, Q06SpendSessionError)

        txid = "cd" * 32
        class OwnedTestRpc:
            def __init__(self):
                self.height = 107
                self.generated = 0
            def attest(self):
                return None
            def call(self, method, params=None):
                if method == "getblockcount":
                    return self.height
                raise AssertionError("WRONG_RPC_METHOD")
            def _call(self, method, params):
                self.generated += 1
                self.height += 1
                self_assert(method == "generatetoaddress"
                            and params == ["1", "public-regtest-test-miner"])

        self_assert = self.assertTrue
        rpc = OwnedTestRpc()
        session = object.__new__(Q06OwnedSpendSession)
        session._lock = RLock()
        session._q06_pending_confirm = txid
        session._q06_uncertain = False
        session.faulted = False
        session.source = SOURCE
        session._q06_owner = object()
        session._rpc = lambda: rpc
        session.snapshot = lambda: SimpleNamespace(
            height=rpc.height,
            history=(SimpleNamespace(txid=txid, confirmations=1),))
        with patch("wam_regtest.bip39_spend_session._owned"), patch(
                "wam_regtest.wsp_live.public_regtest_mining_address",
                return_value="public-regtest-test-miner"):
            with self.assertRaises(Q06SpendSessionError):
                session.confirm_pending("ef" * 32)
            self.assertEqual(rpc.generated, 0)
            receipt = session.confirm_pending(txid)
            self.assertEqual(receipt["status"], "Q06_REGTEST_EXACT_SEND_CONFIRMED")
            self.assertEqual(receipt["height"], 108)
            self.assertEqual(rpc.generated, 1)
            self.assertIsNone(session._q06_pending_confirm)
            with self.assertRaises(Q06SpendSessionError):
                session.confirm_pending(txid)
            self.assertEqual(rpc.generated, 1)

    def test_human_regtest_confirm_ambiguous_write_never_retries(self):
        from threading import RLock
        from unittest.mock import patch
        from wam_regtest.bip39_spend_session import (
            Q06OwnedSpendSession, Q06SpendSessionError)

        txid = "cd" * 32
        attempts = []
        class UnknownRpc:
            def attest(self):
                return None
            def call(self, method, params=None):
                if method == "getblockcount":
                    return 107
                raise AssertionError("WRONG_RPC_METHOD")
            def _call(self, method, params):
                attempts.append(method)
                raise RuntimeError("MUTATION_OUTCOME_UNKNOWN")
        session = object.__new__(Q06OwnedSpendSession)
        session._lock = RLock()
        session._q06_pending_confirm = txid
        session._q06_uncertain = False
        session.faulted = False
        session.source = SOURCE
        session._q06_owner = object()
        session._rpc = lambda: UnknownRpc()
        with patch("wam_regtest.bip39_spend_session._owned"), patch(
                "wam_regtest.wsp_live.public_regtest_mining_address",
                return_value="public-regtest-test-miner"):
            with self.assertRaisesRegex(Q06SpendSessionError,
                                        "Q06_CONFIRM_UNCERTAIN_NO_RETRY"):
                session.confirm_pending(txid)
            self.assertTrue(session._q06_uncertain)
            self.assertTrue(session.faulted)
            with self.assertRaises(Q06SpendSessionError):
                session.confirm_pending(txid)
            self.assertEqual(attempts, ["generatetoaddress"])

    def test_ambiguous_broadcast_retains_bip39_reservation(self):
        _, signed = self._sign_after_irreversible_mark()
        coin = self.proposal.coins[0]
        calls = []
        class RefusedTransport:
            def attest(self):
                pass
            def call(self, method, params=None):
                calls.append(method)
                if method == "gettxout":
                    return {"value": 0.001, "scriptPubKey": {
                        "hex": "5120" + coin["public_key"]}}
                if method == "testmempoolaccept":
                    return [{"allowed": True}]
                if method == "sendrawtransaction":
                    raise RuntimeError("DISPOSABLE_AMBIGUOUS_BROADCAST")
                raise ValueError("Q06_SYNTHETIC_RPC_METHOD_DENIED")
        with self.assertRaises(RuntimeError):
            self.wallet.broadcast(signed, self.proposal.token, RefusedTransport())
        self.assertEqual(calls.count("sendrawtransaction"), 1)
        self.assertEqual(set(row[1] for row in _reservations(self.scanner).values()),
                         {"uncertain"})
        with self.assertRaises(ValueError):
            self.wallet.release_draft(self.proposal.token)


if __name__ == "__main__":
    unittest.main()
