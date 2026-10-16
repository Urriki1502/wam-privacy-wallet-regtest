"""REAL signed WAM Core v0.1.11 Windows x64 REGTEST smoke; no wallet/signing.

This executes the exact Windows wamd.exe and wam-cli.exe only AFTER the
official GPG-signed archive, SHA256, ZIP entry policy and PE64 shape qualify.
Run on a disposable native Windows x64 CI host with explicit consent.
This is not a hardened loader, keystore, GUI or production release gate.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import zipfile

from .windows_release_preflight import (
    ASSET, ROOT, WindowsReleaseError, verify_signed_windows_archive,
)


class WindowsCoreSmokeError(ValueError):
    """Redacted fixed codes only; never include Core stderr or RPC credentials."""


def _deny(reason: str) -> None:
    raise WindowsCoreSmokeError(reason)


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _staged_signed_binaries(archive: Path, receipt: dict, destination: Path) -> tuple[Path, Path]:
    """Create only exact, independently hashed signed Core/CLI members."""
    if destination.exists():
        _deny("WIN_CORE_STAGE_EXISTS_DENIED")
    from .custody import create_directory
    if sys.platform == "win32":
        create_directory(destination)
    else:
        destination.mkdir()
    trusted = receipt["member_sha256"]
    try:
        with zipfile.ZipFile(archive, "r") as z:
            for filename in ("wamd.exe", "wam-cli.exe"):
                member = ROOT + "/bin/" + filename
                entry = z.getinfo(member)
                # The preceding signed-ZIP inspector has already checked ALL
                # members. Recheck the actual source selected for extraction.
                if (entry.orig_filename != member or entry.filename != member
                        or entry.file_size <= 0 or entry.file_size > 128 * 1024 * 1024):
                    _deny("WIN_CORE_MEMBER_SHAPE_DENIED")
                with z.open(entry, "r") as stream:
                    binary = stream.read(128 * 1024 * 1024 + 1)
                if len(binary) != entry.file_size or _hash(binary) != trusted[filename]:
                    _deny("WIN_CORE_STAGED_HASH_DENIED")
                if sys.platform == "win32":
                    from .windows_core_transport import write_new
                    write_new(destination,filename,binary)
                else:
                    with (destination / filename).open("xb") as out:
                        out.write(binary)
                        out.flush()
                        os.fsync(out.fileno())
                if _hash((destination / filename).read_bytes()) != trusted[filename]:
                    _deny("WIN_CORE_STAGED_HASH_DENIED")
        if set(p.name for p in destination.iterdir()) != {"wamd.exe", "wam-cli.exe"}:
            _deny("WIN_CORE_STAGING_CONTENT_DENIED")
        if sys.platform == "win32":
            from .windows_core_transport import write_new, verified_core_paths
            write_new(destination,"receipt.json",json.dumps(receipt,sort_keys=True).encode())
            verified_core_paths(destination)
        return destination / "wamd.exe", destination / "wam-cli.exe"
    except WindowsCoreSmokeError:
        raise
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        _deny("WIN_CORE_STAGING_DENIED")


def _host_env(datadir: Path) -> dict:
    """Minimize inherited DLL search/profile influences for disposable CI."""
    from . import windows_private_storage as store
    store.require_native()
    import ctypes
    from ctypes import wintypes
    get_root=store.K.GetSystemWindowsDirectoryW
    get_root.argtypes=[wintypes.LPWSTR,wintypes.UINT];get_root.restype=wintypes.UINT
    buffer=ctypes.create_unicode_buffer(261)
    size=get_root(buffer,len(buffer))
    root=buffer.value if 1<=size<len(buffer) else None
    if not root or not Path(root).is_dir():
        _deny("WIN_CORE_SYSTEMROOT_DENIED")
    return {
        "SystemRoot": root, "WINDIR": root,
        "PATH": str(Path(root) / "System32"),
        "TEMP": str(datadir), "TMP": str(datadir),
        "APPDATA": str(datadir), "LOCALAPPDATA": str(datadir),
        "USERPROFILE": str(datadir),
    }


def _config(datadir: Path, rpc_port: int, peer_port: int) -> None:
    """No remote RPC/peers, with ephemeral credentials never printed."""
    if (rpc_port == peer_port or not 1024 <= rpc_port <= 65535
            or not 1024 <= peer_port <= 65535):
        _deny("WIN_CORE_PORT_DENIED")
    config = "\n".join((
        "regtest=1", "server=1", "[regtest]",
        "rpcuser=disposable_" + secrets.token_hex(8),
        "rpcpassword=" + secrets.token_hex(32),
        "rpcbind=127.0.0.1", "rpcallowip=127.0.0.1",
        f"rpcport={rpc_port}", f"port={peer_port}", "listen=0", "connect=0",
        "dnsseed=0", "discover=0", "upnp=0", "txindex=1",
        "blockfilterindex=1", "coinstatsindex=1", "fallbackfee=0.0001", "",
    ))
    from .windows_core_transport import write_new
    write_new(datadir,"wam.conf",config.encode("ascii"))


def _rpc(cli: Path, datadir: Path, port: int, env: dict, *args: str, timeout=15):
    argv = [str(cli), f"-datadir={datadir}", "-rpcconnect=127.0.0.1",
            f"-rpcport={port}", *args]
    try:
        process = subprocess.run(
            argv, cwd=datadir, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=timeout, check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired):
        _deny("WIN_CORE_CLI_PROCESS_DENIED")
    if process.returncode or len(process.stdout) > 128 * 1024:
        _deny("WIN_CORE_RPC_DENIED")
    data = process.stdout.decode("utf-8", errors="strict").strip()
    if not data:
        return None
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return data


def smoke_signed_windows_regtest(archive: Path, signing_key: Path, sha256sums: Path,
                                signature: Path, *, consent: bool = False,
                                timeout: int = 120, wsp_source: Path | None = None,
                                confirm_public_fixture_payment: bool = False,
                                qt_readonly_e2e: bool = False,
                                vault_e2e: bool = False) -> dict:
    """Authentic actual Windows node: 101-block smoke with zero peers.

    Deliberately has no WSP scanner, wallet signer, broadcast or real-fund API.
    Native application-wide E2E and loader hardening remain separate gates.
    """
    if consent is not True or type(timeout) is not int or not 30 <= timeout <= 240:
        _deny("WIN_CORE_EXPLICIT_CONSENT_REQUIRED")
    if sys.platform != "win32" or platform.machine().lower() not in ("amd64", "x86_64"):
        _deny("WIN_CORE_NATIVE_X64_ONLY")
    if (type(confirm_public_fixture_payment) is not bool
            or type(qt_readonly_e2e) is not bool
            or type(vault_e2e) is not bool
            or (vault_e2e and not confirm_public_fixture_payment)
            or (qt_readonly_e2e and not confirm_public_fixture_payment)
            or (wsp_source is not None and not confirm_public_fixture_payment)
            or (confirm_public_fixture_payment and
                (type(wsp_source) is not type(Path()) or not wsp_source.is_absolute()))):
        _deny("WIN_CORE_PUBLIC_FIXTURE_SCOPE_DENIED")
    if not all(type(p) is type(Path()) and p.is_file() for p in
               (archive, signing_key, sha256sums, signature)):
        _deny("WIN_CORE_INPUT_DENIED")
    try:
        proof = verify_signed_windows_archive(
            archive, signing_key, sha256sums, signature)
    except WindowsReleaseError:
        _deny("WIN_CORE_SIGNED_ARCHIVE_DENIED")
    if (proof["signed_archive_verified"] is not True
            or proof["platform"] != "windows-x64"
            or proof["wallet_signing_authorized"] is not False
            or proof["mainnet_allowed"] is not False
            or set(proof["member_sha256"]) != {"wamd.exe", "wam-cli.exe"}):
        _deny("WIN_CORE_TRUST_SCOPE_DENIED")

    mine_to_public = None
    if confirm_public_fixture_payment:
        from .wsp_live import public_regtest_mining_address
        try:
            mine_to_public = public_regtest_mining_address(wsp_source)
        except Exception:
            _deny("WIN_CORE_PINNED_WSP_SOURCE_DENIED")

    with tempfile.TemporaryDirectory(prefix="wam-win-real-regtest-") as tmp:
        root = Path(tmp).resolve(strict=True)
        node, cli = _staged_signed_binaries(archive, proof, root / "core")
        datadir = root / "chain"
        from .custody import create_directory
        create_directory(datadir)
        rpc, p2p = _port(), _port()
        _config(datadir, rpc, p2p)
        env = _host_env(datadir)
        daemon = None
        try:
            with (datadir / "node-output.log").open("xb") as log:
                # Verified ZIP members are staged alone; never shell-executed.
                daemon = subprocess.Popen(
                    [str(node), f"-datadir={datadir}", "-daemon=0"],
                    cwd=node.parent, env=env,
                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            deadline = time.monotonic() + timeout
            ready = False
            while time.monotonic() < deadline:
                if daemon.poll() is not None:
                    _deny("WIN_CORE_EARLY_EXIT")
                try:
                    info = _rpc(cli, datadir, rpc, env, "getblockchaininfo", timeout=5)
                    if type(info) is dict and info.get("chain") == "regtest":
                        ready = True
                        break
                except WindowsCoreSmokeError:
                    pass
                time.sleep(0.5)
            if not ready:
                _deny("WIN_CORE_REGTEST_START_TIMEOUT")
            if _rpc(cli, datadir, rpc, env, "getconnectioncount") != 0:
                _deny("WIN_CORE_UNEXPECTED_PEERS")
            _rpc(cli, datadir, rpc, env, "createwallet", "test")
            address = _rpc(cli, datadir, rpc, env, "-rpcwallet=test", "getnewaddress")
            if type(address) is not str or not 20 <= len(address) <= 120:
                _deny("WIN_CORE_REGTEST_ADDRESS_DENIED")
            blocks = _rpc(cli, datadir, rpc, env, "generatetoaddress", "101",
                          mine_to_public or address, timeout=90)
            if type(blocks) is not list or len(blocks) != 101:
                _deny("WIN_CORE_101_BLOCKS_DENIED")
            if _rpc(cli, datadir, rpc, env, "getblockcount") != 101:
                _deny("WIN_CORE_HEIGHT_DENIED")
            tip = _rpc(cli, datadir, rpc, env, "getbestblockhash")
            if type(tip) is not str or len(tip) != 64 or tip != blocks[-1]:
                _deny("WIN_CORE_TIP_DENIED")
            if _rpc(cli, datadir, rpc, env, "getconnectioncount") != 0:
                _deny("WIN_CORE_UNEXPECTED_PEERS")
            wsp_receipt = None
            if confirm_public_fixture_payment:
                from .windows_wsp_regtest import prove_real_windows_wsp_receive
                try:
                    wsp_receipt = prove_real_windows_wsp_receive(
                        cli, datadir, rpc, env, wsp_source, mine_to_public)
                except Exception:
                    _deny("WIN_CORE_WSP_PAYMENT_E2E_DENIED")
            gui_receipt = None
            if qt_readonly_e2e:
                from .windows_read_gui import probe_real_windows_wallet_gui
                try:
                    gui_receipt = probe_real_windows_wallet_gui(
                        node, cli, datadir, rpc, env, wsp_source,
                        proof["member_sha256"]["wamd.exe"])
                except Exception:
                    _deny("WIN_CORE_NATIVE_GUI_READ_E2E_DENIED")
            vault_receipt = None
            if vault_e2e:
                from .windows_vault_probe import prove_real_windows_vault
                vault_receipt = prove_real_windows_vault(cli,datadir,rpc,env,wsp_source,mine_to_public)
            receipt = {
                "status": ("WIN64_REAL_CORE_CREDENTIAL_ENCRYPTED_VAULT_RECOVERY_REORG_PASS"
                           if vault_receipt is not None else
                           "WIN64_SIGNED_CORE_WSP_QT_READ_ONLY_E2E_PASS"
                           if gui_receipt is not None else
                           "WIN64_REAL_CORE_WSP1_BIP352_CONFIRMED_RECEIVE_PASS"
                           if wsp_receipt is not None else
                           "WIN64_SIGNED_WAM_CORE_REGTEST_101_BLOCK_SMOKE_PASS"),
                "official_signed_core": True,
                "real_node_process": True,
                "actual_regtest_101_blocks": True,
                "zero_peers": True,
                "archive_sha256": proof["archive_sha256"],
                "core_sha256": proof["member_sha256"]["wamd.exe"],
                "cli_sha256": proof["member_sha256"]["wam-cli.exe"],
                "wsp_bip352_payment_e2e": wsp_receipt is not None,
                "wsp_receipt": wsp_receipt,
                "vault_receipt": vault_receipt,
                "qt_wallet_e2e": gui_receipt is not None,
                "qt_receipt": gui_receipt,
                "sign_broadcast_authorized": False,
                "production_authorized": False,
                "mainnet_allowed": False,
            }
            return receipt
        finally:
            if daemon is not None:
                if daemon.poll() is None:
                    try:
                        _rpc(cli, datadir, rpc, env, "stop", timeout=8)
                    except WindowsCoreSmokeError:
                        pass
                    try:
                        daemon.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        daemon.kill()
                        daemon.wait(timeout=10)
            # TemporaryDirectory removes the entire experimental chain.
