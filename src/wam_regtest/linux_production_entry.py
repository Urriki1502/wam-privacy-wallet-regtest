"""Frozen Linux x86_64 REGTEST wallet entry. No developer dispatch or CLI router.

Accepted argv only:
  (empty)                  existing desktop flow (manifest + witness dialogs)
  --check-bundle           read-only bundle self-check
  wallet --manifest-sha256 HEX --anchor-socket ABS
         --confirm-experimental-developer-regtest [--recover-backup ABS]
                           existing headless wallet (linux_headless.launch)
Everything else (acceptance probes, --ci-*, q04, external Core/WSP overrides,
report files) returns 64 before resources are read. Environment is ignored.
"""
from pathlib import Path
import platform
import re
import sys

_FLAGS = frozenset(('--confirm-experimental-developer-regtest',))
_VALUED = frozenset(('--manifest-sha256', '--anchor-socket', '--recover-backup'))
_REQUIRED = frozenset(('--manifest-sha256', '--anchor-socket', '--confirm-experimental-developer-regtest'))


def headless_arguments(argv):
    """Strict, abbreviation-free parser; None means refuse."""
    seen = {}
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in seen:
            return None
        if token in _FLAGS:
            seen[token] = True
            index += 1
        elif (token in _VALUED and index + 1 < len(argv)
                and not argv[index + 1].startswith('-')):
            seen[token] = argv[index + 1]
            index += 2
        else:
            return None
    if not _REQUIRED <= set(seen):
        return None
    if not re.fullmatch('[0-9a-f]{64}', seen['--manifest-sha256']):
        return None
    for key in ('--anchor-socket', '--recover-backup'):
        if key in seen and not Path(seen[key]).is_absolute():
            return None
    return seen


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
    headless = None
    if argv[:1] == ['wallet']:
        headless = headless_arguments(argv[1:])
        if headless is None:
            return 64
    elif argv not in ([], ['--check-bundle']):
        return 64
    try:
        core, source = checked_resources()
        if argv == ['--check-bundle']:
            return 0
        if headless is not None:
            from types import SimpleNamespace
            from wam_regtest.linux_headless import run
            backup = headless.get('--recover-backup')
            return run(SimpleNamespace(
                core_dir=core, wsp_source_root=source,
                manifest_sha256=headless['--manifest-sha256'],
                anchor_socket=Path(headless['--anchor-socket']),
                confirm_experimental_developer_regtest=True,
                confirm_headless_e2e=False, confirm_qt_e2e=False, gui=False,
                recover_backup=None if backup is None else Path(backup), report=None))
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
