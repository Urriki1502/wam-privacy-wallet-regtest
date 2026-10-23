"""Native frozen Linux entry with bundled exact Core/WSP and explicit trust.

No downloads, system Python, environment trust bypass or privileged installer.
"""
from pathlib import Path
import platform
import sys


def main():
    try:
        if (sys.platform!='linux' or platform.machine()!='x86_64'
                or not getattr(sys,'frozen',False) or not hasattr(sys,'_MEIPASS')):
            raise ValueError('LINUX_NATIVE_FROZEN_REQUIRED')
        root=Path(sys._MEIPASS).absolute();source=root/'wsp-source';core=root/'core'
        from wam_regtest.wsp_live import _pinned_source
        from wam_regtest.branding import brand_image
        _pinned_source(source);brand_image()
        from wam_sp.core import pub,hash160
        from wam_sp.crypto import shared_point
        if shared_point((1).to_bytes(32,'big'),pub(2))!=pub(2) or len(hash160(pub(31)))!=20:
            raise ValueError('LINUX_BUNDLE_NATIVE_CRYPTO_DENIED')
        args=sys.argv[1:]
        if args[:1]==['--ci-managed-gui-child']:
            from wam_regtest.managed_lifecycle_probe import child
            return child(core,source,args[1:])
        if args[:1]==['--recover-owned-regtest-index']:
            from wam_regtest.supervisor_cli import recover_from_bundle
            return recover_from_bundle(core,args[1:])
        if not args:
            # Desktop launch still requires independent manifest approval and
            # an already provisioned witness. Never auto-install root code.
            from wam_regtest.desktop import qt_application
            from PySide6.QtWidgets import QInputDialog,QMessageBox
            app=qt_application()
            approved,ok=QInputDialog.getText(None,'Experimental developer Core',
                'Enter the independently reviewed Core manifest SHA-256.\n'
                'Linux source build; not an official signed release.')
            if not ok:return 0
            endpoint,ok=QInputDialog.getText(None,'Independent root witness',
                'Absolute socket path of the administratively provisioned root witness:')
            if not ok or not endpoint:return 0
            if QMessageBox.question(None,'Disposable REGTEST only',
                    'Create a fresh isolated local test chain with disposable test keys?\n'
                    'No mainnet, real funds or privileged service installation.',
                    QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return 0
            args=['--gui','--manifest-sha256',approved.strip(),'--anchor-socket',endpoint,
                '--confirm-experimental-developer-regtest']
        if any(a=='--core-dir' or a.startswith('--core-dir=') or a=='--wsp-source-root'
                or a.startswith('--wsp-source-root=') for a in args):
            raise ValueError('LINUX_BUNDLE_EXTERNAL_RESOURCE_OVERRIDE_DENIED')
        sys.argv=[sys.argv[0],'linux-wallet','--core-dir',str(core),'--wsp-source-root',str(source),*args]
        from wam_regtest.cli import main as cli_main
        return cli_main()
    except Exception:
        print('LINUX_FROZEN_WALLET_DENIED',file=sys.stderr)
        return 2
    finally:
        desktop=sys.modules.get('wam_regtest.desktop')
        if desktop is not None:desktop.shutdown_qt()


if __name__=='__main__':raise SystemExit(main())
