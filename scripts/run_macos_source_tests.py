"""Source/unit regression runner with one explicit native Qt lifetime.

This is not real-Core/frozen/network acceptance. Test widget fixtures must be
destroyed before QApplication and Python finalization (otherwise Cocoa can
SIGSEGV in PySide's exit-time wrapper sweep).
"""
import argparse
import sys
import unittest

from wam_regtest.desktop import qt_application, shutdown_qt


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--pattern',default='test*.py')
    args=parser.parse_args()
    if sys.platform!='darwin':raise ValueError('SOURCE_TEST_NATIVE_MACOS_REQUIRED')
    app=qt_application()
    if app.platformName()!='cocoa':raise ValueError('SOURCE_TEST_COCOA_REQUIRED')
    try:
        suite=unittest.defaultTestLoader.discover('tests',pattern=args.pattern)
        result=unittest.TextTestRunner(verbosity=2).run(suite)
    finally:
        from PySide6.QtCore import QCoreApplication,QEvent
        import shiboken6
        for widget in app.topLevelWidgets():
            if shiboken6.isValid(widget):shiboken6.delete(widget)
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        shutdown_qt()
    return int(not result.wasSuccessful())


if __name__=='__main__':raise SystemExit(main())
