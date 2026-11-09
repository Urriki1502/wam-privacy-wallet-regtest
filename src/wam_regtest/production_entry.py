"""Frozen macOS wallet entry. No developer dispatch or external resource paths."""
from pathlib import Path
import platform
import sys


def checked_resources():
    if (sys.platform != 'darwin' or platform.machine().lower() != 'arm64'
            or not getattr(sys, 'frozen', False) or not hasattr(sys, '_MEIPASS')):
        raise ValueError('PRODUCTION_NATIVE_FROZEN_REQUIRED')
    from wam_regtest.core import verified_core_paths
    from wam_regtest.wsp_live import _pinned_source
    from wam_regtest.branding import brand_image, check_bundle_icon
    root = Path(sys._MEIPASS).resolve()
    core, source = (root/'core').resolve(), (root/'wsp-source').resolve()
    verified_core_paths(core)
    _pinned_source(source)
    brand_image()
    check_bundle_icon(Path(sys.executable).parent.parent.parent)
    from wam_sp.core import pub, hash160
    from wam_sp.crypto import shared_point
    if shared_point((1).to_bytes(32, 'big'), pub(2)) != pub(2) or len(hash160(pub(31))) != 20:
        raise ValueError('PRODUCTION_NATIVE_CRYPTO_DENIED')
    return core, source


def main():
    # Validate argv before importing any application code or creating an owner.
    # Environment variables never enable a qualification/developer mode.
    if sys.argv[1:] not in ([], ['--check-bundle']):
        return 64
    try:
        core, source = checked_resources()
        if sys.argv[1:] == ['--check-bundle']:
            return 0
        from wam_regtest.managed_onboarding import launch
        return launch(core, source)
    except Exception:
        # No exception text, path, phrase or arbitrary log payload may escape.
        if sys.stderr is not None:
            print('WAM_PRODUCTION_LAUNCH_DENIED', file=sys.stderr)
        return 2
    finally:
        desktop = sys.modules.get('wam_regtest.desktop')
        if desktop is not None:
            desktop.shutdown_qt()


if __name__ == '__main__':
    raise SystemExit(main())
