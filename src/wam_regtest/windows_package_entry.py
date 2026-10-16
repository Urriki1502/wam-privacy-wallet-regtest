"""Frozen operational Windows x64 REGTEST entry; no system Python or downloads."""
from hashlib import sha256
import io
import json
from pathlib import Path
import platform
import sys
import tempfile


def _resources():
    if (sys.platform!='win32' or platform.machine().lower() not in ('amd64','x86_64')
            or not getattr(sys,'frozen',False) or not hasattr(sys,'_MEIPASS')):
        raise ValueError('WIN_BUNDLE_NATIVE_FROZEN_REQUIRED')
    from wam_regtest.wsp_live import _pinned_source
    from wam_regtest.branding import brand_image
    root=Path(sys._MEIPASS).absolute()
    source=root/'wsp-source';_pinned_source(source);brand_image()
    from wam_sp.core import pub,hash160
    from wam_sp.crypto import shared_point
    if shared_point((1).to_bytes(32,'big'),pub(2))!=pub(2) or len(hash160(pub(31)))!=20:
        raise ValueError('WIN_BUNDLE_NATIVE_CRYPTO_DENIED')
    return root/'core',source


def _stage_original_core(source,destination):
    from wam_regtest import windows_private_storage as store
    from wam_regtest.windows_core_transport import write_new,verified_core_paths
    from wam_regtest.windows_release_preflight import BINARY_SHA256
    store.create_private_directory(destination)
    with store.directory_guard(source,private=False):
        if set(p.name for p in source.iterdir())!={'wamd.exe','wam-cli.exe','receipt.json'}:
            raise ValueError('WIN_BUNDLE_CORE_MEMBERS_DENIED')
        for name in ('wamd.exe','wam-cli.exe','receipt.json'):
            # Distribution ACLs are not runtime custody. Only independently
            # pinned original bytes enter the newly protected executable stage.
            handle=store.create(str(source/name),0x80000000,1,None,3,0x200080,None)
            if handle in (None,store.INVALID):raise ValueError('WIN_BUNDLE_CORE_READ_DENIED')
            try:
                before=store._metadata(handle)
                limit=4096 if name=='receipt.json' else 128*1024*1024
                if not 1<=before[3]<=limit:raise ValueError('WIN_BUNDLE_CORE_SIZE_DENIED')
                import ctypes
                remaining=before[3];parts=[]
                while remaining:
                    size=min(remaining,65536);buf=ctypes.create_string_buffer(size);count=store.w.DWORD()
                    if not store.readfile(handle,buf,size,ctypes.byref(count),None) or not count.value:
                        raise ValueError('WIN_BUNDLE_CORE_READ_DENIED')
                    parts.append(buf.raw[:count.value]);remaining-=count.value
                if before!=store._metadata(handle):raise ValueError('WIN_BUNDLE_CORE_CHANGED_DENIED')
                payload=b''.join(parts)
                if name in BINARY_SHA256 and sha256(payload).hexdigest()!=BINARY_SHA256[name]:
                    raise ValueError('WIN_BUNDLE_CORE_PIN_DENIED')
                write_new(destination,name,payload)
            finally:store.close(handle)
    verified_core_paths(destination)


def main():
    # PyInstaller's native windowed bootloader has no console streams.
    if sys.stdout is None:sys.stdout=io.StringIO()
    if sys.stderr is None:sys.stderr=io.StringIO()
    ci=sys.argv[1:]==['--ci-real-core-wallet']
    try:
        if sys.argv[1:] and not ci:raise ValueError('WIN_BUNDLE_ARGUMENT_DENIED')
        core,source=_resources()
        from wam_regtest.core import smoke_real_core
        with tempfile.TemporaryDirectory(prefix='wam-win-frozen-') as t:
            stage=Path(t).absolute()/'core';_stage_original_core(core,stage)
            proof=smoke_real_core(stage,explicit_consent=True,wsp_source=source,
                wsp_payment_e2e=True,security_e2e=ci,wallet_e2e=ci,
                operational_demo=not ci,interactive_demo=not ci)
            if ci:
                if proof['owned_http_read_component']['status'] != 'REAL_CORE_OWNED_HTTP_READ_COMPONENT_PASS':
                    raise ValueError('WIN_BUNDLE_OWNED_HTTP_DENIED')
                wallet=proof['wallet_live_core'];security=proof['security_live_core']
                if (proof['platform']!='windows-x64' or proof['block_height']!=105
                        or proof['mainnet_allowed'] is not False
                        or wallet['status']!='WIN64_REAL_CORE_NATIVE_QT_SEND_SIGN_BROADCAST_SECURITY_E2E_PASS'
                        or security['actual_core_reorg_depths']!=[1,12,100]
                        or not all(wallet.get(k) is True for k in ('native_qt_prepare_sign_broadcast',
                            'irreversible_anchor_before_native_crypto','sign_broadcast_os_lease_held',
                            'real_core_lost_broadcast_reply_lock_retained','uncertain_reservation_survives_unlock'))
                        or not all(wallet['cross_session_recovery_proof'].get(k) is True for k in
                            ('same_test_keys_recovered','old_reservations_retained',
                             'stale_before_native_signature_denied','stale_before_real_broadcast_denied'))):
                    raise ValueError('WIN_BUNDLE_REAL_WALLET_E2E_DENIED')
                with Path('windows-packaged-wallet-evidence.json').open('x',encoding='utf8') as out:
                    json.dump(proof,out,sort_keys=True,indent=2);out.write('\n')
            elif proof.get('interactive_demo_closed_cleanly') is not True:
                raise ValueError('WIN_BUNDLE_SHUTDOWN_DENIED')
        return 0
    except Exception:
        # No arbitrary exception text, traceback, secret or node log escapes.
        if ci:
            with Path('windows-packaged-wallet-denied.json').open('x',encoding='utf8') as out:
                json.dump({'status':'WIN_BUNDLE_DENIED','mainnet_allowed':False},out)
        else:
            from PySide6.QtWidgets import QApplication,QMessageBox
            app=QApplication.instance() or QApplication([])
            QMessageBox.critical(None,'WAM Privacy Wallet REGTEST',
                'The original Core, private custody or real REGTEST startup could not be verified.')
        return 2
    finally:
        from wam_regtest.desktop import shutdown_qt
        shutdown_qt()


if __name__=='__main__':
    raise SystemExit(main())
