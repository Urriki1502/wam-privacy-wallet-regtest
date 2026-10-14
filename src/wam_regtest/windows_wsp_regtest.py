"""Genuine Windows Core + pinned WSP-1 BIP352 receive proof, disposable REGTEST.

Reuses the EXACT source-qualified WSP Scanner, ScanAccount and transaction
constructor. This is a public fixture ONLY. No user keys, production signer,
operational send, mainnet, hosted scanner or mock RPC may enter this module.
"""
from __future__ import annotations

import re
from pathlib import Path

from .windows_core_regtest_smoke import _rpc

_HASH = re.compile(r"[0-9a-f]{64}\Z")


class WindowsWspError(ValueError):
    """Fixed redacted errors only; no keys, scripts, RPC replies or credentials."""


def _deny(code: str) -> None:
    raise WindowsWspError(code)


class WindowsWspCoreRpc:
    """Read-only scanner surface plus explicit known-public-fixture write calls."""

    def __init__(self, cli: Path, datadir: Path, port: int, env: dict) -> None:
        self.cli, self.datadir, self.port, self.env = cli, datadir, port, env
        self._genesis = None

    def _call(self, method: str, args: list[str]):
        # This adapter is used exclusively by disposable public-fixture E2E.
        # WSP Scanner receives only .call() with a strict read whitelist.
        permitted = {"getblockchaininfo", "getblockcount", "getbestblockhash",
                     "getblockhash", "getblock", "getconnectioncount",
                     "sendrawtransaction", "generatetoaddress"}
        if method not in permitted or type(args) is not list or not all(type(x) is str for x in args):
            _deny("WIN_WSP_RPC_METHOD_DENIED")
        if method == "sendrawtransaction" and (len(args) != 1
                or not 1 <= len(args[0]) <= 2_000_000
                or not all(c in "0123456789abcdef" for c in args[0])):
            _deny("WIN_WSP_PUBLIC_FIXTURE_TX_DENIED")
        if method == "generatetoaddress" and (len(args) != 2 or args[0] != "1"
                or not args[1].startswith("wamrt1q")):
            _deny("WIN_WSP_PUBLIC_FIXTURE_MINE_DENIED")
        return _rpc(self.cli, self.datadir, self.port, self.env, method, *args)

    def attest(self) -> None:
        from .wsp_live import REGTEST_GENESIS
        info = self._call("getblockchaininfo", [])
        if (type(info) is not dict or info.get("chain") != "regtest"
                or type(info.get("blocks")) is not int or not 101 <= info["blocks"] <= 102):
            _deny("WIN_WSP_CHAIN_DENIED")
        if self._call("getblockhash", ["0"]) != REGTEST_GENESIS:
            _deny("WIN_WSP_GENESIS_DENIED")
        if self._call("getconnectioncount", []) != 0:
            _deny("WIN_WSP_PEERS_DENIED")
        self._genesis = REGTEST_GENESIS

    def call(self, method: str, params=None):
        if (self._genesis is None or type(method) is not str
                or method not in {"getblockcount", "getbestblockhash", "getblockhash", "getblock"}
                or type(params) not in (list, type(None))):
            _deny("WIN_WSP_SCANNER_READ_ONLY_DENIED")
        args = [] if params is None else params
        if method in ("getblockcount", "getbestblockhash"):
            if args:
                _deny("WIN_WSP_SCANNER_PARAMS_DENIED")
        elif method == "getblockhash":
            if (len(args) != 1 or type(args[0]) is not int
                    or not 0 <= args[0] <= 100000):
                _deny("WIN_WSP_SCANNER_PARAMS_DENIED")
        else:
            if (len(args) != 2 or type(args[0]) is not str or not _HASH.fullmatch(args[0])
                    or type(args[1]) is not int or args[1] != 3):
                _deny("WIN_WSP_SCANNER_PARAMS_DENIED")
        response = self._call(method, [str(x) for x in args])
        if method in ("getblockhash", "getbestblockhash"):
            if type(response) is not str or not _HASH.fullmatch(response):
                _deny("WIN_WSP_SCANNER_RESPONSE_DENIED")
        if method == "getblockcount" and (type(response) is not int or not 0 <= response <= 102):
            _deny("WIN_WSP_SCANNER_RESPONSE_DENIED")
        if method == "getblock" and (type(response) is not dict
                                    or response.get("hash") != args[0]
                                    or type(response.get("tx")) is not list):
            _deny("WIN_WSP_SCANNER_RESPONSE_DENIED")
        return response


