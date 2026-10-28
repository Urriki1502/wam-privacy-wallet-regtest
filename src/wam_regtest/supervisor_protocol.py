"""T05 supervisor IPC: a small authenticated *control* protocol, never an RPC proxy.

The actual Core-owning supervisor is a separate long-lived process. This
protocol does NOT enable signing, generic Core/wallet RPC or external attach.
Explicit shutdown only reaches the supervisor's own verified child.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import re
import secrets
import threading
import time

MAX_FRAME=4096
PROTOCOL="wam-fusion-managed-supervisor/v2"
READ_COMMANDS=frozenset({"status"})
CONTROL_COMMANDS=frozenset({"start","shutdown","recover-stop"})
STATES=frozenset({"stopped","starting","syncing","ready","busy",
                  "recovery-needed","error"})


class SupervisorProtocolError(ValueError):
    pass


def _distinct(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise SupervisorProtocolError("SUPERVISOR_DUPLICATE_FIELD_DENIED")
        result[key]=value
    return result


def decode_frame(raw):
    if (type(raw) is not bytes or not 1<=len(raw)<=MAX_FRAME
            or raw[-1:]!=b"\n" or b"\n" in raw[:-1]):
        raise SupervisorProtocolError("SUPERVISOR_FRAME_DENIED")
    try: obj=json.loads(raw[:-1].decode("ascii"),object_pairs_hook=_distinct)
    except SupervisorProtocolError:raise
    except (ValueError,UnicodeError):
        raise SupervisorProtocolError("SUPERVISOR_JSON_DENIED") from None
    if type(obj) is not dict or set(obj)!={"protocol","op","nonce","proof","challenge"}:
        raise SupervisorProtocolError("SUPERVISOR_FIELDS_DENIED")
    if obj["protocol"]!=PROTOCOL or type(obj["op"]) is not str or obj["op"] not in READ_COMMANDS|CONTROL_COMMANDS:
        raise SupervisorProtocolError("SUPERVISOR_OPERATION_DENIED")
    for name,digits in (("nonce",32),("proof",64),("challenge",32)):
        if type(obj[name]) is not str or re.fullmatch("[0-9a-f]{"+str(digits)+"}",obj[name]) is None:
            raise SupervisorProtocolError("SUPERVISOR_AUTH_SHAPE_DENIED")
    return obj


def response_proof(secret,nonce,status):
    """Bind the server response to the originating nonce and verified state."""
    if (type(secret) is not bytes or len(secret)!=32 or type(nonce) is not str
            or re.fullmatch("[0-9a-f]{32}",nonce) is None
            or type(status) is not dict or set(status)!={
                "protocol","state","height","core_process_owned","chain","mainnet_allowed"}):
        raise SupervisorProtocolError("SUPERVISOR_RESPONSE_PROOF_DENIED")
    expected=public_status(state=status["state"],chain_height=status["height"],
        owned=status["core_process_owned"])
    if status!=expected:
        raise SupervisorProtocolError("SUPERVISOR_RESPONSE_STATE_DENIED")
    payload=json.dumps(status,sort_keys=True,separators=(",",":")).encode("ascii")
    return hmac.new(secret,b"REPLY\\n"+nonce.encode("ascii")+b"\\n"+payload,
                    hashlib.sha256).hexdigest()


def challenge_proof(secret,challenge):
    if (type(secret) is not bytes or len(secret)!=32 or type(challenge) is not str
            or re.fullmatch('[0-9a-f]{32}',challenge) is None):
        raise SupervisorProtocolError('SUPERVISOR_CHALLENGE_DENIED')
    return hmac.new(secret,(PROTOCOL+'\nHELLO\n'+challenge).encode('ascii'),
                    hashlib.sha256).hexdigest()


def request_proof(secret,op,nonce,challenge):
    if (type(secret) is not bytes or len(secret)!=32 or type(op) is not str
            or op not in READ_COMMANDS|CONTROL_COMMANDS
            or type(nonce) is not str or re.fullmatch("[0-9a-f]{32}",nonce) is None
            or type(challenge) is not str or re.fullmatch('[0-9a-f]{32}',challenge) is None):
        raise SupervisorProtocolError("SUPERVISOR_AUTH_INPUT_DENIED")
    message=(PROTOCOL+"\n"+op+"\n"+nonce+'\n'+challenge).encode("ascii")
    return hmac.new(secret,message,hashlib.sha256).hexdigest()


class ReplayGuard:
    """Bounded live, single-use connection challenges; no lifetime request cap.

    Retired/expired challenges are not reaccepted: verification requires a live
    entry AND the challenge issued to this connection. Fresh 128-bit CSPRNG
    challenges also separate supervisor instances without persisting nonces.
    """
    def __init__(self,secret,limit=4096,*,ttl=5):
        if type(secret) is not bytes or len(secret)!=32:
            raise SupervisorProtocolError("SUPERVISOR_SECRET_DENIED")
        if type(limit) is not int or not 1<=limit<=65536:
            raise SupervisorProtocolError("SUPERVISOR_REPLAY_LIMIT_DENIED")
        if type(ttl) not in (int,float) or not 1<=ttl<=30:
            raise SupervisorProtocolError("SUPERVISOR_CHALLENGE_TTL_DENIED")
        self.__secret=secret
        self.__pending={}
        self.__limit=limit
        self.__ttl=ttl
        self.__lock=threading.Lock()

    def hello(self):
        with self.__lock:
            now=time.monotonic()
            self.__pending={c:end for c,end in self.__pending.items() if end>now}
            if len(self.__pending)>=self.__limit:
                raise SupervisorProtocolError('SUPERVISOR_CHALLENGE_CAPACITY')
            challenge=secrets.token_hex(16)
            if challenge in self.__pending:
                raise SupervisorProtocolError('SUPERVISOR_CHALLENGE_COLLISION')
            self.__pending[challenge]=now+self.__ttl
            return dict(protocol=PROTOCOL,challenge=challenge,
                        proof=challenge_proof(self.__secret,challenge))

    def discard(self,challenge):
        with self.__lock:
            self.__pending.pop(challenge,None)

    def verify(self,raw,challenge):
        # Consume the connection grant atomically, even on malformed/bad auth.
        # A competing connection cannot use its own grant to consume another's.
        with self.__lock:
            expiry=self.__pending.pop(challenge,None)
            if expiry is None or time.monotonic()>=expiry:
                raise SupervisorProtocolError('SUPERVISOR_AUTH_DENIED')
            message=decode_frame(raw)
            if (message['challenge']!=challenge or not hmac.compare_digest(
                    message['proof'],request_proof(self.__secret,message['op'],
                                                  message['nonce'],challenge))):
                raise SupervisorProtocolError('SUPERVISOR_AUTH_DENIED')
            return message['op']

    def sign_status(self,nonce,status):
        return response_proof(self.__secret,nonce,status)


def public_status(*,state,chain_height=None,owned=False):
    if (type(state) is not str or state not in STATES
            or type(owned) is not bool
            or chain_height is not None and
                (type(chain_height) is not int or not 0<=chain_height<=100000000)):
        raise SupervisorProtocolError("SUPERVISOR_STATUS_DENIED")
    return {"protocol":PROTOCOL,"state":state,"height":chain_height,
            "core_process_owned":owned,"chain":"regtest","mainnet_allowed":False}
