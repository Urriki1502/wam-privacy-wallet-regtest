"""Authenticated WSP-1 scanner reads through the Fusion-owned REGTEST Core.

No arbitrary command forwarding, wallet selector, sign/broadcast, RPC cookie,
key material, external hostname, or direct Core connection in this GUI client.
"""
from __future__ import annotations

import secrets
import socket
from pathlib import Path

from .core_supervisor import _profile_read
from .supervisor_store import read_exact
from .managed_scan_protocol import (
    MAX_SCAN_REPLY,ScanProtocolError,decode_reply,encode_request,_scope,
)
from .wsp_live import REGTEST_GENESIS


class ManagedScanError(ValueError):
    pass


class ManagedScanRpc:
    """Scanner-shaped narrowly scoped client. No sign/write capability."""

    def __init__(self,root,*,authorized_readonly=False,timeout=15):
        if (authorized_readonly is not True or type(root) is not type(Path())
                or not root.is_absolute() or type(timeout) not in (int,float)
                or not .5<=timeout<=30):
            raise ManagedScanError("SCAN_CLIENT_CONSENT_OR_ROOT_DENIED")
        self._root=root
        self._timeout=timeout
        self._closed=False
        self._profile=_profile_read(root)
        self._secret=read_exact(root,"supervisor.token",length=32)

    def _request(self,method,params):
        if self._closed:
            raise ManagedScanError("SCAN_CLIENT_CLOSED")
        try:
            _scope(method,params)
            # Refuse a changed supervisor profile before any read. Rebind or
            # Core upgrade needs a new, explicitly reauthorized GUI session.
            if _profile_read(self._root)!=self._profile:
                raise ManagedScanError("SCAN_CLIENT_PROFILE_CHANGED")
            nonce=secrets.token_hex(16)
            frame=encode_request(self._secret,method,params,nonce)
            with socket.create_connection(
                    ("127.0.0.1",self._profile["control_port"]),timeout=self._timeout) as conn:
                conn.settimeout(self._timeout)
                conn.sendall(frame)
                answer=bytearray()
                while len(answer)<=MAX_SCAN_REPLY:
                    chunk=conn.recv(min(65536,MAX_SCAN_REPLY+1-len(answer)))
                    if not chunk:break
                    answer.extend(chunk)
                    if b"\n" in chunk:break
            return decode_reply(bytes(answer),self._secret,method,nonce)
        except ManagedScanError:
            raise
        except Exception:
            raise ManagedScanError("SCAN_CLIENT_READ_UNVERIFIED") from None

    def attest(self):
        info=self._request("getblockchaininfo",[])
        if (type(info) is not dict or info.get("chain")!="regtest"
                or type(info.get("blocks")) is not int):
            raise ManagedScanError("SCAN_CLIENT_CHAIN_DENIED")
        if self._request("getblockhash",[0])!=REGTEST_GENESIS:
            raise ManagedScanError("SCAN_CLIENT_GENESIS_DENIED")
        self._request("getnetworkinfo",[])
        if self._request("getconnectioncount",[])!=0:
            raise ManagedScanError("SCAN_CLIENT_PEERS_DENIED")
        return info

    def call(self,method,params=None):
        args=[] if params is None else params
        _scope(method,args)
        verified=self.attest()
        return verified if method=="getblockchaininfo" else self._request(method,args)

    def close(self):
        self._closed=True
        self._secret=None

    def __repr__(self):
        return "<ManagedScanRpc read-only REGTEST>"
