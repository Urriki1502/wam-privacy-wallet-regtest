"""Read-only, strict sender-side PayJoin inspection for actual WSP PSBTv2.

Adapted safety invariants from wam-privacy Phase 4. This is intentionally NOT
BIP78/BIP77 transport, BIP352 PayJoin, a signer, or a transaction authorization.
No signing key, wallet mutation, network send or broadcast is reachable.

Input ownership and UTXO scripts/values are derived from the sender's real
local scanner and reattested through genuine REGTEST Core gettxout, never from
PSBT-provided ownership labels. Source PSBT is the LOCAL UNSIGNED intent.
"""
from __future__ import annotations

import hmac

MAX_MONEY = 22_000_000 * 100_000_000
MAX_EXTRA_INPUTS = 4
MAX_FEE_ATOMS = 1_000_000


class PayjoinSafetyError(ValueError):
    """Fixed-code only; never embed raw PSBT/addresses/transaction contents."""


def _deny(code: str):
    raise PayjoinSafetyError(code)


def _parse(raw):
    from wam_sp.psbt import PSBT
    if type(raw) is not bytes or not 1 <= len(raw) <= 1_000_000:
        _deny("PJ_PSBT_BYTES_DENIED")
    try:
        obj = PSBT.decode(raw)
        if obj.version != 2 or obj.encode() != raw:
            _deny("PJ_NONCANONICAL_PSBT_V2_DENIED")
        obj.tx.serialize()
        return obj
    except PayjoinSafetyError:
        raise
    except Exception:
        _deny("PJ_PSBT_PARSE_DENIED")


def _sender_proof_present(psbt):
    # BIP352 output derivation depends on ALL eligible transaction inputs.
    # Adding a receiver input changes the input hash and thus destination
    # commitments. Until a separately reviewed rederivation/binding adapter
    # exists, do not falsely accept a PayJoin of a silent-payment output.
    ins = psbt.input_extra or ({},) * len(psbt.utxos)
    outs = psbt.output_extra or ({},) * len(psbt.tx.outputs)
    return (any(b"\x09" in x or b"\x0a" in x for x in outs)
            or any(any(k[:1] in (b"\x1d", b"\x1e") for k in m) for m in ins)
            or any(any(k[:1] in (b"\x07", b"\x08") for k in [k]) for k in psbt.global_extra))


def _finalized_p2tr_external(psbt, index):
    from wam_sp.psbt import Reader
    signature = psbt.signatures or (None,) * len(psbt.tx.inputs)
    extras = psbt.input_extra or ({},) * len(psbt.tx.inputs)
    m = extras[index]
    if signature[index] is not None or set(m) != {b"\x08"}:
        _deny("PJ_RECEIVER_INPUT_METADATA_DENIED")
    raw = m[b"\x08"]
    try:
        reader = Reader(raw)
        if reader.size(1) != 1:
            _deny("PJ_RECEIVER_WITNESS_SHAPE_DENIED")
        sig = reader.blob(65)
        reader.finish()
        if len(sig) != 65 or sig[-1] != 1:
            _deny("PJ_RECEIVER_SIGHASH_ALL_REQUIRED")
        psbt._verify_signature(index, sig)
    except PayjoinSafetyError:
        raise
    except Exception:
        _deny("PJ_RECEIVER_SIGNATURE_DENIED")


