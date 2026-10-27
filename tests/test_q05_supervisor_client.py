"""Control wire fixtures; no real Core/frozen qualification is implied."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from wam_regtest import supervisor_client as client
from wam_regtest.supervisor_protocol import ReplayGuard, public_status, response_proof

SECRET = b't' * 32


class Peer:
    def __init__(self, *, bad_hello=False, bad_reply=False, duplicate=False):
        self.guard = ReplayGuard(SECRET)
        hello = self.guard.hello()
        if bad_hello:
            hello['proof'] = 'é' * 64
        self.data = (json.dumps(hello) + '\n').encode()
        self.bad_reply, self.duplicate = bad_reply, duplicate
        self.sent = []

    def __enter__(self): return self
    def __exit__(self, *_): pass
    def settimeout(self, *_): pass

    def recv(self, size):
        part, self.data = self.data[:size], self.data[size:]
        return part

    def sendall(self, raw):
        self.sent.append(raw)
        self.guard.verify(raw)
        message = json.loads(raw)
        status = public_status(state='ready', owned=True, chain_height=101)
        proof = response_proof(SECRET, message['nonce'], status)
        if self.bad_reply:
            status['height'] = 102
        reply = json.dumps(dict(status, nonce=message['nonce'], proof=proof))
        if self.duplicate:
            reply = reply[:-1] + ',"height":101}'
        self.data = (reply + '\n').encode()


class ClientContracts(unittest.TestCase):
    def control(self, peer, op='status', authorized=False):
        with patch.object(client, '_profile_read', return_value={'control_port': 19001}), \
             patch.object(client, 'read_exact', return_value=SECRET), \
             patch.object(client.socket, 'create_connection', return_value=peer):
            return client.control(Path('/public-unit-fixture'), op, authorized=authorized)

    def test_authenticated_status_and_explicit_control(self):
        for op in ('status', 'start', 'shutdown'):
            result = self.control(Peer(), op, authorized=op != 'status')
            self.assertEqual(result['height'], 101)

    def test_unapproved_control_cannot_open_socket(self):
        peer = Peer()
        with self.assertRaises(client.ManagedClientError):
            self.control(peer, 'start')
        self.assertEqual(peer.sent, [])

    def test_wrong_server_proof_sends_no_request(self):
        peer = Peer(bad_hello=True)
        with self.assertRaises(client.ManagedClientError): self.control(peer)
        self.assertEqual(peer.sent, [])

    def test_modified_response_and_duplicate_fields_refused(self):
        for peer in (Peer(bad_reply=True), Peer(duplicate=True)):
            with self.assertRaises(client.ManagedClientError): self.control(peer)

    def test_truncated_or_oversize_hello_refused(self):
        for data in (b'{}', b'x' * 514, b'\xff\n'):
            peer = Peer()
            peer.data = data
            with self.assertRaises(client.ManagedClientError): self.control(peer)
            self.assertEqual(peer.sent, [])
