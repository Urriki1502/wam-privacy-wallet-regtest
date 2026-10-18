"""K-05 P0 explicit BDB refusal; disposable PUBLIC headers only, no keys."""
from hashlib import sha256
import os
import stat
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from wam_regtest.core_sqlite_import import (
    CoreSqliteImportError,inspect_sqlite_backup,stage_verified_backup,
)
from wam_regtest.legacy_bdb_refusal import inspect_backup_format


class K05LegacyBdbRefusal(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="k05-public-no-wallet-")
        self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name).resolve()
        if os.name!="nt":self.folder.chmod(0o700)

    def test_known_bdb_btree_and_hash_endian_candidates_fail_without_mutation(self):
        for magic in (0x00053162,0x00061561):
            for endian in ("little","big"):
                with self.subTest(magic=magic,endian=endian):
                    source=self.folder/"wallet.dat"
                    body=bytearray(8192)
                    body[12:16]=magic.to_bytes(4,endian)
                    # Known public fixture markers only; no real private
                    # wallet bytes, private descriptors, key material or SQL.
                    source.write_bytes(body)
                    if os.name!="nt":source.chmod(0o600)
                    before=sha256(source.read_bytes()).hexdigest()
                    with self.assertRaisesRegex(
                            CoreSqliteImportError,
                            "^K05_BDB_DEPRECATED_UNSUPPORTED$"):
                        inspect_backup_format(source)
                    self.assertEqual(sha256(source.read_bytes()).hexdigest(),
                                     before)
                    with self.assertRaises(CoreSqliteImportError):
                        inspect_sqlite_backup(source)
                    self.assertEqual(len(list(self.folder.iterdir())),1)

    def test_dev_review_bdb_mode_0644_from_zip_usb_still_gets_bdb_guidance(self):
        if os.name=="nt":
            self.skipTest("POSIX owner-only permission ordering case")
        for mode in (0o600,0o644):
            for endian in ("little","big"):
                source=self.folder/"wallet.dat"
                data=bytearray(8192)
                data[12:16]=(0x00053162).to_bytes(4,endian)
                source.write_bytes(data)
                source.chmod(mode)
                before=sha256(source.read_bytes()).hexdigest()
                with self.subTest(mode=oct(mode),endian=endian):
                    with self.assertRaisesRegex(
                            CoreSqliteImportError,
                            "^K05_BDB_DEPRECATED_UNSUPPORTED$"):
                        inspect_backup_format(source)
                    self.assertEqual(sha256(source.read_bytes()).hexdigest(),
                                     before)
                    # BDB is NEVER allowed to enter real Core's K-04
                    # quarantine even when format classification succeeded.
                    with self.assertRaises(CoreSqliteImportError):
                        inspect_sqlite_backup(source)
                    self.assertEqual(stat.S_IMODE(source.stat().st_mode),mode)

    def test_dev_review_sqlite_mode_0644_still_denied_with_clear_fix(self):
        if os.name=="nt":
            self.skipTest("POSIX custody case")
        source=self.folder/"public-sqlite.dat"
        sql=sqlite3.connect(source)
        try:
            sql.execute("CREATE TABLE public_fixture(id INT)")
            sql.commit()
        finally:sql.close()
        source.chmod(0o644)
        initial=sha256(source.read_bytes()).hexdigest()
        with self.assertRaisesRegex(
                CoreSqliteImportError,
                "^K05_SQLITE_PRIVATE_CUSTODY_REQUIRED$"):
            inspect_backup_format(source)
        with self.assertRaisesRegex(
                CoreSqliteImportError,
                "^K04_SQLITE_SOURCE_CUSTODY_DENIED$"):
            inspect_sqlite_backup(source)
        self.assertEqual(sha256(source.read_bytes()).hexdigest(),initial)
        self.assertEqual(stat.S_IMODE(source.stat().st_mode),0o644)

    def test_unrecognized_dat_never_approved_as_sqlite_or_bdb(self):
        source=self.folder/"unknown.dat"
        source.write_bytes(b"\x00"*4096)
        if os.name!="nt":source.chmod(0o600)
        with self.assertRaisesRegex(
                CoreSqliteImportError,"^K05_UNKNOWN_CORE_DAT_DENIED$"):
            inspect_backup_format(source)

    def test_original_k04_sqlite_positive_path_is_unchanged(self):
        source=self.folder/"core-sqlite.dat"
        sql=sqlite3.connect(source)
        try:
            sql.execute("CREATE TABLE public_only (id INT PRIMARY KEY)")
            sql.execute("INSERT INTO public_only VALUES (1)")
            sql.commit()
        finally:sql.close()
        if os.name!="nt":source.chmod(0o600)
        self.assertEqual(inspect_backup_format(source),
                         inspect_sqlite_backup(source))
        self.assertEqual(inspect_backup_format(source).network,"UNVERIFIED")

    def test_fusion_enc_and_mnemonic_are_never_opened_or_parsed(self):
        # These are *not* Core SQLite or BDB input: dispatch based on
        # extension before opening potentially secret local files.
        for suffix,code in (
                (".enc","K05_FUSION_ENCRYPTED_BACKUP_SEPARATE"),
                (".txt","K05_MNEMONIC_TEXT_NOT_WALLET_DAT"),
                (".json","K05_UNKNOWN_BACKUP_TYPE_DENIED")):
            with self.subTest(suffix=suffix):
                source=self.folder/("private-source"+suffix)
                with patch("wam_regtest.legacy_bdb_refusal.os.open",
                           side_effect=AssertionError("PRIVATE_FILE_OPEN_FORBIDDEN")):
                    with self.assertRaisesRegex(CoreSqliteImportError,code):
                        inspect_backup_format(source)
                self.assertFalse(source.exists())

    def test_missing_consent_still_refuses_staging_and_all_bdb_bytes(self):
        source=self.folder/"wallet.dat"
        body=bytearray(4096)
        body[12:16]=(0x00053162).to_bytes(4,"little")
        source.write_bytes(body)
        if os.name!="nt":source.chmod(0o600)
        target=self.folder/"quarantine"
        target.mkdir(mode=0o700)
        with self.assertRaises(CoreSqliteImportError):
            stage_verified_backup(source,target,authorized=False)
        with self.assertRaises(CoreSqliteImportError):
            stage_verified_backup(source,target,authorized=True)
        self.assertEqual(list(target.iterdir()),[])

    def test_bdb_live_wal_and_symlink_never_classified_or_adopted(self):
        source=self.folder/"wallet.dat"
        data=bytearray(8192)
        data[12:16]=(0x00061561).to_bytes(4,"little")
        source.write_bytes(data)
        if os.name!="nt":source.chmod(0o600)
        wal=self.folder/"wallet.dat-wal"
        wal.write_bytes(b"public-test")
        try:
            with self.assertRaises(CoreSqliteImportError):
                inspect_backup_format(source)
        finally:wal.unlink()
        link=self.folder/"alias.dat"
        try:link.symlink_to(source)
        except (OSError,NotImplementedError):
            if os.name!="nt":raise
        else:
            with self.assertRaises(CoreSqliteImportError):
                inspect_backup_format(link)


if __name__=="__main__":
    unittest.main()