def validate_live_payjoin_psbt_v2(
    original_bytes: bytes,
    candidate_bytes: bytes,
    *,
    wallet_coins,
    live_rpc,
):
    """Inspect PSBTv2 proposal only; no signing, reservation or broadcast.

    Caller must pass scanner-derived wallet_coins and the existing *attested*
    read/write-scoped WalletCoreCli from the disposable REGTEST session.
    Proposals with BIP352 output sender commitments are deliberately DENIED.
    Successful generic P2TR result means sender safety only, not PayJoin E2E.
    """
    from .wallet_session import WalletCoreCli
    from wam_sp.scanner import atoms

    if not isinstance(live_rpc, WalletCoreCli):
        _deny("PJ_ATTESTED_LOCAL_CORE_REQUIRED")
    if type(wallet_coins) not in (tuple, list) or len(wallet_coins) > 10000:
        _deny("PJ_TRUSTED_WALLET_COINS_REQUIRED")
    try:
        owned = {(c["txid"], c["vout"]) for c in wallet_coins}
        if (len(owned) != len(wallet_coins)
                or any(type(t) is not str or len(t) != 64 or
                       type(v) is not int or not 0 <= v < 2**32 for t, v in owned)):
            _deny("PJ_TRUSTED_WALLET_COINS_DENIED")
    except PayjoinSafetyError:
        raise
    except Exception:
        _deny("PJ_TRUSTED_WALLET_COINS_DENIED")

    original = _parse(original_bytes)
    candidate = _parse(candidate_bytes)
    if _sender_proof_present(original) or _sender_proof_present(candidate):
        _deny("PJ_BIP352_REDERIVATION_UNQUALIFIED")
    if original.signatures and any(s is not None for s in original.signatures):
        _deny("PJ_ORIGINAL_ALREADY_SIGNED_DENIED")
    if (original.tx.version != candidate.tx.version
            or original.tx.locktime != candidate.tx.locktime
            or original.global_extra != candidate.global_extra):
        _deny("PJ_HEADER_OR_GLOBAL_MODIFIED")
    if (len(original.tx.inputs) < 1 or len(original.tx.outputs) < 1
            or not len(original.tx.inputs) < len(candidate.tx.inputs)
                 <= len(original.tx.inputs) + MAX_EXTRA_INPUTS
            or len(candidate.tx.inputs) > 128):
        _deny("PJ_RECEIVER_INPUT_COUNT_DENIED")
    if (original.tx.outputs != candidate.tx.outputs
            or original.output_extra != candidate.output_extra):
        _deny("PJ_OUTPUT_CHANGED")
    sender = original.tx.inputs
    source_index = {op: i for i, op in enumerate(sender)}
    if len(source_index) != len(sender) or not set(sender) <= owned:
        _deny("PJ_SENDER_WALLET_OWNERSHIP_DENIED")
    observed = [op for op in candidate.tx.inputs if op in source_index]
    if observed != list(sender):
        _deny("PJ_SENDER_INPUT_REMOVED_OR_REORDERED")
    if len(set(candidate.tx.inputs)) != len(candidate.tx.inputs):
        _deny("PJ_DUPLICATE_OUTPOINT")
    extras_orig = original.input_extra or ({},) * len(sender)
    extras_cand = candidate.input_extra or ({},) * len(candidate.tx.inputs)
    sigs_cand = candidate.signatures or (None,) * len(candidate.tx.inputs)
    seq_orig = original.tx.sequence_values()
    seq_cand = candidate.tx.sequence_values()
    for j, op in enumerate(candidate.tx.inputs):
        if op in source_index:
            i = source_index[op]
            if (seq_cand[j] != seq_orig[i] or candidate.utxos[j] != original.utxos[i]
                    or extras_cand[j] != extras_orig[i] or sigs_cand[j] is not None):
                _deny("PJ_SENDER_INPUT_MUTATED")
    added = [j for j, op in enumerate(candidate.tx.inputs) if op not in source_index]
    if len(added) + len(sender) != len(candidate.tx.inputs):
        _deny("PJ_UNQUALIFIED_INPUT_OWNERSHIP")
    for j in added:
        if candidate.tx.inputs[j] in owned:
            _deny("PJ_RECEIVER_INPUT_OWNED_BY_SENDER")
        val, script = candidate.utxos[j]
        if (type(val) is not int or not 1 <= val <= MAX_MONEY
                or type(script) is not bytes or len(script) != 34
                or script[:2] != b"\x51\x20"
                or seq_cand[j] != original.tx.sequence_values()[0]):
            _deny("PJ_RECEIVER_INPUT_POLICY_DENIED")
        _finalized_p2tr_external(candidate, j)

    original_fee = sum(v for v, _ in original.utxos) - sum(v for v, _ in original.tx.outputs)
    proposal_fee = sum(v for v, _ in candidate.utxos) - sum(v for v, _ in candidate.tx.outputs)
    contributed = sum(candidate.utxos[j][0] for j in added)
    if (not 0 < original_fee <= MAX_FEE_ATOMS
            or not original_fee <= proposal_fee <= MAX_FEE_ATOMS
            or proposal_fee - original_fee != contributed):
        _deny("PJ_FEE_OR_VALUE_CONSERVATION_DENIED")

    try:
        live_rpc.attest()
        tip = (live_rpc.call("getblockcount"), live_rpc.call("getbestblockhash"))
        if (type(tip[0]) is not int or tip[0] < 101
                or type(tip[1]) is not str or len(tip[1]) != 64):
            _deny("PJ_REGTEST_CHAIN_UNQUALIFIED")
        for outpoint, (value, script) in zip(candidate.tx.inputs, candidate.utxos):
            utxo = live_rpc.call("gettxout", [outpoint[0], outpoint[1], True])
            if (type(utxo) is not dict or atoms(utxo.get("value")) != value
                    or utxo.get("scriptPubKey", {}).get("hex") != script.hex()):
                _deny("PJ_CORE_UTXO_MISMATCH")
        if (live_rpc.call("getblockcount"), live_rpc.call("getbestblockhash")) != tip:
            _deny("PJ_REGTEST_TIP_CHANGED")
    except PayjoinSafetyError:
        raise
    except Exception:
        _deny("PJ_REAL_CORE_ATTESTATION_DENIED")

    # Coarse boolean evidence only. No PSBT, keys, outpoints, destinations,
    # amounts, wallet ID, source path, signature or RPC response is returned.
    return {
        "status": "PJ_STRICT_PSBT_V2_SENDER_SAFETY_ONLY_PASS",
        "psbt_v2_canonical": True,
        "new_external_inputs": len(added),
        "outputs_unchanged": True,
        "wallet_inputs_unchanged": True,
        "final_external_schnorr_verified": True,
        "real_core_utxos_verified": True,
        "regtest_only": True,
        "signing_authorized": False,
        "broadcast_authorized": False,
        "payjoin_wire_implemented": False,
        "bip352_payjoin_qualified": False,
    }
