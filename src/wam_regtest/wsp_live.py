"""Pinned, real WSP-1 Scanner.sync against a LIVE signed WAM Core REGTEST.

No synthetic RPC and no mainnet. This scanner connects to the already-running
official v0.1.11 node via the exact signed wam-cli executable and a private
fresh datadir. The initial M1 proof scans actual mined blocks but does NOT
yet claim a BIP352 payment occurred. A positive receive/coins E2E is a
separate acceptance gate, never inferred from an empty-chain scan.
"""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import re
import stat
import subprocess

PINNED_WSP_COMMIT = "ac55f13423620252bdbf848c7e8a280c3b84721e"
REGTEST_GENESIS = "b88f3d262f285e38e184f50bf3eea1c8e615486ae67d3d9eaf0976fbd6d3d30d"
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_READS = frozenset(("getblockcount", "getbestblockhash", "getblockhash", "getblock"))
_MINE_LIMIT = 101


class RealWspScanError(ValueError):
    """A fixed non-secret failure status; never include node output or paths."""


def _pinned_source(root: Path) -> None:
    if type(root) is not type(Path()) or not root.is_absolute():
        raise RealWspScanError("WSP_SOURCE_DIRECTORY_DENIED")
    try:
        sha = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=6, check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        raise RealWspScanError("WSP_SOURCE_PIN_DENIED") from None
    if sha != PINNED_WSP_COMMIT or not (root / "src/wam_sp/scanner.py").is_file():
        raise RealWspScanError("WSP_SOURCE_PIN_DENIED")
    # Installed native WSP must point to exactly this checkout; never
    # silently use a PyPI package, a different editable path or a fake class.
    found = importlib.util.find_spec("wam_sp")
    if found is None or not found.origin:
        raise RealWspScanError("WSP_SOURCE_IMPORT_DENIED")
    try:
        if Path(found.origin).resolve() != (root / "src/wam_sp/__init__.py").resolve():
            raise RealWspScanError("WSP_SOURCE_IMPORT_DENIED")
    except OSError:
        raise RealWspScanError("WSP_SOURCE_IMPORT_DENIED") from None


class LiveCoreReadOnlyCli:
    """Strict method surface; actual signed wam-cli -> actual localhost wamd."""

    __slots__ = ("_binary", "_datadir", "_genesis")

    def __init__(self, binary: Path, datadir: Path) -> None:
        if (type(binary) is not type(Path()) or type(datadir) is not type(Path())
                or not binary.is_absolute() or not datadir.is_absolute()):
            raise RealWspScanError("WSP_LIVE_CLI_SCOPE_DENIED")
        self._binary = binary
        self._datadir = datadir
        self._genesis = None

    def _call(self, method: str, args: list[str]) -> object:
        # Use only the exact signed official CLI verified by parent Core smoke.
        from .core import _read_cli, CoreSmokeError
        try:
            return _read_cli(
                [str(self._binary), f"-datadir={self._datadir}", method, *args],
                timeout=10,
            )
        except CoreSmokeError:
            raise RealWspScanError("WSP_LIVE_RPC_DENIED") from None

    def attest(self) -> None:
        info = self._call("getblockchaininfo", [])
        if (type(info) is not dict or info.get("chain") != "regtest"
                or type(info.get("blocks")) is not int
                or not 0 <= info["blocks"] <= 1_000_000):
            raise RealWspScanError("WSP_LIVE_CHAIN_DENIED")
        genesis = self._call("getblockhash", ["0"])
        if genesis != REGTEST_GENESIS:
            raise RealWspScanError("WSP_LIVE_GENESIS_DENIED")
        peers = self._call("getconnectioncount", [])
        if type(peers) is not int or peers != 0:
            raise RealWspScanError("WSP_LIVE_PEERS_DENIED")
        self._genesis = genesis

    def call(self, method: str, params: list | None = None) -> object:
        if (self._genesis != REGTEST_GENESIS or type(method) is not str
                or method not in _READS or type(params) not in (list, type(None))):
            raise RealWspScanError("WSP_LIVE_METHOD_DENIED")
        args = [] if params is None else params
        if method in ("getblockcount", "getbestblockhash"):
            if args:
                raise RealWspScanError("WSP_LIVE_PARAMS_DENIED")
        elif method == "getblockhash":
            if (len(args) != 1 or type(args[0]) is not int
                    or not 0 <= args[0] <= 1_000_000):
                raise RealWspScanError("WSP_LIVE_PARAMS_DENIED")
        else:
            if (len(args) != 2 or type(args[0]) is not str
                    or not _HASH.fullmatch(args[0])
                    or type(args[1]) is not int or args[1] != 3):
                raise RealWspScanError("WSP_LIVE_PARAMS_DENIED")
        reply = self._call(method, [str(a) for a in args])
        if method in ("getbestblockhash", "getblockhash"):
            if type(reply) is not str or not _HASH.fullmatch(reply):
                raise RealWspScanError("WSP_LIVE_REPLY_DENIED")
        elif method == "getblockcount":
            if type(reply) is not int or not 0 <= reply <= 1_000_000:
                raise RealWspScanError("WSP_LIVE_REPLY_DENIED")
        elif (type(reply) is not dict or reply.get("hash") != args[0]
              or type(reply.get("tx")) is not list):
            raise RealWspScanError("WSP_LIVE_BLOCK_SHAPE_DENIED")
        return reply


