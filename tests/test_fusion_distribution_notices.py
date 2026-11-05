"""Package notices use the wheel metadata and the vendored GNU texts."""
from pathlib import Path
import tempfile
import unittest

from wam_regtest.distribution_notices import stage_distribution_notices
from wam_regtest.qt_bundle_prune import is_prune_candidate, unreferenced_candidates


class DistributionNoticeTests(unittest.TestCase):
    def test_qt_stage_copies_metadata_and_gnu_text(self):
        with tempfile.TemporaryDirectory() as folder:
            stage = stage_distribution_notices(Path(folder) / 'notices', qt=True)
            text = (stage / 'lgpl-3.0.txt').read_bytes()
            self.assertIn(b'GNU LESSER GENERAL PUBLIC LICENSE', text[:120])
            self.assertNotIn(b'\r', text)
            metadata = list(stage.glob('PySide6-*/METADATA'))
            self.assertEqual(len(metadata), 1)
            self.assertIn(b'LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only', metadata[0].read_bytes())
            notice = (stage / 'DISTRIBUTION_NOTICES.txt').read_bytes()
            self.assertIn(b'does not complete a legal review', notice)
            self.assertNotIn(b'\r', notice)

    def test_unreferenced_qt_modules_can_be_named_without_removing_cursor_or_test(self):
        self.assertTrue(is_prune_candidate('libQt6Qml.so.6'))
        self.assertTrue(is_prune_candidate('libQt6Pdf.so.6'))
        self.assertFalse(is_prune_candidate('libQt6Test.so.6'))
        self.assertFalse(is_prune_candidate('libXcursor.so.1'))
        self.assertFalse(is_prune_candidate('libxcb-cursor.so.0'))
        self.assertFalse(is_prune_candidate('libQt6Widgets.so.6'))
        needed = {
            'app': ['libQt6Widgets.so.6', 'libQt6Test.so.6'],
            'libQt6Widgets.so.6': ['libQt6Core.so.6'],
            'libQt6Qml.so.6': ['libQt6Core.so.6'],
            'libQt6Quick.so.6': ['libQt6Qml.so.6'],
        }
        candidates = {'libQt6Qml.so.6', 'libQt6Quick.so.6'}
        self.assertEqual(unreferenced_candidates(needed, candidates), candidates)


if __name__ == '__main__':
    unittest.main()
