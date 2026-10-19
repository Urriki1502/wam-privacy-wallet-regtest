"""K-10 locked handoff composition; disposable public seeds and local files.

Positive identities use genuine pinned BIP39/WSP derivation and encrypted v4
backups. Only Core IPC response parsing is simulated in isolated tests;
no test here creates a real Core wallet, restores a persistent signer or
attests a cross-machine/frozen-UI recovery.
"""
import importlib.util
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from mnemonic import Mnemonic

from wam_regtest.bip39_wallet import Bip39RegtestKeys
from wam_regtest.bip39_durable import Bip39DurableKeyring
from wam_regtest.k10_restore_preflight import inspect_locked_clean_host_handoff
from wam_regtest.k10_portability import K10PortabilityError
from wam_regtest.managed_scan_client import ManagedScanRpc
from wam_regtest.wsp_live import REGTEST_GENESIS


SOURCE=Path(importlib.util.find_spec("wam_sp").origin).resolve().parents[2]
PASSWORD=b"PUBLIC_K10_DISPOSABLE_V4_ENVELOPE_PASSWORD"


class K10LockedHandoffContracts(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="k10-readonly-handoff-")
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name).resolve()
        self.phrase=Mnemonic("english").to_mnemonic(bytes([0x45])*32)
        self.passphrase="PUBLIC_K10_ONLY_HANDoFF"
        with Bip39RegtestKeys(
                self.phrase,source=SOURCE,passphrase=self.passphrase,
                authorized_disposable=True) as ring:
            self.original=ring.public_metadata(0)
        with Bip39DurableKeyring.from_phrase(
                self.phrase,source=SOURCE,passphrase=self.passphrase,
                authorized=True) as ring:
            self.backup=ring.backup(PASSWORD)

    def plan(self,**kw):
        args={
            "phrase":self.phrase,"passphrase":self.passphrase,
            "encrypted_backup":self.backup,"backup_password":PASSWORD,
            "account":0,"prior_trusted_public":self.original,
            "wsp_source":SOURCE,"target_root":self.root,"authorized":True,
        }
        args.update(kw)
        return inspect_locked_clean_host_handoff(**args)

    def test_real_mnemonic_plus_v4_backup_and_empty_host_stay_locked(self):
        result=self.plan()
        self.assertEqual(result["status"],
                         "K10_LOCKED_CLEAN_HOST_HANDOFF_INSPECTED")
        self.assertTrue(result["mnemonic_and_encrypted_v4_backup_identity_equal"])
        self.assertTrue(result["clean_target_namespace_no_known_collision"])
        self.assertFalse(result["core_sqlite_source_copy_byte_equal"])
        self.assertIsNone(result["core_regtest_height_observed"])
        for key in (
                "new_native_anchor_created","source_anchor_transplanted",
                "core_sqlite_wallet_restored","fusion_scanner_checkpoint_restored",
                "old_signed_uncertain_reservations_reconciled",
                "historical_chain_rescan_complete","mempool_reorg_resolved",
                "frozen_gui_recovery_verified","clean_os_physical_acceptance",
                "safe_to_create_wallet","safe_to_unlock","signer_allowed",
                "broadcast_allowed","mainnet_allowed"):
            self.assertIs(result[key],False,key)
        self.assertEqual(list(self.root.iterdir()),[])
        for secret in (self.phrase,self.passphrase,self.original["receive_code"],
                       self.original["account_id"]):
            self.assertNotIn(secret,str(result))

    def test_real_sqlite_byte_copy_does_not_count_as_core_restore(self):
        with tempfile.TemporaryDirectory(prefix="k10-public-core-sqlite-") as d:
            source=Path(d)/"public-source.dat"
            target=Path(d)/"public-target.dat"
            connection=sqlite3.connect(source)
            connection.execute("CREATE TABLE public_demo (value INTEGER)")
            connection.commit()
            connection.close()
            source.chmod(0o600)
            shutil.copyfile(source,target)
            target.chmod(0o600)
            original=source.read_bytes()
            report=self.plan(original_core_sqlite=source,
                             transported_core_sqlite=target)
            self.assertTrue(report["core_sqlite_source_copy_byte_equal"])
            self.assertFalse(report["core_sqlite_wallet_restored"])
            self.assertFalse(report["safe_to_create_wallet"])
            self.assertEqual(source.read_bytes(),original)
            self.assertEqual(target.read_bytes(),original)

    def test_mismatched_keyring_or_wrong_owner_prior_denied(self):
        other_phrase=Mnemonic("english").to_mnemonic(bytes([0x46])*32)
        with Bip39DurableKeyring.from_phrase(
                other_phrase,source=SOURCE,passphrase=self.passphrase,
                authorized=True) as other:
            wrong=other.backup(PASSWORD)
        for options in (
                {"encrypted_backup":wrong},
                {"backup_password":b"PUBLIC_BUT_WRONG_PASSWORD"},
                {"prior_trusted_public":dict(self.original,chain="main")},
                {"account":True},
                {"authorized":False}):
            with self.subTest(fields=tuple(options)):
                with self.assertRaises(K10PortabilityError):
                    self.plan(**options)
        self.assertEqual(list(self.root.iterdir()),[])

    def test_refuses_existing_vault_or_partial_runtime_without_cleanup(self):
        chain=self.root/"chain"
        chain.mkdir()
        target=chain/"wallet-runtime.sqlite-wal"
        target.write_bytes(b"OLD_ENCRYPTED_OR_UNCERTAIN_STATE")
        before=target.read_bytes()
        with self.assertRaisesRegex(
                K10PortabilityError,"K10_CLEAN_HOST_OLD_STATE_DENIED"):
            self.plan()
        self.assertEqual(target.read_bytes(),before)

    def test_core_source_copy_mismatch_cannot_be_promoted(self):
        with tempfile.TemporaryDirectory(prefix="k10-public-core-mismatch-") as d:
            source=Path(d)/"public-source.dat"
            target=Path(d)/"public-target.dat"
            connection=sqlite3.connect(source)
            connection.execute("CREATE TABLE public_demo (value INTEGER)")
            connection.commit();connection.close()
            source.chmod(0o600)
            shutil.copyfile(source,target)
            target.chmod(0o600)
            with open(target,"ab") as fd:
                fd.write(b"malicious")
            with self.assertRaisesRegex(
                    K10PortabilityError,"K10_CORE_BYTES_CHANGED_ON_TRANSFER"):
                self.plan(original_core_sqlite=source,
                          transported_core_sqlite=target)
        self.assertEqual(list(self.root.iterdir()),[])

    def test_core_ipc_requires_separate_operator_consent_and_native_client(self):
        for extra in (
                {"authorized_core_observation":True},
                {"readonly_core_rpc":object(),"authorized_core_observation":True},
                {"readonly_core_rpc":object()},
        ):
            with self.subTest(extra=tuple(extra)):
                with self.assertRaises(K10PortabilityError):
                    self.plan(**extra)

    def test_core_tip_parser_does_not_grant_spending(self):
        fake=object.__new__(ManagedScanRpc)
        info={"chain":"regtest","blocks":101,"bestblockhash":"b"*64}
        def read(method,params=None):
            args=[] if params is None else params
            if method=="getblockhash" and args==[0]:
                return REGTEST_GENESIS
            if method=="getblockhash" and args==[101]:
                return "b"*64
            if method=="getbestblockhash" and args==[]:
                return "b"*64
            raise ValueError("scoped method")
        with patch.object(ManagedScanRpc,"attest",return_value=info),\
             patch.object(ManagedScanRpc,"call",side_effect=read):
            outcome=self.plan(readonly_core_rpc=fake,
                              authorized_core_observation=True)
        self.assertTrue(outcome["core_readonly_regtest_tip_observed"])
        self.assertEqual(outcome["core_regtest_height_observed"],101)
        self.assertFalse(outcome["historical_chain_rescan_complete"])
        self.assertFalse(outcome["old_signed_uncertain_reservations_reconciled"])
        self.assertFalse(outcome["safe_to_unlock"])

    def test_changed_or_wrong_network_core_tip_denied(self):
        fake=object.__new__(ManagedScanRpc)
        for info in (
                {"chain":"main","blocks":101,"bestblockhash":"b"*64},
                {"chain":"regtest","blocks":True,"bestblockhash":"b"*64},
        ):
            with patch.object(ManagedScanRpc,"attest",return_value=info):
                with self.assertRaisesRegex(
                        K10PortabilityError,"K10_CORE_TIP_UNVERIFIED"):
                    self.plan(readonly_core_rpc=fake,
                              authorized_core_observation=True)


if __name__=="__main__":
    unittest.main()
