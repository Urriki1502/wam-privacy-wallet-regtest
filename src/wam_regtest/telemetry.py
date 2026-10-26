"""Observable acceptance counters for Q03 persistent-session reuse measurements.

These are developer-only telemetry counters. They are not part of the wallet
security boundary and must not be exposed to end users or production flows.
"""
from threading import Lock

_lock = Lock()
_counts = {
    "verified_core_paths": 0,
    "cli_spawn": 0,
    "http_connection_create": 0,
    "http_socket_connect": 0,
    "http_request": 0,
    "rpc_attest": 0,
    "wallet_session_rpc_client_create": 0,
}


def increment(name: str, delta: int = 1) -> int:
    with _lock:
        _counts[name] = _counts.get(name, 0) + delta
        return _counts[name]


def get(name: str) -> int:
    with _lock:
        return _counts.get(name, 0)


def reset() -> None:
    with _lock:
        for key in _counts:
            _counts[key] = 0


def snapshot() -> dict:
    with _lock:
        return dict(_counts)
