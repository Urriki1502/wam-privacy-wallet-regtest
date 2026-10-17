"""CI-only genuine Core v0.1.12 authenticated HTTP read probe.

Never used by WAM Fusion runtime. The production ManagedReadRpc v0.1.11
trust/version pin and OwnedCoreBinding must remain unchanged. For this isolated
disposable test only: re-prove kernel socket ownership BEFORE sending any
authentication headers, and strictly read four allowlisted RPC methods.
"""
from __future__ import annotations

import base64
from hashlib import sha256
import http.client
import json
import os
from pathlib import Path
import re
import subprocess
import time

from .core_process import _linux_socket
from .json_rpc import _params, _private_config, _reply, RpcError
from .v012_candidate_compat import (
    Candidate012Denied, candidate_network_reply, candidate_scope_status,
    exact_signed_linux_candidate, CANDIDATE_LINUX_WAMD_SHA)
from .wsp_live import REGTEST_GENESIS

_READS = ("getnetworkinfo", "getblockchaininfo", "getblockhash", "getblockcount", "getconnectioncount")


def _deny(code):
    raise Candidate012Denied(code)


def _running(node: Path, process: subprocess.Popen) -> None:
    try:
        if process.poll() is not None or not Path(f"/proc/{process.pid}/exe").samefile(node):
            _deny("V012_CANDIDATE_PROCESS_DENIED")
    except (OSError, ValueError):
        _deny("V012_CANDIDATE_PROCESS_DENIED")


def _auth(directory: Path) -> tuple[bytes, str]:
    raw = _private_config(directory)  # existing Linux mode/ACL/owner gate
    lines = raw.decode("ascii").splitlines()
    values = {}
    for line in lines:
        if "=" in line and not line.startswith("["):
            key, value = line.split("=", 1)
            if key in values:
                _deny("V012_CANDIDATE_CONFIG_DENIED")
            values[key] = value
    if not (re.fullmatch("[a-zA-Z0-9_]{1,48}", values.get("rpcuser", ""))
            and re.fullmatch("[a-f0-9]{64}", values.get("rpcpassword", ""))):
        _deny("V012_CANDIDATE_CONFIG_DENIED")
    secret = (values["rpcuser"] + ":" + values["rpcpassword"]).encode("ascii")
    return sha256(raw).digest(), "Basic " + base64.b64encode(secret).decode("ascii")


def probe_candidate_http(*, node: Path, process: subprocess.Popen,
                         directory: Path, port: int,
                         official_signer: str, official_archive_sha: str,
                         signed_archive_verified: bool, node_sha: str, cli_sha: str,
                         expected_height: int) -> dict:
    """Scope: four genuine *read-only* calls; no activation or write capability."""
    if (type(port) is not int or not 1 <= port <= 65535
            or type(expected_height) is not int or not 1 <= expected_height <= 1000):
        _deny("V012_CANDIDATE_INPUT_DENIED")
    _running(node, process)
    actual = sha256(node.read_bytes()).hexdigest()
    if actual != CANDIDATE_LINUX_WAMD_SHA or actual != node_sha:
        _deny("V012_CANDIDATE_IMAGE_SHA_DENIED")
    digest, credential = _auth(directory)
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=8)
    try:
        conn.connect()  # no HTTP bytes nor auth have been sent here.
        client_port = conn.sock.getsockname()[1]
        for _ in range(15):  # kernel/server accept may lag the TCP handshake
            _running(node, process)
            if _linux_socket(process.pid, port, client_port):
                break
            time.sleep(.05)
        else:
            _deny("V012_CANDIDATE_KERNEL_SOCKET_DENIED")
        values = {}
        for ident, method in enumerate(_READS, start=1):
            params = [0] if method == "getblockhash" else []
            _params(method, params)
            _running(node, process)
            if not _linux_socket(process.pid, port, client_port):
                _deny("V012_CANDIDATE_SOCKET_REBOUND_DENIED")
            if sha256(_private_config(directory)).digest() != digest:
                _deny("V012_CANDIDATE_CONFIG_CHANGED")
            request = json.dumps(
                {"jsonrpc": "1.0", "id": ident, "method": method, "params": params},
                separators=(",", ":")).encode("ascii")
            conn.request("POST", "/", request, {
                "Authorization": credential,
                "Content-Type": "application/json",
                "Connection": "keep-alive",
            })
            response = conn.getresponse()
            blob = response.read(1024 * 1024 + 1)
            if (response.status != 200 or
                    response.getheader("Content-Type", "").split(";")[0].strip() != "application/json"):
                _deny("V012_CANDIDATE_HTTP_DENIED")
            if method == "getnetworkinfo":
                # v0.1.11 runtime MUST reject this candidate version globally.
                try:
                    _reply(blob, ident, method)
                except RpcError as e:
                    if e.args != ("RPC_VERSION_CAPABILITY_DENIED",):
                        _deny("V012_CANDIDATE_V011_PIN_DENIED")
                else:
                    _deny("V012_CANDIDATE_UNSAFE_VERSION_AUTO_ADMIT")
                values[method] = candidate_network_reply(blob, ident)
            else:
                values[method] = _reply(blob, ident, method)
        exact_signed_linux_candidate(
            signed_archive=signed_archive_verified, signer=official_signer,
            archive_sha=official_archive_sha, node_sha=node_sha, cli_sha=cli_sha,
            process_is_owned=process.poll() is None,
            chain=values["getblockchaininfo"]["chain"],
            genesis=values["getblockhash"], peers=values["getconnectioncount"])
        if (values["getblockcount"] != expected_height or
                values["getblockchaininfo"]["blocks"] != expected_height or
                values["getblockhash"] != REGTEST_GENESIS):
            _deny("V012_CANDIDATE_CHAIN_HEIGHT_DENIED")
        result = candidate_scope_status()
        result.update({
            "signed_real_core_http_reads": True,
            "linux_candidate_rpc_shape_checked": True,
            "observed_zero_peers": values["getconnectioncount"] == 0,
            "read_count": len(_READS),
            "authenticated_loopback": True,
            "kernel_owned_socket": True,
            "candidate_rpc_profile": values["getnetworkinfo"],
            "candidate_chain": "regtest",
            "candidate_height": expected_height,
            "genesis": REGTEST_GENESIS,
            "current_app_v011_refuses_v012": True,
            "no_cli_reads_for_http_probe": True,
            "no_real_wallet_or_mainnet_access": True,
        })
        return result
    except Candidate012Denied:
        raise
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, http.client.HTTPException, RpcError):
        _deny("V012_CANDIDATE_HTTP_PROBE_DENIED")
    finally:
        conn.close()
