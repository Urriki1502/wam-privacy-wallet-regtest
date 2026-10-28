"""Real-WAM-Core-only REGTEST wallet read model for native macOS Qt UI.

One tested, publicly known BIP352 ScanAccount only. No real/user keys, mainnet,
signer, spending, transaction construction, network API outside official Core.
Reads blocks through signed wam-cli and WSP-1 Scanner.sync, backed by its
verified SQLite. Does not treat a cached DB as an attested wallet balance.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import platform
import re
import stat
import sys


class RealWalletReadError(ValueError):
    """Only fixed, redacted categories may be shown in the UI."""


def format_wam(atoms: int, *, grouped: bool = False) -> str:
    if type(atoms) is not int or atoms < 0:
        raise RealWalletReadError("WALLET_AMOUNT_DENIED")
    whole,fraction=divmod(atoms,100_000_000)
    return (f"{whole:,}" if grouped else str(whole))+f".{fraction:08d}"


@dataclass(frozen=True)
class HistoryRow:
    txid: str
    block_height: int
    confirmations: int
    credit_atoms: int
    debit_atoms: int


@dataclass(frozen=True)
class WalletReadSnapshot:
    chain: str
    height: int
    tip: str
    receive_code: str
    confirmed_atoms: int
    confirmed_utxos: int
    history: tuple[HistoryRow, ...]
    core_sha256: str
    synthetic_rpc: bool = False
    demo_account_only: bool = True
    signer_allowed: bool = False
    broadcast_allowed: bool = False
    mainnet_allowed: bool = False
    history_count: int | None = None
    history_sha256: str | None = None
    history_complete: bool = True


def read_real_wallet_snapshot(
    core_dir: Path, datadir: Path, wsp_source_root: Path
) -> WalletReadSnapshot:
    """Scan the actual running Core, then show only fully current SQLite data."""
    if (sys.platform != "darwin" or platform.machine().lower() != "arm64"
            or type(core_dir) is not type(Path())
            or type(datadir) is not type(Path())
            or type(wsp_source_root) is not type(Path())
            or not all(p.is_absolute() for p in (core_dir, datadir, wsp_source_root))):
        raise RealWalletReadError("WALLET_MACOS_ARM64_SCOPE_DENIED")
    try:
        st = datadir.lstat()
        if (not stat.S_ISDIR(st.st_mode) or stat.S_IMODE(st.st_mode) != 0o700
                or st.st_uid != __import__("os").geteuid()
                or datadir.is_symlink() or
                not (datadir / "wam.conf").is_file()):
            raise RealWalletReadError("WALLET_PRIVATE_DATADIR_DENIED")
        from .core import verified_core_paths
        from .history_pages import GUI_HISTORY_LIMIT,sql_history_pages
        from .wsp_live import (
            _pinned_source, LiveCoreReadOnlyCli, REGTEST_GENESIS,
        )
        node, cli, signed = verified_core_paths(core_dir)
        if signed.get("platform") != "macos-arm64":
            raise RealWalletReadError("WALLET_SIGNED_MACOS_CORE_DENIED")
        _pinned_source(wsp_source_root)
        from wam_sp.keystore import ScanAccount
        from wam_sp.core import pub
        from wam_sp.scanner import Scanner
        from wam_sp.watcher import GENESIS
        if GENESIS != REGTEST_GENESIS:
            raise RealWalletReadError("WALLET_REGTEST_GENESIS_DENIED")
        rpc = LiveCoreReadOnlyCli(cli, datadir)
        rpc.attest()
        account = ScanAccount(0, 1, pub(2), birthday=1)
        code = account.payment_code()
        if not code.startswith("wamrtsp1"):
            raise RealWalletReadError("WALLET_BIP352_RECEIVE_CODE_DENIED")
        # Deliberately preserve the same public-demo SQLite used by real E2E.
        path = datadir / "wsp-disposable-native.sqlite"
        scanner = Scanner(path, (account,))
        try:
            scanner.sync(rpc)
            scanner.assert_current()
            tip_height, tip_hash = scanner.store.tip()
            if (tip_height != rpc.call("getblockcount")
                    or tip_hash != rpc.call("getbestblockhash")):
                raise RealWalletReadError("WALLET_CHAIN_CHANGED_DENIED")
            coins = scanner.coins()
            values = []
            for coin in coins:
                v = coin.get("atoms")
                if type(v) is not int or not 0 < v <= 22_000_000 * 100_000_000:
                    raise RealWalletReadError("WALLET_AMOUNT_DENIED")
                values.append(v)
            with scanner.store.transaction():
                history_count,raw=sql_history_pages(
                    scanner.store.db,tip_height,
                    "SELECT txid,height,credit,debit FROM history "
                    "ORDER BY height DESC,txid LIMIT ? OFFSET ?",
                    error=RealWalletReadError,code="WALLET_HISTORY_DENIED",
                    window=GUI_HISTORY_LIMIT)
            history=tuple(HistoryRow(txid,block,conf,credit,debit)
                          for txid,block,credit,debit,conf in raw)
            # Final tip revalidation: refuse to show potentially stale balances.
            if (rpc.call("getblockcount") != tip_height or
                    rpc.call("getbestblockhash") != tip_hash):
                raise RealWalletReadError("WALLET_CHAIN_CHANGED_DENIED")
            return WalletReadSnapshot(
                chain="regtest",
                height=tip_height,
                tip=tip_hash,
                receive_code=code,
                confirmed_atoms=sum(values),
                confirmed_utxos=len(coins),
                history=history,
                core_sha256=signed["wamd_sha256"],
                history_count=history_count,
                history_complete=history_count<=GUI_HISTORY_LIMIT,
            )
        finally:
            scanner.close()
    except RealWalletReadError:
        raise
    except Exception:
        raise RealWalletReadError("WALLET_REAL_CORE_READ_DENIED") from None