def prove_real_windows_wsp_receive(cli: Path, datadir: Path, port: int, env: dict,
                                   wsp_source: Path, mining_address: str) -> dict:
    """Actual Core block -> BIP352 broadcast -> Core confirmation -> SQLite.

    If ANY step fails, never claim that a payment was received. All funds are
    disposable public-regtest fixtures; source pin remains frozen.
    """
    from .wsp_live import (_pinned_source, _public_fixture_payment,
                           public_regtest_mining_address, PINNED_WSP_COMMIT)
    _pinned_source(wsp_source)
    if mining_address != public_regtest_mining_address(wsp_source):
        _deny("WIN_WSP_PUBLIC_MINING_ADDRESS_DENIED")
    from wam_sp.core import pub
    from wam_sp.keystore import ScanAccount
    from wam_sp.scanner import Scanner

    rpc = WindowsWspCoreRpc(cli, datadir, port, env)
    rpc.attest()
    if rpc.call("getblockcount") != 101:
        _deny("WIN_WSP_INITIAL_HEIGHT_DENIED")
    account = ScanAccount(0, 1, pub(2), birthday=1)
    if not account.payment_code().startswith("wamrtsp1"):
        _deny("WIN_WSP_ADDRESS_NAMESPACE_DENIED")
    database = datadir / "wsp-win-disposable-scan.sqlite"
    scanner = None
    try:
        scanner = Scanner(database, (account,))
        first = scanner.sync(rpc)
        if first.blocks != 101 or not scanner.ready or scanner.coins():
            _deny("WIN_WSP_INITIAL_SCAN_DENIED")
        tip = scanner.store.tip()
        scanner.close()
        scanner = Scanner(database, (account,))
        replay = scanner.sync(rpc)
        if replay.blocks != 0 or scanner.store.tip() != tip or scanner.coins():
            _deny("WIN_WSP_RESTART_DENIED")
        txid, atoms, height = _public_fixture_payment(rpc, account, mining_address)
        if height != 102:
            _deny("WIN_WSP_PAYMENT_HEIGHT_DENIED")
        second = scanner.sync(rpc)
        coins = scanner.coins()
        if (second.blocks != 1 or not scanner.ready or len(coins) != 1
                or coins[0]["txid"] != txid or coins[0]["atoms"] != atoms):
            _deny("WIN_WSP_BIP352_RECEIVE_DENIED")
        row = scanner.store.db.execute(
            "SELECT height,credit,debit FROM history WHERE txid=?", (txid,)
        ).fetchone()
        if row is None or row["height"] != 102 or row["credit"] != atoms or row["debit"] != 0:
            _deny("WIN_WSP_SQLITE_HISTORY_DENIED")
        scanner.close()
        scanner = Scanner(database, (account,))
        again = scanner.sync(rpc)
        found = scanner.coins()
        if again.blocks != 0 or len(found) != 1 or found[0]["atoms"] != atoms:
            _deny("WIN_WSP_RESTART_DOUBLE_CREDIT_DENIED")
        if rpc.call("getblockcount") != 102 or rpc._call("getconnectioncount", []) != 0:
            _deny("WIN_WSP_FINAL_CHAIN_DENIED")
        return {
            "status": "WIN64_REAL_CORE_WSP1_BIP352_CONFIRMED_RECEIVE_PASS",
            "wsp_source_commit": PINNED_WSP_COMMIT,
            "real_core": True, "real_onchain_payment": True,
            "scanner_sqlite_history": True, "scanner_restart_no_double_credit": True,
            "confirm_height": 102,
            "operational_wallet_signer_allowed": False,
            "mainnet_allowed": False, "synthetic_rpc": False,
        }
    except WindowsWspError:
        raise
    except Exception:
        _deny("WIN_WSP_REAL_RUNTIME_DENIED")
    finally:
        if scanner is not None:
            scanner.close()
