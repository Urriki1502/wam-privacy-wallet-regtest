"""Fail-closed bundle test contracts; no synthetic RPC acceptance."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from wam_regtest.package_entry import BundleLaunchError, _resource_paths
from wam_regtest.package_manifest import PackageSourceError, stage_pinned_wsp
from wam_regtest.wsp_live import _verify_frozen_source, RealWspScanError, PINNED_WSP_COMMIT


class MacNativePackageContracts(unittest.TestCase):
    def test_finder_bundle_denies_regular_python_and_other_platforms(self):
        with self.assertRaisesRegex(BundleLaunchError,
                                    "^WAM_BUNDLE_MACOS_ARM64_REQUIRED$"):
            _resource_paths()
        with patch.object(sys, "platform", "linux"):
            with self.assertRaises(BundleLaunchError):
                _resource_paths()

    def test_source_staging_cannot_admit_arbitrary_path_or_unknown_git(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            with self.assertRaises(PackageSourceError):
                stage_pinned_wsp(base / "unknown", base / "output")
            self.assertFalse((base / "output").exists())
            with self.assertRaises(PackageSourceError):
                stage_pinned_wsp(base / "unknown", base / "output")

    def test_frozen_app_requires_exact_bundle_source_location(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            (base / "wsp-source").mkdir()
            with patch.object(sys, "_MEIPASS", str(base), create=True):
                with self.assertRaisesRegex(
                    RealWspScanError, "^WSP_FROZEN_SOURCE_SCOPE_DENIED$",
                ):
                    _verify_frozen_source(base / "somewhere")
                with self.assertRaisesRegex(
                    RealWspScanError, "^WSP_FROZEN_SOURCE_DENIED$",
                ):
                    _verify_frozen_source(base / "wsp-source")

    def test_frozen_app_rejects_modified_wsp_member(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve() / "wsp-source"
            folder = root / "src" / "wam_sp"
            folder.mkdir(parents=True)
            source = {
                "src/wam_sp/__init__.py": b"",
                "src/wam_sp/scanner.py": b"print('public dummy')\n",
            }
            for name, raw in source.items():
                f = root / name
                f.write_bytes(raw)
            receipt = {
                "source_commit": PINNED_WSP_COMMIT,
                "files": {name: hashlib.sha256(raw).hexdigest()
                          for name, raw in source.items()},
            }
            (root / "SOURCE_SHA256.json").write_text(json.dumps(receipt))
            (folder / "scanner.py").write_bytes(b"tampered")
            with patch.object(sys, "_MEIPASS", str(root.parent), create=True):
                with self.assertRaisesRegex(
                    RealWspScanError, "^WSP_FROZEN_SOURCE_HASH_DENIED$",
                ):
                    _verify_frozen_source(root)


if __name__ == "__main__":
    unittest.main()
