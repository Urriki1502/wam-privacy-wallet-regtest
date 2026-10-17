"""Real WAM Core v0.1.12 Linux + pinned WSP BIP352 public-fixture receive.

Strictly test-only: Core/CLI, datadir, fixture scalar 31, scanner SQLite and
broadcast are isolated from operational Fusion WalletSession/signing.
"""
from __future__ import annotations

import re
from pathlib import Path

from .wsp_live import (
    _pinned_source, _public_fixture_payment, PINNED_WSP_COMMIT,
    REGTEST_GENESIS, public_regtest_mining_address,
)

_HASH = re.compile(r"[0-9a-f]{64}\Z")
_READER = frozenset(("getblockcount", "getbestblockhash", "getblockhash", "getblock"))


class CandidateWspDenied(ValueError):
    """Only static redacted errors; never reveal raw WSP response or keys."""


def _deny(code: str):
    raise CandidateWspDenied(code)


class CandidateLinuxWspRpc:
    """Read-only scanner adapter; two write methods ONLY for known public fixture."""

    def __init__(self, core_rpc):
        self._rpc = core_rpc
        self._genesis = None

    def _call(self, method: str, args: list[str]):
        if (type(method) is not str or method not in (
                "getblockchaininfo", "getblockcount", "getbestblockhash",
                "getblockhash", "getblock", "getconnectioncount",
                "sendrawtransaction", "generatetoaddress")
                or type(args) is not list or not all(type(x) is str for x in args)):
            _deny("V012_WSP_PUBLIC_FIXTURE_METHOD_DENIED")
        if method == "sendrawtransaction":
            if (len(args) != 1 or not 1 <= len(args[0]) <= 2_000_000
                    or re.fullmatch(r"[0-9a-f]+", args[0]) is None):
                _deny("V012_WSP_PUBLIC_FIXTURE_TX_DENIED")
        elif method == "generatetoaddress":
            if (len(args) != 2 or args[0] != "1" or
                    not args[1].startswith("wamrt1q") or len(args[1]) > 120):
                _deny("V012_WSP_PUBLIC_FIXTURE_MINE_DENIED")
        elif method in ("getblockcount", "getbestblockhash", "getconnectioncount", "getblockchaininfo"):
            if args: _deny("V012_WSP_READ_PARAMS_DENIED")
        elif method == "getblockhash":
            if len(args) != 1 or not args[0].isdigit() or not 0 <= int(args[0]) <= 102:
                _deny("V012_WSP_READ_PARAMS_DENIED")
        elif method == "getblock":
            if (len(args) != 2 or not _HASH.fullmatch(args[0])
                    or args[1] not in ("2", "3")):
                _deny("V012_WSP_READ_PARAMS_DENIED")
        return self._rpc(method, *args)

    def attest(self):
        info = self._call("getblockchaininfo", [])
        if (type(info) is not dict or info.get("chain") != "regtest"
                or type(info.get("blocks")) is not int
                or not 101 <= info["blocks"] <= 102):
            _deny("V012_WSP_REGTEST_DENIED")
        if self._call("getblockhash", ["0"]) != REGTEST_GENESIS:
            _deny("V012_WSP_GENESIS_DENIED")
        if self._call("getconnectioncount", []) != 0:
            _deny("V012_WSP_EXTERNAL_PEERS_DENIED")
        self._genesis = REGTEST_GENESIS

    def call(self, method: str, params=None):
        if (self._genesis != REGTEST_GENESIS or type(method) is not str
                or method not in _READER or type(params) not in (list, type(None))):
            _deny("V012_WSP_SCANNER_READ_ONLY_DENIED")
        args = [] if params is None else params
        if method in ("getblockcount", "getbestblockhash"):
            if args: _deny("V012_WSP_SCANNER_PARAMS_DENIED")
        elif method == "getblockhash":
            if (len(args) != 1 or type(args[0]) is not int
                    or not 0 <= args[0] <= 102):
                _deny("V012_WSP_SCANNER_PARAMS_DENIED")
        elif (len(args) != 2 or type(args[0]) is not str or
              not _HASH.fullmatch(args[0]) or type(args[1]) is not int or args[1] != 3):
            _deny("V012_WSP_SCANNER_PARAMS_DENIED")
        raw = self._call(method, [str(x) for x in args])
        if method in ("getblockhash", "getbestblockhash"):
            if type(raw) is not str or not _HASH.fullmatch(raw):
                _deny("V012_WSP_SCANNER_RESULT_DENIED")
        elif method == "getblockcount":
            if type(raw) is not int or not 0 <= raw <= 102:
                _deny("V012_WSP_SCANNER_RESULT_DENIED")
        elif (type(raw) is not dict or raw.get("hash") != args[0]
              or type(raw.get("tx")) is not list):
            _deny("V012_WSP_SCANNER_RESULT_DENIED")
        return raw


