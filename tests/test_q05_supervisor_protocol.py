"""Unit-only tests: never imply genuine Core/GUI/frozen acceptance."""
import hmac
import json
import unittest
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
            guard.challenge="c"*32
            self.assertEqual(guard.verify(self.frame(op=op)),op)
            with self.assertRaisesRegex(SupervisorProtocolError,"SUPERVISOR_AUTH_DENIED"):
                guard.verify(self.frame(op=op))

    def test_wrong_secret_or_modified_operation_denied(self):
        guard=ReplayGuard(SECRET)
        guard.challenge="c"*32
        frame=self.frame("status",proof=request_proof(b"x"*32,"status",NONCE,"c"*32))
        with self.assertRaisesRegex(SupervisorProtocolError,"SUPERVISOR_AUTH_DENIED"):
            guard.verify(frame)
        with self.assertRaisesRegex(SupervisorProtocolError,"SUPERVISOR_AUTH_DENIED"):
            guard.verify(self.frame("start",proof=request_proof(SECRET,"status",NONCE,"c"*32)))

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

    def test_replay_cache_bound_is_fail_closed(self):
        g=ReplayGuard(SECRET,limit=1)
        g.challenge="c"*32
        self.assertEqual(g.verify(self.frame()),"status")
        with self.assertRaisesRegex(SupervisorProtocolError,"SUPERVISOR_AUTH_DENIED"):
            g.verify(self.frame(nonce="b"*32))

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
        raw=self.frame('start',challenge=first.challenge)
        self.assertEqual(first.verify(raw),'start')
        second=ReplayGuard(SECRET)
        with self.assertRaises(SupervisorProtocolError):second.verify(raw)

    def test_response_authentication_covers_public_state(self):
        from wam_regtest.supervisor_protocol import response_proof
        ready=public_status(state='ready',owned=True,chain_height=101)
        altered=public_status(state='ready',owned=True,chain_height=102)
        self.assertNotEqual(response_proof(SECRET,NONCE,ready),response_proof(SECRET,NONCE,altered))
