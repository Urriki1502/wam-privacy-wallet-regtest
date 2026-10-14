"""Finder launch entry for experimental REAL WAM Core macOS ARM64 REGTEST app.

This launch is intentionally disposable. All keys in its BIP352 example are
public; they must never be used for actual WAM or personal funds. This entry
is bundled by PyInstaller with the signed original WAM Core binaries and
pinned WSP source closure. No hidden downloads or external Python are needed.
"""
from __future__ import annotations

import json
from pathlib import Path
import platform
import sys


class BundleLaunchError(ValueError):
    pass


def _resource_paths() -> tuple[Path, Path]:
    if (sys.platform != "darwin" or platform.machine().lower() != "arm64"
            or not getattr(sys, "frozen", False)
            or not hasattr(sys, "_MEIPASS")):
        raise BundleLaunchError("WAM_BUNDLE_MACOS_ARM64_REQUIRED")
    root = Path(sys._MEIPASS).resolve()
    return root / "core", root / "wsp-source"


def _check_bundle() -> tuple[Path, Path]:
    core_dir, source = _resource_paths()
    from wam_regtest.core import verified_core_paths
    from wam_regtest.wsp_live import _pinned_source
    node, cli, receipt = verified_core_paths(core_dir)
    if receipt.get("platform") != "macos-arm64":
        raise BundleLaunchError("WAM_BUNDLE_CORE_PLATFORM_DENIED")
    _pinned_source(source)
    if not node.is_file() or not cli.is_file():
        raise BundleLaunchError("WAM_BUNDLE_CORE_DENIED")
    return core_dir, source


def main() -> int:
    try:
        core_dir, source = _check_bundle()
        from wam_regtest.core import smoke_real_core
        # Hidden CI mode: actual signed Core + genuine BIP352 + Qt screen.
        ci_mode = sys.argv[1:] == ["--ci-real-core-gui"]
        self_test = sys.argv[1:] == ["--check-bundle"]
        if sys.argv[1:] and not (ci_mode or self_test):
            raise BundleLaunchError("WAM_BUNDLE_ARGUMENT_DENIED")
        if self_test:
            print("MACOS_ARM64_SELF_CONTAINED_CORE_WSP_BUNDLE_PASS")
            return 0

        # Finder launch runs the EXACT same signed actual Core E2E code that
        # GitHub tests. No synthetic RPC and no fallback to a sample snapshot.
        if not ci_mode:
            from PySide6.QtCore import QTimer, Qt
            from PySide6.QtWidgets import QApplication, QSplashScreen
            from PySide6.QtGui import QPixmap, QColor
            app = QApplication.instance() or QApplication([])
            pixmap = QPixmap(620, 260)
            pixmap.fill(QColor("#0C1728"))
            splash = QSplashScreen(pixmap)
            splash.showMessage(
                "WAM Privacy Wallet · REGTEST\n\n"
                "Verifying official WAM Core v0.1.11 and preparing a fresh "
                "public-demo BIP352 payment.\n"
                "NO MAINNET · NO REAL FUNDS · READ ONLY",
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom,
                QColor("#E9FCF6"),
            )
            splash.show()
            app.processEvents()
            # The existing desktop launcher enters the GUI event loop after
            # it finishes the actual mining/payment. Close the splash then.
            QTimer.singleShot(500, splash.close)
        result = smoke_real_core(
            core_dir, explicit_consent=True, wsp_source=source,
            wsp_payment_e2e=True,
            gui_e2e=ci_mode,
            interactive_demo=not ci_mode,
        )
        if ci_mode:
            if (result.get("status") != "REAL_WAM_CORE_V0_1_11_NATIVE_QT_WALLET_E2E_PASS"
                    or not result.get("gui_real_core_e2e_pass")
                    or not result.get("wsp_bip352_e2e_pass")
                    or result.get("mainnet_allowed") is not False):
                raise BundleLaunchError("WAM_BUNDLE_LIVE_E2E_DENIED")
            print("MACOS_ARM64_PACKAGED_APP_REAL_CORE_QT_BIP352_E2E_PASS")
        else:
            if not result.get("interactive_demo_closed_cleanly"):
                raise BundleLaunchError("WAM_BUNDLE_GUI_EXIT_DENIED")
        return 0
    except Exception:
        # Never emit Core log text, RPC passwords, private paths, BIP352 keys
        # or arbitrary subprocess exception details.
        print("WAM_REGTEST_BUNDLE_LAUNCH_DENIED", file=sys.stderr)
        if "--ci-real-core-gui" not in sys.argv:
            try:
                from PySide6.QtWidgets import QApplication, QMessageBox
                app = QApplication.instance() or QApplication([])
                QMessageBox.critical(
                    None, "WAM Privacy Wallet REGTEST",
                    "The signed Core, pinned scanner or REGTEST test run "
                    "could not be verified. No funds or user data were accessed.",
                )
            except Exception:
                pass
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
