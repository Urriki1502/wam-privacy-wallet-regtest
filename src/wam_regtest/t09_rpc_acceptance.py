"""T-09 exact REAL-Core RPC evidence gate, shared by native/frozen executions.

Pure validator of results from already executed native WAM Core/WSP probes.
No mock response, Core startup, network request, signer or credential handling.
Missing data fails closed; it cannot promote PHYSICAL or DEV acceptance.
"""
from __future__ import annotations

class T09EvidenceError(ValueError):
    pass


def require_direct_rpc_evidence(*, platform, height, owned, wsp, wallet,
                                contention=False, operational=False):
    """Validate the current executable's genuine Core/WSP execution receipts.

    Called INSIDE the genuine Core acceptance path, not used to mint evidence
    from unrelated baseline runs. A boolean status or a CI green badge alone
    is insufficient. No raw private paths, auth headers, keys or tx blobs.
    """
    if (platform not in ("macos-arm64","windows-x64","linux-x86_64")
            or type(height) is not int or not 101<=height<=1_000_000
            or type(owned) is not dict or type(wsp) is not dict
            or type(contention) is not bool or type(operational) is not bool):
        raise T09EvidenceError("T09_NATIVE_EVIDENCE_REQUIRED")
    identity=owned.get("rpc_compatibility_profile")
    if (type(identity) is not dict
            or (identity.get("version"),identity.get("subversion"),
                identity.get("protocolversion"))!=(111,"/WAM:0.1.11/",70016)
            or owned.get("status")!="REAL_CORE_OWNED_HTTP_READ_COMPONENT_PASS"
            or owned.get("height")!=height
            or owned.get("repeated_authenticated_reads")!=8
            or any(owned.get(k) is not True for k in (
                "t03_live_height_tip_parity_on_owned_core",
                "t04_post_launch_pair_stable_during_core_hash",
                "process_image_and_established_socket_before_auth",
                "wrong_process_endpoint_denied_before_any_http_bytes",
                "genuine_core_invalid_auth_denied",
                "write_denied_before_wire"))
            or owned.get("synthetic_core_rpc") is not False
            or owned.get("mainnet_allowed") is not False):
        raise T09EvidenceError("T09_NATIVE_RPC_TRUST_DENIED")
    if (wsp.get("scanner_transport")!="owned-http"
            or wsp.get("cli_and_rehash_forbidden_during_scan") is not True
            or wsp.get("real_core_rpc") is not True
            or wsp.get("synthetic_rpc") is not False
            or wsp.get("wsp_bip352_payment_confirmed") is not True
            or wsp.get("regtest_fixture_broadcast_confirmed") is not True):
        raise T09EvidenceError("T09_NATIVE_WSP_INTEGRATION_DENIED")
    if contention:
        busy=owned.get("node_busy_read_component")
        idle=owned.get("idle_read_component")
        if (type(busy) is not dict
                or busy.get("status")!="REAL_CORE_BUSY_READ_RECOVERY_PASS"
                or busy.get("read_attempt_limit")!=3
                or busy.get("observed_busy_attempts")!=3
                or type(busy.get("queue_response_503")) is not int
                or busy["queue_response_503"]<1
                or busy.get("recovered_without_daemon_restart") is not True
                or busy.get("no_synthetic_rpc") is not True
                or type(idle) is not dict
                or idle.get("status")!="REAL_CORE_IDLE_READ_RECONNECT_PASS"
                or idle.get("old_socket_closed_before_request") is not True
                or idle.get("request_replayed") is not False):
            raise T09EvidenceError("T09_NATIVE_BUSY_OR_IDLE_DENIED")
    if operational:
        if (type(wallet) is not dict
                or wallet.get("real_core_rpc") is not True
                or wallet.get("synthetic_rpc") is not False
                or wallet.get("mainnet_allowed") is not False):
            raise T09EvidenceError("T09_NATIVE_WALLET_DENIED")
        if platform in ("macos-arm64","windows-x64"):
            proof=wallet.get("operational_snapshot_http")
            if (wallet.get("native_qt_prepare_sign_broadcast") is not True
                    or wallet.get("real_core_lost_broadcast_reply_lock_retained") is not True
                    or type(proof) is not dict
                    or proof.get("transport")!="owned-http"
                    or proof.get("cli_and_rehash_forbidden") is not True):
                raise T09EvidenceError("T09_NATIVE_WALLET_RPC_DENIED")
        elif (wallet.get("status")=="REAL_LINUX_CORE_ROOT_WITNESS_HEADLESS_WALLET_E2E_PASS"
                and wallet.get("lost_actual_broadcast_reply_retained") is not True):
            raise T09EvidenceError("T09_LINUX_UNCERTAIN_BROADCAST_DENIED")
        elif (wallet.get("status")=="REAL_LINUX_CORE_ROOT_WITNESS_NATIVE_QT_WALLET_E2E_PASS"
                and wallet.get("separate_native_sign_broadcast_approvals") is not True):
            raise T09EvidenceError("T09_LINUX_GUI_APPROVAL_DENIED")
    return {
        "status":"T09_REAL_CORE_DIRECT_RPC_COMPONENT_PASS",
        "platform":platform,
        "height":height,
        "rpc_profile":"WAM-v0.1.11/70016",
        "native_core_authenticated":True,
        "no_per_read_cli_or_binary_rehash":True,
        "foreign_endpoint_pre_auth_denied":True,
        "genuine_invalid_auth_denied":True,
        "read_rpc_write_denied":True,
        "real_bip352_receive_and_sqlite":True,
        "genuine_busy_idle_recovery_checked":contention,
        "operational_wallet_checked":operational,
        "frozen_entrypoint":False,  # overwritten only by the actual caller
        "physical_accepted":False,
        "dev_reviewed":False,
        "synthetic_rpc":False,
        "mainnet_allowed":False,
    }
