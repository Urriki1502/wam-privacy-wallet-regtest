"""Authenticated control-only client for a long-lived T05 supervisor.

Refuse foreign endpoints, malformed replies and wrong network. This interface
does not expose Core RPC or grant signer permissions.
"""
import json
from pathlib import Path
import re
import secrets
import socket
import time

from .supervisor_protocol import PROTOCOL,request_proof,response_proof,public_status,SupervisorProtocolError,_distinct,challenge_proof
from .supervisor_store import read_exact,SupervisorStorageError
from .core_supervisor import _profile_read,ManagedCoreError


class ManagedClientError(ValueError):pass


def control(root,op="status",*,authorized=False,timeout=3):
    if (type(op) is not str or op not in ("status","start","shutdown")
            or op!="status" and authorized is not True
            or type(timeout) not in (int,float) or not .1<=timeout<=120):
        raise ManagedClientError("MANAGED_CLIENT_OPERATION_NOT_APPROVED")
    try:
        deadline=time.monotonic()+timeout
        def remaining():
            left=deadline-time.monotonic()
            if left<=0:raise TimeoutError
            return left
        profile=_profile_read(root)
        token=read_exact(root,"supervisor.token",length=32)
        nonce=secrets.token_hex(16)
        with socket.create_connection(("127.0.0.1",profile["control_port"]),timeout=remaining()) as conn:
            hello=bytearray()
            while len(hello)<=512:
                conn.settimeout(remaining())
                part=conn.recv(1)
                if not part:break
                hello.extend(part)
                if part==b'\n':break
            if not hello.endswith(b'\n') or len(hello)>512:
                raise ManagedClientError('MANAGED_CLIENT_CHALLENGE_DENIED')
            challenge=json.loads(hello.decode('ascii'),object_pairs_hook=_distinct)
            if (type(challenge) is not dict or set(challenge)!={'protocol','challenge','proof'}
                    or challenge['protocol']!=PROTOCOL or type(challenge['proof']) is not str
                    or re.fullmatch('[0-9a-f]{64}',challenge['proof']) is None
                    or not secrets.compare_digest(challenge['proof'],
                        challenge_proof(token,challenge['challenge']))):
                raise ManagedClientError('MANAGED_CLIENT_CHALLENGE_DENIED')
            epoch=challenge['challenge']
            envelope={"protocol":PROTOCOL,"op":op,"nonce":nonce,'challenge':epoch,
                      "proof":request_proof(token,op,nonce,epoch)}
            raw=(json.dumps(envelope,sort_keys=True,separators=(",",":"))+"\n").encode("ascii")
            conn.settimeout(remaining())
            conn.sendall(raw)
            result=bytearray()
            while len(result)<=1024:
                conn.settimeout(remaining())
                part=conn.recv(1)
                if not part:break
                result.extend(part)
                if part==b"\n":break
        if not result.endswith(b"\n") or len(result)>1024:
            raise ManagedClientError("MANAGED_CLIENT_REPLY_DENIED")
        response=json.loads(result.decode("ascii"),object_pairs_hook=_distinct)
        if (type(response) is not dict or set(response)!={
            "protocol","state","height","core_process_owned","chain",
            "mainnet_allowed","nonce","proof"}
                or response["protocol"]!=PROTOCOL or response["chain"]!="regtest"
                or response["mainnet_allowed"] is not False or response["nonce"]!=nonce
                or type(response["proof"]) is not str
                or not re.fullmatch("[0-9a-f]{64}",response["proof"])):
            raise ManagedClientError("MANAGED_CLIENT_WRONG_SERVER_DENIED")
        public={k:v for k,v in response.items() if k not in ("nonce","proof")}
        verified=public_status(state=public["state"],
            chain_height=public["height"],owned=public["core_process_owned"])
        if (verified!=public or not secrets.compare_digest(response["proof"],
              response_proof(token,nonce,verified))):
            raise ManagedClientError("MANAGED_CLIENT_REPLY_NOT_AUTHENTICATED")
        remaining()  # Parsing/authentication cannot renew the original budget.
        return verified
    except ManagedClientError:raise
    except (OSError,ValueError,UnicodeError,SupervisorStorageError,ManagedCoreError,
            SupervisorProtocolError,json.JSONDecodeError):
        raise ManagedClientError("MANAGED_CLIENT_NOT_VERIFIED") from None
