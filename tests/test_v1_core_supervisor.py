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

    def test_control_scan_spend_tokens_are_distinct_and_persistent(self):
        from wam_regtest.managed_scan_protocol import (
            encode_request as scan_request,ScanProtocolError)
        from wam_regtest.managed_spend_protocol import (
            encode_request as spend_request,SpendProtocolError)
        from wam_regtest.supervisor_protocol import SupervisorProtocolError
        with self.patched():
            owner=CoreSupervisor(self.root,self.core,authorized=True)
            try:
                control=read_exact(self.root,"supervisor.token",length=32)
                scan=read_exact(self.root,"supervisor.scan.token",length=32)
                spend=read_exact(self.root,"supervisor.spend.token",length=32)
                self.assertEqual(len({control,scan,spend}),3)
                nonce="a"*32
                raw=spend_request(scan,"sendrawtransaction",["01"],nonce)
                with self.assertRaises(SpendProtocolError):
                    owner._spend_handle(raw)
                raw=scan_request(spend,"getblockcount",[],nonce)
                with self.assertRaises(ScanProtocolError):
                    owner._scan_handle(raw)
                raw=(json.dumps({"protocol":PROTOCOL,"op":"start",
                    "nonce":nonce,"proof":request_proof(scan,"start",nonce)})+"\n").encode("ascii")
                with self.assertRaises(SupervisorProtocolError):
                    owner.handle(raw)
                self.assertIsNone(owner.process)
            finally:
                owner.close_listener();owner.stack.close()
            other=CoreSupervisor(self.root,self.core,authorized=True)
            try:
                self.assertEqual(read_exact(self.root,"supervisor.token"),control)
                self.assertEqual(read_exact(self.root,"supervisor.scan.token"),scan)
                self.assertEqual(read_exact(self.root,"supervisor.spend.token"),spend)
            finally:other.close_listener();other.stack.close()

    def test_existing_profile_scoped_upgrade_once_and_partial_refusal(self):
        with self.patched():
            owner=CoreSupervisor(self.root,self.core,authorized=True)
            try:
                old_profile=read_exact(self.root,"supervisor.profile")
                old_control=read_exact(self.root,"supervisor.token")
                chain=owner.directory
            finally:owner.close_listener();owner.stack.close()
            # Simulate an authenticated legacy v1 node created before separate
            # IPC credentials existed: the chain, wallet and profile remain.
            (self.root/"supervisor.scan.token").unlink()
            (self.root/"supervisor.spend.token").unlink()
            upgraded=CoreSupervisor(self.root,self.core,authorized=True)
            try:
                self.assertEqual(chain,upgraded.directory)
                self.assertEqual(read_exact(self.root,"supervisor.profile"),old_profile)
                self.assertEqual(read_exact(self.root,"supervisor.token"),old_control)
                self.assertTrue(read_exact(self.root,"supervisor.scan.token",length=32))
                self.assertTrue(read_exact(self.root,"supervisor.spend.token",length=32))
            finally:upgraded.close_listener();upgraded.stack.close()
            # An interrupted upgrade is ambiguous: never overwrite/reset it.
            retained=read_exact(self.root,"supervisor.scan.token",length=32)
            (self.root/"supervisor.spend.token").unlink()
            with self.assertRaisesRegex(ManagedCoreError,
                    "^MANAGED_IPC_SCOPE_UPGRADE_REQUIRED$"):
                CoreSupervisor(self.root,self.core,authorized=True)
            self.assertEqual(read_exact(self.root,"supervisor.scan.token"),retained)
            self.assertFalse((self.root/"supervisor.spend.token").exists())
            self.assertEqual(read_exact(self.root,"supervisor.profile"),old_profile)

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

    def test_t07_positive_503_status_cooldown_coalesces_reads_and_recovers(self):
        from unittest.mock import Mock
        import threading
        from wam_regtest.json_rpc import RpcError
        from wam_regtest.core_supervisor import BUSY_STATUS_COOLDOWN_SECONDS
        self.assertEqual(BUSY_STATUS_COOLDOWN_SECONDS,12)
        owner=CoreSupervisor.__new__(CoreSupervisor)
        owner._lock=threading.RLock()
        owner._state="ready"
        owner._busy_until=0.0
        owner.process=Mock()
        owner.process.poll.return_value=None
        owner.binding=Mock()
        owner.read=Mock()
        owner.read.attest.side_effect=[
            RpcError("RPC_NODE_BUSY"),
            {"chain":"regtest","blocks":101,"initialblockdownload":False},
        ]
        with patch("wam_regtest.core_supervisor.time.monotonic",
                   side_effect=(100.0,105.0,113.0)):
            first=owner.status()  # Only Core's positive 503 begins cooldown.
            second=owner.status() # Reuses an authenticated busy state, NO RPC.
            third=owner.status()  # Cooldown elapsed; reattest from live Core.
        self.assertEqual(first["state"],"busy")
        self.assertEqual(second["state"],"busy")
        self.assertIsNone(first["height"])
        self.assertIsNone(second["height"])
        self.assertTrue(first["core_process_owned"])
        self.assertEqual(owner.read.attest.call_count,2)
        self.assertEqual(owner.binding._assert_image.call_count,3)
        self.assertEqual(third["state"],"ready")
        self.assertEqual(third["height"],101)
        self.assertEqual(owner._busy_until,0.0)
        self.assertFalse(third["mainnet_allowed"])

    def test_t07_busy_never_masks_core_exit_or_image_change(self):
        from unittest.mock import Mock
        import threading
        for failure in ("exited","changed_image"):
            with self.subTest(failure=failure):
                owner=CoreSupervisor.__new__(CoreSupervisor)
                owner._lock=threading.RLock()
                owner._state="busy"
                owner._busy_until=100000000.0
                owner.process=Mock()
                owner.process.poll.return_value=(1 if failure=="exited" else None)
                owner.binding=Mock()
                if failure=="changed_image":
                    owner.binding._assert_image.side_effect=ValueError("tamper")
                reader=Mock()
                owner.read=reader
                status=owner.status()
                self.assertEqual(status["state"],"recovery-needed")
                self.assertFalse(status["core_process_owned"])
                self.assertIsNone(status["height"])
                self.assertEqual(owner._busy_until,0.0)
                reader.attest.assert_not_called()
                if failure=="exited":
                    reader.close.assert_called_once()
                    self.assertIsNone(owner.read)

    def test_supervisor_core_start_uses_once_verified_rpc_port(self):
        # Unit fixture: the real E2E on each runner separately starts Core.
        from unittest.mock import Mock
        import threading
        owner=CoreSupervisor.__new__(CoreSupervisor)
        owner._lock=threading.RLock()
        owner._consecutive_failures=0
        owner.process=None
        owner.binding=None
        owner.read=None
        owner._state="stopped"
        owner.directory=Path.cwd()/"fixture-chain"
        owner.core=Path.cwd()/"fixture-core"
        owner.node=owner.core/"wamd"
        owner._child_environment=lambda:{"PATH":"/usr/bin"}
        proc=Mock()
        proc.poll.return_value=None
        with (patch("wam_regtest.core_supervisor.local_rpc_port",return_value=27319) as port,
              patch("wam_regtest.core_supervisor.subprocess.Popen",return_value=proc) as spawn,
              patch("wam_regtest.core_supervisor.OwnedCoreBinding") as binding,
              patch.object(owner,"_ready",return_value="verified-owned-read") as ready):
            owner.start()
        port.assert_called_once_with(owner.directory)
        spawn.assert_called_once()
        binding.assert_called_once_with(proc,owner.core,owner.directory)
        self.assertEqual(ready.call_count,1)
        self.assertEqual(ready.call_args.args[1],27319)
        self.assertEqual(owner.read,"verified-owned-read")
        self.assertEqual(owner._state,"ready")

    def test_ready_does_not_reopen_rpc_config_after_launch(self):
        from unittest.mock import Mock
        from types import SimpleNamespace
        import time
        owner=CoreSupervisor.__new__(CoreSupervisor)
        owner.directory=Path.cwd()/"fixture-chain"
        owner.core=Path.cwd()/"fixture-core"
        owner.process=Mock()
        owner.process.poll.return_value=None
        # Explicit method stub: unittest.mock reserves names starting with
        # 'assert_' unless declared on the object.
        owner.binding=SimpleNamespace(assert_socket=Mock())
        class FakeSocket:
            def __enter__(self):return self
            def __exit__(self,*args):return False
        reader=Mock()
        reader._connection=SimpleNamespace(port=27319)
        reader.attest.return_value={"chain":"regtest","blocks":101}
        with (patch("wam_regtest.core_supervisor.local_rpc_port",
                    side_effect=AssertionError("second config read forbidden")) as port,
              patch("wam_regtest.core_supervisor.socket.create_connection",
                    return_value=FakeSocket()) as connect,
              patch("wam_regtest.core_supervisor.ManagedReadRpc",
                    return_value=reader) as read):
            actual=owner._ready(time.monotonic()+3,27319)
        self.assertIs(actual,reader)
        port.assert_not_called()
        connect.assert_called_once_with(("127.0.0.1",27319),timeout=.25)
        owner.binding.assert_socket.assert_called_once()
        read.assert_called_once()
        reader.attest.assert_called_once()

    def test_ready_rejects_unauthorized_config_port_drift(self):
        from unittest.mock import Mock
        from types import SimpleNamespace
        import time
        owner=CoreSupervisor.__new__(CoreSupervisor)
        owner.directory=Path.cwd()/"fixture-chain"
        owner.core=Path.cwd()/"fixture-core"
        owner.process=Mock()
        owner.process.poll.return_value=None
        # Explicit method stub: unittest.mock reserves names starting with
        # 'assert_' unless declared on the object.
        owner.binding=SimpleNamespace(assert_socket=Mock())
        class FakeSocket:
            def __enter__(self):return self
            def __exit__(self,*args):return False
        reader=Mock()
        reader._connection=SimpleNamespace(port=27320)
        with (patch("wam_regtest.core_supervisor.socket.create_connection",
                    return_value=FakeSocket()),
              patch("wam_regtest.core_supervisor.ManagedReadRpc",return_value=reader),
              self.assertRaisesRegex(ManagedCoreError,"MANAGED_CONFIG_PORT_CHANGED")):
            owner._ready(time.monotonic()+3,27319)
        reader.close.assert_called_once()
        reader.attest.assert_not_called()

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
