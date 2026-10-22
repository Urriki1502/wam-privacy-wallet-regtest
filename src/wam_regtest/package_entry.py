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
import os
import sys


class BundleLaunchError(ValueError):
    pass


def _resource_paths() -> tuple[Path, Path]:
    if (sys.platform != "darwin" or platform.machine().lower() != "arm64"
            or not getattr(sys, "frozen", False)
            or not hasattr(sys, "_MEIPASS")):
        raise BundleLaunchError("WAM_BUNDLE_MACOS_ARM64_REQUIRED")
    root = Path(sys._MEIPASS).resolve()
    # PyInstaller relocates data under Contents/Resources and places a safe
    # symlink in _MEIPASS. Resolve that *directory* before Core refuses links;
    # the actual verified wamd/wam-cli members remain regular unmodified files.
    return (root / "core").resolve(), (root / "wsp-source").resolve()


def _check_bundle() -> tuple[Path, Path]:
    core_dir, source = _resource_paths()
    from wam_regtest.core import verified_core_paths
    from wam_regtest.wsp_live import _pinned_source
    node, cli, receipt = verified_core_paths(core_dir)
    if receipt.get("platform") != "macos-arm64":
        raise BundleLaunchError("WAM_BUNDLE_CORE_PLATFORM_DENIED")
    _pinned_source(source)
    from wam_regtest.branding import brand_image, check_bundle_icon
    brand_image()
    check_bundle_icon(Path(sys.executable).parent.parent.parent)
    # The ARM64 coincurve wheel embeds a package-local CFFI extension loaded
    # by native code, which static Python import analysis cannot discover.
    # Exercise native crypto in the frozen self-check, before starting Core.
    try:
        from wam_sp.core import pub, hash160
        from wam_sp.crypto import shared_point
        from wam_sp.keystore import Keyring
        if (shared_point((1).to_bytes(32, "big"), pub(2)) != pub(2)
                or len(hash160(pub(31))) != 20):
            raise BundleLaunchError("WAM_BUNDLE_NATIVE_CRYPTO_DENIED")
    except ImportError:
        raise BundleLaunchError("WAM_BUNDLE_NATIVE_CRYPTO_IMPORT_DENIED") from None
    if not node.is_file() or not cli.is_file():
        raise BundleLaunchError("WAM_BUNDLE_CORE_DENIED")
    return core_dir, source


