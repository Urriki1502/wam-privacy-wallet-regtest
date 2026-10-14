"""Offline adversarial PSBTv2-byte tests; NOT PayJoin wire or Core E2E.

Uses the same pinned WSP PSBTv2 codec and real secp256k1 Schnorr verification
as the app. The fake read-only RPC exists ONLY in these unit contracts.
Production requires the real attested local WalletCoreCli.
"""
import unittest
from dataclasses import replace
from coincurve import PrivateKey

from wam_sp.psbt import PSBT, Tx
from wam_sp.transaction import compact, blob
from wam_regtest.wallet_session import WalletCoreCli
from wam_regtest.payjoin_safety import validate_live_payjoin_psbt_v2, PayjoinSafetyError


SENDER_KEY = PrivateKey(b"\x00" * 31 + b"\x05")
OTHER_KEY = PrivateKey(b"\x00" * 31 + b"\x09")
SENDER_SCRIPT = b"\x51\x20" + SENDER_KEY.public_key.format()[1:]
OTHER_SCRIPT = b"\x51\x20" + OTHER_KEY.public_key.format()[1:]
SENDER = ("a"*64, 0)
OTHER = ("b"*64, 1)


class _OfflineReadOnlyRpc(WalletCoreCli):
    """Fixed local stub for hostile byte tests only; never E2E acceptance."""
    def __init__(self, prevouts):
        self.prevouts = dict(prevouts)
        self.calls = []
        self.changed = False
    def attest(self):
        self.calls.append("attest")
    def call(self, method, params=None):
        self.calls.append(method)
        if method == "getblockcount":
            return 104
        if method == "getbestblockhash":
            return "f"*64 if self.changed else "e"*64
        if method != "gettxout":
            raise AssertionError("unexpected_rpc")
        return self.prevouts.get((params[0], params[1]))


def _utxo(atoms, script):
    return {"value": f"{atoms/100_000_000:.8f}",
            "scriptPubKey": {"hex": script.hex()}}


def _candidate():
    orig = PSBT(Tx((SENDER,), ((50_000, OTHER_SCRIPT), (49_000, SENDER_SCRIPT))),
                ((100_000, SENDER_SCRIPT),))
    p = PSBT(Tx((SENDER, OTHER), orig.tx.outputs),
             orig.utxos + ((20_000, OTHER_SCRIPT),))
    sig = OTHER_KEY.sign_schnorr(p.tx.sighash(p.utxos, 1, 1)) + b"\x01"
    return orig, replace(
        p, input_extra=({}, {b"\x08": compact(1) + blob(sig)})
    )


