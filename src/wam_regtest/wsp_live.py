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
import hashlib
import json
import sys
from decimal import Decimal, InvalidOperation
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


def _verify_frozen_source(root: Path) -> None:
    """Verify the complete bundled WSP .py source corpus, not a Git checkout.

    PyInstaller applications cannot rely on system git or checkout metadata.
    The pinned source corpus and its SHA-256 manifest are generated on the
    macOS build runner from the reviewed WSP commit. This remains an
    experimental REGTEST package, not runtime code-signing attestation.
    """
    try:
        bundle = Path(sys._MEIPASS).resolve()
        if root.resolve() != (bundle / "wsp-source").resolve():
            raise RealWspScanError("WSP_FROZEN_SOURCE_SCOPE_DENIED")
        receipt = json.loads((root / "SOURCE_SHA256.json").read_text())
        records = receipt["files"]
        if (receipt["source_commit"] != PINNED_WSP_COMMIT
                or type(records) is not dict or not 2 <= len(records) <= 200):
            raise RealWspScanError("WSP_FROZEN_SOURCE_MANIFEST_DENIED")
        base = root / "src" / "wam_sp"
        actual = {
            p.relative_to(root).as_posix()
            for p in base.rglob("*.py") if p.is_file()
        }
        if set(records) != actual:
            raise RealWspScanError("WSP_FROZEN_SOURCE_CLOSURE_DENIED")
        for relative, expected in records.items():
            if (type(relative) is not str
                    or not relative.startswith("src/wam_sp/")
                    or ".." in Path(relative).parts
                    or type(expected) is not str
                    or not re.fullmatch(r"[0-9a-f]{64}", expected)):
                raise RealWspScanError("WSP_FROZEN_SOURCE_MANIFEST_DENIED")
            member = root / relative
            if member.is_symlink() or not member.is_file():
                raise RealWspScanError("WSP_FROZEN_SOURCE_MEMBER_DENIED")
            if hashlib.sha256(member.read_bytes()).hexdigest() != expected:
                raise RealWspScanError("WSP_FROZEN_SOURCE_HASH_DENIED")
        spec = importlib.util.find_spec("wam_sp")
        if spec is None or not spec.origin:
            raise RealWspScanError("WSP_FROZEN_PACKAGE_DENIED")
        # The imported package must be part of the sealed PyInstaller runtime,
        # not any unrelated system or user-site installation.
        if not Path(spec.origin).resolve().is_relative_to(bundle):
            raise RealWspScanError("WSP_FROZEN_PACKAGE_ORIGIN_DENIED")
    except RealWspScanError:
        raise
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise RealWspScanError("WSP_FROZEN_SOURCE_DENIED") from None


