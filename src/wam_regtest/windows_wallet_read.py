"""Attested REAL Windows Core + pinned WSP native SQLite -> Qt read model.

Read-only disposable BIP352 REGTEST account, no signer, imports or mainnet.
Never serve a cached tip if the native RPC state has moved.
"""
from __future__ import annotations

from hashlib import sha256
import re
from pathlib import Path

from .wallet_read import WalletReadSnapshot, HistoryRow
from .wsp_live import _pinned_source, PINNED_WSP_COMMIT, REGTEST_GENESIS
from .windows_wsp_regtest import WindowsWspCoreRpc

_HASH = re.compile(r"[0-9a-f]{64}\Z")


class WindowsWalletReadError(ValueError):
    """Fixed redacted error classifications only."""


def read_native_windows_wallet(core: Path, cli: Path, datadir: Path, port: int,
                               environment: dict, wsp_source: Path,
                               expected_core_sha256: str) -> WalletReadSnapshot:
    """A fresh real scanner validates the chain tip before serving a balance."""
    if (type(core) is not type(Path()) or type(cli) is not type(Path())
            or type(datadir) is not type(Path()) or type(wsp_source) is not type(Path())
            or not all(p.is_absolute() for p in (core, cli, datadir, wsp_source))
            or type(expected_core_sha256) is not str
            or not _HASH.fullmatch(expected_core_sha256)):
        raise WindowsWalletReadError("WIN_READ_SCOPE_DENIED")
    try:
        if (not core.is_file() or not cli.is_file()
                or sha256(core.read_bytes()).hexdigest() != expected_core_sha256):
            raise WindowsWalletReadError("WIN_READ_STAGED_CORE_DENIED")
        _pinned_source(wsp_source)
        from wam_sp.core import pub
        from wam_sp.keystore import ScanAccount
        from wam_sp.scanner import Scanner
        from wam_sp.watcher import GENESIS

        if GENESIS != REGTEST_GENESIS:
            raise WindowsWalletReadError("WIN_READ_GENESIS_DENIED")
        rpc = WindowsWspCoreRpc(cli, datadir, port, environment)
        rpc.attest()
        height = rpc.call("getblockcount")
        if type(height) is not int or height not in (101, 102):
            raise WindowsWalletReadError("WIN_READ_HEIGHT_DENIED")
        account = ScanAccount(0, 1, pub(2), birthday=1)
        code = account.payment_code()
        if not code.startswith("wamrtsp1"):
            raise WindowsWalletReadError("WIN_READ_BIP352_NAMESPACE_DENIED")
        scanner = Scanner(datadir / "wsp-win-disposable-scan.sqlite", (account,))
        try:
            scanner.sync(rpc)
            scanner.assert_current()
            tip_height, tip_hash = scanner.store.tip()
            if tip_height != height or tip_hash != rpc.call("getbestblockhash"):
                raise WindowsWalletReadError("WIN_READ_TIP_DENIED")
            coins = scanner.coins()
            amounts = []
            for coin in coins:
                n = coin.get("atoms")
                if type(n) is not int or not 0 < n <= 22_000_000 * 100_000_000:
                    raise WindowsWalletReadError("WIN_READ_AMOUNT_DENIED")
                amounts.append(n)
            history = []
            for row in scanner.store.db.execute(
                "SELECT txid,height,credit,debit FROM history "
                "ORDER BY height DESC,txid LIMIT 100"
            ):
                txid, block, credit, debit = row
                if (type(txid) is not str or not _HASH.fullmatch(txid)
                        or type(block) is not int or not 1 <= block <= tip_height
                        or type(credit) is not int or type(debit) is not int
                        or not 0 <= credit <= 22_000_000 * 100_000_000
                        or not 0 <= debit <= 22_000_000 * 100_000_000):
                    raise WindowsWalletReadError("WIN_READ_HISTORY_DENIED")
                history.append(HistoryRow(txid, block, tip_height-block+1, credit, debit))
            if rpc.call("getblockcount") != tip_height or rpc.call("getbestblockhash") != tip_hash:
                raise WindowsWalletReadError("WIN_READ_CHAIN_CHANGED_DENIED")
            if rpc._call("getconnectioncount", []) != 0:
                raise WindowsWalletReadError("WIN_READ_EXTERNAL_PEERS_DENIED")
            return WalletReadSnapshot(
                chain="regtest", height=tip_height, tip=tip_hash,
                receive_code=code, confirmed_atoms=sum(amounts),
                confirmed_utxos=len(coins), history=tuple(history),
                core_sha256=expected_core_sha256,
                synthetic_rpc=False, demo_account_only=True,
                signer_allowed=False, broadcast_allowed=False,
                mainnet_allowed=False,
            )
        finally:
            scanner.close()
    except WindowsWalletReadError:
        raise
    except Exception:
        raise WindowsWalletReadError("WIN_READ_REAL_CORE_WSP_DENIED") from None
