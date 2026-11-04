"""Focused real-Qt geometry regressions; NOT Core/custody acceptance."""
import unittest


class UiTextLayoutTests(unittest.TestCase):
    def test_backup_advanced_footer_light_dark_small_default_window(self):
        from wam_regtest.ui_layout_probe import check_layouts
        result = check_layouts()
        self.assertEqual(result['status'], 'UI_LAYOUT_PASS')
        self.assertEqual(len(result['measurements']), 32)
        self.assertFalse(result['backend_or_core_started'])

    def test_ui_candidate_does_not_claim_core_or_full_runtime_qualification(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from wam_regtest.release_candidate import write_candidate_manifest
        with TemporaryDirectory() as folder:
            receipt = write_candidate_manifest(Path(folder), 'macos-arm64',
                {'wamd': 'a' * 64, 'wam-cli': 'b' * 64},
                qualification_scope='ui-layout-focused')
        self.assertTrue(receipt['native_ui_layout_e2e_pass'])
        self.assertFalse(receipt['native_final_executable_e2e_pass'])
        self.assertFalse(receipt['full_exact_commit_Q01_Q06_qualified'])
        self.assertFalse(receipt['dev_wam_reviewed'])
