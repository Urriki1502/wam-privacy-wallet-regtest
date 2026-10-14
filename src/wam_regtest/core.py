"""Real WAM v0.1.11 Core REGTEST disposable RPC smoke, never mock or mainnet.

This is a developer acceptance harness, not a production executable loader
binding or key custody boundary. No user datadir is ever read or modified.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import stat
import subprocess
import tempfile
import time

from .release import ARCHIVES, CLI_SHA256, _sha


class CoreSmokeError(RuntimeError):
    """Fixed redacted errors, no paths/passwords/logs."""


def verified_core_paths(core_dir: Path) -> tuple[Path, Path, dict]:
    if not core_dir.is_absolute() or core_dir.is_symlink():
        raise CoreSmokeError("CORE_DIRECTORY_DENIED")
    try:
        receipt = json.loads((core_dir / "receipt.json").read_text())
        platform = receipt["platform"]
        node = core_dir / "wamd"
        cli = core_dir / "wam-cli"
        if (platform not in ARCHIVES or
                receipt["signed_archive_verified"] is not True or
                receipt.get("mainnet_allowed") is not False or
                receipt.get("loader_process_binding_qualified") is not False or
                receipt["wamd_sha256"] != ARCHIVES[platform][1] or
                (platform in CLI_SHA256 and receipt.get("wam_cli_sha256") != CLI_SHA256[platform])):
            raise CoreSmokeError("CORE_RECEIPT_DENIED")
        for path, key in ((node, "wamd_sha256"), (cli, "wam_cli_sha256")):
            s = path.lstat()
            if (not stat.S_ISREG(s.st_mode) or s.st_nlink != 1
                    or s.st_size <= 0 or s.st_size > 128 * 1024 * 1024
                    or path.is_symlink() or _sha(path) != receipt[key]):
                raise CoreSmokeError("CORE_EXACT_BINARY_DENIED")
        return node, cli, receipt
    except CoreSmokeError:
        raise
    except (OSError, KeyError, TypeError, ValueError):
        raise CoreSmokeError("CORE_EXACT_BINARY_DENIED") from None


def _port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _read_cli(cmd: list[str], timeout: int = 15) -> object:
    from .network_policy import local_rpc_port, NetworkPolicyError
    try:
        if (type(cmd) is not list or len(cmd)<3 or type(cmd[1]) is not str
                or not cmd[1].startswith("-datadir=")):
            raise CoreSmokeError("CORE_LOCAL_RPC_COMMAND_DENIED")
        directory=Path(cmd[1][9:])
        port=local_rpc_port(directory)
        isolated=[cmd[0],cmd[1],"-rpcconnect=127.0.0.1",f"-rpcport={port}",*cmd[2:]]
        p = subprocess.run(isolated, capture_output=True, text=True, timeout=timeout, check=False,
            env={"PATH":"/usr/bin:/bin:/usr/sbin:/sbin","HOME":str(directory),"LC_ALL":"C"})
    except NetworkPolicyError:
        raise CoreSmokeError("CORE_LOCAL_NETWORK_POLICY_DENIED") from None
    except (OSError, subprocess.TimeoutExpired):
        raise CoreSmokeError("CORE_RPC_PROCESS_DENIED") from None
    if p.returncode != 0:
        raise CoreSmokeError("CORE_RPC_DENIED")
    value = p.stdout.strip()
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _write_private_config(datadir: Path, rpcport: int, p2pport: int) -> None:
    # Password stays in owner-only wam.conf; never passed as a command argument.
    password = secrets.token_hex(32)
    user = "disposable_" + secrets.token_hex(8)
    # Bitcoin Core/WAM Core requires network-scoped settings such as
    # connect/port/rpcport under the explicit [regtest] stanza. Putting these
    # options in the global stanza makes real wamd EXIT 1 before RPC starts.
    global_values = {"regtest": "1", "server": "1"}
    network_values = {
        "rpcuser": user, "rpcpassword": password,
        "rpcbind": "127.0.0.1", "rpcallowip": "127.0.0.1", "rpcport": str(rpcport),
        "port": str(p2pport), "listen": "0", "connect": "0", "dnsseed": "0",
        "discover": "0", "upnp": "0", "txindex": "1", "blockfilterindex": "1",
        "coinstatsindex": "1", "fallbackfee": "0.0001",
    }
    config = datadir / "wam.conf"
    fd = os.open(config, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as out:
        for k, v in global_values.items():
            out.write(f"{k}={v}\n")
        out.write("[regtest]\n")
        for k, v in network_values.items():
            out.write(f"{k}={v}\n")
        out.flush()
        os.fsync(out.fileno())


def _early_exit_category(datadir: Path) -> str:
    """Classify actual wamd stderr WITHOUT emitting log lines or credentials.

    The node log remains inside the private disposable datadir. Only fixed
    non-secret categories escape the process boundary to CI.
    """
    try:
        log = datadir / "core-output.log"
        with log.open("rb") as stream:
            data = stream.read(65536).decode("utf-8", "replace").lower()
    except OSError:
        return "CORE_DAEMON_EARLY_EXIT_LOG_UNAVAILABLE"
    if any(word in data for word in ("dyld", "library not loaded", "symbol not found")):
        return "CORE_MACOS_DYNAMIC_LIBRARY_UNAVAILABLE"
    if any(word in data for word in ("unknown configuration", "unknown option",
                                     "unrecognized option", "invalid parameter")):
        return "CORE_DAEMON_OPTION_UNSUPPORTED"
    if any(word in data for word in ("permission denied", "operation not permitted")):
        return "CORE_DAEMON_PERMISSION_DENIED"
    if any(word in data for word in ("unable to bind", "could not bind",
                                     "unable to start http server")):
        return "CORE_DAEMON_PORT_BIND_DENIED"
    if any(word in data for word in ("error opening block database", "database corrupt",
                                     "database environment")):
        return "CORE_DAEMON_DATABASE_DENIED"
    # Report only a fixed vocabulary of observed startup tokens. Never send
    # arbitrary daemon lines (could contain RPC credentials or private paths).
    import re
    safe_words = frozenset((
        "error", "failed", "fatal", "regtest", "config", "configuration",
        "unknown", "invalid", "unsupported", "argument", "option", "daemon",
        "wallet", "datadir", "rpc", "bind", "port", "peer", "network",
        "index", "txindex", "coinstatsindex", "blockfilterindex", "connect",
        "listen", "permission", "denied", "directory", "database", "file",
        "lock", "address", "genesis", "server", "shutdown", "usage", "help",
        "timeout", "missing", "cannot", "unable", "not", "set", "already",
        "bitcoin", "wam", "core", "refused", "incompatible", "root",
    ))
    tokens = [w for w in re.findall(r"[a-z]{2,32}", data)
              if w in safe_words]
    if tokens:
        return "CORE_DAEMON_EXIT_LOG_TOKENS_" + "_".join(tokens[:12]).upper()
    return "CORE_DAEMON_EARLY_EXIT_UNCLASSIFIED"


def smoke_real_core(core_dir: Path, *, explicit_consent: bool, timeout: int = 120,
                    wsp_source: Path | None = None,
                    wsp_payment_e2e: bool = False,
                    gui_e2e: bool = False,
                    interactive_demo: bool = False,
                    security_e2e: bool = False,
                    wallet_e2e: bool = False, operational_demo: bool = False,
                    recovery_case: tuple | None = None) -> dict:
    if explicit_consent is not True or not 30 <= timeout <= 240:
        raise CoreSmokeError("CORE_REAL_REGTEST_CONSENT_DENIED")
    if (wsp_source is not None and
            (type(wsp_source) is not type(Path()) or not wsp_source.is_absolute())):
        raise CoreSmokeError("CORE_WSP_SOURCE_SCOPE_DENIED")
    if (type(wsp_payment_e2e) is not bool
            or (wsp_payment_e2e and wsp_source is None)):
        raise CoreSmokeError("CORE_PUBLIC_FIXTURE_PAYMENT_SCOPE_DENIED")
    if (type(gui_e2e) is not bool or (gui_e2e and not wsp_payment_e2e)):
        raise CoreSmokeError("CORE_REAL_GUI_SCOPE_DENIED")
    if (type(interactive_demo) is not bool
            or (interactive_demo and (not wsp_payment_e2e
                                      or wsp_source is None or gui_e2e))):
        raise CoreSmokeError("CORE_REAL_DEMO_SCOPE_DENIED")
    if type(security_e2e) is not bool or (security_e2e and (not wsp_payment_e2e or interactive_demo)):
        raise CoreSmokeError("CORE_SECURITY_SCOPE_DENIED")
    if (type(wallet_e2e) is not bool or (wallet_e2e and not security_e2e)
            or type(operational_demo) is not bool or (operational_demo and not interactive_demo)):
        raise CoreSmokeError("CORE_DISPOSABLE_WALLET_SCOPE_DENIED")
    if recovery_case is not None and (type(recovery_case) is not tuple or len(recovery_case)!=5
            or not wsp_payment_e2e or interactive_demo or gui_e2e or security_e2e or wallet_e2e):
        raise CoreSmokeError("CORE_RECOVERY_CASE_SCOPE_DENIED")
    node, cli, receipt = verified_core_paths(core_dir)
    # The caller runs on a dedicated CI runner or owner-approved macOS test host.
    # We intentionally do NOT claim fd-to-loader or hardened process provenance.
    with tempfile.TemporaryDirectory(prefix="wam-real-regtest-") as temp:
        # Canonicalize the OS-created temporary directory: macOS /var is a
        # system symlink. Private storage then walks canonical ancestors with
        # O_NOFOLLOW rather than relaxing its symlink checks.
        datadir = Path(temp).resolve(strict=True)
        datadir.chmod(0o700)
        rpc, p2p = _port(), _port()
        if rpc == p2p:
            raise CoreSmokeError("CORE_PORT_COLLISION_DENIED")
        _write_private_config(datadir, rpc, p2p)
        prefix = [str(cli), f"-datadir={datadir}"]
        proc = None
        try:
            with (datadir / "core-output.log").open("xb") as log:
                # Only the exact path/hash from signed receipt; no shell or user keys.
                proc = subprocess.Popen(
                    [str(node), f"-datadir={datadir}", "-daemon=0"],
                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                    cwd=datadir,
                    env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "HOME": str(datadir), "LC_ALL": "C"},
                )
            end = time.monotonic() + timeout
            info = None
            while time.monotonic() < end:
                if proc.poll() is not None:
                    code = proc.returncode
                    status = _early_exit_category(datadir)
                    # Process status is a bounded integer; no paths, passwords
                    # or uncontrolled log text are emitted.
                    if type(code) is int and -255 <= code <= 255:
                        status += "_STATUS_" + ("NEG" if code < 0 else "POS") + str(abs(code))
                    raise CoreSmokeError(status)
                try:
                    candidate = _read_cli(prefix + ["getblockchaininfo"], timeout=5)
                    if isinstance(candidate, dict):
                        info = candidate
                        break
                except CoreSmokeError:
                    pass
                time.sleep(0.5)
            if info is None or info.get("chain") != "regtest":
                raise CoreSmokeError("CORE_WRONG_CHAIN_DENIED")
            if _read_cli(prefix + ["getconnectioncount"]) != 0:
                raise CoreSmokeError("CORE_EXTERNAL_PEERS_DENIED")
            _read_cli(prefix + ["createwallet", "test"])
            addr = _read_cli(prefix + ["-rpcwallet=test", "getnewaddress"])
            if not isinstance(addr, str) or not 20 <= len(addr) <= 120:
                raise CoreSmokeError("CORE_REGTEST_ADDRESS_DENIED")
            # The deliberately public scalar 31 is never a user key. For
            # opted-in payment E2E, mine coinbase to its known P2WPKH script.
            # This supplies an actual matured UTXO that the pinned WSP
            # serializer can spend into a genuine BIP352 output.
            mine_to = addr
            if wsp_payment_e2e:
                from .wsp_live import public_regtest_mining_address
                mine_to = public_regtest_mining_address(wsp_source)
            mined = _read_cli(prefix + ["generatetoaddress", "101", mine_to], timeout=90)
            if not isinstance(mined, list) or len(mined) != 101:
                raise CoreSmokeError("CORE_REGTEST_GENERATE_DENIED")
            height = _read_cli(prefix + ["getblockcount"])
            if type(height) is not int or height < 101:
                raise CoreSmokeError("CORE_REGTEST_HEIGHT_DENIED")
            tip = _read_cli(prefix + ["getbestblockhash"])
            if not isinstance(tip, str) or len(tip) != 64 or tip != mined[-1]:
                raise CoreSmokeError("CORE_REGTEST_TIP_DENIED")
            final = _read_cli(prefix + ["getblockchaininfo"])
            if not isinstance(final, dict) or final.get("chain") != "regtest" or final.get("blocks") != height:
                raise CoreSmokeError("CORE_REGTEST_CHAIN_DRIFT_DENIED")
            if _read_cli(prefix + ["getconnectioncount"]) != 0:
                raise CoreSmokeError("CORE_EXTERNAL_PEERS_DENIED")
            wsp_receipt = None
            if wsp_source is not None:
                from .wsp_live import scan_actual_core_blocks, RealWspScanError
                try:
                    wsp_receipt = scan_actual_core_blocks(
                        cli, datadir, wsp_source, expected_height=height,
                        payment_e2e=wsp_payment_e2e,
                        mining_address=(mine_to if wsp_payment_e2e else None),
                    )
                except RealWspScanError as exc:
                    raise CoreSmokeError(str(exc)) from None
            gui_receipt = None
            if gui_e2e:
                # The REAL daemon remains running here. The native Qt worker
                # independently opens WSP SQLite and calls official Core RPC
                # again before any Receive/Balance/History UI claim.
                try:
                    from .desktop_probe import probe_running_real_core_gui
                    gui_receipt = probe_running_real_core_gui(
                        core_dir, datadir, wsp_source,
                        expected_height=wsp_receipt["observed_height"],
                        expected_txid=wsp_receipt["public_fixture_payment_txid"],
                        expected_atoms=wsp_receipt["confirmed_receive_atoms"],
                    )
                except Exception:
                    raise CoreSmokeError("CORE_MACOS_NATIVE_QT_E2E_DENIED") from None
            demo_finished = False
            if interactive_demo:
                # Owner-approved, disposable REGTEST only. Launch the real Qt
                # live-sync window while wamd is alive, not after temp cleanup.
                # The existing finally shuts down wamd and deletes test data
                # only AFTER the user has closed the GUI.
                try:
                    from .desktop import launch_readonly_wallet
                    print("REAL REGTEST PUBLIC DEMO: no mainnet or real funds; "
                          "close the wallet window to stop Core and delete the test chain.",
                          flush=True)
                    if operational_demo:
                        from .operational_gui import launch_disposable_wallet
                        exit_status = launch_disposable_wallet(core_dir,datadir,wsp_source,mine_to)
                    else:
                        exit_status = launch_readonly_wallet(core_dir,datadir,wsp_source)
                    if exit_status != 0:
                        raise CoreSmokeError("CORE_REAL_DEMO_WINDOW_DENIED")
                    demo_finished = True
                except CoreSmokeError:
                    raise
                except Exception:
                    raise CoreSmokeError("CORE_REAL_DEMO_GUI_DENIED") from None
            security_receipt = None
            if security_e2e:
                from .security_probe import probe_security, SecurityProbeError
                try:
                    security_receipt = probe_security(cli, datadir, wsp_source, mine_to)
                except SecurityProbeError as exc:
                    raise CoreSmokeError(str(exc)) from None
            wallet_receipt = None
            if wallet_e2e:
                from .wallet_probe import probe_wallet, WalletProbeError
                try:
                    wallet_receipt = probe_wallet(core_dir,datadir,wsp_source,mine_to)
                except WalletProbeError as exc:
                    raise CoreSmokeError(str(exc)) from None
            recovery_receipt = None
            if recovery_case is not None:
                from .reopen_probe import probe_reopened_wallet, ReopenProbeError
                try:
                    recovery_receipt = probe_reopened_wallet(core_dir,datadir,wsp_source,mine_to,recovery_case)
                except ReopenProbeError as exc:
                    raise CoreSmokeError(str(exc)) from None
            final_height = _read_cli(prefix + ["getblockcount"])
            final_tip = _read_cli(prefix + ["getbestblockhash"])
            if (type(final_height) is not int or not 101<=final_height<=1_000_000
                    or type(final_tip) is not str or len(final_tip)!=64
                    or _read_cli(prefix+["getconnectioncount"])!=0):
                raise CoreSmokeError("CORE_FINAL_CHAIN_ATTESTATION_DENIED")
            return {
                "wallet_live_core": wallet_receipt,
                "recovery_live_core": recovery_receipt,
                "security_live_core": security_receipt,
                "interactive_demo_closed_cleanly": demo_finished,
                "gui_real_core_e2e_pass": gui_receipt is not None,
                "gui_live_core_view": gui_receipt,
                "status": ("REAL_WAM_CORE_V0_1_11_NATIVE_QT_WALLET_E2E_PASS"
                           if gui_receipt is not None else
                           "REAL_WAM_CORE_V0_1_11_BIP352_RECEIVE_E2E_PASS"
                           if wsp_payment_e2e and wsp_receipt is not None else
                           "REAL_WAM_CORE_V0_1_11_REGTEST_AND_NATIVE_WSP_SCANNER_PASS"
                           if wsp_receipt is not None else
                           "REAL_WAM_CORE_V0_1_11_REGTEST_RPC_101_BLOCKS_PASS"),
                "wsp_real_core_scan_pass": wsp_receipt is not None,
                "wsp_live_scan": wsp_receipt,
                "regtest_public_fixture_broadcast_confirmed": (
                    wsp_receipt["regtest_fixture_broadcast_confirmed"]
                    if wsp_receipt is not None else False
                ),
                "platform": receipt["platform"], "node_sha256": receipt["wamd_sha256"],
                "chain": "regtest",
                "block_height": final_height,
                "tip": final_tip,
                "live_wamd_process_observed": True, "live_rpc_observed": True,
                "wallet_send_e2e_pass": wallet_receipt is not None,
                "wsp_bip352_e2e_pass": (
                    wsp_receipt["wsp_bip352_payment_confirmed"]
                    if wsp_receipt is not None else False
                ),
                "mainnet_allowed": False, "production_process_binding_qualified": False,
            }
        finally:
            if proc is not None:
                if proc.poll() is None:
                    try:
                        _read_cli(prefix + ["stop"], timeout=8)
                    except CoreSmokeError:
                        pass
                    try:
                        proc.wait(timeout=12)
                    except subprocess.TimeoutExpired:
                        proc.terminate()
                        try:
                            proc.wait(timeout=6)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            proc.wait(timeout=6)
