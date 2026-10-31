"""Unit-only tests: never imply genuine Core/GUI/frozen acceptance."""
import hmac
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from wam_regtest.supervisor_protocol import (
    PROTOCOL,MAX_FRAME,ReplayGuard,SupervisorProtocolError,decode_frame,
    public_status,request_proof,
)

SECRET=b"t"*32
NONCE="a"*32


class SupervisorProtocolContracts(unittest.TestCase):
    def frame(self,op="status",nonce=NONCE,proof=None,challenge="c"*32):
        return (json.dumps({"protocol":PROTOCOL,"op":op,"nonce":nonce,
            "challenge":challenge,"proof":proof or request_proof(SECRET,op,nonce,challenge)},sort_keys=True)+"\n").encode("ascii")

    def test_authenticated_status_and_control_are_distinct(self):
        for op in ("status","start","shutdown"):
            guard=ReplayGuard(SECRET)
            challenge=guard.hello()["challenge"]
            self.assertEqual(guard.verify(self.frame(op=op,challenge=challenge),challenge),op)
            with self.assertRaisesRegex(SupervisorProtocolError,"SUPERVISOR_AUTH_DENIED"):
                guard.verify(self.frame(op=op,challenge=challenge),challenge)

    def test_wrong_secret_or_modified_operation_denied(self):
        guard=ReplayGuard(SECRET)
        challenge=guard.hello()["challenge"]
        frame=self.frame("status",challenge=challenge,proof=request_proof(b"x"*32,"status",NONCE,challenge))
        with self.assertRaisesRegex(SupervisorProtocolError,"SUPERVISOR_AUTH_DENIED"):
            guard.verify(frame,challenge)
        challenge=guard.hello()["challenge"]
        with self.assertRaisesRegex(SupervisorProtocolError,"SUPERVISOR_AUTH_DENIED"):
            guard.verify(self.frame("start",challenge=challenge,proof=request_proof(SECRET,"status",NONCE,challenge)),challenge)

    def test_duplicate_json_and_oversize_denied(self):
        raw=b'{"protocol":"x","protocol":"y","op":"status","nonce":"'+b"a"*32+b'","proof":"'+b"0"*64+b'"}\n'
        with self.assertRaisesRegex(SupervisorProtocolError,"SUPERVISOR_DUPLICATE_FIELD_DENIED"):
            decode_frame(raw)
        for invalid in (b"",b"{}\n"*3000,b"{}",b"{}\n\n",b"\xff\n"):
            with self.assertRaises(SupervisorProtocolError):decode_frame(invalid)

    def test_privileged_unknown_command_never_valid(self):
        for op in ("rpc","sendrawtransaction","stop","attach","restart","createwallet"):
            with self.assertRaisesRegex(SupervisorProtocolError,"SUPERVISOR_AUTH_INPUT_DENIED"):
                request_proof(SECRET,op,NONCE,"c"*32)

    def test_pending_capacity_recovers_without_reaccepting_old_grant(self):
        g=ReplayGuard(SECRET,limit=1)
        c=g.hello()['challenge']
        with self.assertRaises(SupervisorProtocolError):g.hello()
        old=self.frame(challenge=c)
        self.assertEqual(g.verify(old,c),'status')
        for _ in range(5000):
            current=g.hello()['challenge']
            self.assertEqual(g.verify(self.frame(challenge=current),current),'status')
        with self.assertRaises(SupervisorProtocolError):g.verify(old,c)

    def test_expired_discarded_and_cross_connection_grants_refused(self):
        with patch('wam_regtest.supervisor_protocol.time.monotonic',return_value=1) as now:
            g=ReplayGuard(SECRET,limit=2,ttl=5)
            first=g.hello()['challenge'];second=g.hello()['challenge']
            with self.assertRaises(SupervisorProtocolError):
                g.verify(self.frame(challenge=first),second)
            self.assertEqual(g.verify(self.frame(challenge=first),first),'status')
            c=g.hello()['challenge'];raw=self.frame(challenge=c)
            now.return_value=7
            with self.assertRaises(SupervisorProtocolError):g.verify(raw,c)
            next_c=g.hello()['challenge'];g.discard(next_c)
            with self.assertRaises(SupervisorProtocolError):g.verify(self.frame(challenge=next_c),next_c)

    def test_concurrent_replay_has_exactly_one_winner(self):
        g=ReplayGuard(SECRET);c=g.hello()['challenge'];raw=self.frame(challenge=c)
        def attempt(_):
            try:g.verify(raw,c);return 1
            except SupervisorProtocolError:return 0
        with ThreadPoolExecutor(max_workers=16) as workers:
            self.assertEqual(sum(workers.map(attempt,range(100))),1)

    def test_concurrent_clients_rotate_independently(self):
        g=ReplayGuard(SECRET,limit=32)
        def request(_):
            c=g.hello()['challenge']
            return g.verify(self.frame(challenge=c),c)
        with ThreadPoolExecutor(max_workers=16) as workers:
            self.assertEqual(list(workers.map(request,range(512))),['status']*512)

    def test_public_status_only_redacted_runtime_claim(self):
        result=public_status(state="ready",chain_height=103,owned=True)
        self.assertEqual(result["chain"],"regtest")
        self.assertFalse(result["mainnet_allowed"])
        self.assertNotIn("token",result)
        for args in ({"state":"mainnet"},{"state":"ready","chain_height":-1},
                     {"state":"ready","owned":1},{"state":"ready","chain_height":True}):
            with self.assertRaises(SupervisorProtocolError):public_status(**args)

    def test_captured_request_cannot_replay_after_supervisor_restart(self):
        first=ReplayGuard(SECRET)
        challenge=first.hello()['challenge']
        raw=self.frame('start',challenge=challenge)
        self.assertEqual(first.verify(raw,challenge),'start')
        second=ReplayGuard(SECRET)
        with self.assertRaises(SupervisorProtocolError):second.verify(raw,second.hello()["challenge"])

    def test_response_authentication_covers_public_state(self):
        from wam_regtest.supervisor_protocol import response_proof
        ready=public_status(state='ready',owned=True,chain_height=101)
        altered=public_status(state='ready',owned=True,chain_height=102)
        self.assertNotEqual(response_proof(SECRET,NONCE,ready),response_proof(SECRET,NONCE,altered))
