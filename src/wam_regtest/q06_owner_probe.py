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
    # Fixed non-sensitive stage markers; avoid opaque subprocess timeout.
    def stage(label):
        print("MACOS_Q06_OWNER_STAGE=" + label, flush=True)
    stage("NATIVE_SCOPE_VERIFIED")
    with custody.private_temporary_directory(prefix="q06-owner-frozen-") as t:
        parent=Path(t).resolve()
        def new_executor():
            root=parent/("wam-fusion-core-"+secrets.token_hex(8))
            custody.create_directory(root)
            # Do NOT create the disposable Keychain before CoreSupervisor:
            # a fresh owner requires an empty namespace other than its lock.
            # Backend opens the original owner first, then creates this anchor.
            return WalletExecutor(
                lambda:Bip39ReadOnlyBackend(
                    root,core,source,_anchor_factory=adapter.make_anchor))
        first=new_executor()
        second=None
        window=None
        good=False
        try:
            stage("CREATE_SEED_AND_OWNED_CORE_START")
            opened=first.request("open",password,"create","",timeout=120)
            stage("CREATE_SEED_AND_OWNED_CORE_PASS")
            phrase=opened["mnemonic_once"]
            if (type(phrase) is not str or len(phrase.split())!=12
                    or not opened["receive_code"].startswith("wamrtsp1")
                    or opened["signer_allowed"] is not False):
                raise ValueError("Q06_OWNER_MNEMONIC_OR_RECEIVE_DENIED")
            stage("GENESIS_READ_ONLY_SCAN_START")
            first_view=first.request("snapshot",timeout=120)
            stage("GENESIS_READ_ONLY_SCAN_PASS")
            if (first_view["status"]!="Q06_REGTEST_REAL_CORE_READ_ONLY_VERIFIED"
                    or first_view["height"]!=0 or first_view["tip"]!=REGTEST_GENESIS
                    or first_view["confirmed_atoms"]!=0 or first_view["history_count_shown"]!=0
                    or first_view["signer_allowed"] is not False
                    or first_view["broadcast_allowed"] is not False):
                raise ValueError("Q06_OWNER_NATIVE_CORE_SCAN_DENIED")
            stage("COCOA_QT_RECEIVE_START")
            window=Bip39TrialWindow(first)
            stage("COCOA_QT_RECEIVE_PASS")
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
            stage("COCOA_QT_RECEIVE_BINDING_PASS")
            # One genuine signed-Core fixture payment addressed to the keys
            # derived from THIS 12-word BIP39 profile. This must never be
            # confused with Q05's previously green funded-wallet proof.
            stage("GENUINE_CORE_PUBLIC_FUND_START")
            funded=first.request("mine",timeout=240)
            stage("GENUINE_CORE_PUBLIC_FUND_PASS")
            stage("GENUINE_CORE_FUNDED_SCAN_START")
            funded_view=first.request("snapshot",timeout=120)
            stage("GENUINE_CORE_FUNDED_SCAN_PASS")
            if (funded["status"]!="Q06_REGTEST_PUBLIC_BIP39_RECEIVE_FUNDED"
                    or funded_view["confirmed_atoms"]!=funded["atoms"]
                    or funded_view["available_atoms"]!=funded["atoms"]
                    or funded_view["history_count_shown"]<1
                    or funded_view["height"]!=funded["height"]
                    or funded_view["signer_allowed"] is not False
                    or funded_view["broadcast_allowed"] is not False):
                raise ValueError("Q06_OWNER_ACTUAL_BIP39_FUNDED_RECEIVE_DENIED")
            window._on_ready("snapshot",funded_view)
            app.processEvents()
            if str(funded["atoms"]) not in window.balance.text().replace(",",""):
                raise ValueError("Q06_OWNER_FUNDED_QT_BALANCE_DENIED")
            data["Q06_actual_onchain_BIP39_received_atoms"]=funded["atoms"]
            data["Q06_actual_Core_confirmed_BIP39_txid_sha256"]=sha256(funded["txid"].encode()).hexdigest()
            data["Q06_native_Qt_funded_balance_bound"]=True
            # Never touch a Q05 reference or create a signing grant.
            first.request("lock")
            stage("ENCRYPTED_SEED_REOPEN_START")
            reopened=first.request("open",password,"reopen","",timeout=120)
            stage("ENCRYPTED_SEED_REOPEN_PASS")
            if (reopened["mnemonic_once"] or reopened["receive_code"]!=opened["receive_code"]):
                raise ValueError("Q06_OWNER_ENCRYPTED_REOPEN_IDENTITY_DENIED")
            first.request("lock")
            window._poll.stop();window.hide()
            # Do not call closeEvent while the executor is still owning Core;
            # the Qt close path intentionally queues its own quit command.
            stage("ORIGINAL_CORE_SHUTDOWN_START")
            first.request("quit",timeout=60)
            if not first.join(15) or not first.closed:
                raise ValueError("Q06_OWNER_ORIGINAL_CORE_SHUTDOWN_DENIED")
            data["Q06_original_core_clean_shutdown"]=True
            stage("ORIGINAL_CORE_SHUTDOWN_PASS")
            second=new_executor()
            stage("FRESH_OWNER_BIP39_RESTORE_START")
            restored=second.request("open",password,"restore",phrase,timeout=120)
            stage("FRESH_OWNER_BIP39_RESTORE_PASS")
            if (restored["mnemonic_once"]
                    or restored["account_id"]!=opened["account_id"]
                    or restored["receive_code"]!=opened["receive_code"]):
                raise ValueError("Q06_OWNER_NEW_PROFILE_RESTORE_IDENTITY_DENIED")
            stage("FRESH_OWNER_CORE_SCAN_START")
            second_view=second.request("snapshot",timeout=120)
            stage("FRESH_OWNER_CORE_SCAN_PASS")
            if second_view["tip"]!=REGTEST_GENESIS or second_view["confirmed_atoms"]!=0:
                raise ValueError("Q06_OWNER_RESTORED_NEW_CORE_SCAN_DENIED")
            stage("RESTORED_OWNER_SHUTDOWN_START")
            second.request("quit",timeout=60)
            if not second.join(15) or not second.closed:
                raise ValueError("Q06_OWNER_RESTORED_SHUTDOWN_DENIED")
            data["Q06_BIP39_disposable_fresh_restore_same_receive"]=True
            data["Q06_12_word_native_owned_core"]=True
            data["receive_code_sha256"]=sha256(opened["receive_code"].encode()).hexdigest()
            data["status"]="Q06_NATIVE_BIP39_12_READONLY_OWNER_GUI_PASS"
            stage("NATIVE_OWNER_READ_ONLY_ALL_PASS")
            good=True
        finally:
            if window is not None:
                window._poll.stop()
                window.hide()
            # Failure must not tear down an uncertain owner/core or delete its
            # chain/anchor. Keep the forensic root; do not rerun silently.
            if not good:
                data["status"]="FAIL_SAFE_EVIDENCE_RETAINED"
                # Only ask an idle original owner to shut down. No retry,
                # force-kill or automatic adoption of an uncertain write.
                stage("FAIL_CLOSED_EXPLICIT_OWNER_SHUTDOWN_ATTEMPT")
                for executor in (second,first):
                    if executor is None or executor.closed or executor.busy:
                        continue
                    try:
                        executor.request("quit",timeout=45)
                        executor.join(15)
                    except Exception:
                        stage("FAIL_CLOSED_OWNER_PRESERVED")
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
        print("MACOS_Q06_NATIVE_BIP39_12_GUI_CORE_READONLY_PASS",flush=True)
        return 0
    except Exception:
        # Fixed public failure only, not secret, path, exception text or mnemonic.
        print("MACOS_Q06_NATIVE_BIP39_12_GUI_CORE_READONLY_DENIED",flush=True)
        return 2
