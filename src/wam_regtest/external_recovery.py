"""Reconnection and recovery for external Core read-only attachment.

On any disconnect or identity mismatch we discard the previous attachment and
require a fresh authorization decision. We never silently migrate an external
attached node to Fusion managed-Core ownership.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .external_core import ExternalCoreAttachment, ExternalAttachmentError
from .telemetry import increment


class ExternalRecoveryError(RuntimeError):
    """Fixed redacted recovery status."""


@dataclass(frozen=True)
class ReconnectPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 8.0
    identity_ttl_seconds: float = 5.0


class ExternalCoreSession:
    """Session wrapper that re-creates ExternalCoreAttachment on reconnect.

    Each successful (re)connect requires:
      - operator consent (supplied via authorize callback);
      - fresh process/socket/chain attestation;
      - matching genesis and version.

    If reconnection cannot prove the same or a newly-authorized external Core,
    the session enters RECOVERY_NEEDED and refuses RPC until the operator
    explicitly authorizes again.
    """

    def __init__(self, *, authorize: Callable[[], dict], policy: ReconnectPolicy | None = None):
        if not callable(authorize):
            raise ExternalRecoveryError('EXTERNAL_RECOVERY_AUTHORIZE_CALLBACK_REQUIRED')
        self._authorize = authorize
        self._policy = policy or ReconnectPolicy()
        self._attachment: ExternalCoreAttachment | None = None
        self._last_identity_time: float = 0.0
        self._recovery_needed = False
        self._last_spec: dict | None = None

    def _is_fresh_identity(self) -> bool:
        return (self._attachment is not None
                and time.monotonic() - self._last_identity_time <= self._policy.identity_ttl_seconds)

    def _connect(self, spec: dict | None = None):
        if spec is None:
            spec = self._authorize()
        required = ('pid', 'rpc_port', 'datadir', 'core_dir', 'operator_consent')
        if not all(k in spec for k in required) or spec.get('operator_consent') is not True:
            raise ExternalRecoveryError('EXTERNAL_RECOVERY_AUTHORIZATION_DENIED')
        # Treat any change in PID, port, datadir, core_dir or cookie path as a
        # different external node that requires explicit fresh authorization.
        if self._last_spec is not None:
            for key in ('pid', 'rpc_port', 'datadir', 'core_dir', 'auth_cookie'):
                if self._last_spec.get(key) != spec.get(key):
                    raise ExternalRecoveryError('EXTERNAL_RECOVERY_IDENTITY_CHANGED')
        attachment = ExternalCoreAttachment(
            pid=int(spec['pid']),
            rpc_port=int(spec['rpc_port']),
            datadir=Path(spec['datadir']),
            core_dir=Path(spec['core_dir']),
            operator_consent=True,
            timeout=float(spec.get('timeout', 10.0)),
            auth_cookie=Path(spec['auth_cookie']) if spec.get('auth_cookie') else None,
        )
        self._attachment = attachment
        self._last_spec = dict(spec)
        self._last_identity_time = time.monotonic()
        self._recovery_needed = False
        increment('external_recovery_connected')

    def _ensure_attached(self):
        if self._recovery_needed:
            raise ExternalRecoveryError('EXTERNAL_RECOVERY_NEEDED')
        if self._attachment is None:
            self._connect()
            return
        if not self._is_fresh_identity():
            try:
                # Lightweight identity re-attestation without RPC.
                self._attachment._assert_process_image()
                self._last_identity_time = time.monotonic()
            except ExternalAttachmentError:
                self._attachment.close()
                self._attachment = None
                self._reconnect()

    def _reconnect(self):
        last_error = None
        for attempt in range(self._policy.max_attempts):
            try:
                # Reconnect to the originally authorized spec only.
                self._connect(self._last_spec)
                return
            except ExternalAttachmentError as exc:
                last_error = exc
                delay = min(self._policy.base_delay_seconds * (2 ** attempt),
                            self._policy.max_delay_seconds)
                time.sleep(delay)
        self._recovery_needed = True
        raise ExternalRecoveryError('EXTERNAL_RECOVERY_FAILED') from last_error

    def read(self, method: str, params: list | None = None):
        if params is None:
            params = []
        self._ensure_attached()
        try:
            result = self._attachment.read(method, params)
            self._last_identity_time = time.monotonic()
            return result
        except ExternalAttachmentError as exc:
            # Any identity drift or unreachable error triggers recovery.
            self._attachment.close()
            self._attachment = None
            if exc.args[0] in (
                'EXTERNAL_ATTACHMENT_RPC_UNREACHABLE',
                'EXTERNAL_ATTACHMENT_RPC_NODE_BUSY',
                'EXTERNAL_ATTACHMENT_SOCKET_OWNER_DENIED',
                'EXTERNAL_ATTACHMENT_IMAGE_DENIED',
                'EXTERNAL_ATTACHMENT_BINARY_CHANGED',
                'EXTERNAL_ATTACHMENT_CHAIN_DENIED',
                'EXTERNAL_ATTACHMENT_GENESIS_DENIED',
                'EXTERNAL_ATTACHMENT_VERSION_DENIED',
            ):
                self._reconnect()
                return self._attachment.read(method, params)
            self._recovery_needed = True
            raise ExternalRecoveryError('EXTERNAL_RECOVERY_NEEDED') from exc

    def status(self) -> dict:
        return {
            'recovery_needed': self._recovery_needed,
            'attached': self._attachment is not None and not self._recovery_needed,
        }

    def close(self):
        if self._attachment is not None:
            self._attachment.close()
            self._attachment = None
        self._recovery_needed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False