def prove_public_receive(rpc_call, datadir: Path, wsp_source: Path, mining_address: str):
    """Genuine public-fixture raw transaction -> Core -> BIP352 SQLite receive."""
    if (type(datadir) is not type(Path()) or not datadir.is_absolute()
            or datadir.is_symlink() or type(mining_address) is not str):
        _deny("V012_WSP_DIRECTORY_DENIED")
    _pinned_source(wsp_source)
    if mining_address != public_regtest_mining_address(wsp_source):
        _deny("V012_WSP_FIXTURE_ADDRESS_DENIED")
    from wam_sp.core import pub
    from wam_sp.keystore import ScanAccount
    from wam_sp.scanner import Scanner
    from wam_sp.watcher import GENESIS

    if GENESIS != REGTEST_GENESIS:
        _deny("V012_WSP_SOURCE_GENESIS_DENIED")
    rpc = CandidateLinuxWspRpc(rpc_call)
    rpc.attest()
    if rpc.call("getblockcount") != 101:
        _deny("V012_WSP_INITIAL_HEIGHT_DENIED")
    account = ScanAccount(0, 1, pub(2), birthday=1)
    if not account.payment_code().startswith("wamrtsp1"):
        _deny("V012_WSP_BIP352_NAMESPACE_DENIED")
    database = datadir / "wsp-v012-test-only.sqlite"
    scanner = None
    try:
        scanner = Scanner(database, (account,))
        initial = scanner.sync(rpc)
        if initial.blocks != 101 or not scanner.ready or scanner.coins():
            _deny("V012_WSP_INITIAL_SCAN_DENIED")
        tip = scanner.store.tip()
        scanner.close()
        scanner = Scanner(database, (account,))
        replay = scanner.sync(rpc)
        if replay.blocks != 0 or scanner.store.tip() != tip or scanner.coins():
            _deny("V012_WSP_RESTART_DENIED")
        txid, atoms, height = _public_fixture_payment(
            rpc, account, mining_address)
        if height != 102:
            _deny("V012_WSP_PAYMENT_HEIGHT_DENIED")
        second = scanner.sync(rpc)
        coins = scanner.coins()
        if (second.blocks != 1 or not scanner.ready or len(coins) != 1
                or coins[0]["txid"] != txid or coins[0]["atoms"] != atoms):
            _deny("V012_WSP_CONFIRMED_BIP352_RECEIVE_DENIED")
        row = scanner.store.db.execute(
            "SELECT height,credit,debit FROM history WHERE txid=?", (txid,)).fetchone()
        if (row is None or row["height"] != 102
                or row["credit"] != atoms or row["debit"] != 0):
            _deny("V012_WSP_SQLITE_HISTORY_DENIED")
        scanner.close()
        scanner = Scanner(database, (account,))
        final = scanner.sync(rpc)
        after = scanner.coins()
        if (final.blocks != 0 or len(after) != 1
                or after[0]["txid"] != txid or after[0]["atoms"] != atoms):
            _deny("V012_WSP_DOUBLE_CREDIT_RESTART_DENIED")
        if rpc._call("getconnectioncount", []) != 0:
            _deny("V012_WSP_PEERS_CHANGED_DENIED")
        return {
            "status": "V012_LINUX_REAL_WSP1_BIP352_CONFIRMED_RECEIVE_COMPONENT_PASS",
            "wsp_source_commit": PINNED_WSP_COMMIT,
            "real_signed_v012_core": True,
            "actual_core_consensus_broadcast_confirmed": True,
            "real_bip352_receive_credited": True,
            "received_atoms": atoms,
            "confirmation_height": height,
            "native_scanner_blocks": initial.blocks,
            "scan_after_payment_blocks": second.blocks,
            "sqlite_restart_no_double_credit": True,
            "source_qualified": True,
            "core_genesis": REGTEST_GENESIS,
            "zero_external_peers": True,
            "public_known_scalar_only": True,
            "operational_signing_authorized": False,
            "fusion_v012_activated": False,
            "wsp_gui_walletsession_v012_qualified": False,
            "mainnet_allowed": False,
        }
    except CandidateWspDenied:
        raise
    except Exception:
        _deny("V012_WSP_REAL_RUNTIME_DENIED")
    finally:
        if scanner is not None: scanner.close()
