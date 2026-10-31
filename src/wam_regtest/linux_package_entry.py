"""Native frozen Linux entry with bundled exact Core/WSP and explicit trust.

No downloads, system Python, environment trust bypass or privileged installer.
"""
from pathlib import Path
import platform
import re
import sys

from wam_regtest.external_core import ExternalAttachmentError


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
        q04_mode = args and args[0] == 'q04-external-miner'
        if args[:1]==['--ci-q05-managed-wallet']:
            from wam_regtest.q05_packaged import run
            return run(core,source,args[1:])
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
            from wam_regtest.linux_runtime import configure
            configure(core,approved.strip(),Path(endpoint),authorized=True)
            from wam_regtest.managed_onboarding import launch
            return launch(core,source)
        if any(a=='--core-dir' or a.startswith('--core-dir=') or a=='--wsp-source-root'
                or a.startswith('--wsp-source-root=') for a in args):
            raise ValueError('LINUX_BUNDLE_EXTERNAL_RESOURCE_OVERRIDE_DENIED')
        if q04_mode:
            sys.argv=[sys.argv[0],'q04-external-miner','--core-dir',str(core),
                '--confirm-disposable-regtest',*args[1:]]
        else:
            sys.argv=[sys.argv[0],'linux-wallet','--core-dir',str(core),'--wsp-source-root',str(source),*args]
        from wam_regtest.cli import main as cli_main
        return cli_main()
    except Exception as error:
        # Emit only a fixed code from known boundaries, never exception text,
        # OS paths, credentials or a traceback. The process still fails.
        from wam_regtest.linux_developer_core import LinuxCoreError
        from wam_regtest.q04_runner import Q04RunnerError
        from wam_regtest.q04_fixture import Q04FixtureError
        from wam_regtest.rpc_contention import RpcContentionError
        reason='LINUX_FROZEN_UNCLASSIFIED'
        if type(error) in (LinuxCoreError,Q04RunnerError,Q04FixtureError,ExternalAttachmentError,RpcContentionError):
            args=error.args
            if (len(args)==1 and type(args[0]) is str and len(args[0])<=110
                    and re.fullmatch(r'(?:LINUX|Q04|EXTERNAL_ATTACHMENT)_[A-Z0-9_]{4,100}',args[0])):
                reason=args[0]
        print('LINUX_FROZEN_WALLET_DENIED:'+reason,file=sys.stderr)
        return 2
    finally:
        desktop=sys.modules.get('wam_regtest.desktop')
        if desktop is not None:desktop.shutdown_qt()


if __name__=='__main__':raise SystemExit(main())
