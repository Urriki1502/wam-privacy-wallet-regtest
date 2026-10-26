"""Q03 shared authenticated HTTP JSON-RPC transport contracts.

Tests use a local loopback HTTP server and a dummy binding so they do not
require a real Core process. They verify fail-closed behavior, malformed reply
handling, config drift, node-busy retry bounds and write-method refusal.
"""
from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import socketserver
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from wam_regtest import json_rpc as json_rpc_module
from wam_regtest.core_process import CoreBindingError
from wam_regtest.json_rpc import (
    ManagedReadRpc,
    RpcError,
    _params,
    _reply,
    _result,
)
from wam_regtest.network_policy import NetworkPolicyError, parse_local_config


VALID_CONFIG = b"""regtest=1
server=1
[regtest]
port=19000
rpcport=19001
rpcuser=disposable_0000000000000001
rpcpassword=0000000000000000000000000000000000000000000000000000000000000001
rpcbind=127.0.0.1
rpcallowip=127.0.0.1
listen=0
connect=0
dnsseed=0
discover=0
upnp=0
txindex=1
blockfilterindex=1
coinstatsindex=1
fallbackfee=0.0001
"""

_CHANGED_CONFIG = VALID_CONFIG.replace(b"rpcport=19001", b"rpcport=19002")

REGTEST_GENESIS = "b88f3d262f285e38e184f50bf3eea1c8e615486ae67d3d9eaf0976fbd6d3d30d"


def _auth_for(config: bytes) -> str:
    values = dict(line.split("=", 1) for line in config.decode("ascii").splitlines()[3:])
    return "Basic " + base64.b64encode(
        (values["rpcuser"] + ":" + values["rpcpassword"]).encode("ascii")
    ).decode("ascii")


class _DummyBinding:
    """Acceptable to ManagedReadRpc because we patch json_rpc.OwnedCoreBinding."""

    def __init__(self, core: Path, directory: Path, *, fail_after: int = 0):
        self.core = core
        self.directory = directory
        self._fail_after = fail_after
        self._calls = 0

    def _assert_image(self):
        self._calls += 1
        if 0 < self._fail_after < self._calls:
            raise CoreBindingError("RPC_OWNED_PROCESS_EXITED")

    def assert_socket(self, sock):
        pass


