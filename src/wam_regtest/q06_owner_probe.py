"""One bounded actual macOS signed-Core Q06 owner/read-only application probe.

Invoked INSIDE the frozen macOS app by its existing packaging qualification
job, never through the normal Finder launch. No mainnet, no general mining,
no Q05 Keyring migration, no signing/broadcast or private evidence.
"""
from hashlib import sha256
import json
from pathlib import Path
import platform
import secrets
import sys

from . import custody
from .bip39_owner_backend import Bip39ReadOnlyBackend
from .q05_platforms import DarwinArm64Adapter
from .wallet_executor import WalletExecutor
from .wsp_live import REGTEST_GENESIS, _pinned_source


def qualify(core,source):
    if sys.platform!="darwin" or platform.machine().lower()!="arm64":
        raise ValueError("Q06_OWNER_NATIVE_MACOS_REQUIRED")
    from .core import verified_core_paths
    verified_core_paths(core)
    _pinned_source(source)
    adapter=DarwinArm64Adapter()
    adapter.enforce_host()
    from .desktop import qt_application
    app=qt_application()
    if app.platformName()!="cocoa":
        raise ValueError("Q06_OWNER_NATIVE_COCOA_REQUIRED")
    from .bip39_owner_gui import Bip39TrialWindow
    password=b"public-disposable-q06-native-macos-only"
    data={"status":"FAIL","network":"regtest","mainnet_allowed":False,
          "Q06_12_word_native_owned_core":False,"Q06_original_core_clean_shutdown":False,
          "Q06_BIP39_disposable_fresh_restore_same_receive":False,
          "Q06_native_Qt_receive_bound":False,"Q06_Sign_or_Broadcast_executed":False}
    with custody.private_temporary_directory(prefix="q06-owner-frozen-") as t:
        parent=Path(t).resolve()
        def new_executor():
            root=parent/("wam-fusion-core-"+secrets.token_hex(8))
            custody.create_directory(root)
            keychain=adapter.make_anchor(root)
            return WalletExecutor(
                lambda:Bip39ReadOnlyBackend(root,core,source,keychain=keychain))
        first=new_executor()
        second=None
        window=None
        good=False
        try:
            opened=first.request("open",password,"create","")
            phrase=opened["mnemonic_once"]
            if (type(phrase) is not str or len(phrase.split())!=12
                    or not opened["receive_code"].startswith("wamrtsp1")
                    or opened["signer_allowed"] is not False):
                raise ValueError("Q06_OWNER_MNEMONIC_OR_RECEIVE_DENIED")
            first_view=first.request("snapshot")
            if (first_view["status"]!="Q06_REGTEST_REAL_CORE_READ_ONLY_VERIFIED"
                    or first_view["height"]!=0 or first_view["tip"]!=REGTEST_GENESIS
                    or first_view["confirmed_atoms"]!=0 or first_view["history_count_shown"]!=0
                    or first_view["signer_allowed"] is not False
                    or first_view["broadcast_allowed"] is not False):
                raise ValueError("Q06_OWNER_NATIVE_CORE_SCAN_DENIED")
            window=Bip39TrialWindow(first)
            window.show()
            sanitized=dict(opened);sanitized["mnemonic_once"]=""
            window._on_ready("open",sanitized)
            window._on_ready("snapshot",first_view)
            app.processEvents()
            if (window.receive.text()!=opened["receive_code"]
                    or "0 atoms" not in window.balance.text()
                    or not window.isVisible()):
                raise ValueError("Q06_OWNER_QT_BINDING_DENIED")
            data["Q06_native_Qt_receive_bound"]=True
            # Never touch a Q05 reference or create a signing grant.
            first.request("lock")
            reopened=first.request("open",password,"reopen","")
            if (reopened["mnemonic_once"] or reopened["receive_code"]!=opened["receive_code"]):
                raise ValueError("Q06_OWNER_ENCRYPTED_REOPEN_IDENTITY_DENIED")
            first.request("lock")
            window._poll.stop();window.hide();window.close()
            window=None
            first.request("quit")
            if not first.join(15) or not first.closed:
                raise ValueError("Q06_OWNER_ORIGINAL_CORE_SHUTDOWN_DENIED")
            data["Q06_original_core_clean_shutdown"]=True
            second=new_executor()
            restored=second.request("open",password,"restore",phrase)
            if (restored["mnemonic_once"]
                    or restored["account_id"]!=opened["account_id"]
                    or restored["receive_code"]!=opened["receive_code"]):
                raise ValueError("Q06_OWNER_NEW_PROFILE_RESTORE_IDENTITY_DENIED")
            second_view=second.request("snapshot")
            if second_view["tip"]!=REGTEST_GENESIS or second_view["confirmed_atoms"]!=0:
                raise ValueError("Q06_OWNER_RESTORED_NEW_CORE_SCAN_DENIED")
            second.request("quit")
            if not second.join(15) or not second.closed:
                raise ValueError("Q06_OWNER_RESTORED_SHUTDOWN_DENIED")
            data["Q06_BIP39_disposable_fresh_restore_same_receive"]=True
            data["Q06_12_word_native_owned_core"]=True
            data["receive_code_sha256"]=sha256(opened["receive_code"].encode()).hexdigest()
            data["status"]="Q06_NATIVE_BIP39_12_READONLY_OWNER_GUI_PASS"
            good=True
        finally:
            if window is not None:
                window._poll.stop()
                window.hide()
            # Failure must not tear down an uncertain owner/core or delete its
            # chain/anchor. Keep the forensic root; do not rerun silently.
            if not good:
                data["status"]="FAIL_SAFE_EVIDENCE_RETAINED"
            phrase=None
    return data


def run(core,source):
    try:
        report=qualify(core,source)
        with Path("q06-frozen-readonly-evidence.json").open("x") as out:
            json.dump(report,out,sort_keys=True,indent=2)
            out.write("\n")
        if report["status"]!="Q06_NATIVE_BIP39_12_READONLY_OWNER_GUI_PASS":
            raise ValueError("Q06_NATIVE_READONLY_OWNER_DENIED")
        print("MACOS_Q06_NATIVE_BIP39_12_GUI_CORE_READONLY_PASS")
        return 0
    except Exception:
        # Fixed public failure only, not secret, path, exception text or mnemonic.
        print("MACOS_Q06_NATIVE_BIP39_12_GUI_CORE_READONLY_DENIED")
        return 2