def _pinned_source(root: Path) -> None:
    if type(root) is not type(Path()) or not root.is_absolute():
        raise RealWspScanError("WSP_SOURCE_DIRECTORY_DENIED")
    if getattr(sys, "frozen", False):
        _verify_frozen_source(root)
        return
    try:
        sha = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=6, check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        raise RealWspScanError("WSP_SOURCE_PIN_DENIED") from None
    if sha != PINNED_WSP_COMMIT or not (root / "src/wam_sp/scanner.py").is_file():
        raise RealWspScanError("WSP_SOURCE_PIN_DENIED")
    # Git status and filenames cannot authenticate imported bytes: index flags
    # can hide tracked changes and replacement refs can substitute Git trees.
    # Keep status as an early refusal, then check the literal pin independently.
    try:
        dirty = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain",
             "--untracked-files=all", "--", "src/wam_sp"],
            capture_output=True, timeout=6, check=True,
        ).stdout
        # Refuse dirty tracked/untracked source immediately. A source tree
        # already known to be altered must not proceed to the manifest step.
        if dirty.strip():
            raise RealWspScanError("WSP_SOURCE_WORKTREE_DENIED")
        tree = subprocess.run(
            ["git", "--no-replace-objects", "-C", str(root), "ls-tree", "-r",
             "-z", PINNED_WSP_COMMIT, "--", "src/wam_sp"],
            capture_output=True, timeout=6, check=True,
        ).stdout
    except RealWspScanError:
        raise
    except (OSError, subprocess.SubprocessError):
        raise RealWspScanError("WSP_SOURCE_WORKTREE_DENIED") from None
    try:
        from .build_provenance import _file, _blob
        base = root / "src" / "wam_sp"
        for directory in (root, root / "src", base):
            info = directory.lstat()
            if (not stat.S_ISDIR(info.st_mode)
                    or getattr(info, "st_file_attributes", 0) & 0x400):
                raise RealWspScanError("WSP_SOURCE_CLOSURE_DENIED")
        if len(tree) > 65536:
            raise RealWspScanError("WSP_SOURCE_CLOSURE_DENIED")
        declared = {}
        for row in tree.split(b"\0"):
            if not row:
                continue
            header, name = row.split(b"\t", 1)
            mode, kind, oid = header.decode("ascii").split()
            relative = name.decode("utf-8")
            parts = Path(relative)
            if (mode not in ("100644", "100755") or kind != "blob"
                    or not re.fullmatch(r"[0-9a-f]{40}", oid)
                    or not relative.startswith("src/wam_sp/")
                    or parts.is_absolute() or ".." in parts.parts
                    or "\\" in relative or parts.suffix != ".py"
                    or relative in declared):
                raise RealWspScanError("WSP_SOURCE_CLOSURE_DENIED")
            declared[relative] = oid
        actual = set()
        total = 0
        for count, member in enumerate(base.rglob("*"), 1):
            if count > 2000:
                raise RealWspScanError("WSP_SOURCE_CLOSURE_DENIED")
            info = member.lstat()
            if (stat.S_ISLNK(info.st_mode)
                    or getattr(info, "st_file_attributes", 0) & 0x400):
                raise RealWspScanError("WSP_SOURCE_CLOSURE_DENIED")
            if stat.S_ISDIR(info.st_mode):
                continue
            if not stat.S_ISREG(info.st_mode):
                raise RealWspScanError("WSP_SOURCE_CLOSURE_DENIED")
            relative = member.relative_to(root).as_posix()
            suffix = member.suffix.lower()
            if suffix == ".py":
                total += info.st_size
                if (relative not in declared or info.st_size > 4 * 1024 * 1024
                        or total > 16 * 1024 * 1024):
                    raise RealWspScanError("WSP_SOURCE_CLOSURE_DENIED")
                raw, _ = _file(member)  # Stable native handle; no hardlink/reparse.
                if (_blob(raw) != declared[relative]
                        and _blob(raw.replace(b"\r\n", b"\n")) != declared[relative]):
                    raise RealWspScanError("WSP_SOURCE_HASH_DENIED")
                actual.add(relative)
            elif suffix in (".pyw", ".so", ".pyd", ".dll", ".dylib", ".pyo"):
                raise RealWspScanError("WSP_SOURCE_CLOSURE_DENIED")
            elif suffix == ".pyc" and member.parent.name != "__pycache__":
                raise RealWspScanError("WSP_SOURCE_CLOSURE_DENIED")
        if not 2 <= len(declared) <= 200 or set(declared) != actual:
            raise RealWspScanError("WSP_SOURCE_CLOSURE_DENIED")
        # Ordinary interpreter caches remain allowed. This is not bytecode,
        # import-hook, hostile-host or validation-to-import race attestation.
    except RealWspScanError:
        raise
    except (OSError,ValueError,UnicodeError):
        raise RealWspScanError("WSP_SOURCE_CLOSURE_DENIED") from None
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


def public_regtest_mining_address(source_root: Path) -> str:
    """Publicly known scalar 31: disposable REGTEST ONLY, never a user key."""
    _pinned_source(source_root)
    from wam_sp.core import pub, hash160
    from wam_sp.codec import encode
    return encode("wamrt", hash160(pub(31)), version=0, bech32m=False)


