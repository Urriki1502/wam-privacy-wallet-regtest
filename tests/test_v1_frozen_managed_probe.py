"""Scope/custody negatives only; genuine frozen Core evidence is build-gated."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from wam_regtest.frozen_managed_probe import arguments, publish_report, run


class FrozenManagedProbeScope(unittest.TestCase):
    def setUp(self):
        self.root=str(Path(tempfile.gettempdir()).resolve()/'wam-fusion-core-0123456789abcdef')
        self.report=str(Path(tempfile.gettempdir()).resolve()/'wam-fusion-core-fedcba9876543210')
        self.consent=['--confirm-disposable-regtest-probe']

    def test_regular_python_cannot_enter_frozen_role(self):
        with self.assertRaisesRegex(ValueError,'FROZEN_PROBE_BOOTLOADER_REQUIRED'):
            run([],Path('external-core'),Path('external-wsp'))

    def test_consent_role_shape_and_distinct_report_required(self):
        with self.assertRaisesRegex(ValueError,'FROZEN_PROBE_CONSENT_REQUIRED'):
            arguments(['supervisor','--root',self.root])
        for values in (
            ['supervisor','--root',self.root,'--report-root',self.report,'--wait-for-crash'],
            ['gui','--root',self.root,'--report-root',self.root,'--expected-height','101'],
            ['gui','--root',self.root,'--report-root',self.report,'--expected-height','-1'],
            ['scan','--root',self.root,'--report-root',self.report,'--expected-before','0',
             '--max-blocks','101'],
        ):
            with self.subTest(values=values),self.assertRaises(ValueError):
                arguments([*values,*self.consent])

    def test_supervisor_report_must_be_distinct_and_explicit(self):
        valid=['supervisor','--root',self.root,*self.consent]
        with self.assertRaises(ValueError):arguments(valid)
        with self.assertRaisesRegex(ValueError,'FROZEN_PROBE_REPORT_ROOT_DENIED'):
            arguments([*valid,'--report-root',self.root])
        args=arguments([*valid,'--report-root',self.report])
        self.assertEqual(args.role,'supervisor')
        self.assertNotEqual(args.root,args.report_root)

    def test_no_arbitrary_module_or_external_core_or_abbreviated_consent(self):
        for extra in (['--core-dir','external'],['--wsp-source','external'],
                      ['--module','os'],['--confirm-disposable-regtest']):
            with self.subTest(extra=extra),self.assertRaises(SystemExit) as caught:
                arguments(['supervisor','--root',self.root,*extra])
            self.assertEqual(caught.exception.code,2)

    def test_importing_scope_has_no_qt_dependency(self):
        child=subprocess.run([sys.executable,'-c',
            "import sys;import wam_regtest.frozen_managed_probe;"
            "assert not any(x.startswith(('PySide6','shiboken6')) for x in sys.modules)"],
            capture_output=True,timeout=15)
        self.assertEqual(child.returncode,0)

    @unittest.skipUnless(sys.platform in ('darwin','win32'),'Native Qt installed')
    def test_windowed_probe_refusal_exits_without_modal_dialog(self):
        child=subprocess.run([sys.executable,'-c',
            "import sys;from wam_regtest.windows_package_entry import main;"
            "sys.argv=['test','--ci-managed-process','supervisor','--root',sys.argv[1],"
            "'--confirm-disposable-regtest-probe'];raise SystemExit(main())",self.root],
            capture_output=True,timeout=15)
        self.assertEqual(child.returncode,2)

    @unittest.skipUnless(sys.platform in ('darwin','win32'),'Native Mac/Windows fixture custody')
    def test_native_report_is_bounded_create_only_and_rejects_symlink(self):
        from wam_regtest.custody import create_directory
        from wam_regtest.supervisor_store import read_exact
        import json
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()/'wam-fusion-core-0123456789abcdef'
            create_directory(root)
            value={'height':101,'authenticated_gui_ready':True,'wallet_adopted':False}
            publish_report(root,value)
            self.assertEqual(json.loads(read_exact(root,'supervisor.profile')),value)
            with self.assertRaises(ValueError):publish_report(root,value)
            self.assertEqual(json.loads(read_exact(root,'supervisor.profile')),value)
            with self.assertRaises(ValueError):publish_report(root,{'large':'x'*4096})
            if sys.platform=='darwin':
                link=root.parent/'wam-fusion-core-fedcba9876543210'
                link.symlink_to(root,target_is_directory=True)
                with self.assertRaises(ValueError):publish_report(link,value)
