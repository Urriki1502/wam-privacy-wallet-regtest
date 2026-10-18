"""K-04 native SQLite header/source/descriptor refusals (NOT Core E2E)."""
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from wam_regtest.core_sqlite_import import (
    CoreSqliteImportError,SQLITE_MAGIC,
    inspect_sqlite_backup,stage_verified_backup,
    require_distinct_descriptors,verify_restored_core_wallet,
)
from wam_regtest.wsp_live import REGTEST_GENESIS


class CoreSqlitePreflightContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="k04-public-sqlite-")
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        if os.name!="nt":self.root.chmod(0o700)
        self.source=self.root/"k04-public-test.dat"
        with sqlite3.connect(self.source) as sql:
            sql.execute("CREATE TABLE public_dummy(id INTEGER PRIMARY KEY)")
            sql.execute("INSERT INTO public_dummy VALUES (1)")
            sql.commit()
        if os.name!="nt":self.source.chmod(0o600)

    def test_real_sqlite_magic_hash_and_no_private_descriptor_parsing(self):
        original=self.source.read_bytes()
        self.assertTrue(original.startswith(SQLITE_MAGIC))
        a=inspect_sqlite_backup(self.source)
        self.assertEqual(a.format,"sqlite")
        self.assertEqual(a.network,"UNVERIFIED")
        self.assertEqual(a.byte_count,len(original))
        self.assertIn("redacted",repr(a))
        self.assertNotIn("k04-public",repr(a))

    def test_reject_legacy_bdb_junk_missing_size_hardlink_and_symlink(self):
        for suffix,payload in (
                ("legacy-bdb",b"\x00\x05\x31\x62"*1024),
                ("truncated",SQLITE_MAGIC+b"\x00"*30),
                ("empty",b""),
                ("oversized-header",b"NOT_SQLITE"*550),
        ):
            with self.subTest(suffix=suffix):
                candidate=self.root/(suffix+".dat")
                candidate.write_bytes(payload)
                if os.name!="nt":candidate.chmod(0o600)
                with self.assertRaises(CoreSqliteImportError):
                    inspect_sqlite_backup(candidate)
        alias=self.root/"alias.dat"
        alias.symlink_to(self.source)
        with self.assertRaises(CoreSqliteImportError):
            inspect_sqlite_backup(alias)
        linked=self.root/"linked.dat"
        os.link(self.source,linked)
        with self.assertRaises(CoreSqliteImportError):
            inspect_sqlite_backup(self.source)

    def test_live_wal_shm_or_journal_denied_before_read(self):
        for extension in ("-wal","-shm","-journal"):
            path=self.source.with_name(self.source.name+extension)
            path.write_bytes(b"UNOWNED_TEST_ONLY")
            try:
                with self.assertRaisesRegex(
                        CoreSqliteImportError,"^K04_SQLITE_LIVE_OR_PARTIAL_BACKUP_DENIED$"):
                    inspect_sqlite_backup(self.source)
            finally:path.unlink()

    def test_broad_posix_file_mode_denied(self):
        if os.name=="nt":self.skipTest("Windows native ACL custody exercised in real runner")
        self.source.chmod(0o644)
        with self.assertRaisesRegex(
                CoreSqliteImportError,"^K04_SQLITE_SOURCE_CUSTODY_DENIED$"):
            inspect_sqlite_backup(self.source)

    def test_explicit_disposable_staging_consent_and_no_overwrite(self):
        from wam_regtest import custody
        staged=self.root/"quarantine"
        staged.mkdir(mode=0o700)
        if os.name!="nt":staged.chmod(0o700)
        with self.assertRaises(CoreSqliteImportError):
            stage_verified_backup(self.source,staged)
        class PrivateTestStore:
            @staticmethod
            def validate_directory(directory):
                s=directory.lstat()
                if not directory.is_dir() or directory.is_symlink() or (
                    os.name!="nt" and s.st_mode & 0o077):
                    raise ValueError("NOT_PRIVATE")
        with patch("wam_regtest.custody.storage",return_value=PrivateTestStore()):
            copied,proof=stage_verified_backup(self.source,staged,authorized=True)
        self.assertNotEqual(copied,self.source)
        self.assertEqual(inspect_sqlite_backup(copied),proof)
        self.assertEqual(inspect_sqlite_backup(self.source),proof)
        self.assertEqual(len(list(staged.iterdir())),1)
        self.assertTrue(copied.name.endswith(".dat"))
        self.assertNotIn(self.source.name,copied.name)

    def test_public_core_descriptor_overlap_and_chain_refusals(self):
        a={"descriptors":[
            {"desc":"wpkh(PUBLIC_A)#check","internal":False},
            {"desc":"tr(PUBLIC_B)#check","internal":True},
        ]}
        b={"descriptors":[
            {"desc":"tr(PUBLIC_B)#check","internal":True},
            {"desc":"tr(PUBLIC_C)#check","internal":False},
        ]}
        c={"descriptors":[
            {"desc":"wpkh(PUBLIC_D)#check","internal":False},
        ]}
        with self.assertRaisesRegex(CoreSqliteImportError,"K04_CORE_ACCOUNT_OVERLAP_DENIED"):
            require_distinct_descriptors(a,b)
        self.assertTrue(require_distinct_descriptors(a,c))
        for bad in (
            {"descriptors":[{"desc":"xprvSECRET","internal":False}]},
            {"descriptors":[{"desc":"PUBLIC","internal":1}]},
            {"descriptors":[{"desc":"PUBLIC","internal":False}]*2},
        ):
            with self.assertRaises(CoreSqliteImportError):
                require_distinct_descriptors(bad,c)
        info={"format":"sqlite","descriptors":True,
              "private_keys_enabled":True,"scanning":False}
        accepted=verify_restored_core_wallet(
            chain="regtest",genesis=REGTEST_GENESIS,
            wallet_info=info,descriptor_listing=a)
        self.assertEqual(accepted["status"],
                         "K04_CORE_SQLITE_REGTEST_RESTORE_VERIFIED")
        self.assertFalse(accepted["wallet_spend_authorized"])
        for wrong in (
            {"chain":"main","genesis":REGTEST_GENESIS},
            {"chain":"regtest","genesis":"f"*64},
            {"chain":"regtest","genesis":REGTEST_GENESIS,
             "wallet_info":{**info,"format":"bdb"}},
            {"chain":"regtest","genesis":REGTEST_GENESIS,
             "wallet_info":{**info,"descriptors":False}},
        ):
            with self.subTest(wrong=tuple(wrong)):
                with self.assertRaises(CoreSqliteImportError):
                    verify_restored_core_wallet(
                        chain=wrong.get("chain","regtest"),
                        genesis=wrong.get("genesis",REGTEST_GENESIS),
                        wallet_info=wrong.get("wallet_info",info),
                        descriptor_listing=a)


if __name__=="__main__":
    unittest.main()
