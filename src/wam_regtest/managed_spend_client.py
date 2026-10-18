"""Consent-scoped REGTEST WSP transaction client bound to its owned scanner.

The existing ManagedScanRpc is unchanged (read-only). This separate client
can issue exactly three payment RPC methods after explicit GUI approval. It
never exports keys, selects Core wallets, guesses a node or retries a write.
"""
from __future__ import annotations
import secrets
import socket
import time
from pathlib import Path

from .core_supervisor import _profile_read
from .supervisor_store import read_exact
from .managed_scan_client import ManagedScanRpc
from .managed_spend_protocol import (
    _params,MAX_SPEND_REPLY,decode_reply,encode_request,
)


class ManagedSpendError(ValueError):pass


class ManagedSpendRpc:
    def __init__(self,root,read_rpc,*,authorized=False,timeout=15):
        if (authorized is not True or type(root) is not type(Path())
                or not root.is_absolute() or type(read_rpc) is not ManagedScanRpc
                or read_rpc._root!=root or read_rpc._closed
                or type(timeout) not in (int,float) or not .5<=timeout<=30):
            raise ManagedSpendError("SPEND_SESSION_CONSENT_OR_OWNER_DENIED")
        self._root,self._reader,self._timeout=root,read_rpc,timeout
        self._profile=_profile_read(root)
        if self._profile!=read_rpc._profile:
            raise ManagedSpendError("SPEND_SESSION_PROFILE_DENIED")
        self._secret=read_exact(root,"supervisor.spend.token",length=32)
        self._closed=False

    def attest(self):
        if self._closed:raise ManagedSpendError("SPEND_SESSION_CLOSED")
        return self._reader.attest()

    def call(self,method,params=None):
        if self._closed:raise ManagedSpendError("SPEND_SESSION_CLOSED")
        args=[] if params is None else params
        if method in ("getbestblockhash","getblockcount","getblockhash",
                      "getblockchaininfo"):
            return self._reader.call(method,args)
        _params(method,args)
        try:
            # Attest original Core before every spend-capable RPC. In-flight
            # uncertainty always leaves the UTXO reservation locked.
            self._reader.attest()
            if _profile_read(self._root)!=self._profile:
                raise ManagedSpendError("SPEND_SESSION_PROFILE_CHANGED")
            nonce=secrets.token_hex(16)
            raw=encode_request(self._secret,method,args,nonce)
            deadline=time.monotonic()+self._timeout
            def remaining():
                left=deadline-time.monotonic()
                if left<=0:raise TimeoutError
                return left
            with socket.create_connection(("127.0.0.1",
                    self._profile["control_port"]),timeout=remaining()) as conn:
                conn.settimeout(remaining())
                conn.sendall(raw)
                response=bytearray()
                while len(response)<=MAX_SPEND_REPLY:
                    conn.settimeout(remaining())
                    part=conn.recv(min(8192,MAX_SPEND_REPLY+1-len(response)))
                    if not part:break
                    response.extend(part)
                    if b"\n" in part:break
            value=decode_reply(bytes(response),self._secret,method,nonce)
            remaining()
            # A server replacement after a transaction is not "retryable".
            if _profile_read(self._root)!=self._profile:
                raise ManagedSpendError("SPEND_SESSION_PROFILE_CHANGED")
            self._reader.attest()
            return value
        except Exception:
            raise ManagedSpendError("SPEND_RESULT_UNCERTAIN_NO_RETRY") from None

    def close(self):
        self._closed=True
        self._secret=None

    def __repr__(self):
        return "<ManagedSpendRpc REGTEST one-operation capability>"
