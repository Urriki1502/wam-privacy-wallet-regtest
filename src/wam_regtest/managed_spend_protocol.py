"""Explicit WSP payment operations, independently HMAC-scoped from scanner reads.

No general Core JSON-RPC forwarding: only verified gettxout, single-transaction
mempool preflight, or single sendrawtransaction. Every request is authenticated,
fresh, bounded, REGTEST-only and records one-use nonce. The GUI must anchor the
signed/uncertain WSP reservation BEFORE requesting a broadcast. A dropped
reply is never retried automatically.
"""
from __future__ import annotations
from decimal import Decimal
import hmac
import hashlib
import json
import re

from .managed_scan_protocol import _canonical,_nonce
from .supervisor_protocol import _distinct

SPEND_PROTOCOL="wam-fusion-managed-spend/v1"
MAX_SPEND_REQUEST=16384
MAX_SPEND_REPLY=8192
MAX_SPEND_NONCES=65536
METHODS=frozenset(("gettxout","testmempoolaccept","sendrawtransaction"))


class SpendProtocolError(ValueError):pass


def _params(method,params):
    if method not in METHODS or type(params) is not list:
        raise SpendProtocolError("SPEND_METHOD_OR_PARAMS_DENIED")
    if method=="gettxout":
        if (len(params)!=3 or type(params[0]) is not str
                or re.fullmatch(r"[0-9a-f]{64}",params[0]) is None
                or type(params[1]) is not int or not 0<=params[1]<2**32
                or params[2] is not True):
            raise SpendProtocolError("SPEND_PARAMS_DENIED")
    else:
        raw=(params[0][0] if method=="testmempoolaccept" and
             len(params)==1 and type(params[0]) is list and len(params[0])==1
             else params[0] if method=="sendrawtransaction" and len(params)==1 else None)
        if (type(raw) is not str or not 2<=len(raw)<=12000
                or len(raw)%2 or re.fullmatch("[0-9a-f]+",raw) is None):
            raise SpendProtocolError("SPEND_RAW_SCOPE_DENIED")


def _result(method,value):
    if method=="gettxout":
        valid=(value is None or type(value) is dict
               and type(value.get("scriptPubKey")) is dict
               and type(value["scriptPubKey"].get("hex")) is str
               and re.fullmatch(r"[0-9a-f]{4,200}",value["scriptPubKey"]["hex"])
               and type(value.get("value")) in (int,float,Decimal,str))
    elif method=="testmempoolaccept":
        valid=(type(value) is list and len(value)==1
               and type(value[0]) is dict
               and type(value[0].get("allowed")) is bool)
    else:
        valid=(type(value) is str and re.fullmatch(r"[0-9a-f]{64}",value) is not None)
    if not valid:raise SpendProtocolError("SPEND_RESULT_DENIED")
    return value


def _proof(secret,domain,body):
    if type(secret) is not bytes or len(secret)!=32:
        raise SpendProtocolError("SPEND_NATIVE_TOKEN_DENIED")
    return hmac.new(secret,domain+_canonical(body),hashlib.sha256).hexdigest()


def encode_request(secret,method,params,nonce):
    _params(method,params);_nonce(nonce)
    body={"protocol":SPEND_PROTOCOL,"method":method,"params":params,
          "nonce":nonce,"approved":True,"chain":"regtest"}
    raw=_canonical({**body,"proof":_proof(secret,b"SPEND_REQ_V1\0",body)})+b"\n"
    if len(raw)>MAX_SPEND_REQUEST:raise SpendProtocolError("SPEND_FRAME_TOO_LARGE")
    return raw


def decode_request(raw,secret,seen):
    if (type(raw) is not bytes or not 1<=len(raw)<=MAX_SPEND_REQUEST
            or not raw.endswith(b"\n") or b"\n" in raw[:-1]
            or type(seen) is not set or len(seen)>=MAX_SPEND_NONCES):
        raise SpendProtocolError("SPEND_FRAME_DENIED")
    try:record=json.loads(raw[:-1].decode("ascii"),object_pairs_hook=_distinct)
    except Exception:raise SpendProtocolError("SPEND_FRAME_JSON_DENIED") from None
    if (type(record) is not dict or set(record)!={
            "protocol","method","params","nonce","approved","chain","proof"}
            or record["protocol"]!=SPEND_PROTOCOL
            or record["approved"] is not True or record["chain"]!="regtest"
            or type(record["proof"]) is not str
            or re.fullmatch(r"[0-9a-f]{64}",record["proof"]) is None):
        raise SpendProtocolError("SPEND_SCOPE_DENIED")
    method,params,nonce=record["method"],record["params"],record["nonce"]
    _params(method,params);_nonce(nonce)
    if nonce in seen:raise SpendProtocolError("SPEND_REPLAY_DENIED")
    body={k:v for k,v in record.items() if k!="proof"}
    if not hmac.compare_digest(record["proof"],_proof(secret,b"SPEND_REQ_V1\0",body)):
        raise SpendProtocolError("SPEND_AUTH_DENIED")
    seen.add(nonce)
    return method,params,nonce


def encode_reply(secret,method,nonce,result):
    _nonce(nonce);_result(method,result)
    body={"protocol":SPEND_PROTOCOL,"method":method,"nonce":nonce,
          "chain":"regtest","mainnet_allowed":False,"result":result}
    raw=_canonical({**body,"proof":_proof(secret,b"SPEND_REPLY_V1\0",body)})+b"\n"
    if len(raw)>MAX_SPEND_REPLY:raise SpendProtocolError("SPEND_REPLY_TOO_LARGE")
    return raw


def decode_reply(raw,secret,method,nonce):
    _nonce(nonce)
    if (type(raw) is not bytes or not 1<=len(raw)<=MAX_SPEND_REPLY
            or not raw.endswith(b"\n") or b"\n" in raw[:-1]):
        raise SpendProtocolError("SPEND_REPLY_FRAME_DENIED")
    try:
        data=json.loads(raw[:-1].decode("ascii"),object_pairs_hook=_distinct,
                        parse_float=Decimal,
                        parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except Exception:raise SpendProtocolError("SPEND_REPLY_JSON_DENIED") from None
    if (type(data) is not dict or set(data)!={
            "protocol","method","nonce","chain","mainnet_allowed","result","proof"}
            or data["protocol"]!=SPEND_PROTOCOL or data["method"]!=method
            or data["nonce"]!=nonce or data["chain"]!="regtest"
            or data["mainnet_allowed"] is not False
            or type(data["proof"]) is not str
            or re.fullmatch(r"[0-9a-f]{64}",data["proof"]) is None):
        raise SpendProtocolError("SPEND_REPLY_SHAPE_DENIED")
    body={k:v for k,v in data.items() if k!="proof"}
    if not hmac.compare_digest(data["proof"],_proof(secret,b"SPEND_REPLY_V1\0",body)):
        raise SpendProtocolError("SPEND_REPLY_AUTH_DENIED")
    return _result(method,data["result"])
