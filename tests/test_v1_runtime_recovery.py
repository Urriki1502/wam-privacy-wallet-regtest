"""Supplemental recovery contracts; genuine Core/GUI qualification is separate."""
import base64
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from wam_regtest.runtime_recovery import (verify_image, RuntimeLease, enroll,
    RuntimeRecoveryError, _image, _retain_image, _lease_root)


class ExactRuntimeContracts(unittest.TestCase):
    def setUp(self):
        from wam_sp.keystore import Keyring
        from wam_sp.store import Store
        self.temporary=tempfile.TemporaryDirectory(prefix='wam-runtime-contract-')
        self.root=Path(self.temporary.name).resolve(); self.root.chmod(0o700)
        self.path=self.root/'wallet-runtime.sqlite'
        self.password=b'public-source-contract-only'
        ring=Keyring()
        self.store=Store(self.path,[a.identity() for a in ring.accounts()])
        for number,state in enumerate(('signed','uncertain'),1):
            self.store.db.execute('INSERT INTO reservations VALUES(?,?,?,?,?)',
                (str(number)*64,0,'public-token-'+str(number),state,1234))
        self.payload={'keys':base64.b64encode(ring.backup(self.password)).decode(),
            'checkpoint':base64.b64encode(self.store.export_checkpoint(self.password)).decode()}
        ring.close()
        self.raw=self.path.read_bytes()

    def tearDown(self):
        self.store.close(); self.temporary.cleanup()

    def test_exact_full_state_and_irreversible_rows(self):
        self.assertTrue(verify_image(self.raw,self.payload,self.password))
        for statement in ("DELETE FROM reservations WHERE state='signed'",
                          "UPDATE reservations SET state='draft' WHERE state='uncertain'",
                          "UPDATE reservations SET token='changed' WHERE state='signed'"):
            db=sqlite3.connect(':memory:'); db.deserialize(self.raw)
            db.execute(statement); db.commit(); changed=db.serialize(); db.close()
            with self.subTest(statement=statement),self.assertRaises(RuntimeRecoveryError):
                verify_image(changed,self.payload,self.password)
        self.assertEqual(self.path.read_bytes(),self.raw)

    def test_no_schema_migration_or_trigger_adoption(self):
        for statement in ('PRAGMA user_version=2',
                'CREATE VIEW injected AS SELECT * FROM reservations',
                'CREATE TABLE unknown(value TEXT)'):
            db=sqlite3.connect(':memory:'); db.deserialize(self.raw)
            db.execute(statement); db.commit(); changed=db.serialize(); db.close()
            with self.subTest(statement=statement),self.assertRaises(Exception):
                verify_image(changed,self.payload,self.password)
        self.assertEqual(self.path.read_bytes(),self.raw)

    def test_bad_password_corruption_and_foreign_keys_refused(self):
        with self.assertRaises(Exception): verify_image(self.raw,self.payload,b'public-wrong-password')
        with self.assertRaises(Exception): verify_image(b'corrupted'+self.raw[9:],self.payload,self.password)
        from wam_sp.keystore import Keyring
        ring=Keyring(); foreign=dict(self.payload,keys=base64.b64encode(ring.backup(self.password)).decode()); ring.close()
        with self.assertRaises(Exception): verify_image(self.raw,foreign,self.password)
        self.assertEqual(self.path.read_bytes(),self.raw)

    @unittest.skipUnless(sys.platform=='darwin','native macOS custody supplement; other platforms run real CI GUI')
    def test_native_lifetime_lease_and_unknown_residue(self):
        import secrets
        wallet=secrets.token_hex(16)
        lease=RuntimeLease(wallet)
        try:
            with self.assertRaises(RuntimeRecoveryError): RuntimeLease(wallet)
            script='from wam_regtest.runtime_recovery import RuntimeLease; RuntimeLease('+repr(wallet)+')'
            result=subprocess.run([sys.executable,'-c',script],capture_output=True,timeout=10)
            self.assertNotEqual(result.returncode,0)
            self.assertIn(b'RUNTIME_SESSION_BUSY',result.stderr)
            with self.assertRaises(RuntimeRecoveryError): enroll(self.root,wallet,self.password)
            self.assertEqual(self.path.read_bytes(),self.raw)
            with _image(self.root) as (raw,remove):
                self.assertEqual(raw,self.raw)
                (self.root/'wallet-runtime.sqlite-wal').write_bytes(b'unknown')
                with self.assertRaises(RuntimeRecoveryError): remove()
            self.assertTrue(self.path.exists())
            with self.assertRaises(RuntimeRecoveryError):
                with _image(self.root): pass
            self.assertEqual(self.path.read_bytes(),self.raw)
        finally: lease.close()
        other=RuntimeLease(wallet); other.close()

    @unittest.skipUnless(sys.platform=='darwin','native macOS custody supplement')
    def test_archive_interruption_retry_and_changed_archive_refusal(self):
        self.store.close()
        with self.assertRaisesRegex(RuntimeError,'public-source-interruption'):
            with _image(self.root) as (raw,remove):
                verify_image(raw,self.payload,self.password)
                name=_retain_image(self.root,raw,self.password)
                raise RuntimeError('public-source-interruption')
        self.assertEqual(self.path.read_bytes(),self.raw)
        archived=(self.root/name).read_bytes()
        self.assertEqual(_retain_image(self.root,self.raw,self.password),name)
        self.assertEqual((self.root/name).read_bytes(),archived)
        (self.root/name).write_bytes(archived[:-1]+bytes([archived[-1]^1]))
        with self.assertRaises(Exception): _retain_image(self.root,self.raw,self.password)
        self.assertEqual(self.path.read_bytes(),self.raw)

    @unittest.skipUnless(os.name=='posix','native POSIX stable-namespace contract')
    def test_temp_environment_cannot_split_wallet_lease_namespace(self):
        from unittest.mock import patch
        original=_lease_root()
        with patch.dict(os.environ,{'TMPDIR':str(self.root),'TEMP':str(self.root)}):
            self.assertEqual(_lease_root(),original)

    @unittest.skipUnless(sys.platform=='darwin','native POSIX nonregular recovery refusal')
    def test_fifo_residue_is_refused_without_blocking_worker(self):
        with tempfile.TemporaryDirectory(prefix='wam-runtime-nonregular-') as tmp:
            root=Path(tmp).resolve(); root.chmod(0o700)
            os.mkfifo(root/'wallet-runtime.sqlite',0o600)
            script='from pathlib import Path; from wam_regtest.runtime_recovery import _image; _image(Path('+repr(str(root))+')).__enter__()'
            result=subprocess.run([sys.executable,'-c',script],capture_output=True,timeout=5)
            self.assertNotEqual(result.returncode,0)
            self.assertTrue((root/'wallet-runtime.sqlite').exists())


if __name__=='__main__': unittest.main()
