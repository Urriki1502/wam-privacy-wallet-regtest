"""K-10 source fixture is public-contract-tested without running Core.

Mocked Core RPC response tests do not prove real signing, chain custody or
cross-host success. The script itself requires a live isolated signed Core
before private REGTEST backup keys may be written by its genuine run.
"""
from contextlib import contextmanager, ExitStack
from pathlib import Path
import json
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock,patch

from scripts.issue45_k10_core_source_fixture import (
    generate_disposable_core_fixture,K10SourceFixtureError,
)
from wam_regtest.core_sqlite_import import inspect_sqlite_backup
from wam_regtest.wsp_live import REGTEST_GENESIS


class K10CoreSourceFixtureContracts(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix="k10-core-public-producer-")
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name).resolve()
        self.output=self.root/"private-output"
        self.core=self.root/"signed-disposable-core"
        self.dummy=self.root/"public-fixture-sqlite.dat"
        conn=sqlite3.connect(self.dummy)
        conn.execute("CREATE TABLE public_fixture (value INTEGER)")
        conn.commit()
        conn.close()
        self.dummy.chmod(0o600)
        self.desc={
            "descriptors":[
                {"desc":"wpkh([abc123]tpubPUBLICONLY/0/*)#pub","internal":False},
                {"desc":"wpkh([abc123]tpubPUBLICONLY/1/*)#pub","internal":True}
            ]
        }

    def mocks(self):
        stack=ExitStack()
        self.addCleanup(stack.close)
        proof={"wamd_sha256":"a"*64,"wam_cli_sha256":"b"*64,
               "platform":"linux-x86_64"}
        verify=stack.enter_context(patch(
            "scripts.issue45_k10_core_source_fixture.verified_core_paths",
            return_value=(None,None,proof)))
        def new_directory(path):
            path.mkdir(mode=0o700,exist_ok=False)
        create=stack.enter_context(patch(
            "scripts.issue45_k10_core_source_fixture.create_directory",
            side_effect=new_directory))
        core=Mock()
        core.receipt=proof
        core.read.attest.return_value={"chain":"regtest","blocks":0}
        @contextmanager
        def owner(path,*,authorized=False):
            if authorized is not True:raise ValueError
            yield core
        process=stack.enter_context(patch(
            "scripts.issue45_k10_core_source_fixture.disposable_core",
            side_effect=owner))
        def read_rpc(owned,wallet,method,*args,**kwargs):
            if method=="createwallet":return {"name":"k04-source"}
            if method=="getwalletinfo":
                return {"format":"sqlite","descriptors":True}
            if method=="getblockchaininfo":return {"chain":"regtest"}
            if method=="getblockhash":return REGTEST_GENESIS
            if method=="getnewaddress":return "bcrt1qpublicfixtureonly"
            if method=="generatetoaddress":return ["a"*64 for _ in range(101)]
            if method=="listdescriptors":return self.desc
            if method=="backupwallet":
                output=kwargs["backup_target"]
                shutil.copyfile(self.dummy,output)
                output.chmod(0o600)
                return None
            raise AssertionError("unexpected RPC")
        rpc=stack.enter_context(patch(
            "scripts.issue45_k10_core_source_fixture._wallet_rpc",
            side_effect=read_rpc))
        return proof,verify,create,process,rpc

    def generate(self,**changes):
        args={"authorized":True}
        args.update(changes)
        return generate_disposable_core_fixture(
            self.core,self.output,**args)

    def test_disposable_source_writes_backup_and_redacted_manifest_once(self):
        proof,verify,create,process,rpc=self.mocks()
        result=self.generate()
        self.assertEqual(result["schema"],
                         "wam-fusion-k10-disposable-core-transfer/v1")
        self.assertEqual(result["chain"],"regtest")
        self.assertFalse(result["cross_os_core_restore_qualified"])
        self.assertFalse(result["signer_allowed"])
        self.assertFalse(result["mainnet_allowed"])
        backup=self.output/"core-wallet-backup.dat"
        assert backup.exists()
        self.assertEqual(inspect_sqlite_backup(backup).file_sha256,
                         result["backup_sha256"])
        self.assertEqual(json.loads(
            (self.output/"public-manifest.json").read_text()),result)
        self.assertNotIn("PUBLICONLY",str(result))
        self.assertNotIn("bcrt1q",str(result))
        process.assert_called_once_with(self.core,authorized=True)
        self.assertEqual(sum(c.args[2]=="backupwallet"
                             for c in rpc.call_args_list),1)

    def test_existing_output_or_wrong_consent_refused_before_source(self):
        _,_,_,process,_=self.mocks()
        self.output.mkdir()
        (self.output/"do-not-overwrite").write_bytes(b"old")
        with self.assertRaisesRegex(K10SourceFixtureError,
                                    "K10_SOURCE_FIXTURE_OUTPUT_DENIED"):
            self.generate()
        self.assertEqual((self.output/"do-not-overwrite").read_bytes(),b"old")
        with self.assertRaisesRegex(K10SourceFixtureError,
                                    "K10_SOURCE_FIXTURE_CONSENT_REQUIRED"):
            self.generate(authorized=False)
        process.assert_not_called()

    def test_no_private_fixture_manifest_if_core_identity_changed(self):
        proof,_,_,_,_=self.mocks()
        proof["wamd_sha256"]="f"*64
        # Both verifier and process share the same mutated reference here.
        # Assert a *mismatched* process identity instead.
        with patch("scripts.issue45_k10_core_source_fixture.disposable_core") as launch:
            @contextmanager
            def changed(path,*,authorized=False):
                record=Mock()
                record.receipt={"wamd_sha256":"f"*64,
                                "wam_cli_sha256":"c"*64}
                yield record
            launch.side_effect=changed
            with self.assertRaisesRegex(K10SourceFixtureError,
                                        "K10_SOURCE_FIXTURE_NOT_QUALIFIED"):
                self.generate()
        self.assertFalse((self.output/"public-manifest.json").exists())
        self.assertTrue(self.output.exists())

    def test_wrong_chain_refused_without_backup(self):
        _,_,_,_,rpc=self.mocks()
        old=rpc.side_effect
        def wrong_chain(owned,wallet,method,*args,**kwargs):
            if method=="getblockhash":return "f"*64
            return old(owned,wallet,method,*args,**kwargs)
        rpc.side_effect=wrong_chain
        with self.assertRaisesRegex(
                K10SourceFixtureError,"K10_SOURCE_FIXTURE_NOT_QUALIFIED"):
            self.generate()
        self.assertFalse((self.output/"core-wallet-backup.dat").exists())
        self.assertFalse((self.output/"public-manifest.json").exists())

    def test_failure_after_copy_never_writes_success_manifest(self):
        _,_,_,_,rpc=self.mocks()
        old=rpc.side_effect
        def torn_backup(owned,wallet,method,*args,**kwargs):
            reply=old(owned,wallet,method,*args,**kwargs)
            if method=="backupwallet":
                output=kwargs["backup_target"]
                output.write_bytes(b"TORN_PUBLIC_DISPOSABLE_SQLITE")
            return reply
        rpc.side_effect=torn_backup
        with self.assertRaisesRegex(
                K10SourceFixtureError,"K10_SOURCE_FIXTURE_NOT_QUALIFIED"):
            self.generate()
        self.assertFalse((self.output/"public-manifest.json").exists())
        self.assertTrue((self.output/"core-wallet-backup.dat").exists())


if __name__=="__main__":
    unittest.main()
