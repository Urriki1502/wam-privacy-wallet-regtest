"""RPC contention handling for read-only attachment and managed Core reads.

Provides bounded backoff with jitter for idempotent reads, GUI refresh
coalescing, and visible NODE BUSY status. Writes are never retried.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable

from .telemetry import increment


class RpcContentionError(RuntimeError):
    """Fixed redacted contention status; no credentials or paths."""


@dataclass(frozen=True)
class BackoffPolicy:
    """Bounded exponential backoff with jitter for idempotent reads only."""
    base_seconds: float = 0.25
    max_seconds: float = 8.0
    max_retries: int = 3
    jitter: float = 0.25

    def delay(self, attempt: int) -> float:
        if not 0 <= attempt < self.max_retries:
            raise RpcContentionError('RPC_CONTENTION_RETRY_EXHAUSTED')
        exponential = self.base_seconds * (2 ** attempt)
        capped = min(exponential, self.max_seconds)
        jitter_amount = capped * self.jitter * (2 * random.random() - 1)
        return max(0.01, capped + jitter_amount)


class ReadCoalescer:
    """Coalesce GUI refresh ticks during genuine Core RPC busy state.

    After observing a busy signal (HTTP 503 or RPC_NODE_BUSY), the supervisor
    returns cached busy status for a short cooldown instead of hammering Core.
    It still independently re-attests native process identity on every status
    call, but avoids issuing new RPC until the cooldown expires.
    """

    def __init__(self, cooldown_seconds: float = 12.0):
        if not 1.0 <= cooldown_seconds <= 60.0:
            raise RpcContentionError('RPC_CONTENTION_COOLDOWN_INVALID')
        self._cooldown = float(cooldown_seconds)
        self._busy_until: float | None = None

    def mark_busy(self):
        self._busy_until = time.monotonic() + self._cooldown
        increment('rpc_contention_busy_marked')

    def is_busy(self) -> bool:
        if self._busy_until is None:
            return False
        if time.monotonic() >= self._busy_until:
            self._busy_until = None
            return False
        return True

    def reset(self):
        self._busy_until = None


class ContentionAwareRpc:
    """Wrap a read-only RPC callable with bounded retry and busy coalescing.

    The underlying callable must raise a fixed error whose first argument is one
    of the recognized busy signals. Writes are rejected at the boundary.
    """

    _BUSY_SIGNALS = frozenset((
        'RPC_CORE_WARMUP',
        'RPC_NODE_BUSY',
        'EXTERNAL_ATTACHMENT_RPC_NODE_BUSY',
    ))

    def __init__(self, read_callable: Callable, policy: BackoffPolicy | None = None,
                 coalescer: ReadCoalescer | None = None,
                 ownership_attest_callable: Callable | None = None):
        if not callable(read_callable):
            raise RpcContentionError('RPC_CONTENTION_CALLABLE_REQUIRED')
        self._read = read_callable
        self._policy = policy or BackoffPolicy()
        self._coalescer = coalescer or ReadCoalescer()
        self._ownership_attest = ownership_attest_callable

    def _is_busy_signal(self, error) -> bool:
        return (isinstance(error, Exception)
                and error.args
                and error.args[0] in self._BUSY_SIGNALS)

    def _is_auth_signal(self, error) -> bool:
        return (isinstance(error, Exception)
                and error.args
                and error.args[0] in ('EXTERNAL_ATTACHMENT_RPC_AUTH_DENIED',))

    def read(self, method: str, params: list | None = None):
        if params is None:
            params = []
        if self._coalescer.is_busy():
            increment('rpc_contention_coalesced')
            raise RpcContentionError('RPC_NODE_BUSY')

        last_error = None
        for attempt in range(self._policy.max_retries + 1):
            try:
                return self._read(method, params)
            except Exception as exc:
                last_error = exc
                if self._is_auth_signal(exc):
                    # Auth failure is never a transient busy signal.
                    raise
                if not self._is_busy_signal(exc):
                    raise
                if attempt < self._policy.max_retries:
                    delay = self._policy.delay(attempt)
                    increment('rpc_contention_retry')
                    time.sleep(delay)
                else:
                    self._coalescer.mark_busy()
                    raise RpcContentionError('RPC_NODE_BUSY') from exc

        # Unreachable, but guard anyway.
        self._coalescer.mark_busy()
        raise RpcContentionError('RPC_NODE_BUSY') from last_error

    def status(self) -> dict:
        """Return supervisor-visible status without hitting Core RPC if busy."""
        busy = self._coalescer.is_busy()
        owned = False
        if self._ownership_attest is not None:
            try:
                owned = bool(self._ownership_attest())
            except Exception:
                owned = False
        return {
            'busy': busy,
            'core_process_owned': owned,
            'chain_height': None,
            'tip': None,
        }

    def reset(self):
        self._coalescer.reset()