def scan_actual_core_blocks(cli: Path, datadir: Path, source_root: Path,
                            *, expected_height: int) -> dict[str, object]:
    """Real WSP scanner -> 101 actual Core blocks -> SQLite restart/replay proof.

    Fixture deliberately contains only a publicly known scan key. It has zero
    funds and must not be used to receive any real value.
    """
    if (type(expected_height) is not int or expected_height != _MINE_LIMIT
            or type(datadir) is not type(Path()) or not datadir.is_absolute()
            or datadir.is_symlink()
            or stat.S_IMODE(datadir.stat().st_mode) != 0o700):
        raise RealWspScanError("WSP_LIVE_REGTEST_SCOPE_DENIED")
    _pinned_source(source_root)
    from wam_sp.core import pub
    from wam_sp.keystore import ScanAccount
    from wam_sp.scanner import Scanner
    from wam_sp.watcher import GENESIS

    if GENESIS != REGTEST_GENESIS:
        raise RealWspScanError("WSP_LIVE_UPSTREAM_GENESIS_DENIED")
    rpc = LiveCoreReadOnlyCli(cli, datadir)
    rpc.attest()
    if rpc.call("getblockcount") != expected_height:
        raise RealWspScanError("WSP_LIVE_HEIGHT_DENIED")
    account = ScanAccount(0, 1, pub(2), birthday=1)
    code = account.payment_code()
    if not code.startswith("wamrtsp1"):
        raise RealWspScanError("WSP_LIVE_RECEIVE_NAMESPACE_DENIED")
    path = datadir / "wsp-disposable-native.sqlite"
    scanner = None
    try:
        scanner = Scanner(path, (account,))
        observed = scanner.sync(rpc)
        if (observed.blocks != expected_height
                or scanner.store.tip()[0] != expected_height
                or not scanner.ready or scanner.coins()):
            raise RealWspScanError("WSP_LIVE_NATIVE_SCAN_DENIED")
        tip = scanner.store.tip()[1]
        if tip != rpc.call("getbestblockhash"):
            raise RealWspScanError("WSP_LIVE_TIP_MISMATCH")
        scanner.close()
        scanner = None
        scanner = Scanner(path, (account,))
        replay = scanner.sync(rpc)
        if (replay.blocks != 0 or scanner.store.tip() != (expected_height, tip)
                or not scanner.ready or scanner.coins()):
            raise RealWspScanError("WSP_LIVE_SQLITE_RESTART_DENIED")
        return {
            "status": "REAL_WAM_CORE_WSP1_SCANNER_LIVE_101_BLOCKS_PASS",
            "source_commit": PINNED_WSP_COMMIT,
            "regtest_genesis": REGTEST_GENESIS,
            "observed_height": expected_height,
            "verified_tip": tip,
            "actual_scanner_blocks_processed": observed.blocks,
            "sqlite_restart_blocks_processed": replay.blocks,
            "public_demo_receive_code_validated": True,
            "confirmed_demo_utxos": 0,
            "real_core_rpc": True,
            "synthetic_rpc": False,
            "wsp_bip352_payment_confirmed": False,
            "signing_allowed": False,
            "mainnet_allowed": False,
        }
    except RealWspScanError:
        raise
    except Exception:
        raise RealWspScanError("WSP_LIVE_NATIVE_RUNTIME_DENIED") from None
    finally:
        if scanner is not None:
            scanner.close()
