"""Safe, explicit, read-only attachment to an already-running WAM Core REGTEST node.

This module distinguishes *observed* external Core authority from *Fusion-owned*
managed-Core authority. It never adopts, terminates, edits config/datadir, loads a
wallet, or acquires mining/signing authority through read-only attachment.
"""
from __future__ import annotations

import base64
import http.client
import json
import os
import socket
import stat
import sys
import time
from pathlib import Path

from .core_process import CoreBindingError, _image, _metadata, _linux_socket, _mac_socket, _windows_socket
from .json_rpc import RpcError, _reply, _params, _HTTP_READS, SUPPORTED_RPC, MAX_REPLY, MAX_BLOCK_REPLY
from .telemetry import increment
from .wsp_live import REGTEST_GENESIS


class ExternalAttachmentError(ValueError):
    """Fixed redacted error; no paths/credentials/process details."""


class ExternalCoreAttachment:
    """Read-only observer of an already-running genuine WAM Core REGTEST process.

    The operator must explicitly authorize attachment. Before any credentials are
    sent, we verify:
      - the declared PID exists and its process image is the expected wamd binary;
      - the server half of the loopback socket is owned by that same PID;
      - the RPC chain is regtest and the genesis hash matches the pinned WSP value;
      - the RPC version tuple matches the supported v0.1.11 tuple.

    Only idempotent read methods are allowed. Writes, wallet loads, and any
    operation that could mutate the external node are denied at the boundary.
    """

    def __init__(self, *, pid: int, rpc_port: int, datadir: Path,
                 core_dir: Path, operator_consent: bool,
                 timeout: float = 10.0, auth_cookie: Path | None = None):
        if operator_consent is not True:
            raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_CONSENT_REQUIRED')
        if type(pid) is not int or pid <= 0:
            raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_PID_REQUIRED')
        if type(rpc_port) is not int or not 1024 <= rpc_port <= 65535:
            raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_PORT_REQUIRED')
        if type(datadir) is not type(Path()) or not datadir.is_absolute():
            raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_DATADIR_REQUIRED')
        if type(core_dir) is not type(Path()) or not core_dir.is_absolute():
            raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_CORE_DIR_REQUIRED')
        if type(timeout) not in (int, float) or not 1 <= timeout <= 60:
            raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_TIMEOUT_REQUIRED')

        self._pid = pid
        self._rpc_port = rpc_port
        self._datadir = datadir
        self._core_dir = core_dir
        self._timeout = float(timeout)
        self._auth_cookie = auth_cookie
        self._closed = False

        # Resolve expected binaries from core_dir (trusted review boundary).
        self._node, self._cli, self._receipt = self._verified_core_paths(core_dir)
        self._node_meta = _metadata(self._node)

        # Verify the external process image matches the expected binary.
        self._assert_process_image()

        # Load credentials from explicit cookie path or datadir cookie file.
        self._auth = self._load_auth()

        # Verify RPC endpoint ownership and chain identity before any credential use.
        self._attest_endpoint()

        increment('external_attachment_created')

    @staticmethod
    def _verified_core_paths(core_dir: Path):
        from .core import verified_core_paths
        return verified_core_paths(core_dir)

    def _assert_process_image(self):
        try:
            image = _image(self._pid, self._datadir)
        except CoreBindingError as exc:
            raise ExternalAttachmentError(exc.args[0]) from None
        same = (os.path.samefile(image, self._node) if sys.platform == 'win32'
                else os.path.normcase(image) == os.path.normcase(str(self._node.resolve(strict=True))))
        if not same:
            raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_IMAGE_DENIED')
        # Binary metadata must still match the trusted receipt.
        try:
            if _metadata(self._node) != self._node_meta:
                raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_BINARY_CHANGED')
        except CoreBindingError as exc:
            raise ExternalAttachmentError(exc.args[0]) from None

    def _load_auth(self):
        """Load credentials from cookie file only when safely accessible.

        On Windows we use the repository's existing native private-file boundary.
        On POSIX the cookie file must be regular, owner-only, not a symlink, and
        owned by the current user (same-user attachment only).
        """
        if self._auth_cookie is not None:
            cookie_path = self._auth_cookie
        else:
            cookie_path = self._datadir / 'regtest' / '.cookie'

        if sys.platform == 'win32':
            from .windows_core_transport import read_private, WindowsCoreTransportError
            # Windows: read through native private-file guard; path must be under datadir.
            rel = cookie_path.relative_to(self._datadir)
            try:
                raw = read_private(self._datadir, str(rel).replace('\\', '/'))
            except WindowsCoreTransportError as exc:
                raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_COOKIE_CUSTODY_DENIED') from None
        else:
            try:
                s = cookie_path.lstat()
            except OSError:
                raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_COOKIE_INACCESSIBLE') from None

            if (not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or cookie_path.is_symlink()
                    or s.st_uid != os.geteuid() or stat.S_IMODE(s.st_mode) != 0o600):
                raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_COOKIE_CUSTODY_DENIED')

            try:
                raw = cookie_path.read_bytes()
            except OSError:
                raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_COOKIE_INACCESSIBLE') from None

        if not 10 <= len(raw) <= 512 or b':' not in raw:
            raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_COOKIE_INVALID')
        return base64.b64encode(raw).decode('ascii')

    def _socket_proof(self):
        """Verify that the loopback RPC socket server side is owned by self._pid."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(self._timeout)
            try:
                probe.connect(('127.0.0.1', self._rpc_port))
            except (OSError, socket.timeout):
                raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_RPC_UNREACHABLE') from None
            local = probe.getsockname()
            remote = probe.getpeername()
            if local[0] != '127.0.0.1' or remote[0] != '127.0.0.1':
                raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_LOOPBACK_REQUIRED')
            self._assert_process_image()
            if sys.platform == 'darwin':
                found = _mac_socket(self._pid, remote[1], local[1])
            elif sys.platform == 'linux':
                found = _linux_socket(self._pid, remote[1], local[1])
            elif sys.platform == 'win32':
                found = _windows_socket(self._pid, remote[1], local[1], self._datadir)
            else:
                raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_PLATFORM_UNSUPPORTED')
            if not found:
                raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_SOCKET_OWNER_DENIED')
            return probe

    def _attest_endpoint(self):
        """Verify chain, genesis and version before trusting the RPC endpoint."""
        # First verify socket ownership without sending credentials.
        self._socket_proof()

        # Only after socket ownership proof do we send credentials for chain attestation.
        blockchain = self._rpc('getblockchaininfo', [])
        if type(blockchain) is not dict or blockchain.get('chain') != 'regtest':
            raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_CHAIN_DENIED')
        genesis_hash = self._rpc('getblockhash', [0])
        if genesis_hash != REGTEST_GENESIS:
            raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_GENESIS_DENIED')
        network = self._rpc('getnetworkinfo', [])
        if (type(network) is not dict
                or (network.get('version'), network.get('subversion'), network.get('protocolversion')) != SUPPORTED_RPC):
            raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_VERSION_DENIED')
        increment('external_attachment_attested')

    def _rpc(self, method: str, params: list):
        if self._closed:
            raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_CLOSED')
        _params(method, params)
        identifier = int(time.time() * 1000) & 0x7FFFFFFF
        body = json.dumps({'jsonrpc': '1.0', 'id': identifier, 'method': method, 'params': params},
                          ensure_ascii=True).encode('utf8')

        # Re-attest process/socket on every call; fail closed on identity drift.
        self._assert_process_image()

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(self._timeout)
            try:
                probe.connect(('127.0.0.1', self._rpc_port))
            except (OSError, socket.timeout):
                raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_RPC_UNREACHABLE') from None
            local, remote = probe.getsockname(), probe.getpeername()
            self._assert_process_image()
            if sys.platform == 'darwin':
                found = _mac_socket(self._pid, remote[1], local[1])
            elif sys.platform == 'linux':
                found = _linux_socket(self._pid, remote[1], local[1])
            elif sys.platform == 'win32':
                found = _windows_socket(self._pid, remote[1], local[1], self._datadir)
            else:
                raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_PLATFORM_UNSUPPORTED')
            if not found:
                raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_SOCKET_OWNER_DENIED')

            conn = http.client.HTTPConnection('127.0.0.1', self._rpc_port, timeout=self._timeout)
            try:
                conn.sock = probe
                headers = {
                    'Authorization': f'Basic {self._auth}',
                    'Content-Type': 'application/json',
                }
                conn.request('POST', '/', body, headers)
                response = conn.getresponse()
                # Distinguish HTTP 503 work-queue busy from transport/auth/identity failures.
                if response.status == 503:
                    increment('external_attachment_503_observed')
                    raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_RPC_NODE_BUSY')
                if response.status == 401:
                    raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_RPC_AUTH_DENIED')
                if response.status != 200:
                    raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_RPC_TRANSPORT_DENIED')
                raw = response.read(MAX_BLOCK_REPLY if method == 'getblock' else MAX_REPLY)
            except http.client.HTTPException:
                raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_RPC_FAILED') from None
            except OSError:
                raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_RPC_UNREACHABLE') from None
            finally:
                conn.close()

        try:
            return _reply(raw, identifier, method)
        except RpcError as exc:
            # Pass through known busy/error signals so contention layer can handle them.
            if exc.args[0] in ('RPC_CORE_WARMUP',):
                raise
            raise ExternalAttachmentError(exc.args[0]) from None

    def read(self, method: str, params: list | None = None):
        """Execute one allowed read-only RPC call with re-attestation."""
        if params is None:
            params = []
        if method not in _HTTP_READS:
            raise ExternalAttachmentError('EXTERNAL_ATTACHMENT_READ_SCOPE_DENIED')
        return self._rpc(method, params)

    def status(self) -> dict:
        """Return externally observed status; never claim managed-Core ownership."""
        return {
            'busy': False,
            'external_core_process_observed': self._pid if not self._closed else None,
            'core_process_owned': False,  # External attachment is observation, not ownership.
            'chain_height': None,
            'tip': None,
        }

    def close(self):
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False
