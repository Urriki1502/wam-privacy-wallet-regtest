"""T-06 protected existing Core attach negative contracts; not real-Core proof."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock,patch

from wam_regtest.attached_core import (
    AttachedCoreBinding,AttachedCoreError,AttachedReadOnlyCore,_birth,
)
from wam_regtest.json_rpc import ManagedReadRpc,RpcError


class ExistingCoreAttachContracts(unittest.TestCase):
    def test_attach_requires_exact_consent_absolute_paths_and_observed_pid(self):
        base=Path.cwd()
        for pid in (True,0,1,-1,"123",None,2**31):
            with self.subTest(pid=pid):
                with self.assertRaises(AttachedCoreError):
                    AttachedCoreBinding(base,base,pid,authorized_readonly=True)
        with self.assertRaises(AttachedCoreError):
            AttachedCoreBinding(base,base,os.getpid())
        with self.assertRaises(AttachedCoreError):
            AttachedCoreBinding(Path("relative"),base,os.getpid(),
                                authorized_readonly=True)
        with self.assertRaisesRegex(
            AttachedCoreError,"^ATTACH_READONLY_CONSENT_REQUIRED$"):
            AttachedReadOnlyCore(base,base,os.getpid())

    def test_process_identity_reuse_denied_before_socket_or_core_request(self):
        binder=object.__new__(AttachedCoreBinding)
        binder.pid=54321
        binder._birth_id=("platform",54321,"first-process")
        with (patch("wam_regtest.attached_core._birth",
                    return_value=("platform",54321,"reused-pid")),
              patch("wam_regtest.attached_core._image") as image):
            with self.assertRaisesRegex(
                    AttachedCoreError,"^ATTACH_PID_REUSED_OR_EXITED$"):
                binder._assert_image()
            image.assert_not_called()

    def test_external_binding_cannot_upgrade_to_wallet_or_write_authority(self):
        reader=object.__new__(ManagedReadRpc)
        reader._connection=Mock()
        reader._connection._binding=object()
        for method,args in (("sendrawtransaction",["00"]),
                            ("testmempoolaccept",[["00"]]),
                            ("gettxout",["a"*64,0,True])):
            with self.subTest(method=method):
                with self.assertRaisesRegex(
                        RpcError,"^RPC_ATTACHED_WRITE_DENIED$"):
                    reader.write_owned_regtest(method,args,authorized=True)
        with self.assertRaisesRegex(RpcError,"^RPC_ATTACHED_WALLET_READ_DENIED$"):
            reader.mining_snapshot(authorized_readonly=True)
        reader._connection.request.assert_not_called()

    def test_readonly_wrapper_denies_all_core_mutations_before_socket(self):
        attached=object.__new__(AttachedReadOnlyCore)
        attached._reader=Mock()
        for name,args in (("stop",[]),("createwallet",["test"]),
                          ("loadwallet",["test"]),("sendrawtransaction",["00"]),
                          ("generatetoaddress",[1,"address"]),("dumpprivkey",["a"])):
            with self.subTest(method=name):
                with self.assertRaises(RpcError):
                    attached.call(name,args)
        attached._reader.call.assert_not_called()

    def test_native_pid_birth_is_observed_not_caller_supplied(self):
        # Native platform process metadata; no WAM Core executable launched.
        # A regular Python runner is allowed to have arbitrary argv.
        identity=_birth(os.getpid())
        self.assertIsInstance(identity,tuple)
        self.assertGreaterEqual(len(identity),3)
        if sys.platform=="linux":
            self.assertEqual(identity[0],"linux")
            self.assertIsInstance(identity[1],int)
        elif sys.platform=="darwin":
            self.assertEqual(identity[0],"macos")
        elif sys.platform=="win32":
            self.assertEqual(identity[0],"windows")


if __name__=="__main__":
    unittest.main()
