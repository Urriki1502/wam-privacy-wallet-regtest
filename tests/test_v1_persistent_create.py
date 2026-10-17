"""No Core process/real keys: create-once persistent identity negative tests."""
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch
from wam_regtest.persistent_profile import create_disposable_profile,PersistentProfileError

A='a'*64
B='b'*64
C='c'*64


@unittest.skipUnless(os.name=='posix','POSIX candidate; Windows never approved')
class CreateOnceProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='wam-managed-create-')
        self.addCleanup(self.temp.cleanup)
        self.parent=Path(self.temp.name).resolve(strict=True)/'wam-fusion-regtest-profiles'
        self.parent.mkdir(mode=0o700)

    def create(self,**kwargs):
        return create_disposable_profile(self.parent,expected_genesis=A,
                                         expected_node_sha256=B,
                                         expected_cli_sha256=C,**kwargs)

    def test_operator_approved_create_once_and_readback_only(self):
        root,record=self.create(authorized=True)
        self.assertEqual(root.parent,self.parent)
        self.assertEqual(root.stat().st_mode&0o777,0o700)
        self.assertEqual((root/'profile.json').stat().st_mode&0o777,0o600)
        self.assertEqual(record['network'],'regtest')
        self.assertFalse(record['persistent_runtime_qualified'])
        self.assertFalse(record['attach_authorized'])
        self.assertFalse(record['signing_authorized'])
        self.assertFalse(record['mainnet_allowed'])

    def test_denies_without_explicit_consent_no_side_effects(self):
        with self.assertRaisesRegex(PersistentProfileError,'PROFILE_CREATE_EXPLICIT_CONSENT_REQUIRED'):
            self.create()
        self.assertEqual(list(self.parent.iterdir()),[])

    def test_collision_does_not_delete_or_overwrite_existing_profile(self):
        with patch('wam_regtest.persistent_profile.secrets.token_hex',
                   side_effect=['f'*16,'d'*32]):
            root,_=self.create(authorized=True)
        original=(root/'profile.json').read_bytes()
        with patch('wam_regtest.persistent_profile.secrets.token_hex',return_value='f'*16):
            with self.assertRaisesRegex(PersistentProfileError,'PROFILE_NEW_NAMESPACE_CONFLICT'):
                self.create(authorized=True)
        self.assertEqual((root/'profile.json').read_bytes(),original)

    def test_untrusted_parent_and_invalid_external_pin_do_not_create(self):
        self.parent.chmod(0o755)
        with self.assertRaises(PersistentProfileError):self.create(authorized=True)
        self.parent.chmod(0o700)
        with self.assertRaisesRegex(PersistentProfileError,'PROFILE_INDEPENDENT_PIN_REQUIRED'):
            create_disposable_profile(self.parent,authorized=True,
                                      expected_genesis='mainnet',expected_node_sha256=B,
                                      expected_cli_sha256=C)
        self.assertEqual(list(self.parent.iterdir()),[])

    def test_symlink_parent_denied_even_when_target_private(self):
        alias=self.parent.parent/'wam-fusion-regtest-profiles-alias'
        alias.symlink_to(self.parent,target_is_directory=True)
        with self.assertRaises(PersistentProfileError):
            create_disposable_profile(alias,authorized=True,expected_genesis=A,
                                      expected_node_sha256=B,expected_cli_sha256=C)