def _public_fixture_payment(rpc, account, mining_address: str, *,
                            funding_height: int = 1,
                            expected_before_height: int = 101) -> tuple[str, int, int]:
    """Actual signed raw P2WPKH spend → BIP352 P2TR on the real regtest chain.

    The fixture scalar 31 is globally known; it MUST NEVER leave disposable
    REGTEST. Signatures are produced locally by the pinned WSP demo serializer,
    then validated by real Core mempool and consensus during block generation.
    """
    from wam_sp.core import Input, pub, send
    from wam_sp.transaction import p2wpkh, signed_single_input
    if (type(funding_height) is not int or funding_height not in (1, 2, 3)
            or type(expected_before_height) is not int or expected_before_height not in (101, 102, 103)
            or rpc.call("getblockcount") != expected_before_height):
        raise RealWspScanError("WSP_PUBLIC_FIXTURE_HEIGHT_DENIED")
    expected_after = expected_before_height + 1
    first_hash = rpc.call("getblockhash", [funding_height])
    block = rpc._call("getblock", [first_hash, "2"])
    if (type(block) is not dict or block.get("hash") != first_hash
            or type(block.get("tx")) is not list or len(block["tx"]) != 1):
        raise RealWspScanError("WSP_LIVE_FUNDING_BLOCK_DENIED")
    cb = block["tx"][0]
    script_hex = p2wpkh(31).hex()
    matches = [o for o in cb.get("vout", [])
               if type(o) is dict and type(o.get("scriptPubKey")) is dict
               and o["scriptPubKey"].get("hex") == script_hex]
    if (len(matches) != 1 or type(cb.get("txid")) is not str
            or not _HASH.fullmatch(cb["txid"])):
        raise RealWspScanError("WSP_LIVE_PUBLIC_FUNDING_DENIED")
    out = matches[0]
    if type(out.get("n")) is not int or not 0 <= out["n"] < 100:
        raise RealWspScanError("WSP_LIVE_PUBLIC_FUNDING_DENIED")
    try:
        atoms = Decimal(str(out["value"])) * 100_000_000
        if not atoms.is_finite() or atoms != int(atoms):
            raise ValueError()
        amount = int(atoms)
    except (ValueError, KeyError, TypeError, InvalidOperation):
        raise RealWspScanError("WSP_LIVE_FUNDING_AMOUNT_DENIED") from None
    fee = 10_000
    if not 100_000 <= amount < 100 * 100_000_000:
        raise RealWspScanError("WSP_LIVE_FUNDING_AMOUNT_DENIED")
    txin = Input(
        cb["txid"], out["n"], p2wpkh(31),
        witness=(b"\x30", pub(31)), secret=31,
    )
    output = b"\x51\x20" + send((txin,), (account.payment_code(),))[0]
    raw = signed_single_input(
        txin, amount, ((amount - fee, output),), 31,
    )
    # Real consensus validates this exact fixture signature and BIP352
    # script; success cannot be forged by a synthetic result.
    txid = rpc._call("sendrawtransaction", [raw])
    if type(txid) is not str or not _HASH.fullmatch(txid):
        raise RealWspScanError("WSP_LIVE_PAYMENT_BROADCAST_DENIED")
    confirmed = rpc._call("generatetoaddress", ["1", mining_address])
    if (type(confirmed) is not list or len(confirmed) != 1
            or type(confirmed[0]) is not str or not _HASH.fullmatch(confirmed[0])
            or rpc.call("getblockcount") != expected_after):
        raise RealWspScanError("WSP_LIVE_PAYMENT_CONFIRM_DENIED")
    return txid, amount - fee, expected_after


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
                            *, expected_height: int, payment_e2e: bool = False,
                            mining_address: str | None = None) -> dict[str, object]:
    """Real WSP scanner -> 101 actual Core blocks -> SQLite restart/replay proof.

    Fixture deliberately contains only a publicly known scan key. It has zero
    funds and must not be used to receive any real value.
    """
    if (type(payment_e2e) is not bool
            or (payment_e2e and
                (type(mining_address) is not str or
                 not mining_address.startswith("wamrt1q") or
                 mining_address != public_regtest_mining_address(source_root)))
            or type(expected_height) is not int or expected_height != _MINE_LIMIT
            or type(datadir) is not type(Path()) or not datadir.is_absolute()
            or datadir.is_symlink()):
        raise RealWspScanError("WSP_LIVE_REGTEST_SCOPE_DENIED")
    from .custody import storage
    try:
        storage().validate_directory(datadir)
    except (ValueError,OSError):
        raise RealWspScanError("WSP_LIVE_NATIVE_CUSTODY_DENIED") from None
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
        matched = False
        payment_txid = None
        amount = 0
        received = 0
        if payment_e2e:
            payment_txid, amount, new_height = _public_fixture_payment(
                rpc, account, mining_address,
            )
            payment_scan = scanner.sync(rpc)
            coins = scanner.coins()
            if (payment_scan.blocks != 1 or new_height != 102
                    or scanner.store.tip()[0] != 102
                    or not scanner.ready or len(coins) != 1
                    or coins[0]["txid"] != payment_txid
                    or coins[0]["atoms"] != amount):
                raise RealWspScanError("WSP_LIVE_BIP352_PAYMENT_NOT_DETECTED")
            row = scanner.store.db.execute(
                "SELECT credit,debit,height FROM history WHERE txid=?",
                (payment_txid,),
            ).fetchone()
            if (row is None or row["credit"] != amount
                    or row["debit"] != 0 or row["height"] != 102):
                raise RealWspScanError("WSP_LIVE_BIP352_HISTORY_DENIED")
            matched = True
            received = amount
            tip = scanner.store.tip()[1]
            scanner.close()
            scanner = None
            scanner = Scanner(path, (account,))
            final_replay = scanner.sync(rpc)
            again = scanner.coins()
            if (final_replay.blocks != 0 or len(again) != 1
                    or again[0]["txid"] != payment_txid
                    or again[0]["atoms"] != amount):
                raise RealWspScanError("WSP_LIVE_BIP352_RESTART_DENIED")
        return {
            "status": ("REAL_WAM_CORE_WSP1_BIP352_CONFIRMED_RECEIVE_PASS"
                       if matched else
                       "REAL_WAM_CORE_WSP1_SCANNER_LIVE_101_BLOCKS_PASS"),
            "source_commit": PINNED_WSP_COMMIT,
            "regtest_genesis": REGTEST_GENESIS,
            "observed_height": (102 if matched else expected_height),
            "verified_tip": tip,
            "actual_scanner_blocks_processed": observed.blocks,
            "sqlite_restart_blocks_processed": replay.blocks,
            "public_demo_receive_code_validated": True,
            "confirmed_demo_utxos": (1 if matched else 0),
            "confirmed_receive_atoms": received,
            "public_fixture_payment_txid": payment_txid,
            "regtest_fixture_broadcast_confirmed": matched,
            "real_core_rpc": True,
            "synthetic_rpc": False,
            "wsp_bip352_payment_confirmed": matched,
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
