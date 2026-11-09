"""Build preservation and isolation contracts; no frozen/Core acceptance."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import os
from wam_regtest.macos_build_layout import prepare,frozen_environment


class MacosBuildLayoutContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        (self.root/'bundle-input').mkdir()
        self.core=self.root/'bundle-input'/'core';self.core.mkdir()
        self.verify=patch('wam_regtest.core.verified_core_paths',return_value=())
        self.verify.start();self.addCleanup(self.verify.stop)

    def test_create_only_override_keeps_old_outputs_and_core_paths_untouched(self):
        for name in ('build','dist','package-output','core'):
            p=self.root/name;p.mkdir();(p/'keep').write_bytes(b'original evidence')
        output=self.root/'bundle-input'/'new-build'
        self.assertEqual(prepare(self.root,self.core,output),output)
        for name in ('build','dist','package-output','core'):
            self.assertEqual((self.root/name/'keep').read_bytes(),b'original evidence')
        with self.assertRaisesRegex(ValueError,'NEW_OUTPUT_REQUIRED'):
            prepare(self.root,self.core,output)

    def test_existing_default_outputs_foreign_paths_and_links_refuse(self):
        (self.root/'dist').mkdir();(self.root/'dist'/'receipt').write_bytes(b'keep')
        with self.assertRaisesRegex(ValueError,'EXISTING_OUTPUT_DENIED'):
            prepare(self.root,self.core)
        with self.assertRaises(ValueError):prepare(self.root,self.core,self.root/'other')
        if os.name!='nt':
            link=self.root/'bundle-input'/'linked';link.symlink_to(self.core,target_is_directory=True)
            with self.assertRaises(ValueError):prepare(self.root,link,self.root/'bundle-input'/'new')
        self.assertFalse((self.root/'bundle-input'/'new').exists())

    def test_bad_core_is_rejected_before_any_output_is_created(self):
        output=self.root/'bundle-input'/'new'
        with patch('wam_regtest.core.verified_core_paths',side_effect=ValueError('CORE_DENIED')):
            with self.assertRaises(ValueError):prepare(self.root,self.core,output)
        self.assertFalse(output.exists())

    def test_final_executable_loses_all_developer_python_and_loader_overrides(self):
        raw={'PYTHONPATH':'private','PYTHONHOME':'private','VIRTUAL_ENV':'private',
             'DYLD_LIBRARY_PATH':'private','DYLD_FRAMEWORK_PATH':'private',
             'DYLD_INSERT_LIBRARIES':'private','QT_PLUGIN_PATH':'private',
             'QML_IMPORT_PATH':'private','WAM_MACOS_CORE_DIR':'private','HOME':'kept'}
        clean=frozen_environment(raw,'cocoa')
        self.assertEqual(clean,{'HOME':'kept','PATH':'/usr/bin:/bin:/usr/sbin:/sbin',
                                'QT_QPA_PLATFORM':'cocoa'})
