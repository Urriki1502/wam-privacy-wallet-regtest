"""Explicit native Q05 acceptance client; control/status only, never wallet keys.

The real-Core harness may kill this separate GUI process after its authenticated
ready report. This proves GUI process isolation, not WSP wallet continuity.
"""
import argparse
import json
from pathlib import Path
import sys
import time


def probe(root, height, *, wait_for_crash=False, report=None):
    from .supervisor_store import _root
    _root(root)
    if (type(height) is not int or not 0 <= height <= 1_000_000
            or type(wait_for_crash) is not bool):
        raise ValueError("T05_GUI_PROBE_HEIGHT_DENIED")
    from .desktop import qt_application, shutdown_qt
    from .managed_gui import ManagedCoreWindow
    from PySide6.QtCore import QTimer
    from shiboken6 import delete, isValid
    if report is None:
        report = lambda value: print(json.dumps(value), flush=True)
    app = qt_application()
    window = ManagedCoreWindow(root)
    window.show()
    try:
        window.request_sync()
        deadline = time.monotonic() + 25
        while window._worker is not None and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        if (window._worker is not None or not window._managed_authenticated
                or window._managed_state != "ready"
                or " · height " + str(height) + " · " not in window.status.text()
                or window.session is not None or window._snapshot is not None
                or window.dashboard.go_send.isEnabled()):
            raise ValueError("T05_GUI_PROBE_UNVERIFIED")
        if wait_for_crash:
            # Bounded real event loop. The harness must observe this readiness
            # before abruptly killing ONLY this owned GUI child, never Core.
            report({"height": height, "wallet_adopted": False,
                    "authenticated_gui_ready": True})
            QTimer.singleShot(30_000, app.quit)
            app.exec()
            raise ValueError("T05_GUI_PROBE_CRASH_NOT_INJECTED")
    finally:
        if window._worker is not None:
            # IPC itself is bounded. Never destroy a live QThread or conceal a
            # teardown failure; failure here must remain a failing process.
            if not window._worker.wait(5000):
                raise ValueError("T05_GUI_PROBE_WORKER_STILL_RUNNING")
            app.processEvents()
        if not window.close():
            raise ValueError("T05_GUI_PROBE_CLOSE_DENIED")
        delete(window)
        assert not isValid(window)
        app.processEvents()
        shutdown_qt()
    report({"height": height, "wallet_adopted": False,
            "authenticated_gui_ready": True,
            "native_shutdown_completed": True})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--expected-height", required=True, type=int)
    parser.add_argument("--confirm-disposable-regtest-probe", action="store_true")
    parser.add_argument("--wait-for-crash", action="store_true")
    args = parser.parse_args()
    if not args.confirm_disposable_regtest_probe:
        return 2
    try:
        probe(args.root, args.expected_height, wait_for_crash=args.wait_for_crash)
        return 0
    except Exception:
        print("T05_GUI_NATIVE_PROCESS_PROBE_DENIED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
