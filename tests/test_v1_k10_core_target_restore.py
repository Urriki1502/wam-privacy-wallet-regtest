"""K-10 isolated SQLite transfer destination contracts, no owner wallets.

The input is a newly-created disposable local SQLite database; RPC calls
are mocked ONLY in these source tests. Genuine WAM Core restore behavior
requires a separate native E2E run, never claimed by a mocked response.
"""
from contextlib import contextmanager, ExitStack
from hashlib import sha256
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts.issue45_k10_core_target_restore import (
    qualify_isolated_core_restore, K10CoreTransferRefusal,
)
from wam_regtest.core_sqlite_import import inspect_sqlite_backup
from wam_regtest.v1_contracts import core_descriptor_identity
from wam_regtest.wsp_live import REGTEST_GENESIS

DESCRIPTORS={
    "descriptors":[
        {"desc":"wpkh([abcd1234/84h/1h/0h]tpubPUBLICONLY/0/*)#example","internal":False},
        {"desc":"wpkh([abcd1234/84h/1h/0h]tpubPUBLICONLY/1/*)#example","internal":True},
    ]
}


class K10IsolatedCoreTransferContracts(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix="k10-core-target-public-")
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name).resolve()
        self.source=self.root/"disposable-core-original.dat"
        self.core=self.root/"public-signed-core"
        conn=sqlite3.connect(self.source)
        conn.execute("CREATE TABLE public_fixture (value INTEGER)")
        conn.commit()
        conn.close()
        self.source.chmod(0o600)
        self.digest=sha256(self.source.read_bytes()).hexdigest()
        self.desc=core_descriptor_identity(DESCRIPTORS)

    def qualify(self,**changes):
        opts={
            "expected_backup_sha256":self.digest,
            "expected_descriptor_sha256":self.desc,
            "authorized":True,
        }
        opts.update(changes)
        return qualify_isolated_core_restore(self.core,self.source,**opts)

    def mocks(self):
        stack=ExitStack()
        self.addCleanup(stack.close)
        immutable={"wamd_sha256":"a"*64,"wam_cli_sha256":"b"*64}
        verify=stack.enter_context(patch(
            "scripts.issue45_k10_core_target_restore.verified_core_paths",
            return_value=(None,None,immutable)))
        def create(path):
            path.mkdir(mode=0o700,exist_ok=False)
        stack.enter_context(patch(
            "scripts.issue45_k10_core_target_restore.create_directory",
            side_effect=create))
        def stage(original,folder,*,authorized=False):
            if authorized is not True:
                raise ValueError("source not approved")
            target=folder/"wallet-disposable-test-copy.dat"
            shutil.copyfile(original,target)
            target.chmod(0o600)
            return target,inspect_sqlite_backup(target)
        stage_mock=stack.enter_context(patch(
            "scripts.issue45_k10_core_target_restore.stage_verified_backup",
            side_effect=stage))
        core=Mock()
        core.receipt=immutable
        core.read.attest.return_value={"chain":"regtest","blocks":0}
        @contextmanager
        def isolated(path,*,authorized=False):
            if authorized is not True:
                raise ValueError
            yield core
        process=stack.enter_context(patch(
            "scripts.issue45_k10_core_target_restore.disposable_core",
            side_effect=isolated))
        def rpc(owned,wallet,method,*args,**kw):
            if method=="getblockhash" and args==("0",):
                return REGTEST_GENESIS
            if method=="restorewallet":
                return {"name":"k04-reviewed"}
            if method=="getwalletinfo":
                return {"format":"sqlite","descriptors":True,
                        "private_keys_enabled":True,"scanning":False}
            if method=="listdescriptors":
                return DESCRIPTORS
            raise AssertionError("Unexpected RPC")
        rpc_mock=stack.enter_context(patch(
            "scripts.issue45_k10_core_target_restore._wallet_rpc",
            side_effect=rpc))
        return verify,stage_mock,process,rpc_mock,core

    def test_exact_digest_descriptor_restored_only_to_disposable_core(self):
        verify,stage,process,rpc,core=self.mocks()
        before=self.source.read_bytes()
        result=self.qualify()
        self.assertEqual(result["status"],
                         "K10_CORE_SQLITE_ISOLATED_RESTORE_VERIFIED")
        self.assertTrue(result["core_native_restorewallet_observed"])
        self.assertTrue(result["descriptor_public_identity_matched_expected"])
        self.assertTrue(result["source_backup_byte_identity_preserved"])
        self.assertEqual(self.source.read_bytes(),before)
        process.assert_called_once_with(self.core,authorized=True)
        self.assertEqual(sum(c.args[2]=="restorewallet"
                             for c in rpc.call_args_list),1)
        for flag in ("destination_restored_into_fusion",
                     "origin_os_provenance_verified",
                     "cross_os_physical_qualified",
                     "original_wsp_history_reconciled",
                     "signed_uncertain_reservations_reconciled",
                     "new_native_anchor_created","safe_to_unlock",
                     "signer_allowed","broadcast_allowed","mainnet_allowed"):
            self.assertIs(result[flag],False,flag)
        self.assertNotIn(self.desc,str(result))
        self.assertNotIn(self.digest,str(result))

    def test_wrong_digest_or_consent_never_launches_core(self):
        _,_,process,_,_=self.mocks()
        with self.assertRaisesRegex(
                K10CoreTransferRefusal,
                "K10_CORE_TRANSFER_SOURCE_HASH_DENIED"):
            self.qualify(expected_backup_sha256="f"*64)
        with self.assertRaisesRegex(
                K10CoreTransferRefusal,
                "K10_CORE_TRANSFER_EXPLICIT_TEST_CONSENT_REQUIRED"):
            self.qualify(authorized=False)
        process.assert_not_called()

    def test_descriptor_mismatch_is_denied_not_spend_authorized(self):
        _,_,process,rpc,_=self.mocks()
        with self.assertRaisesRegex(
                K10CoreTransferRefusal,
                "K10_CORE_TRANSFER_DESCRIPTOR_MISMATCH"):
            self.qualify(expected_descriptor_sha256="f"*64)
        self.assertTrue(process.called)
        self.assertTrue(rpc.called)

    def test_wrong_network_or_unowned_binary_fails_closed(self):
        _,_,process,_,core=self.mocks()
        core.read.attest.return_value={"chain":"main","blocks":0}
        with self.assertRaisesRegex(
                K10CoreTransferRefusal,"K10_CORE_TRANSFER_WRONG_CHAIN"):
            self.qualify()
        core.read.attest.return_value={"chain":"regtest","blocks":0}
        core.receipt={"wamd_sha256":"f"*64,
                      "wam_cli_sha256":"b"*64}
        with self.assertRaisesRegex(
                K10CoreTransferRefusal,
                "K10_CORE_TRANSFER_BINARY_CHANGED"):
            self.qualify()

    def test_restore_rpc_warning_and_failure_refused(self):
        _,_,_,rpc,_=self.mocks()
        rpc.side_effect=lambda owned,wallet,method,*args,**kw: (
            {"name":"k04-reviewed","warnings":["unsafe"]}
            if method=="restorewallet"
            else REGTEST_GENESIS if method=="getblockhash"
            else {"chain":"regtest"}
        )
        with self.assertRaisesRegex(
                K10CoreTransferRefusal,
                "K10_CORE_TRANSFER_RESTORE_UNVERIFIED"):
            self.qualify()

    def test_source_modified_after_restored_is_refused(self):
        _,_,_,rpc,_=self.mocks()
        original=rpc.side_effect
        def corrupt_after_restore(owned,wallet,method,*args,**kw):
            value=original(owned,wallet,method,*args,**kw)
            if method=="listdescriptors":
                self.source.write_bytes(self.source.read_bytes()+b"CORRUPT")
            return value
        rpc.side_effect=corrupt_after_restore
        with self.assertRaisesRegex(
                K10CoreTransferRefusal,
                "K10_CORE_TRANSFER_RESTORE_FAILED"):
            self.qualify()

    def test_invalid_backup_path_or_hash_denied_before_process(self):
        _,_,process,_,_=self.mocks()
        with self.assertRaisesRegex(
                K10CoreTransferRefusal,"K10_CORE_TRANSFER_INPUT_DENIED"):
            self.qualify(expected_backup_sha256="INVALID")
        with self.assertRaisesRegex(
                K10CoreTransferRefusal,"K10_CORE_TRANSFER_INPUT_DENIED"):
            qualify_isolated_core_restore(
                self.core,Path("relative.dat"),
                expected_backup_sha256=self.digest,
                expected_descriptor_sha256=self.desc,authorized=True)
        process.assert_not_called()


if __name__=="__main__":
    unittest.main()
