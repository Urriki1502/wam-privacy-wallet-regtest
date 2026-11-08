"""Frozen Linux x86_64 REGTEST wallet entry. No developer dispatch or CLI router.

Accepted argv only:
  (empty)                  existing desktop flow (manifest + witness dialogs)
  --check-bundle           read-only bundle self-check
Everything else returns 64 before resources are read, including the
headless `wallet ...` CLI: Linux headless uses the legacy base WalletSession
custody, not the Q06 BIP39 original-owner path, so it is NOT a production
spending authority (six-gate decision B). It remains an experimental REGTEST
engineering tool in the qualification build. Environment is ignored.
"""
from pathlib import Path
import platform
import sys

def checked_resources():
    if (sys.platform != 'linux' or platform.machine() != 'x86_64'
            or not getattr(sys, 'frozen', False) or not hasattr(sys, '_MEIPASS')):
        raise ValueError('LINUX_PRODUCTION_NATIVE_FROZEN_REQUIRED')
    root = Path(sys._MEIPASS).absolute()
    source, core = root/'wsp-source', root/'core'
    from wam_regtest.wsp_live import _pinned_source
    from wam_regtest.branding import brand_image
    _pinned_source(source)
    brand_image()
    from wam_sp.core import pub, hash160
    from wam_sp.crypto import shared_point
    if shared_point((1).to_bytes(32, 'big'), pub(2)) != pub(2) or len(hash160(pub(31))) != 20:
        raise ValueError('LINUX_PRODUCTION_NATIVE_CRYPTO_DENIED')
    return core, source


def _desktop(core, source):
    # Same desktop flow as the qualification entry: independent manifest
    # approval and an already provisioned witness. Never installs root code.
    from wam_regtest.desktop import qt_application
    from PySide6.QtWidgets import QInputDialog, QMessageBox
    qt_application()
    approved, ok = QInputDialog.getText(None, 'Official signed Core v0.1.13',
        'Enter the independently reviewed Core manifest SHA-256.\n'
        'Official Core; independently reviewed Ubuntu24.04 loader closure.')
    if not ok:
        return 0
    endpoint, ok = QInputDialog.getText(None, 'Independent root witness',
        'Absolute socket path of the administratively provisioned root witness:')
    if not ok or not endpoint:
        return 0
    if QMessageBox.question(None, 'Disposable REGTEST only',
            'Create a fresh isolated local test chain with disposable test keys?\n'
            'No mainnet, real funds or privileged service installation.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
        return 0
    from wam_regtest.linux_runtime import configure
    configure(core, approved.strip(), Path(endpoint), authorized=True)
    from wam_regtest.managed_onboarding import launch
    return launch(core, source)


def main():
    argv = sys.argv[1:]
    if argv not in ([], ['--check-bundle']):
        return 64
    try:
        core, source = checked_resources()
        if argv == ['--check-bundle']:
            return 0
        return _desktop(core, source)
    except Exception:
        # Fixed token only; never exception text, paths or secrets.
        print('LINUX_PRODUCTION_WALLET_DENIED', file=sys.stderr)
        return 2
    finally:
        desktop = sys.modules.get('wam_regtest.desktop')
        if desktop is not None:
            desktop.shutdown_qt()


if __name__ == '__main__':
    raise SystemExit(main())