class PayjoinStrictByteSafetyContracts(unittest.TestCase):
    def setUp(self):
        self.original, self.candidate = _candidate()
        self.rpc = _OfflineReadOnlyRpc({
            SENDER: _utxo(100_000, SENDER_SCRIPT),
            OTHER: _utxo(20_000, OTHER_SCRIPT),
        })
        self.coins = [{"txid": SENDER[0], "vout": SENDER[1]}]

    def inspect(self, proposal=None, original=None, rpc=None, coins=None):
        return validate_live_payjoin_psbt_v2(
            (original or self.original).encode(),
            (proposal or self.candidate).encode(),
            wallet_coins=self.coins if coins is None else coins,
            live_rpc=self.rpc if rpc is None else rpc,
        )

    def denied(self, code, **kwargs):
        with self.assertRaisesRegex(PayjoinSafetyError, "^" + code + "$"):
            self.inspect(**kwargs)

    def test_actual_v2_codec_signed_external_input_strict_positive(self):
        record = self.inspect()
        self.assertEqual(record["status"], "PJ_STRICT_PSBT_V2_SENDER_SAFETY_ONLY_PASS")
        self.assertTrue(record["final_external_schnorr_verified"])
        self.assertTrue(record["real_core_utxos_verified"])
        self.assertFalse(record["signing_authorized"])
        self.assertFalse(record["broadcast_authorized"])
        self.assertFalse(record["payjoin_wire_implemented"])
        self.assertFalse(record["bip352_payjoin_qualified"])
        self.assertNotIn(SENDER[0], str(record))
        self.assertEqual(self.rpc.calls.count("gettxout"), 2)

    def test_output_theft_or_amount_redirection_fails(self):
        candidate = self.candidate
        for outputs in (
            ((49_999, OTHER_SCRIPT), (49_001, SENDER_SCRIPT)),
            ((50_000, SENDER_SCRIPT), (49_000, OTHER_SCRIPT)),
        ):
            with self.subTest(outputs=outputs):
                self.denied("PJ_OUTPUT_CHANGED",
                            proposal=replace(candidate, tx=replace(candidate.tx, outputs=outputs)))

    def test_sender_sequence_reorder_and_utxo_mutation_fails(self):
        p = self.candidate
        self.denied("PJ_SENDER_INPUT_MUTATED",
                    proposal=replace(p, utxos=((101_000, SENDER_SCRIPT), p.utxos[1])))
        modified = replace(p.tx, sequences=(0xFFFFFFFE, 0xFFFFFFFD))
        self.denied("PJ_SENDER_INPUT_MUTATED", proposal=replace(p, tx=modified))
        reorder = replace(p.tx, inputs=(OTHER, SENDER))
        # Any malformed alignment/sig is rejected, not considered PayJoin.
        with self.assertRaises(PayjoinSafetyError):
            self.inspect(proposal=replace(p, tx=reorder))

    def test_attested_utxo_and_sender_ownership_scope(self):
        self.denied("PJ_RECEIVER_INPUT_OWNED_BY_SENDER",
                    coins=self.coins + [{"txid": OTHER[0], "vout": OTHER[1]}])
        self.denied("PJ_SENDER_WALLET_OWNERSHIP_DENIED", coins=[])
        rpc = _OfflineReadOnlyRpc({SENDER: _utxo(100_000, SENDER_SCRIPT)})
        self.denied("PJ_CORE_UTXO_MISMATCH", rpc=rpc)
        rpc = _OfflineReadOnlyRpc({
            SENDER: _utxo(100_000, SENDER_SCRIPT),
            OTHER: _utxo(20_001, OTHER_SCRIPT),
        })
        self.denied("PJ_CORE_UTXO_MISMATCH", rpc=rpc)

    def test_invalid_signature_or_metadata_is_rejected(self):
        p = self.candidate
        invalid = replace(p, input_extra=({}, {b"\x08": compact(1) + blob(b"\x11"*64 + b"\x01")}))
        self.denied("PJ_RECEIVER_SIGNATURE_DENIED", proposal=invalid)
        no_final = replace(p, input_extra=({}, {}))
        self.denied("PJ_RECEIVER_INPUT_METADATA_DENIED", proposal=no_final)
        unsigned_sighash = replace(p, input_extra=({}, {b"\x08": compact(1) + blob(b"\x11"*64)}))
        self.denied("PJ_RECEIVER_SIGHASH_ALL_REQUIRED", proposal=unsigned_sighash)
        leak = replace(p, input_extra=({}, {b"\x08":p.input_extra[1][b"\x08"], b"\x06"+OTHER_KEY.public_key.format():b"x"}))
        self.denied("PJ_RECEIVER_INPUT_METADATA_DENIED", proposal=leak)

    def test_original_final_signatures_and_unsafe_header_fail(self):
        orig = replace(self.original, signatures=(b"\x33"*64,))
        self.denied("PJ_ORIGINAL_ALREADY_SIGNED_DENIED", original=orig)
        p = replace(self.candidate, tx=replace(self.candidate.tx, locktime=100))
        self.denied("PJ_HEADER_OR_GLOBAL_MODIFIED", proposal=p)

    def test_bip352_output_sender_proof_must_fail_closed(self):
        # Even validly encoded BIP352 output info is not sufficient proof of
        # post-PayJoin address derivation after the input set is changed.
        pair = SENDER_KEY.public_key.format() + OTHER_KEY.public_key.format()
        orig = replace(self.original, output_extra=({b"\x09": pair}, {}))
        candidate = replace(self.candidate, output_extra=({b"\x09": pair}, {}))
        self.denied("PJ_BIP352_REDERIVATION_UNQUALIFIED",
                    original=orig, proposal=candidate)

    def test_wrong_rpc_type_or_untrusted_signed_original_fails_before_lookup(self):
        self.denied("PJ_ATTESTED_LOCAL_CORE_REQUIRED", rpc=object())
        self.assertEqual(self.rpc.calls, [])

    def test_reject_both_parties_same_prevout(self):
        p = replace(self.candidate, tx=replace(self.candidate.tx, inputs=(SENDER, SENDER)))
        with self.assertRaises(PayjoinSafetyError):
            self.inspect(proposal=p)


if __name__ == "__main__":
    unittest.main()
