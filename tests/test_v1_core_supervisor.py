"""Supplemental T05 fixture unit contracts: no synthetic chain PASS."""
from contextlib import contextmanager,ExitStack
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from wam_regtest.core_supervisor import CoreSupervisor,ManagedCoreError
from wam_regtest.supervisor_protocol import PROTOCOL,request_proof
from wam_regtest.supervisor_store import read_exact


@unittest.skipUnless(os.name=="posix","Windows native Core ownership has separate runner")
class CoreSupervisorContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="wam-t05-owner-")
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve(strict=True)/"wam-fusion-core-0123456789abcdef"
        self.root.mkdir(mode=0o700)
        self.core=self.root.parent/"public-core-source"
        self.core.mkdir()

    def patched(self):
        stack=ExitStack()
        from wam_regtest.wsp_live import REGTEST_GENESIS
        receipt={"wamd_sha256":"a"*64,"wam_cli_sha256":"b"*64}
        stack.enter_context(patch("wam_regtest.core_supervisor.verified_core_paths",
            return_value=(self.core/"wamd",self.core/"wam-cli",receipt)))
        stack.enter_context(patch("wam_regtest.custody.create_directory",
            side_effect=lambda p:p.mkdir(mode=0o700)))
        stack.enter_context(patch("wam_regtest.core_supervisor._write_private_config",
            side_effect=lambda p,a,b:(p/"wam.conf").write_text("PUBLIC_TEST_ONLY")))
        stack.enter_context(patch("wam_regtest.custody.storage",
            return_value=type("Store",(),{"validate_directory":staticmethod(lambda p:p.is_dir())})()))
        return stack

    def test_durable_profile_reopen_and_single_owner_gate(self):
        with self.patched():
            owner=CoreSupervisor(self.root,self.core,authorized=True)
            try:
                old=read_exact(self.root,"supervisor.profile")
                token=read_exact(self.root,"supervisor.token",length=32)
                chain=owner.directory
                self.assertEqual(owner.status()["state"],"stopped")
                with self.assertRaises(Exception):
                    CoreSupervisor(self.root,self.core,authorized=True)
            finally:
                owner.close_listener();owner.stack.close()
            owner=CoreSupervisor(self.root,self.core,authorized=True)
            try:
                self.assertEqual(chain,owner.directory)
                self.assertEqual(read_exact(self.root,"supervisor.profile"),old)
                self.assertEqual(read_exact(self.root,"supervisor.token"),token)
                self.assertFalse(owner.status()["mainnet_allowed"])
            finally:owner.close_listener();owner.stack.close()

    def test_partial_control_receipt_does_not_adopt_or_reset(self):
        self.root.joinpath("supervisor.profile").write_text("untrusted")
        self.root.joinpath("supervisor.profile").chmod(0o600)
        with self.patched():
            with self.assertRaises(ManagedCoreError):
                CoreSupervisor(self.root,self.core,authorized=True)
        self.assertEqual((self.root/"supervisor.profile").read_text(),"untrusted")
        self.assertFalse((self.root/"chain").exists())

    def test_token_authenticated_status_and_replay(self):
        with self.patched():
            owner=CoreSupervisor(self.root,self.core,authorized=True)
            try:
                token=read_exact(self.root,"supervisor.token",length=32)
                nonce="1"*32
                frame=(json.dumps({"protocol":PROTOCOL,"op":"status","nonce":nonce,
                    "proof":request_proof(token,"status",nonce)})+"\n").encode("ascii")
                reply=owner.handle(frame)
                self.assertEqual(reply["nonce"],nonce)
                self.assertEqual(reply["state"],"stopped")
                self.assertRegex(reply["proof"],r"^[0-9a-f]{64}$")
                with self.assertRaises(Exception):owner.handle(frame)
            finally:owner.close_listener();owner.stack.close()


class SupervisorTransportResilience(unittest.TestCase):
    """GUI/client crashes must never tear down the long-lived Core owner."""

    class _Client:
        def __init__(self,frames,*,drop_on_reply=False):
            self.frames=list(frames)
            self.drop_on_reply=drop_on_reply
            self.sent=b""
            self.timeouts=[]

        def settimeout(self,seconds):
            self.timeouts.append(seconds)

        def recv(self,limit):
            if not self.frames:return b""
            data=self.frames.pop(0)
            if isinstance(data,Exception):raise data
            if len(data)>limit:raise AssertionError("unbounded IPC read")
            return data

        def sendall(self,data):
            if self.drop_on_reply:raise BrokenPipeError("disposable client disconnected")
            self.sent+=data

    def _owner(self):
        from wam_regtest.supervisor_protocol import SupervisorProtocolError
        owner=CoreSupervisor.__new__(CoreSupervisor)
        def deny(_):
            raise SupervisorProtocolError("SUPERVISOR_FRAME_DENIED")
        owner.handle=deny
        return owner

    def test_client_disappears_before_reply_supervisor_survives(self):
        client=self._Client([b"bad\\n"],drop_on_reply=True)
        self._owner()._serve_client(client)
        self.assertTrue(client.timeouts)

    def test_stalled_or_aborted_client_is_rejected_without_server_crash(self):
        import socket
        for failure in (socket.timeout("slow client"),ConnectionResetError("abort")):
            client=self._Client([failure])
            self._owner()._serve_client(client)
            status=json.loads(client.sent)
            self.assertEqual(status["state"],"error")
            self.assertFalse(status["mainnet_allowed"])
            self.assertEqual(status["chain"],"regtest")
            self.assertNotIn("abort",client.sent.decode())

    def test_oversized_unterminated_frame_is_denied(self):
        client=self._Client([b"x"*256]*16)
        self._owner()._serve_client(client)
        self.assertEqual(json.loads(client.sent)["state"],"error")
        self.assertTrue(all(0<timeout<=3.0 for timeout in client.timeouts))
