"""T05 profile preflight is negative-only until genuine persistent Core E2E."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from wam_regtest.persistent_profile import (
    SCHEMA, inspect_profile, PersistentProfileError,
)

A='a'*64
B='b'*64
C='c'*64


@unittest.skipUnless(os.name=='posix','Windows native persistent Core is not qualified')
class PersistentProfileInspection(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='wam-t05-unit-')
        self.addCleanup(self.temp.cleanup)
        base=Path(self.temp.name).resolve(strict=True)
        self.root=base/'wam-fusion-owned-regtest-1234567890abcdef'
        self.root.mkdir(mode=0o700)
        self.file=self.root/'profile.json'
        self.record={'schema':SCHEMA,'network':'regtest','core_version':'v0.1.11',
                     'genesis_hash':A,'node_sha256':B,'cli_sha256':C,'profile_id':'d'*32}
        self.write(self.record)

    def write(self,value):
        self.file.write_text(json.dumps(value,separators=(',',':')))
        self.file.chmod(0o600)

    def inspect(self,**kw):
        return inspect_profile(self.root,expected_genesis=kw.get('genesis',A),
                               expected_node_sha256=kw.get('node',B),
                               expected_cli_sha256=kw.get('cli',C))

    def test_read_only_contract_never_grants_runtime_sign_or_attach(self):
        receipt=self.inspect()
        self.assertTrue(receipt['pins_matched'])
        for permission in ('persistent_runtime_qualified','attach_authorized',
                           'signing_authorized','mainnet_allowed'):
            self.assertIs(receipt[permission],False)
        self.assertEqual(self.file.read_text(),json.dumps(self.record,separators=(',',':')))

    def test_mainnet_or_unknown_fields_denied(self):
        for update in ({'network':'mainnet'},{'core_version':'v0.1.12'},
                       {'unknown_field':'hidden'}, {'profile_id':'INVALID'}):
            self.write({**self.record,**update})
            with self.assertRaises(PersistentProfileError):self.inspect()
        self.write(self.record)

    def test_independently_supplied_pins_required_and_exact(self):
        for field in ('genesis','node','cli'):
            with self.assertRaisesRegex(PersistentProfileError,'PROFILE_TRUST_PINS_MISMATCH'):
                self.inspect(**{field:'e'*64})
            with self.assertRaisesRegex(PersistentProfileError,'PROFILE_INDEPENDENT_PIN_REQUIRED'):
                self.inspect(**{field:'not-a-hash'})

    def test_duplicate_json_fields_denied(self):
        self.file.write_text('{"schema":"x","schema":"y"}')
        self.file.chmod(0o600)
        with self.assertRaisesRegex(PersistentProfileError,'PROFILE_DUPLICATE_FIELD_DENIED'):
            self.inspect()

    def test_symlink_and_hardlink_file_denied(self):
        other=self.root/'replacement'
        other.write_bytes(self.file.read_bytes());other.chmod(0o600)
        self.file.unlink();self.file.symlink_to(other)
        with self.assertRaises(PersistentProfileError):self.inspect()
        self.file.unlink();os.link(other,self.file)
        with self.assertRaisesRegex(PersistentProfileError,'PROFILE_RECEIPT_CUSTODY_DENIED'):
            self.inspect()

    def test_wrong_permissions_and_namespace_denied(self):
        self.file.chmod(0o644)
        with self.assertRaisesRegex(PersistentProfileError,'PROFILE_RECEIPT_CUSTODY_DENIED'):
            self.inspect()
        self.file.chmod(0o600);self.root.chmod(0o755)
        with self.assertRaisesRegex(PersistentProfileError,'PROFILE_ROOT_CUSTODY_DENIED'):
            self.inspect()
        self.root.chmod(0o700)
        with self.assertRaisesRegex(PersistentProfileError,'PROFILE_OWNED_NAMESPACE_REQUIRED'):
            inspect_profile(self.root.parent,expected_genesis=A,
                            expected_node_sha256=B,expected_cli_sha256=C)
