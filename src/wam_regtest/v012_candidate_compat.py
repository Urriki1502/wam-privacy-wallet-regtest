"""Read-only v0.1.12 *candidate* RPC compatibility: no wallet/runtime activation.

The pinned v0.1.11 application RPC profile must NOT be relaxed by this test.
Measured, independently signed Linux v0.1.12 binary and release identities are
accepted solely as the input to a disposable CI component probe. They do not
authorize Fusion WalletSession/GUI/WSP/signing/real funds or other OS builds.
"""
from __future__ import annotations

from decimal import Decimal
import json
import re

from .json_rpc import MAX_REPLY, RpcError, SUPPORTED_RPC, _unique
from .wsp_live import REGTEST_GENESIS

CANDIDATE_VERSION = (112, "/WAM:0.1.12/", 70016)
CANDIDATE_LINUX_ARCHIVE_SHA = "4bc22c1b315deb214596b20bbaf42f6845f58d3e52c490362b706000334a24d1"
CANDIDATE_LINUX_WAMD_SHA = "9d13b329f451486930a3cf799b360237bcc7e858e94a964f817df520428374db"
CANDIDATE_LINUX_CLI_SHA = "455d85aa1ce35f70c71da6947a79b549f33c4116168ff7ecdc41b067a3fbe907"
CANDIDATE_SIGNER = "4BD4A8D3AFD43F5CBCB500E23798462FE00ADBA4"
_HEX = re.compile(r"[0-9a-f]{64}\Z")


class Candidate012Denied(ValueError):
    """Static, redacted component-only denial; no untrusted field leakage."""


def exact_signed_linux_candidate(*, signed_archive, signer, archive_sha,
                                 node_sha, cli_sha, process_is_owned,
                                 chain, genesis, peers) -> None:
    """All properties required, but a success is NOT installation consent."""
    if not (signed_archive is True and type(signer) is str
            and signer == CANDIDATE_SIGNER
            and type(archive_sha) is str and archive_sha == CANDIDATE_LINUX_ARCHIVE_SHA
            and type(node_sha) is str and node_sha == CANDIDATE_LINUX_WAMD_SHA
            and type(cli_sha) is str and cli_sha == CANDIDATE_LINUX_CLI_SHA
            and process_is_owned is True and chain == "regtest"
            and type(genesis) is str and genesis == REGTEST_GENESIS
            and type(peers) is int and peers == 0):
        raise Candidate012Denied("V012_CANDIDATE_LINUX_IDENTITY_DENIED")


def candidate_network_reply(raw: bytes, request_id: int) -> dict:
    """No application global version override; parse only test-owned candidate."""
    if type(request_id) is not int or not 1 <= request_id <= 1000:
        raise Candidate012Denied("V012_CANDIDATE_REPLY_DENIED")
    try:
        if type(raw) is not bytes or not 1 <= len(raw) <= MAX_REPLY:
            raise ValueError
        packet = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                            parse_float=Decimal,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if (type(packet) is not dict or set(packet) != {"id", "result", "error"}
                or type(packet["id"]) is not int or packet["id"] != request_id
                or packet["error"] is not None):
            raise ValueError
        info = packet["result"]
        if (type(info) is not dict or type(info.get("version")) is not int
                or type(info.get("subversion")) is not str
                or type(info.get("protocolversion")) is not int
                or (info["version"], info["subversion"],
                    info["protocolversion"]) != CANDIDATE_VERSION):
            raise ValueError
        # Core may expose extra informational fields; never emit them.
        return {key: info[key] for key in ("version", "subversion", "protocolversion")}
    except (ValueError, UnicodeError, TypeError, KeyError, RecursionError, RpcError):
        raise Candidate012Denied("V012_CANDIDATE_REPLY_DENIED") from None


def candidate_scope_status() -> dict:
    if SUPPORTED_RPC != (111, "/WAM:0.1.11/", 70016):
        raise Candidate012Denied("V012_V011_RUNTIME_PIN_CHANGED")
    return {
        "candidate_version": "v0.1.12",
        "test_only": True,
        "v011_application_pin_unchanged": True,
        "linux_candidate_rpc_shape_checked": False,
        "fusion_v012_activated": False,
        "macos_v012_qualified": False,
        "windows_v012_qualified": False,
        "wsp_gui_signing_qualified": False,
        "user_core_install_authorized": False,
        "mainnet_allowed": False,
    }
