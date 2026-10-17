"""Real TCP slow-peer negatives, NOT synthetic Core/chain acceptance."""
from contextlib import contextmanager
from pathlib import Path
import socket
import threading
import time
import unittest
from unittest.mock import patch

from wam_regtest.managed_scan_client import ManagedScanRpc, ManagedScanError
from wam_regtest.supervisor_client import control, ManagedClientError


@contextmanager
def slow_unverified_peer():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(2)
    stop = threading.Event()
    accepted = []
    def serve():
        try:
            with listener.accept()[0] as connection:
                accepted.append(True)
                connection.settimeout(1)
                connection.recv(4096)  # public test-token request, no Core secrets
                connection.sendall(b"{")
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline and not stop.wait(.02):
                    connection.sendall(b" ")
        except OSError:
            pass  # Client deadline/close is the expected refusal.
    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    try:
        yield listener.getsockname()[1], accepted
    finally:
        stop.set()
        listener.close()
        worker.join(timeout=3)
        if worker.is_alive():
            raise AssertionError("SLOW_PEER_FIXTURE_NOT_REAPED")


class ManagedIpcDeadline(unittest.TestCase):
    def test_control_trickle_cannot_extend_whole_request_budget(self):
        with slow_unverified_peer() as (port, accepted):
            with patch("wam_regtest.supervisor_client._profile_read",
                       return_value={"control_port": port}), patch(
                       "wam_regtest.supervisor_client.read_exact", return_value=b"t" * 32):
                started = time.monotonic()
                with self.assertRaises(ManagedClientError):
                    control(Path.cwd(), timeout=.15)
                elapsed = time.monotonic() - started
        self.assertEqual(len(accepted), 1)  # no automatic replay/reconnect
        self.assertLess(elapsed, 1.25)

    def test_scan_trickle_cannot_extend_whole_request_budget(self):
        with slow_unverified_peer() as (port, accepted):
            with patch("wam_regtest.managed_scan_client._profile_read",
                       return_value={"control_port": port}), patch(
                       "wam_regtest.managed_scan_client.read_exact", return_value=b"t" * 32):
                client = ManagedScanRpc(Path.cwd(), authorized_readonly=True, timeout=.5)
                try:
                    started = time.monotonic()
                    with self.assertRaises(ManagedScanError):
                        client._request("getblockcount", [])
                    elapsed = time.monotonic() - started
                finally:
                    client.close()
        self.assertEqual(len(accepted), 1)
        self.assertLess(elapsed, 1.5)
