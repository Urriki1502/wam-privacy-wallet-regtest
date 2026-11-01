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
