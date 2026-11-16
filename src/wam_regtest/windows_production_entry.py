"""Frozen Windows x64 REGTEST wallet entry. No developer dispatch.

Distributed bytes accept only an empty argv (normal wallet) or the read-only
`--check-bundle`. Environment variables never enable a qualification mode.
The qualification-only executable keeps windows_package_entry and its tests.
"""
import io
from pathlib import Path
import platform
import sys
import tempfile


def checked_resources():
    if (sys.platform != 'win32' or platform.machine().lower() not in ('amd64', 'x86_64')
            or not getattr(sys, 'frozen', False) or not hasattr(sys, '_MEIPASS')):
        raise ValueError('WIN_PRODUCTION_NATIVE_FROZEN_REQUIRED')
    from wam_regtest.wsp_live import _pinned_source
    from wam_regtest.branding import brand_image
    root = Path(sys._MEIPASS).absolute()
    source = root/'wsp-source'
    _pinned_source(source)
    brand_image()
    from wam_sp.core import pub, hash160
    from wam_sp.crypto import shared_point
    if shared_point((1).to_bytes(32, 'big'), pub(2)) != pub(2) or len(hash160(pub(31))) != 20:
        raise ValueError('WIN_PRODUCTION_NATIVE_CRYPTO_DENIED')
    return root/'core', source


def main():
    # The windowed bootloader has no console streams.
    if sys.stdout is None:
        sys.stdout = io.StringIO()
    if sys.stderr is None:
        sys.stderr = io.StringIO()
    # Validate argv before importing any application code or creating an owner.
    if sys.argv[1:] not in ([], ['--check-bundle']):
        return 64
    try:
        core, source = checked_resources()
        from wam_regtest.windows_core_stage import _stage_original_core
        with tempfile.TemporaryDirectory(prefix='wam-win-wallet-') as temporary:
            stage = Path(temporary).absolute()/'core'
            # Only independently pinned original Core bytes enter the new
            # private executable stage, exactly as the qualification entry.
            _stage_original_core(core, stage)
            if sys.argv[1:] == ['--check-bundle']:
                return 0
            from wam_regtest.managed_onboarding import launch
            return launch(stage, source)
    except Exception:
        # No exception text, path, phrase or arbitrary payload may escape.
        if not sys.argv[1:]:
            try:
                from PySide6.QtWidgets import QApplication, QMessageBox
                QApplication.instance() or QApplication([])
                QMessageBox.critical(None, 'WAM Privacy Wallet REGTEST',
                    'The original Core, private custody or real REGTEST startup could not be verified.')
            except Exception:
                pass
        return 2
    finally:
        desktop = sys.modules.get('wam_regtest.desktop')
        if desktop is not None:
            desktop.shutdown_qt()


if __name__ == '__main__':
    raise SystemExit(main())
