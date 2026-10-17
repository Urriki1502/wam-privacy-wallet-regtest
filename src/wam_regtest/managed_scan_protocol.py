"""Dedicated authenticated read-only REGTEST scanner IPC (Q05).

Only the supervisor's existing OwnedCoreBinding-backed ManagedReadRpc may
service these requests. This is NOT a generic RPC proxy: no wallet selectors,
credentials, write/mining methods, endpoint arguments, or signer material.
"""
from __future__ import annotations

from decimal import Decimal
import hashlib
import hmac
import json
import re

from .json_rpc import _params, _result
from .supervisor_protocol import _distinct

SCAN_PROTOCOL="wam-fusion-managed-scan/v1"
SCAN_METHODS=frozenset({
    "getblockchaininfo","getblockcount","getbestblockhash","getblockhash",
    "getblock","getnetworkinfo","getconnectioncount",
})
MAX_SCAN_REQUEST=4096
MAX_SCAN_REPLY=32*1024*1024+4096
MAX_SCAN_NONCES=65536


class ScanProtocolError(ValueError):
    pass


def _canonical(value):
    def decimal_safe(obj):
        if type(obj) is Decimal and obj.is_finite():
            return str(obj)
        raise TypeError("SCAN_UNSERIALIZABLE")
    try:
        return json.dumps(value,sort_keys=True,separators=(",",":"),
                          ensure_ascii=True,allow_nan=False,
                          default=decimal_safe).encode("ascii")
    except (ValueError,TypeError,OverflowError):
        raise ScanProtocolError("SCAN_SERIALIZATION_DENIED") from None


def _nonce(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{32}",value) is None:
        raise ScanProtocolError("SCAN_NONCE_DENIED")


def _scope(method,params):
    if type(method) is not str or method not in SCAN_METHODS:
        raise ScanProtocolError("SCAN_METHOD_DENIED")
    try:
        _params(method,params)
    except Exception:
        raise ScanProtocolError("SCAN_PARAMS_DENIED") from None


def request_proof(secret,method,params,nonce):
    _scope(method,params);_nonce(nonce)
    if type(secret) is not bytes or len(secret)!=32:
        raise ScanProtocolError("SCAN_AUTH_SCOPE_DENIED")
    message=_canonical({"protocol":SCAN_PROTOCOL,"method":method,
                        "params":params,"nonce":nonce})
    return hmac.new(secret,b"SCAN_REQ_V1\0"+message,hashlib.sha256).hexdigest()


def encode_request(secret,method,params,nonce):
    proof=request_proof(secret,method,params,nonce)
    raw=_canonical({"protocol":SCAN_PROTOCOL,"method":method,
                    "params":params,"nonce":nonce,"proof":proof})+b"\n"
    if len(raw)>MAX_SCAN_REQUEST:raise ScanProtocolError("SCAN_REQUEST_TOO_LARGE")
    return raw


def decode_request(raw,secret,seen):
    if (type(raw) is not bytes or not 1<=len(raw)<=MAX_SCAN_REQUEST
            or not raw.endswith(b"\n") or b"\n" in raw[:-1]
            or type(seen) is not set):
        raise ScanProtocolError("SCAN_REQUEST_FRAME_DENIED")
    try:
        data=json.loads(raw[:-1].decode("ascii"),object_pairs_hook=_distinct)
    except Exception:
        raise ScanProtocolError("SCAN_REQUEST_JSON_DENIED") from None
    if (type(data) is not dict or set(data)!={"protocol","method","params","nonce","proof"}
            or data["protocol"]!=SCAN_PROTOCOL or type(data["params"]) is not list
            or type(data["proof"]) is not str or re.fullmatch(r"[0-9a-f]{64}",data["proof"]) is None):
        raise ScanProtocolError("SCAN_REQUEST_SHAPE_DENIED")
    method,params,nonce=data["method"],data["params"],data["nonce"]
    expected=request_proof(secret,method,params,nonce)
    if (len(seen)>=MAX_SCAN_NONCES or nonce in seen
            or not hmac.compare_digest(expected,data["proof"])):
        raise ScanProtocolError("SCAN_AUTH_DENIED")
    seen.add(nonce)
    return method,params,nonce


def encode_reply(secret,method,nonce,result):
    _scope(method,[] if method!="getblockhash" and method!="getblock" else
           ([0] if method=="getblockhash" else ["a"*64,3]))
    _nonce(nonce)
    # Result was already checked by ManagedReadRpc. Check shape again before IPC.
    try:_result(method,result)
    except Exception:
        raise ScanProtocolError("SCAN_UNTRUSTED_CORE_RESULT") from None
    body={"protocol":SCAN_PROTOCOL,"nonce":nonce,"method":method,
          "chain":"regtest","mainnet_allowed":False,"result":result}
    canonical=_canonical(body)
    proof=hmac.new(secret,b"SCAN_REPLY_V1\0"+canonical,hashlib.sha256).hexdigest()
    raw=_canonical({**body,"proof":proof})+b"\n"
    if len(raw)>MAX_SCAN_REPLY:
        raise ScanProtocolError("SCAN_REPLY_TOO_LARGE")
    return raw


def decode_reply(raw,secret,method,nonce):
    _scope(method,[] if method not in ("getblockhash","getblock") else
           ([0] if method=="getblockhash" else ["a"*64,3]))
    _nonce(nonce)
    if (type(raw) is not bytes or not 1<=len(raw)<=MAX_SCAN_REPLY
            or not raw.endswith(b"\n") or b"\n" in raw[:-1]):
        raise ScanProtocolError("SCAN_REPLY_FRAME_DENIED")
    try:data=json.loads(raw[:-1].decode("ascii"),object_pairs_hook=_distinct,
                        parse_float=Decimal,
                        parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except Exception:
        raise ScanProtocolError("SCAN_REPLY_JSON_DENIED") from None
    if (type(data) is not dict or set(data)!={
            "protocol","nonce","method","chain","mainnet_allowed","result","proof"}
            or data["protocol"]!=SCAN_PROTOCOL or data["nonce"]!=nonce
            or data["method"]!=method or data["chain"]!="regtest"
            or data["mainnet_allowed"] is not False
            or type(data["proof"]) is not str or re.fullmatch(r"[0-9a-f]{64}",data["proof"]) is None):
        raise ScanProtocolError("SCAN_REPLY_SCOPE_DENIED")
    body={k:v for k,v in data.items() if k!="proof"}
    expected=hmac.new(secret,b"SCAN_REPLY_V1\0"+_canonical(body),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected,data["proof"]):
        raise ScanProtocolError("SCAN_REPLY_AUTH_DENIED")
    try:_result(method,data["result"])
    except Exception:
        raise ScanProtocolError("SCAN_REPLY_RESULT_DENIED") from None
    return data["result"]