class _JsonRpcHandler(http.server.BaseHTTPRequestHandler):
    """Method -> result/error/status; shared state via server_instance."""

    expected_auth: str = ""
    busy_remaining: int = 0
    fail_next_status: int | None = None
    fail_next_body: bytes = b""
    _id_counter: int = 0
    _lock = threading.Lock()

    def log_message(self, fmt, *args):
        pass

    def _body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length)

    def do_POST(self):
        body = self._body()
        with self._lock:
            _JsonRpcHandler._id_counter += 1

        auth = self.headers.get("Authorization", "")
        if auth != self.expected_auth:
            self.send_response(401)
            self.end_headers()
            return

        if _JsonRpcHandler.fail_next_status is not None:
            status = _JsonRpcHandler.fail_next_status
            payload = _JsonRpcHandler.fail_next_body
            _JsonRpcHandler.fail_next_status = None
            _JsonRpcHandler.fail_next_body = b""
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)
            return

        if _JsonRpcHandler.busy_remaining > 0:
            _JsonRpcHandler.busy_remaining -= 1
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"result":null,"error":null,"id":0}')
            return

        try:
            req = json.loads(body.decode("utf8"))
        except Exception:
            self.send_response(400)
            self.end_headers()
            return

        method = req.get("method")
        identifier = req.get("id")
        result = None
        error = None
        if method == "getblockchaininfo":
            result = {"chain": "regtest", "blocks": 102}
        elif method == "getblockhash":
            height = req["params"][0]
            result = REGTEST_GENESIS if height == 0 else "a" * 64
        elif method == "getnetworkinfo":
            result = {"version": 111, "subversion": "/WAM:0.1.11/", "protocolversion": 70016}
        elif method == "getconnectioncount":
            result = 0
        elif method == "getblockcount":
            result = 102
        elif method == "getbestblockhash":
            result = "b" * 64
        elif method == "getblock":
            result = {"hash": req["params"][0], "height": 1, "tx": []}
        else:
            error = {"code": -32601, "message": "method not found"}

        response = json.dumps({"result": result, "error": error, "id": identifier}).encode("utf8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(response)


class _Server(socketserver.TCPServer):
    allow_reuse_address = True


class LocalJsonRpcContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._orig_binding = json_rpc_module.OwnedCoreBinding
        json_rpc_module.OwnedCoreBinding = _DummyBinding
        cls._server = _Server(("127.0.0.1", 0), _JsonRpcHandler)
        cls.port = cls._server.server_address[1]
        cls._server_thread = threading.Thread(target=cls._server.serve_forever, daemon=True)
        cls._server_thread.start()
        cls.core_dir = Path(tempfile.mkdtemp())
        cls.datadir = Path(tempfile.mkdtemp())

    @classmethod
    def tearDownClass(cls):
        cls._server.shutdown()
        cls._server.server_close()
        json_rpc_module.OwnedCoreBinding = cls._orig_binding

    def setUp(self):
        _JsonRpcHandler.expected_auth = _auth_for(VALID_CONFIG)
        _JsonRpcHandler.busy_remaining = 0
        _JsonRpcHandler.fail_next_status = None
        _JsonRpcHandler.fail_next_body = b""
        self._config_patch = patch.object(
            json_rpc_module, "_private_config", return_value=VALID_CONFIG
        )
        self._config_patch.start()
        self.addCleanup(self._config_patch.stop)

    def _make_config_for_port(self, port: int) -> bytes:
        return VALID_CONFIG.replace(b"rpcport=19001", f"rpcport={port}".encode("ascii"))

    def _transport(self, *, config: bytes | None = None, binding: _DummyBinding | None = None):
        if config is None:
            config = self._make_config_for_port(self.port)
        if binding is None:
            binding = _DummyBinding(self.core_dir, self.datadir)
        self._config_patch.stop()
        new_patch = patch.object(json_rpc_module, "_private_config", return_value=config)
        new_patch.start()
        self.addCleanup(new_patch.stop)
        return ManagedReadRpc(self.core_dir, self.datadir, authorized_readonly=True, binding=binding)

    def test_parse_local_config_accepts_valid(self):
        self.assertEqual(parse_local_config(VALID_CONFIG), 19001)

    def test_parse_local_config_denies_remote_or_incomplete(self):
        for bad in (
            b"mainnet=1\nserver=1\n[regtest]\n" + b"\n".join(
                line for line in VALID_CONFIG.splitlines()[3:] if not line.startswith((b"port", b"rpcport"))
            ) + b"\nport=1\nrpcport=2\n",
            VALID_CONFIG.replace(b"rpcbind=127.0.0.1", b"rpcbind=0.0.0.0"),
            VALID_CONFIG + b"rpcconnect=127.0.0.1\n",
            VALID_CONFIG.replace(b"[regtest]", b"[main]"),
        ):
            with self.subTest(bad[:40]):
                with self.assertRaises(NetworkPolicyError):
                    parse_local_config(bad)

    def test_params_allows_read_methods(self):
        _params("getblockchaininfo", [])
        _params("getblockcount", [])
        _params("getblockhash", [1])
        _params("getblock", ["a" * 64, 3])

    def test_params_denies_writes_and_bad_arguments(self):
        with self.assertRaisesRegex(RpcError, "RPC_READ_SCOPE_DENIED"):
            _params("sendrawtransaction", ["00"])
        with self.assertRaisesRegex(RpcError, "RPC_PARAMS_DENIED"):
            _params("getblockchaininfo", [1])
        with self.assertRaisesRegex(RpcError, "RPC_PARAMS_DENIED"):
            _params("getblockhash", ["not-int"])
        with self.assertRaisesRegex(RpcError, "RPC_PARAMS_DENIED"):
            _params("getblock", ["short", 2])

    def test_reply_accepts_valid(self):
        self.assertEqual(_reply(b'{"result":102,"error":null,"id":1}', 1, "getblockcount"), 102)

    def test_reply_denies_malformed(self):
        cases = [
            (b"not json", "non-JSON"),
            (b'{"result":1,"error":null}', "missing id"),
            (b'{"result":1,"error":null,"id":2}', "wrong id"),
            (b'{"result":1,"error":null,"id":1,"extra":2}', "extra key"),
            (b'{"result":1,"id":1}', "missing error"),
            (b'{"id":1,"id":2,"result":1,"error":null}', "duplicate keys"),
            (b"" , "empty body"),
        ]
        for raw, label in cases:
            with self.subTest(label):
                with self.assertRaisesRegex(RpcError, "RPC_REPLY_INVALID"):
                    _reply(raw, 1, "getblockcount")

    def test_reply_denies_oversized(self):
        big = b'{"result":' + b'"' + b"x" * (json_rpc_module.MAX_REPLY + 10) + b'","error":null,"id":1}'
        with self.assertRaisesRegex(RpcError, "RPC_REPLY_INVALID"):
            _reply(big, 1, "getblockcount")

    def test_result_denies_unsupported_version(self):
        with self.assertRaisesRegex(RpcError, "RPC_VERSION_CAPABILITY_DENIED"):
            _result("getnetworkinfo", {"version": 110, "subversion": "/WAM:0.1.10/", "protocolversion": 70015})

    def test_transport_attests_and_reads(self):
        with self._transport() as rpc:
            info = rpc.call("getblockchaininfo", [])
            self.assertEqual(info["chain"], "regtest")
            count = rpc.call("getblockcount", [])
            self.assertEqual(count, 102)

    def test_transport_redacts_repr(self):
        with self._transport() as rpc:
            text = repr(rpc)
            self.assertNotIn("rpcpassword", text)
            self.assertNotIn("Basic ", text)
            self.assertIn("redacted", text)

    def test_authentication_denied_closes(self):
        _JsonRpcHandler.expected_auth = "Basic invalid"
        with self.assertRaisesRegex(RpcError, "RPC_AUTHENTICATION_DENIED"):
            with self._transport() as rpc:
                rpc.call("getblockcount", [])

    def test_node_busy_retries_then_succeeds(self):
        _JsonRpcHandler.busy_remaining = 1
        with self._transport() as rpc:
            self.assertEqual(rpc.call("getblockcount", []), 102)

    def test_node_busy_exhausted_fails_closed(self):
        _JsonRpcHandler.busy_remaining = 3
        with self.assertRaisesRegex(RpcError, "RPC_NODE_BUSY"):
            with self._transport() as rpc:
                rpc.call("getblockcount", [])

    def test_config_drift_fails_closed(self):
        base_config = self._make_config_for_port(self.port)
        changed_config = base_config.replace(b"rpcport=" + str(self.port).encode(),
                                             b"rpcport=19002")

        with self._transport(config=base_config) as rpc:
            rpc._request("getblockcount", [])
            with patch.object(json_rpc_module, "_private_config", return_value=changed_config):
                with self.assertRaisesRegex(RpcError, "RPC_CONFIG_CHANGED"):
                    rpc._assert_config()

    def test_core_restart_fails_closed(self):
        binding = _DummyBinding(self.core_dir, self.datadir, fail_after=1)
        with self.assertRaisesRegex(RpcError, "RPC_OWNED_PROCESS_EXITED"):
            with self._transport(binding=binding) as rpc:
                rpc.call("getblockcount", [])

    def test_no_write_retry(self):
        with self._transport() as rpc:
            with self.assertRaisesRegex(RpcError, "RPC_READ_SCOPE_DENIED"):
                rpc.call("sendrawtransaction", ["00"])

    def test_malformed_http_response(self):
        _JsonRpcHandler.fail_next_status = 200
        _JsonRpcHandler.fail_next_body = b'{"result": null, "error": null, "id": 0'
        with self.assertRaisesRegex(RpcError, "RPC_REPLY_INVALID"):
            with self._transport() as rpc:
                rpc.call("getblockcount", [])

    def test_explicit_read_consent_required(self):
        with self.assertRaisesRegex(RpcError, "RPC_EXPLICIT_READ_CONSENT_REQUIRED"):
            ManagedReadRpc(self.core_dir, self.datadir, authorized_readonly=False,
                           binding=_DummyBinding(self.core_dir, self.datadir))

    def test_managed_process_binding_required(self):
        class NotABinding:
            core = self.core_dir
            directory = self.datadir
        with self.assertRaisesRegex(RpcError, "RPC_MANAGED_PROCESS_REQUIRED"):
            ManagedReadRpc(self.core_dir, self.datadir, authorized_readonly=True,
                           binding=NotABinding())


class NativeConfigCustodyContracts(unittest.TestCase):
    """Exercise the real native config path on POSIX, if available."""

    @unittest.skipUnless(os.name == "posix", "native custody test is POSIX only")
    def test_private_config_parses_generated_profile(self):
        import sys
        from wam_regtest.core import _write_private_config
        with tempfile.TemporaryDirectory() as t:
            d = Path(t).resolve()
            os.chmod(d, 0o700)
            _write_private_config(d, 12345, 12346)
            # On macOS the native path requires an ACL-free 0o700 directory.
            if sys.platform == "darwin":
                with patch.object(json_rpc_module, "parse_local_config",
                                  side_effect=parse_local_config) as _:
                    raw = json_rpc_module._private_config(d)
                    self.assertEqual(parse_local_config(raw), 12345)
            else:
                raw = json_rpc_module._private_config(d)
                self.assertEqual(parse_local_config(raw), 12345)


if __name__ == "__main__":
    unittest.main()
