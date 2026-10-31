"""Packaging boundaries without claiming a frozen/native execution."""
import contextlib
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch

from wam_regtest.managed_onboarding import selected_profile
from wam_regtest.q05_package_provenance import validate,read,NAME
from wam_regtest.q05_packaged import run

ROOT=Path(__file__).resolve().parents[1]


class PackagedManagedContracts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def test_new_profile_selection_creates_no_files_and_never_reuses_existing(self):
        with patch('wam_regtest.managed_onboarding.secrets.token_hex',return_value='a'*16):
            selected=selected_profile(self.root,True)
            self.assertFalse(selected.exists());self.assertEqual(list(self.root.iterdir()),[])
            selected.mkdir();(selected/'residue').write_bytes(b'preserve')
            with self.assertRaises(ValueError):selected_profile(self.root,True)
            self.assertEqual((selected/'residue').read_bytes(),b'preserve')

    def test_existing_selection_never_initializes_missing_profile_or_follows_link(self):
        profile=self.root/('wam-fusion-core-'+'b'*16);profile.mkdir()
        with self.assertRaises(ValueError):selected_profile(profile,False)
        (profile/'supervisor.profile').write_bytes(b'not-authenticated-here')
        self.assertEqual(selected_profile(profile,False),profile)
        # Actual profile contents are authenticated only by original native
        # owner; selection does not grant a capability or rewrite the file.
        self.assertEqual((profile/'supervisor.profile').read_bytes(),b'not-authenticated-here')
        if sys.platform!='win32':
            link=self.root/'link';link.symlink_to(profile,target_is_directory=True)
            with self.assertRaises(ValueError):selected_profile(link,False)

    def stamp(self):
        return dict(schema='wam-build-source/v1',source_head_sha='a'*40,checkout_sha='b'*40,
            native_source_inventory_sha256='c'*64,tracked_source_matches_head=True,
            source_unchanged_across_build=True,literal_python_files_verified=10,
            raw_python_tree_sha256='d'*64)

    def test_frozen_stamp_requires_exact_fields_and_native_runtime(self):
        self.assertEqual(validate(self.stamp()),self.stamp())
        for field in ('source_head_sha','checkout_sha','native_source_inventory_sha256',
                      'tracked_source_matches_head','source_unchanged_across_build',
                      'literal_python_files_verified','raw_python_tree_sha256'):
            value=self.stamp();value[field]=False
            with self.assertRaises(ValueError):validate(value)
        with self.assertRaisesRegex(ValueError,'FROZEN_RUNTIME_REQUIRED'):read()
        (self.root/NAME).write_text(json.dumps(self.stamp()))
        with patch.object(sys,'frozen',True,create=True),patch.object(sys,'_MEIPASS',str(self.root),create=True):
            proof=read();self.assertEqual(proof['candidate_source_sha'],'a'*40)
            self.assertTrue(proof['outer_artifact_manifest_required'])
            self.assertEqual(len(proof['frozen_executable_sha256']),64)

    def test_packaged_probe_refuses_nonfrozen_and_resource_overrides(self):
        args=['--root',str(self.root),'--receipt',str(self.root/'receipt'),
            '--confirm-disposable-regtest']
        with self.assertRaisesRegex(ValueError,'EXPLICIT_SCOPE_REQUIRED'):run(self.root,self.root,args)
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            run(self.root,self.root,[*args,'--core-dir','/foreign'])

    def test_linux_frozen_requires_external_witness_before_core_or_gui(self):
        with patch.object(sys,'platform','linux'),patch.object(sys,'frozen',True,create=True):
            with self.assertRaisesRegex(ValueError,'EXPLICIT_SCOPE_REQUIRED'):
                run(self.root,self.root,['--root',str(self.root),'--receipt',str(self.root/'r'),
                    '--confirm-disposable-regtest','--qualification-test-witness'])

    def test_macos_q05_entry_dispatches_explicit_bundled_resources(self):
        entry=runpy.run_path(str(ROOT/'src/wam_regtest/package_entry.py'));main=entry['main']
        with patch.dict(main.__globals__,{'_check_bundle':lambda:(self.root/'core',self.root/'wsp')}), \
             patch('wam_regtest.q05_packaged.run',return_value=0) as probe, \
             patch.object(sys,'argv',['wallet','--ci-q05-managed-wallet','--root','/explicit']):
            self.assertEqual(main(),0)
            probe.assert_called_once_with(self.root/'core',self.root/'wsp',['--root','/explicit'])
