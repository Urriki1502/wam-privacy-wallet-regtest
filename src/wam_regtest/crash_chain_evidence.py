"""K-09 bounded, owner-requested REAL REGTEST Core chain risk observation.

This is a narrow READ-ONLY diagnostic through the existing authenticated
ManagedScanRpc; no new RPC methods, no mempool or wallet RPC, no signer.
A missing spend in recent blocks NEVER proves an outpoint is unspent or
unbroadcast. Output contains fixed redacted counts only.
"""
from __future__ import annotations

import re


_HASH = re.compile(r"[0-9a-f]{64}\Z")
MAX_OUTPOINTS = 2048
MAX_BLOCKS = 8
MAX_TRANSACTIONS_PER_BLOCK = 4096
MAX_INPUTS_PER_BLOCK = 16384


class CrashChainEvidenceError(ValueError):
    pass


def _deny(code):
    raise CrashChainEvidenceError(code)


def _outpoints(items):
    if type(items) not in (frozenset, set, tuple):
        _deny("K09_CORE_OUTPOINT_SCOPE_DENIED")
    if len(items)>MAX_OUTPOINTS:
        _deny("K09_CORE_OUTPOINT_SET_LIMIT")
    points=set()
    for x in items:
        if (type(x) is not tuple or len(x)!=2
                or type(x[0]) is not str or not _HASH.fullmatch(x[0])
                or type(x[1]) is not int or not 0<=x[1]<2**32):
            _deny("K09_CORE_OUTPOINT_FORMAT_DENIED")
        points.add(x)
    if len(points)!=len(items):
        _deny("K09_CORE_DUPLICATE_OUTPOINT_DENIED")
    return frozenset(points)


def _observe_rpc(read, outpoints, *, limit):
    """Internal parser: read is a pre-attested, strictly scoped RPC function.

    Unit tests can use a fake read callable for parsing contracts; public
    entrypoint below requires the actual ManagedScanRpc concrete class.
    """
    if not callable(read) or type(limit) is not int or not 1<=limit<=MAX_BLOCKS:
        _deny("K09_CORE_WINDOW_SCOPE_DENIED")
    target=_outpoints(outpoints)
    try:
        height=read("getblockcount",[])
        tip=read("getbestblockhash",[])
        if (type(height) is not int or not 0<=height<=1_000_000
                or type(tip) is not str or not _HASH.fullmatch(tip)):
            _deny("K09_CORE_TIP_SHAPE_DENIED")
        if read("getblockhash",[height])!=tip:
            _deny("K09_CORE_TIP_CHANGED")
        lowest=max(1,height-limit+1)
        observed=set()
        inspected=0
        for block_height in range(height,lowest-1,-1):
            digest=read("getblockhash",[block_height])
            if type(digest) is not str or not _HASH.fullmatch(digest):
                _deny("K09_CORE_BLOCK_HASH_DENIED")
            block=read("getblock",[digest,3])
            if (type(block) is not dict or block.get("hash")!=digest
                    or type(block.get("height")) is not int
                    or block["height"]!=block_height
                    or type(block.get("tx")) is not list
                    or not 1<=len(block["tx"])<=MAX_TRANSACTIONS_PER_BLOCK):
                _deny("K09_CORE_BLOCK_SHAPE_DENIED")
            total_inputs=0
            for tx in block["tx"]:
                if type(tx) is not dict or type(tx.get("vin")) is not list:
                    _deny("K09_CORE_INPUTS_SHAPE_DENIED")
                total_inputs+=len(tx["vin"])
                if total_inputs>MAX_INPUTS_PER_BLOCK:
                    _deny("K09_CORE_INPUTS_LIMIT")
                for vin in tx["vin"]:
                    if type(vin) is not dict:
                        _deny("K09_CORE_INPUT_SHAPE_DENIED")
                    # Coinbase has no previous output to consume.
                    if "coinbase" in vin:
                        if type(vin["coinbase"]) is not str or "txid" in vin:
                            _deny("K09_CORE_COINBASE_SHAPE_DENIED")
                        continue
                    prev=vin.get("txid")
                    n=vin.get("vout")
                    if (type(prev) is not str or not _HASH.fullmatch(prev)
                            or type(n) is not int or not 0<=n<2**32):
                        _deny("K09_CORE_INPUT_SHAPE_DENIED")
                    if (prev,n) in target:
                        observed.add((prev,n))
            inspected+=1
        if (read("getblockcount",[])!=height
                or read("getbestblockhash",[])!=tip
                or read("getblockhash",[height])!=tip):
            _deny("K09_CORE_TIP_CHANGED")
        return {
            "observation":"K09_RECENT_CHAIN_SPEND_RISK_ONLY",
            "regtest_height":height,
            "blocks_scanned":inspected,
            "outpoints_checked":len(target),
            "onchain_spent_outpoints_observed":len(observed),
            "window_reaches_genesis":height<=limit,
            "mempool_evidence_available":False,
            "full_chain_reconciled":False,
            "signed_or_uncertain_reservations_reconciled":False,
            "safe_to_discard_proven":False,
            "operator_discard_available":False,
            "wallet_unlocked":False,
            "signer_allowed":False,
            "broadcast_allowed":False,
        }
    except CrashChainEvidenceError:
        raise
    except Exception:
        _deny("K09_CORE_READ_UNVERIFIED")


def observe_recent_core_spends(rpc, outpoints, *, authorized=False, max_blocks=8):
    """Require native authenticated IPC client and separate explicit consent.

    The caller is responsible for the original REGTEST wallet/owner scope
    and must NEVER use this diagnostic as permission for destructive action.
    """
    from .managed_scan_client import ManagedScanRpc
    if authorized is not True:
        _deny("K09_CORE_OPERATOR_CONSENT_REQUIRED")
    if type(rpc) is not ManagedScanRpc:
        _deny("K09_CORE_AUTHENTICATED_IPC_REQUIRED")
    if type(max_blocks) is not int or not 1<=max_blocks<=MAX_BLOCKS:
        _deny("K09_CORE_WINDOW_SCOPE_DENIED")
    points=_outpoints(outpoints)
    try:
        info=rpc.attest()
        if (type(info) is not dict or info.get("chain")!="regtest"
                or type(info.get("blocks")) is not int
                or type(info.get("bestblockhash")) is not str
                or not _HASH.fullmatch(info["bestblockhash"])):
            _deny("K09_CORE_CHAIN_ATTESTATION_DENIED")
        result=_observe_rpc(rpc.call, points, limit=max_blocks)
        if (result["regtest_height"]!=info["blocks"]
                or rpc.call("getbestblockhash")!=info["bestblockhash"]):
            _deny("K09_CORE_ATTESTED_TIP_CHANGED")
        return result
    except CrashChainEvidenceError:
        raise
    except Exception:
        _deny("K09_CORE_ATTESTATION_OR_READ_DENIED")
