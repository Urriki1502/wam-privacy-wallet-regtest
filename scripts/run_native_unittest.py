"""Native Qt-safe unittest launcher; same tests/gates, deterministic app teardown.

A Qt QApplication must be shut down while Python/PySide6 modules are still
alive, NOT during interpreter finalization. Preserve all failures/skips.
"""
import argparse
import sys
import unittest


def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument("--pattern",default="test*.py")
    ap.add_argument("--start-directory",default="tests")
    args=ap.parse_args(argv)
    if not args.pattern.endswith(".py") or "/" in args.pattern or "\\" in args.pattern:
        raise ValueError("UNTEST_PATTERN_DENIED")
    suite=unittest.defaultTestLoader.discover(args.start_directory,pattern=args.pattern)
    try:
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    finally:
        # Exactly the same native teardown required by packaged GUI entry.
        # Never hide an exception/test failure; a teardown crash remains FAIL.
        if "wam_regtest.desktop" in sys.modules:
            from wam_regtest.desktop import shutdown_qt
            shutdown_qt()


if __name__=="__main__":
    raise SystemExit(main())