def main() -> int:
    try:
        core_dir, source = _check_bundle()
        if sys.argv[1:2]==['--recover-owned-regtest-index']:
            from wam_regtest.supervisor_cli import recover_from_bundle
            return recover_from_bundle(core_dir,sys.argv[2:])
        if sys.argv[1:2]==['--ci-managed-gui-child']:
            from wam_regtest.managed_lifecycle_probe import child
            return child(core_dir,source,sys.argv[2:])
        from wam_regtest.core import smoke_real_core
        # Hidden CI mode: actual signed Core + genuine BIP352 + Qt screen.
        cocoa_mode = sys.argv[1:] == ["--ci-real-core-wallet-cocoa"]
        ci_mode = sys.argv[1:] == ["--ci-real-core-gui"] or cocoa_mode
        if cocoa_mode and os.environ.get("QT_QPA_PLATFORM") != "cocoa":
            raise BundleLaunchError("WAM_BUNDLE_COCOA_PLATFORM_REQUIRED")
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
            from PySide6.QtGui import QPixmap, QColor, QPainter
            from wam_regtest.desktop import qt_application
            from wam_regtest.branding import brand_image
            app = qt_application()
            pixmap = QPixmap(620, 300)
            pixmap.fill(QColor("#10100F"))
            painter = QPainter(pixmap)
            painter.drawPixmap(260,20,QPixmap(str(brand_image())).scaled(100,100,
                Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
            painter.end()
            splash = QSplashScreen(pixmap)
            splash.showMessage(
                "WAM Privacy Wallet · REGTEST\n\n"
                "Verifying official WAM Core v0.1.11 and preparing a fresh "
                "test-only BIP352 payment.\n"
                "NO MAINNET · NO REAL FUNDS · DISPOSABLE TEST KEYS",
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom,
                QColor("#F1C55A"),
            )
            splash.show()
            app.processEvents()
            # The existing desktop launcher enters the GUI event loop after
            # it finishes the actual mining/payment. Close the splash then.
            QTimer.singleShot(500, splash.close)
        result = smoke_real_core(
            core_dir, explicit_consent=True, wsp_source=source,
            wsp_payment_e2e=True,
            gui_e2e=ci_mode and not cocoa_mode,
            security_e2e=ci_mode,
            wallet_e2e=ci_mode,
            operational_demo=not ci_mode,
            interactive_demo=not ci_mode,
        )
        if ci_mode:
            if (result['wsp_live_scan']['scanner_transport'] != 'owned-http'
                    or result['wsp_live_scan']['cli_and_rehash_forbidden_during_scan'] is not True):
                raise BundleLaunchError('BUNDLE_SCANNER_HTTP_REQUIRED')
            if result['owned_startup_component']['status'] != 'REAL_CORE_OWNED_STARTUP_COLLISION_AND_PREAUTH_PASS':
                raise ValueError('BUNDLE_OWNED_STARTUP_ACCEPTANCE_REQUIRED')
            if result['graceful_shutdown_component']['status'] != 'REAL_CORE_GRACEFUL_SHUTDOWN_CONTINUITY_PASS':
                raise ValueError('BUNDLE_GRACEFUL_SHUTDOWN_ACCEPTANCE_REQUIRED')
            if result['index_recovery_component']['status'] != 'REAL_CORE_EXPLICIT_INDEX_RECOVERY_WALLET_CONTINUITY_PASS':
                raise ValueError('BUNDLE_INDEX_RECOVERY_ACCEPTANCE_REQUIRED')
            if result['bip39_index_recovery_component']['status'] != 'REAL_BIP39_MANAGED_INDEX_RECOVERY_PASS':
                raise ValueError('FROZEN_BIP39_INDEX_RECOVERY_DENIED')
            if result['a06_recovery_acceptance']['status'] != 'A06_RECOVERY_A_B_C_PASS':
                raise ValueError('FROZEN_A06_A_B_C_REQUIRED')
            if result['frozen_operator_recovery_component']['status'] != 'ACTUAL_FROZEN_OPERATOR_REINDEX_ENTRY_PASS':
                raise ValueError('BUNDLE_OPERATOR_ENTRY_ACCEPTANCE_REQUIRED')
            if (result['mining_account_component']['status'] != 'REAL_CORE_REGTEST_MINING_ACCOUNT_MATURITY_PASS'
                    or result['mining_account_component']['native_gui_depths'] != [99,100,101]
                    or result['mining_account_component']['owned_http_matches_independent_cli'] is not True):
                raise BundleLaunchError('BUNDLE_MINING_ACCEPTANCE_DENIED')
            if result['owned_http_read_component']['idle_read_component']['status'] != 'REAL_CORE_IDLE_READ_RECONNECT_PASS':
                raise BundleLaunchError('BUNDLE_IDLE_READ_REQUIRED')
            if result['owned_http_read_component']['node_busy_read_component']['status'] != 'REAL_CORE_BUSY_READ_RECOVERY_PASS':
                raise BundleLaunchError('BUNDLE_BUSY_READ_REQUIRED')
            if result['owned_http_read_component']['status'] != 'REAL_CORE_OWNED_HTTP_READ_COMPONENT_PASS':
                raise BundleLaunchError('WAM_BUNDLE_OWNED_HTTP_DENIED')
            expected_status = ("REAL_WAM_CORE_V0_1_11_BIP352_RECEIVE_E2E_PASS" if cocoa_mode else
                               "REAL_WAM_CORE_V0_1_11_NATIVE_QT_WALLET_E2E_PASS")
            if (result.get("status") != expected_status
                    or result.get("gui_real_core_e2e_pass") is not (not cocoa_mode)
                    or not result.get("wsp_bip352_e2e_pass")
                    or result.get("mainnet_allowed") is not False):
                raise BundleLaunchError("WAM_BUNDLE_LIVE_E2E_DENIED")
            if result["security_live_core"]["status"] != "REAL_CORE_MACOS_KEYCHAIN_ENCRYPTED_RECOVERY_REORG_PASS":
                raise BundleLaunchError("WAM_BUNDLE_SECURITY_E2E_DENIED")
            if result["wallet_live_core"]["status"] != "REAL_CORE_NATIVE_QT_SEND_SIGN_BROADCAST_SECURITY_E2E_PASS":
                raise BundleLaunchError("WAM_BUNDLE_WALLET_E2E_DENIED")
            if result["wallet_live_core"].get("cross_session_key_recovery") is not True:
                raise BundleLaunchError("WAM_BUNDLE_CROSS_SESSION_RECOVERY_DENIED")
            wallet=result["wallet_live_core"]
            if wallet['operational_snapshot_http']['cli_and_rehash_forbidden'] is not True:
                raise BundleLaunchError('BUNDLE_WALLET_HTTP_REQUIRED')
            security=result["security_live_core"]
            if not all(wallet.get(name) is True for name in (
                    "irreversible_anchor_before_native_crypto", "sign_broadcast_os_lease_held",
                    "real_core_lost_broadcast_reply_lock_retained", "uncertain_reservation_survives_unlock",
                    "background_sync_timer_live_core_verified", "local_network_privacy_diagnostics", "authenticated_selected_local_disclosure")):
                raise BundleLaunchError("WAM_BUNDLE_INTERRUPTED_PAYMENT_DENIED")
            if not all(security.get(name) is True for name in (
                    "separate_process_lease_contended", "killed_process_lease_released",
                    "failed_restore_plaintext_cleaned", "missing_or_replaced_keychain_anchor_denied",
                    "unanchored_snapshot_retry_denied")):
                raise BundleLaunchError("WAM_BUNDLE_NATIVE_FAILURE_PATHS_DENIED")
            if cocoa_mode:
                if result["wallet_live_core"].get("qt_auto_system_events_verified") is not True:
                    raise BundleLaunchError("WAM_BUNDLE_COCOA_AUTO_APPEARANCE_DENIED")
                print("MACOS_COCOA_PACKAGED_AUTO_LIGHT_DARK_REAL_CORE_WALLET_PASS")
            # Public disposable-fixture facts only. Keep actual frozen evidence
            # alongside artifacts, instead of relying solely on PASS log lines.
            from wam_regtest.desktop import qt_application
            result.update(frozen_entrypoint=True, qt_platform=qt_application().platformName())
            report='macos-cocoa-packaged-wallet-evidence.json' if cocoa_mode else 'macos-packaged-wallet-evidence.json'
            with Path(report).open('x',encoding='utf8') as stream:
                json.dump(result,stream,sort_keys=True,indent=2);stream.write('\n')
            print("MACOS_ARM64_PACKAGED_CROSS_SESSION_BACKUP_RECOVERY_PASS")
            print("MACOS_ARM64_PACKAGED_NATIVE_QT_SEND_SIGN_BROADCAST_SECURITY_PASS")
            print("MACOS_ARM64_PACKAGED_ENCRYPTED_RECOVERY_REORG_E2E_PASS")
            print("MACOS_ARM64_PACKAGED_APP_REAL_CORE_QT_BIP352_E2E_PASS")
        else:
            if not result.get("interactive_demo_closed_cleanly"):
                raise BundleLaunchError("WAM_BUNDLE_GUI_EXIT_DENIED")
        return 0
    except Exception as error:
        # Only a small fixed-code vocabulary; never emit arbitrary Core log
        # text, RPC credentials, paths, traceback or secrets.
        code = str(error)
        accepted = {"BundleLaunchError", "CoreSmokeError",
                    "RealWspScanError", "ReleaseError"}
        reason = (code if type(error).__name__ in accepted
                  and 5 <= len(code) <= 110
                  and code == code.upper()
                  and code.replace("_", "").isalnum()
                  else "UNKNOWN")
        print("WAM_REGTEST_BUNDLE_LAUNCH_DENIED:" + reason, file=sys.stderr)
        # The CI modes MUST NEVER open a modal Qt message box; it can hang
        # headless runners, obscuring the exact reason for bundle rejection.
        if len(sys.argv) == 1:
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
    finally:
        desktop = sys.modules.get("wam_regtest.desktop")
        if desktop is not None:
            desktop.shutdown_qt()


if __name__ == "__main__":
    raise SystemExit(main())
