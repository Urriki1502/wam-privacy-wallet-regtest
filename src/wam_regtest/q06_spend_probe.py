"""Packaged macOS ARM64 Q06 owned BIP39 real-Core spend/restore qualification.

One disposable signed-Core REGTEST chain; never production, mainnet or user
keys. Human review remains a separate product gate. Nothing in this probe
should be interpreted as independent security acceptance.
"""
from hashlib import sha256
import json
from pathlib import Path
import platform
import secrets
import sys

from . import custody
from .bip39_owner_backend import Bip39ReadOnlyBackend
from .wallet_executor import WalletExecutor
from .wsp_live import _pinned_source


def qualify(core, source):
    if sys.platform != "darwin" or platform.machine().lower() != "arm64":
        raise ValueError("Q06_SPEND_MACOS_NATIVE_REQUIRED")
    from .core import verified_core_paths
    verified_core_paths(core)
    _pinned_source(source)
    from .q05_platforms import DarwinArm64Adapter
    from .desktop import qt_application
    from .bip39_fusion_gui import Bip39FusionWindow
    from .bip39_12 import Bip39Regtest12Keys
    from mnemonic import Mnemonic
    app = qt_application()
    if app.platformName() != "cocoa":
        raise ValueError("Q06_SPEND_NATIVE_COCOA_REQUIRED")
    adapter = DarwinArm64Adapter()
    adapter.enforce_host()

    data = {
        "status": "FAIL",
        "network": "regtest",
        "mainnet_allowed": False,
        "signed_core": True,
        "q06_bip39_spend_confirmed": False,
        "q06_bip39_same_owner_reopen_reserved": False,
        "q06_bip39_same_chain_seed_history_recovery": False,
        "q06_post_reopen_txid_readonly_reconciliation": False,
        "q06_bip39_fresh_mnemonic_full_history_recovery": False,
    }
    def stage(message):
        print("MACOS_Q06_SPEND_STAGE=" + message, flush=True)

    with custody.private_temporary_directory(prefix="q06-spend-frozen-") as temp:
        root = Path(temp).resolve() / ("wam-fusion-core-" + secrets.token_hex(8))
        custody.create_directory(root)
        password = b"public-disposable-q06-signed-core-spend-only"
        executor = WalletExecutor(lambda: Bip39ReadOnlyBackend(
            root, core, source, _anchor_factory=adapter.make_anchor))
        window = None
        good = False
        try:
            stage("CREATE_START")
            created = executor.request("open", password, "create", "", timeout=120)
            phrase = created["mnemonic_once"]
            if (len(phrase.split()) != 12 or
                    not created["receive_code"].startswith("wamrtsp1")):
                raise ValueError("Q06_SPEND_CREATE_IDENTITY_DENIED")
            stage("CREATE_PASS")
            stage("FUND_START")
            funded = executor.request("mine", timeout=240)
            before = executor.request("snapshot", timeout=120)
            if (before["confirmed_atoms"] != funded["atoms"]
                    or before["available_atoms"] != funded["atoms"]):
                raise ValueError("Q06_SPEND_RECEIVE_DENIED")
            stage("RECEIVE_FUNDED_PASS")
            stage("ACTIVATE_CHECKPOINT_START")
            active = executor.request("activate", timeout=240)
            if (active["signer_allowed"] is not True
                    or active["broadcast_allowed"] is not True
                    or active["mainnet_allowed"] is not False
                    or active["confirmed_atoms"] != funded["atoms"]
                    or active["receive_code"] != created["receive_code"]):
                raise ValueError("Q06_SPEND_NATIVE_ACTIVATION_DENIED")
            stage("ACTIVATE_CHECKPOINT_PASS")
            window = Bip39FusionWindow(executor)
            window.show()
            sanitized = dict(created)
            sanitized["mnemonic_once"] = ""
            window._on_ready("open", sanitized)
            window._on_ready("activate", active)
            app.processEvents()
            if (not window.isVisible() or not window.send.isEnabled()
                    or not window.receive.text() == created["receive_code"]):
                raise ValueError("Q06_SPEND_QT_BINDING_DENIED")
            stage("COCOA_SEND_BUTTON_BOUND_PASS")

            with Bip39Regtest12Keys(
                    Mnemonic("english").to_mnemonic(bytes([1] * 16)),
                    source=source, authorized_disposable=True) as payee:
                destination = payee.public_metadata()["receive_code"]
            atoms = min(50_000, funded["atoms"] // 4)
            if atoms < 330 or funded["atoms"] < atoms + 1000:
                raise ValueError("Q06_SPEND_FUNDS_NOT_SPENDABLE")
            stage("PREPARE_START")
            prepared = executor.request("prepare", destination, atoms, 1000, timeout=240)
            if (prepared.code != destination or prepared.atoms != atoms
                    or prepared.fee != 1000 or len(prepared.commitment) != 64):
                raise ValueError("Q06_SPEND_INTENT_DENIED")
            stage("PREPARE_ANCHORED_PASS")
            signed = executor.request("sign", prepared.commitment, timeout=240)
            if signed.commitment != prepared.commitment:
                raise ValueError("Q06_SPEND_SIGNED_INTENT_DENIED")
            stage("SIGNED_ANCHORED_PASS")
            broadcast = executor.request("broadcast", prepared.commitment, timeout=240)
            if not isinstance(broadcast, str) or len(broadcast) != 64:
                raise ValueError("Q06_SPEND_TXID_DENIED")
            stage("BROADCAST_ANCHORED_PASS")
            # Exercise the same exact-tx confirmation action exposed by
            # the human GUI, not a CI-only alternate mining path.
            confirmed = executor.request("confirm", broadcast, timeout=120)
            if (confirmed["status"] != "Q06_REGTEST_EXACT_SEND_CONFIRMED"
                    or confirmed["txid"] != broadcast):
                raise ValueError("Q06_SPEND_CONFIRM_DENIED")
            after = executor.request("snapshot", timeout=240)
            if (after["height"] != confirmed["height"]
                    or after["history_count_shown"] < 2
                    or after["receive_code"] != created["receive_code"]):
                raise ValueError("Q06_SPEND_HISTORY_DENIED")
            stage("ONCHAIN_CONFIRMATION_PASS")
            # Exercise actual native Qt signal handling with the real Core TXID.
            # A subsequent automatic snapshot must not hide the copyable ID.
            window._on_ready("broadcast", broadcast)
            window._on_ready("snapshot", after)
            app.processEvents()
            from .wallet_read import format_wam
            if (window.navigation.count()!=6
                    or window.overview.balance_value.text()
                       !=format_wam(after["confirmed_atoms"],grouped=True)+" WAM"
                    or window.receive_page.code!=opened["receive_code"]
                    or window.history_page.table.rowCount()<2):
                raise ValueError("Q06_FROZEN_FUSION_GUI_AFTER_SEND_DENIED")
            if (not window.last_txid.isReadOnly()
                    or window.last_txid.text() != broadcast):
                raise ValueError("Q06_GUI_TXID_PERSISTENT_COPY_DENIED")
            stage("COCOA_BROADCAST_TXID_COPYABLE_PASS")
            # Rebuild a NEW scanner from the 12 words against THIS same
            # attested Core. Do not adopt its checkpoint/signing authority.
            stage("SAME_CHAIN_MNEMONIC_RESCAN_START")
            recovery = executor.request("recovery_verify", phrase, timeout=240)
            if (recovery["status"] != "Q06_SAME_CHAIN_BIP39_HISTORY_RESCAN_PASS"
                    or recovery["history_count"] < 2
                    or recovery["confirmed_atoms"] != after["confirmed_atoms"]
                    or recovery["receive_code"] != created["receive_code"]
                    or recovery["same_chain_only"] is not True
                    or recovery["signer_allowed"] is not False
                    or recovery["signed_reservations_restored"] is not False):
                raise ValueError("Q06_SPEND_SAME_CHAIN_RECOVERY_DENIED")
            data["q06_bip39_same_chain_seed_history_recovery"] = True
            stage("SAME_CHAIN_MNEMONIC_RESCAN_PASS")
            data["q06_bip39_spend_confirmed"] = True
            data["txid_sha256"] = sha256(broadcast.encode("ascii")).hexdigest()
            data["receive_sha256"] = sha256(
                created["receive_code"].encode("ascii")).hexdigest()

            executor.request("lock", timeout=90)
            stage("LOCKED_ORIGINAL_PASS")
            reopened = executor.request("open", password, "reopen", "", timeout=120)
            if (reopened["receive_code"] != created["receive_code"]
                    or reopened["mnemonic_once"]):
                raise ValueError("Q06_SPEND_REOPEN_IDENTITY_DENIED")
            recovered = executor.request("activate", timeout=240)
            if (recovered["height"] != after["height"]
                    or recovered["confirmed_atoms"] != after["confirmed_atoms"]
                    or recovered["reservation_count"] != after["reservation_count"]
                    or recovered["history_count_shown"] < 2
                    or recovered["receive_code"] != created["receive_code"]):
                raise ValueError("Q06_SPEND_REOPEN_STATE_DENIED")
            data["q06_bip39_same_owner_reopen_reserved"] = True
            stage("REOPEN_ANCHORED_RESERVATION_PASS")
            stage("POST_REOPEN_TXID_INSPECTION_START")
            resolved=executor.request("inspect_confirmed",broadcast,timeout=240)
            unknown=executor.request("inspect_confirmed","f"*64,timeout=240)
            if (resolved["status"]!="Q06_CONFIRMED_IN_VERIFIED_HISTORY"
                    or resolved["txid"]!=broadcast
                    or resolved["write_attempted"] is not False
                    or resolved["broadcast_allowed"] is not False
                    or unknown["status"]!="Q06_TX_NOT_IN_CONFIRMED_HISTORY"
                    or unknown["write_attempted"] is not False):
                raise ValueError("Q06_POST_REOPEN_TXID_INSPECTION_DENIED")
            data["q06_post_reopen_txid_readonly_reconciliation"]=True
            stage("POST_REOPEN_TXID_INSPECTION_PASS")
            executor.request("quit", timeout=90)
            if not executor.join(15) or not executor.closed:
                raise ValueError("Q06_SPEND_OWNED_SHUTDOWN_DENIED")
            stage("CLEAN_CORE_SHUTDOWN_PASS")
            data["status"] = "Q06_NATIVE_BIP39_SEND_CONFIRM_REOPEN_PASS"
            good = True
            return data
        finally:
            if window is not None:
                window._poll.stop()
                window.hide()
                if good:
                    from PySide6.QtCore import QCoreApplication, QEvent
                    window.deleteLater()
                    QCoreApplication.sendPostedEvents(
                        None, QEvent.Type.DeferredDelete)
                    app.processEvents()
            # Preserve the exact Core/chain/native state on an uncertain
            # failure. No force-kill, orphan sweep, automatic replay or retry.
            if not good and not executor.busy and not executor.closed:
                try:
                    executor.request("quit", timeout=45)
                    executor.join(15)
                except Exception:
                    stage("UNCERTAIN_OWNER_PRESERVED")
            phrase = None


def run(core, source):
    try:
        receipt = qualify(core, source)
        with Path("q06-frozen-spend-evidence.json").open("x") as output:
            json.dump(receipt, output, sort_keys=True, indent=2)
            output.write("\n")
        if (receipt["status"] != "Q06_NATIVE_BIP39_SEND_CONFIRM_REOPEN_PASS"
                or receipt["q06_bip39_spend_confirmed"] is not True
                or receipt["q06_bip39_same_owner_reopen_reserved"] is not True):
            raise ValueError("Q06_SPEND_NOT_QUALIFIED")
        print("MACOS_Q06_NATIVE_BIP39_SEND_CONFIRM_REOPEN_PASS", flush=True)
        return 0
    except Exception:
        print("MACOS_Q06_NATIVE_BIP39_SEND_CONFIRM_REOPEN_DENIED", flush=True)
        return 2
