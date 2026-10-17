"""Authenticated control-only client for a long-lived T05 supervisor.

Refuse foreign endpoints, malformed replies and wrong network. This interface
does not expose Core RPC or grant signer permissions.
"""
import json
from pathlib import Path
import re
import secrets
import socket

from .supervisor_protocol import PROTOCOL,request_proof,public_status,SupervisorProtocolError
from .supervisor_store import read_exact,SupervisorStorageError
from .core_supervisor import _profile_read,ManagedCoreError


class ManagedClientError(ValueError):pass


def control(root,op="status",*,authorized=False,timeout=3):
    if (type(op) is not str or op not in ("status","start","shutdown")
            or op!="status" and authorized is not True
            or type(timeout) not in (int,float) or not .1<=timeout<=15):
        raise ManagedClientError("MANAGED_CLIENT_OPERATION_NOT_APPROVED")
    try:
        profile=_profile_read(root)
        token=read_exact(root,"supervisor.token",length=32)
        nonce=secrets.token_hex(16)
        envelope={"protocol":PROTOCOL,"op":op,"nonce":nonce,
                  "proof":request_proof(token,op,nonce)}
        raw=(json.dumps(envelope,sort_keys=True,separators=(",",":"))+"\n").encode("ascii")
        with socket.create_connection(("127.0.0.1",profile["control_port"]),timeout=timeout) as conn:
            conn.settimeout(timeout)
            conn.sendall(raw)
            result=bytearray()
            while len(result)<=1024:
                part=conn.recv(1)
                if not part:break
                result.extend(part)
                if part==b"\n":break
        if not result.endswith(b"\n") or len(result)>1024:
            raise ManagedClientError("MANAGED_CLIENT_REPLY_DENIED")
        response=json.loads(result.decode("ascii"))
        if (type(response) is not dict or set(response)!={
            "protocol","state","height","core_process_owned","chain","mainnet_allowed"}
                or response["protocol"]!=PROTOCOL or response["chain"]!="regtest"
                or response["mainnet_allowed"] is not False):
            raise ManagedClientError("MANAGED_CLIENT_WRONG_SERVER_DENIED")
        verified=public_status(state=response["state"],
            chain_height=response["height"],owned=response["core_process_owned"])
        if verified!=response:raise ManagedClientError("MANAGED_CLIENT_REPLY_DENIED")
        return verified
    except ManagedClientError:raise
    except (OSError,ValueError,UnicodeError,SupervisorStorageError,ManagedCoreError,
            SupervisorProtocolError,json.JSONDecodeError):
        raise ManagedClientError("MANAGED_CLIENT_NOT_VERIFIED") from None
