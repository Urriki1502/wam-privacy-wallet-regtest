"""Frozen Windows/Linux Q06 REGTEST integration qualification.

Real owned Core, pinned WSP and native custody. One fresh disposable profile;
no RPC mocks, no foreign checkpoint, no mainnet, no owner merge authorization.
Native GUI binding is checked on desktop builds; Linux headless omits Qt.
"""
from hashlib import sha256
import json
from pathlib import Path
import platform
import re
import sys

from .bip39_12 import Bip39Regtest12Keys
from .bip39_owner_backend import Bip39ReadOnlyBackend
from .q05_platforms import detect_adapter
from .wallet_executor import WalletExecutor
from .wsp_live import _pinned_source
from .core import verified_core_paths


class Q06PlatformQualificationError(ValueError):
    pass


def qualify(core, source, root, receipt, *, confirmed=False,
            linux_manifest=None, linux_witness=None, headless=False):
    if (confirmed is not True or not getattr(sys, "frozen", False)
            or platform.system() not in ("Windows", "Linux")
            or not root.is_absolute() or not receipt.is_absolute()
            or root.exists() or root.is_symlink() or receipt.exists() or receipt.is_symlink()
            or not re.fullmatch(r"wam-fusion-core-[0-9a-f]{16}", root.name)
            or not root.parent.is_dir()
            or type(headless) is not bool
            or (platform.system() == "Windows" and headless)):
        raise Q06PlatformQualificationError("Q06_PLATFORM_SCOPE_DENIED")
    adapter = detect_adapter()
    adapter.enforce_host()
    _pinned_source(source)
    verified_core_paths(core)
    stage = "PREFLIGHT"
    record = {
        "schema": "q06-native-frozen-owned-core/v1",
        "status": "FAIL", "failure_stage": stage,
        "platform": adapter.platform_id, "frozen": True,
        "headless": headless, "synthetic_rpc": False,
        "official_signed_core": adapter.official_signed,
        "native_custody": True, "mainnet_allowed": False,
        "physical_accepted": False, "independent_reviewed": False,
        "same_chain_mnemonic_history_recovered": False,
        "fresh_chain_full_history_recovered": False,
        "same_owner_reopened": False, "post_reopen_txid_verified": False,
        "signed_core_transaction_confirmed": False,
        "native_gui_checked": False,
    }
    exe = Path(sys.executable)
    if not exe.is_file():
        raise Q06PlatformQualificationError("Q06_PLATFORM_FROZEN_EXECUTABLE_MISSING")
    record["frozen_executable_sha256"] = sha256(exe.read_bytes()).hexdigest()
    executor = None
    window = None
    good = False
    phrase = None
    def step(name):
        nonlocal stage
        stage = name
        record["failure_stage"] = name
        print("Q06_" + adapter.platform_id.upper().replace("-", "_")
              + "_STAGE=" + name, flush=True)
    try:
        step("TRUST")
        adapter.prepare_trust(core, linux_manifest, linux_witness, test_witness=False)
        step("CREATE")
        password = b"disposable-native-frozen-q06-cross-platform"
        executor = WalletExecutor(lambda: Bip39ReadOnlyBackend(
            root, core, source, _anchor_factory=adapter.make_anchor))
        opened = executor.request("open", password, "create", "", timeout=120)
        phrase = opened["mnemonic_once"]
        if (len(phrase.split()) != 12
                or not opened["receive_code"].startswith("wamrtsp1")
                or opened["signer_allowed"] is not False):
            raise Q06PlatformQualificationError("Q06_PLATFORM_CREATE_DENIED")
        step("FUND")
        funded = executor.request("mine", timeout=240)
        first = executor.request("snapshot", timeout=240)
        if (first["confirmed_atoms"] != funded["atoms"]
                or first["available_atoms"] != funded["atoms"]
                or first["history_count_shown"] < 1):
            raise Q06PlatformQualificationError("Q06_PLATFORM_FUNDED_RECEIVE_DENIED")
        step("ACTIVATE")
        active = executor.request("activate", timeout=240)
        if (active["signer_allowed"] is not True
                or active["broadcast_allowed"] is not True
                or active["confirmed_atoms"] != funded["atoms"]
                or active["mainnet_allowed"] is not False):
            raise Q06PlatformQualificationError("Q06_PLATFORM_NATIVE_SPEND_DENIED")
        if not headless:
            step("NATIVE_QT")
            from .desktop import qt_application
            from .bip39_owner_gui import Bip39TrialWindow
            app = qt_application()
            expected = "windows" if sys.platform == "win32" else "xcb"
            if app.platformName() != expected:
                raise Q06PlatformQualificationError("Q06_PLATFORM_NATIVE_QT_DENIED")
            window = Bip39TrialWindow(executor)
            window.show()
            show = dict(opened, mnemonic_once="")
            window._on_ready("open", show)
            window._on_ready("activate", active)
            app.processEvents()
            if not window.isVisible() or not window.send.isEnabled() or window.receive.text() != opened["receive_code"]:
                raise Q06PlatformQualificationError("Q06_PLATFORM_QT_BINDING_DENIED")
            record["native_gui_checked"] = True
        from mnemonic import Mnemonic
        with Bip39Regtest12Keys(Mnemonic("english").to_mnemonic(bytes([1]*16)),
                                source=source, authorized_disposable=True) as other:
            destination = other.public_metadata()["receive_code"]
        atoms = min(50_000, funded["atoms"]//4)
        if atoms < 330 or funded["atoms"] < atoms + 1_000:
            raise Q06PlatformQualificationError("Q06_PLATFORM_INSUFFICIENT_TEST_FUNDS")
        step("PREPARE")
        draft = executor.request("prepare", destination, atoms, 1_000, timeout=240)
        if draft.code != destination or draft.atoms != atoms or len(draft.commitment) != 64:
            raise Q06PlatformQualificationError("Q06_PLATFORM_INTENT_DENIED")
        step("SIGN")
        signed = executor.request("sign", draft.commitment, timeout=240)
        if signed.commitment != draft.commitment:
            raise Q06PlatformQualificationError("Q06_PLATFORM_SIGN_DENIED")
        step("BROADCAST")
        txid = executor.request("broadcast", draft.commitment, timeout=240)
        if type(txid) is not str or re.fullmatch(r"[0-9a-f]{64}", txid) is None:
            raise Q06PlatformQualificationError("Q06_PLATFORM_BROADCAST_DENIED")
        step("CONFIRM")
        confirmed_tx = executor.request("confirm", txid, timeout=240)
        after = executor.request("snapshot", timeout=240)
        if (confirmed_tx["status"] != "Q06_REGTEST_EXACT_SEND_CONFIRMED"
                or confirmed_tx["txid"] != txid
                or after["height"] != confirmed_tx["height"]
                or after["history_count_shown"] < 2):
            raise Q06PlatformQualificationError("Q06_PLATFORM_CONFIRM_DENIED")
        if window is not None:
            window._on_ready("broadcast", txid)
            window._on_ready("snapshot", after)
            app.processEvents()
            if window.last_txid.text() != txid or not window.last_txid.isReadOnly():
                raise Q06PlatformQualificationError("Q06_PLATFORM_TXID_COPY_DENIED")
        record["signed_core_transaction_confirmed"] = True
        step("INDEPENDENT_SAME_CHAIN_RESCAN")
        rescan = executor.request("recovery_verify", phrase, timeout=240)
        if (rescan["status"] != "Q06_SAME_CHAIN_BIP39_HISTORY_RESCAN_PASS"
                or rescan["receive_code"] != opened["receive_code"]
                or rescan["confirmed_atoms"] != after["confirmed_atoms"]
                or rescan["history_count"] < 2
                or rescan["same_chain_only"] is not True
                or rescan["signed_reservations_restored"] is not False
                or rescan["signer_allowed"] is not False):
            raise Q06PlatformQualificationError("Q06_PLATFORM_RESCAN_DENIED")
        record["same_chain_mnemonic_history_recovered"] = True
        step("LOCK_REOPEN")
        executor.request("lock", timeout=120)
        again = executor.request("open", password, "reopen", "", timeout=120)
        current = executor.request("activate", timeout=240)
        if (again["receive_code"] != opened["receive_code"] or again["mnemonic_once"]
                or current["confirmed_atoms"] != after["confirmed_atoms"]
                or current["reservation_count"] != after["reservation_count"]
                or current["history_count_shown"] < 2):
            raise Q06PlatformQualificationError("Q06_PLATFORM_REOPEN_DENIED")
        record["same_owner_reopened"] = True
        step("POST_REOPEN_READONLY_TXID")
        found = executor.request("inspect_confirmed", txid, timeout=240)
        absent = executor.request("inspect_confirmed", "f"*64, timeout=240)
        if (found["status"] != "Q06_CONFIRMED_IN_VERIFIED_HISTORY"
                or found["write_attempted"] is not False
                or absent["status"] != "Q06_TX_NOT_IN_CONFIRMED_HISTORY"
                or absent["write_attempted"] is not False):
            raise Q06PlatformQualificationError("Q06_PLATFORM_TXID_RECONCILIATION_DENIED")
        record["post_reopen_txid_verified"] = True
        record["txid_sha256"] = sha256(txid.encode("ascii")).hexdigest()
        record["receive_code_sha256"] = sha256(opened["receive_code"].encode("ascii")).hexdigest()
        step("CLEAN_SHUTDOWN")
        executor.request("quit", timeout=120)
        if not executor.join(15) or not executor.closed:
            raise Q06PlatformQualificationError("Q06_PLATFORM_OWNER_STILL_LIVE")
        good = True
        record["status"] = "Q06_NATIVE_FROZEN_REAL_CORE_PASS"
        record["failure_stage"] = None
        return record
    except Exception:
        # No exception repr, files, paths, mnemonic or RPC content in receipt.
        return record
    finally:
        if window is not None:
            window._poll.stop()
            window.hide()
        if good:
            adapter.teardown()
        # Failed session, Core, native journal, chain and test witness are left
        # untouched for explicit forensic review. Never retry signed sends.
        phrase = None


def run(core, source, argv):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--confirm-disposable-regtest", action="store_true")
    parser.add_argument("--linux-developer-manifest")
    parser.add_argument("--linux-root-witness", type=Path)
    parser.add_argument("--headless", action="store_true")
    a = parser.parse_args(argv)
    record = qualify(
        core, source, a.root, a.receipt, confirmed=a.confirm_disposable_regtest,
        linux_manifest=a.linux_developer_manifest,
        linux_witness=a.linux_root_witness, headless=a.headless)
    with a.receipt.open("x", encoding="utf8") as output:
        json.dump(record, output, sort_keys=True, indent=2)
        output.write("\n")
    return 0 if record["status"] == "Q06_NATIVE_FROZEN_REAL_CORE_PASS" else 2
