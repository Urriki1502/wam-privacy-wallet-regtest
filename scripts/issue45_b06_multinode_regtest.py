"""Issue #45 B-06: two *genuine* pinned WAM Core REGTEST daemons.

Disposable independent data directories, explicit one-shot loopback P2P,
chain branches (reorg depths 1/12/100), restart and original WSP Scanner
SQLite rollback. This is a NON-PRODUCTION integration test: it never starts,
reads or attaches to a user's Core, wallet, miner, config, or keychain.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import time

from wam_regtest.core import verified_core_paths
from wam_regtest.wsp_live import (
    REGTEST_GENESIS, _pinned_source, _public_fixture_payment,
    public_regtest_mining_address,
)

SHA64 = re.compile(r"[0-9a-f]{64}")
DURATIONS = (1, 12, 100)
RPC_READS = frozenset(("getblockcount", "getbestblockhash", "getblockhash", "getblock"))
RPC_LAB_ONLY = frozenset((
    "getblockchaininfo", "getnetworkinfo", "getpeerinfo", "getconnectioncount",
    "getblockcount", "getbestblockhash", "getblockhash", "getblock",
    "generatetoaddress", "sendrawtransaction", "addnode", "disconnectnode", "stop",
))


class B06LabError(ValueError):
    """Only redacted error codes; do not leak datadirs or RPC secrets."""


def _fresh_ports() -> tuple[int, int, int, int]:
    # Bootstrap-time loopback ephemeral selection. Nodes still fail closed
    # on bind conflict; dynamic ports do not confer production authorization.
    reserved = []
    try:
        for _ in range(4):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", 0))
            reserved.append(sock)
        values = tuple(s.getsockname()[1] for s in reserved)
        if len(set(values)) != 4:
            raise B06LabError("B06_PORT_COLLISION_DENIED")
        return values
    finally:
        for sock in reserved:
            sock.close()


def make_private_lab_config(datadir: Path, rpc: int, p2p: int) -> None:
    """Different from the zero-peer *production wallet* network policy.

    Only a disposable test harness may open a local P2P listener. No remote
    DNS, clearnet seeds, proxy or WAN bind, and no user-supplied directory.
    """
    if (type(datadir) is not type(Path()) or not datadir.is_absolute()
            or datadir.is_symlink() or not datadir.is_dir()
            or not 1024 <= rpc <= 65535 or not 1024 <= p2p <= 65535
            or rpc == p2p):
        raise B06LabError("B06_CONFIG_SCOPE_DENIED")
    config = (
        "regtest=1\nserver=1\n[regtest]\n"
        "rpcuser=disposable_" + secrets.token_hex(8) + "\n"
        "rpcpassword=" + secrets.token_hex(32) + "\n"
        "rpcbind=127.0.0.1\nrpcallowip=127.0.0.1\n"
        "rpcport=" + str(rpc) + "\n"
        "port=" + str(p2p) + "\n"
        "bind=127.0.0.1\nlisten=1\n"
        "connect=0\ndnsseed=0\ndiscover=0\nupnp=0\n"
        "txindex=1\nblockfilterindex=1\ncoinstatsindex=1\n"
        "fallbackfee=0.0001\n"
    )
    name = datadir / "wam.conf"
    try:
        with name.open("x", encoding="ascii") as output:
            output.write(config)
        name.chmod(0o600)
    except OSError:
        raise B06LabError("B06_PRIVATE_CONFIG_DENIED") from None


def _rpc(cli: Path, data: Path, method: str, args=(), *, timeout: int = 30):
    # NEVER expose rpcuser/rpcpassword via process argv or CI logs.
    # Exact typed parameter gates also prevent accidental Core wallet methods
    # and arbitrary caller strings reaching the temporary node.
    if (method not in RPC_LAB_ONLY or type(args) not in (tuple, list)
            or not 1 <= timeout <= 120
            or type(cli) is not type(Path()) or type(data) is not type(Path())
            or not cli.is_absolute() or not data.is_absolute()):
        raise B06LabError("B06_RPC_METHOD_SCOPE_DENIED")
    args=list(args)
    zero=("getblockchaininfo","getnetworkinfo","getpeerinfo",
          "getconnectioncount","getblockcount","getbestblockhash","stop")
    valid=False
    if method in zero:
        valid=not args
    elif method=="getblockhash":
        valid=(len(args)==1 and type(args[0]) is int
               and 0<=args[0]<=10_000)
    elif method=="getblock":
        valid=(len(args)==2 and type(args[0]) is str
               and SHA64.fullmatch(args[0]) is not None
               and args[1] in (2,3,"2","3"))
    elif method=="generatetoaddress":
        valid=(len(args)==2 and type(args[0]) in (int,str)
               and str(args[0]).isdigit() and 1<=int(args[0])<=101
               and type(args[1]) is str
               and args[1].startswith("wamrt1q")
               and 20<=len(args[1])<=128
               and re.fullmatch("[a-z0-9]+",args[1]) is not None)
    elif method=="sendrawtransaction":
        valid=(len(args)==1 and type(args[0]) is str
               and 2<=len(args[0])<=2_000_000
               and len(args[0])%2==0
               and re.fullmatch("[0-9a-f]+",args[0]) is not None)
    elif method in ("addnode","disconnectnode"):
        valid=(len(args)==(2 if method=="addnode" else 1)
               and type(args[0]) is str
               and re.fullmatch(r"127\.0\.0\.1:[1-9][0-9]{3,4}",args[0]) is not None
               and (method!="addnode" or args[1]=="onetry"))
    if not valid:
        raise B06LabError("B06_RPC_METHOD_SCOPE_DENIED")
    cmd = [str(cli), "-datadir=" + str(data), "-rpcconnect=127.0.0.1",
           method, *[str(v) for v in args]]
    try:
        proc = subprocess.run(cmd, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout,
            env={"PATH":"/usr/bin:/bin:/usr/sbin:/sbin","HOME":str(data),"LC_ALL":"C"})
        if proc.returncode or len(proc.stdout) > 32*1024*1024:
            raise B06LabError("B06_NATIVE_CORE_RPC_DENIED")
        raw = proc.stdout.decode("utf-8").strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    except B06LabError:
        raise
    except (OSError, UnicodeError, subprocess.TimeoutExpired):
        raise B06LabError("B06_NATIVE_CORE_RPC_UNAVAILABLE") from None


def _verify_chain(cli, data):
    info = _rpc(cli, data, "getblockchaininfo")
    networks = _rpc(cli, data, "getnetworkinfo")
    genesis = _rpc(cli, data, "getblockhash", (0,))
    if (type(info) is not dict or info.get("chain") != "regtest"
            or genesis != REGTEST_GENESIS
            or type(networks) is not dict
            or (networks.get("version"), networks.get("subversion"),
                networks.get("protocolversion")) != (111, "/WAM:0.1.11/", 70016)):
        raise B06LabError("B06_NATIVE_REGTEST_IDENTITY_DENIED")
    peer_info = _rpc(cli, data, "getpeerinfo")
    if (type(peer_info) is not list
            or any(type(p) is not dict or type(p.get("addr")) is not str
                   or not p["addr"].startswith("127.0.0.1:") for p in peer_info)):
        raise B06LabError("B06_NON_LOCAL_PEER_DENIED")
    return info


class LabReader:
    """Scanner-only adapter for an isolated peer lab; never a wallet transport."""

    def __init__(self, cli: Path, data: Path):
        self.cli, self.data = cli, data

    def attest(self):
        _verify_chain(self.cli, self.data)

    def call(self, method, params=None):
        if method not in RPC_READS or type(params) not in (list, type(None)):
            raise B06LabError("B06_SCANNER_READ_SCOPE_DENIED")
        args = [] if params is None else params
        if method in ("getblockcount","getbestblockhash") and args:
            raise B06LabError("B06_SCANNER_ARGUMENT_DENIED")
        if method == "getblockhash" and (len(args) != 1 or type(args[0]) is not int):
            raise B06LabError("B06_SCANNER_ARGUMENT_DENIED")
        if method == "getblock" and (len(args) != 2 or type(args[0]) is not str
                or SHA64.fullmatch(args[0]) is None or args[1] != 3):
            raise B06LabError("B06_SCANNER_ARGUMENT_DENIED")
        return _rpc(self.cli, self.data, method, args)

    def _call(self, method, args):
        if method not in ("getblock", "generatetoaddress", "sendrawtransaction"):
            raise B06LabError("B06_FIXTURE_WRITE_SCOPE_DENIED")
        if type(args) is not list:
            raise B06LabError("B06_FIXTURE_PARAMS_DENIED")
        return _rpc(self.cli, self.data, method, args, timeout=100)


def _wait(predicate, error, *, timeout=55):
    limit = time.monotonic()+timeout
    while time.monotonic() < limit:
        try:
            if predicate():
                return
        except B06LabError:
            pass
        time.sleep(.25)
    raise B06LabError(error)


class PrivateNode:
    def __init__(self, binary: Path, cli: Path, data: Path, rpcport: int, p2pport: int):
        self.binary, self.cli, self.data = binary, cli, data
        self.rpcport, self.p2pport = rpcport, p2pport
        self.process = None

    def start(self):
        if self.process is not None:
            raise B06LabError("B06_PROCESS_ALREADY_STARTED")
        if not self.data.is_absolute() or not self.data.is_dir():
            raise B06LabError("B06_PROCESS_DIR_DENIED")
        env={"PATH":"/usr/bin:/bin:/usr/sbin:/sbin","HOME":str(self.data),"LC_ALL":"C"}
        try:
            # The file is in the disposable private directory; never upload it.
            with (self.data/"core-output.log").open("ab") as logfile:
                self.process = subprocess.Popen(
                    [str(self.binary),"-datadir="+str(self.data),"-daemon=0"],
                    cwd=self.data,env=env,stdin=subprocess.DEVNULL,
                    stdout=logfile,stderr=subprocess.STDOUT)
            def ready():
                if self.process.poll() is not None:
                    raise B06LabError("B06_PROCESS_EARLY_EXIT")
                _verify_chain(self.cli,self.data)
                return True
            _wait(ready, "B06_PROCESS_START_TIMEOUT",timeout=90)
        except B06LabError:
            raise
        except OSError:
            raise B06LabError("B06_PROCESS_START_DENIED") from None

    def rpc(self, method, *args, timeout=30):
        return _rpc(self.cli, self.data, method, args, timeout=timeout)

    def height(self):
        height=self.rpc("getblockcount")
        if type(height) is not int or not 0 <= height <= 10_000:
            raise B06LabError("B06_HEIGHT_INVALID")
        return height

    def tip(self):
        value=self.rpc("getbestblockhash")
        if type(value) is not str or SHA64.fullmatch(value) is None:
            raise B06LabError("B06_TIP_INVALID")
        return value

    def mine(self, count, address):
        if type(count) is not int or not 1 <= count <= 101:
            raise B06LabError("B06_MINE_BOUND_DENIED")
        value = self.rpc("generatetoaddress",count,address,timeout=120)
        if type(value) is not list or len(value) != count:
            raise B06LabError("B06_REAL_BLOCK_CREATION_DENIED")

    def stop(self):
        p=self.process
        if p is None:
            return
        try:
            if p.poll() is None:
                try: self.rpc("stop",timeout=10)
                except B06LabError: pass
                try:p.wait(timeout=18)
                except subprocess.TimeoutExpired:
                    p.terminate()
                    try:p.wait(timeout=8)
                    except subprocess.TimeoutExpired:p.kill();p.wait(timeout=8)
        finally:
            self.process=None


def _peer(node: PrivateNode, other: PrivateNode):
    target="127.0.0.1:"+str(other.p2pport)
    node.rpc("addnode",target,"onetry")
    _wait(lambda: node.rpc("getconnectioncount") == 1
          and other.rpc("getconnectioncount") == 1, "B06_PEER_CONNECT_TIMEOUT")
    _verify_chain(node.cli,node.data)
    _verify_chain(other.cli,other.data)


def _unlink(node: PrivateNode, other: PrivateNode):
    target="127.0.0.1:"+str(other.p2pport)
    node.rpc("disconnectnode",target)
    _wait(lambda: node.rpc("getconnectioncount") == 0
          and other.rpc("getconnectioncount") == 0, "B06_PEER_DISCONNECT_TIMEOUT")


def _converge(node: PrivateNode, other: PrivateNode):
    _wait(lambda: node.height()==other.height() and node.tip()==other.tip(),
          "B06_REAL_CHAIN_CONVERGENCE_TIMEOUT",timeout=75)


def genuine_two_node_lab(core_dir: Path, wsp_source: Path, *, authorized: bool):
    if (authorized is not True or type(core_dir) is not type(Path())
            or type(wsp_source) is not type(Path())
            or not core_dir.is_absolute() or not wsp_source.is_absolute()
            or core_dir.is_symlink() or wsp_source.is_symlink()
            or sys.platform != "darwin"):
        raise B06LabError("B06_DISPOSABLE_NATIVE_SCOPE_DENIED")
    node, cli, receipt = verified_core_paths(core_dir)
    _pinned_source(wsp_source)
    from wam_sp.core import pub
    from wam_sp.keystore import ScanAccount
    from wam_sp.scanner import Scanner

    if receipt.get("platform") != "macos-arm64":
        raise B06LabError("B06_PINNED_CORE_PLATFORM_DENIED")
    address=public_regtest_mining_address(wsp_source)
    rpc_a,p2p_a,rpc_b,p2p_b=_fresh_ports()
    with tempfile.TemporaryDirectory(prefix="wam-b06-private-regtest-") as location:
        base=Path(location).resolve(strict=True)
        base.chmod(0o700)
        for label in ("node-a","node-b"):
            part=base/label
            part.mkdir(mode=0o700)
        a_dir,b_dir=base/"node-a",base/"node-b"
        make_private_lab_config(a_dir,rpc_a,p2p_a)
        make_private_lab_config(b_dir,rpc_b,p2p_b)
        a=PrivateNode(node,cli,a_dir,rpc_a,p2p_a)
        b=PrivateNode(node,cli,b_dir,rpc_b,p2p_b)
        scanner=None
        try:
            a.start();b.start()
            if a.height()!=0 or b.height()!=0:
                raise B06LabError("B06_NON_FRESH_CHAIN_DENIED")
            a.mine(101,address)
            _peer(a,b);_converge(a,b)
            if a.height()!=101:
                raise B06LabError("B06_MATURITY_HEIGHT_DENIED")
            reader=LabReader(cli,a_dir)
            account=ScanAccount(0,1,pub(2),birthday=1)  # PUBLIC disposable WSP fixture
            scanner=Scanner(a_dir/"b06-original-wsp.sqlite",(account,))
            initial=scanner.sync(reader)
            if initial.blocks!=101 or scanner.store.tip()!=(101,a.tip()) or scanner.coins():
                raise B06LabError("B06_INITIAL_WSP_SQLITE_DENIED")
            rounds=[]
            for depth in DURATIONS:
                _unlink(a,b)
                fork=a.height()
                if fork!=b.height() or a.tip()!=b.tip():
                    raise B06LabError("B06_PRE_FORK_TIP_DENIED")
                fixture_on_old_branch=False
                if depth==1:
                    before=a.height()
                    txid,atoms,new_height=_public_fixture_payment(
                        reader,account,address,expected_before_height=before)
                    if not (type(txid) is str and SHA64.fullmatch(txid)
                            and atoms>0 and new_height==fork+1):
                        raise B06LabError("B06_REAL_BIP352_FIXTURE_DENIED")
                    fixture_on_old_branch=True
                else:
                    a.mine(depth,address)
                orphan_hash=a.tip()
                advanced=scanner.sync(reader)
                old_coins=scanner.coins()
                if (scanner.store.tip()!=(fork+depth,orphan_hash)
                        or advanced.blocks!=depth
                        or (bool(old_coins) != fixture_on_old_branch)):
                    raise B06LabError("B06_ORPHAN_BRANCH_SCAN_DENIED")
                b.mine(depth+1,address)
                if a.tip()==b.tip() or b.height()!=fork+depth+1:
                    raise B06LabError("B06_INDEPENDENT_FORK_DENIED")
                _peer(a,b);_converge(a,b)
                if a.tip()==orphan_hash or a.height()!=fork+depth+1:
                    raise B06LabError("B06_ACTUAL_REORG_DENIED")
                new=scanner.sync(reader)
                if (new.rollback!=depth or scanner.store.tip()!=(a.height(),a.tip())
                        or not scanner.ready or scanner.coins()):
                    raise B06LabError("B06_GENUINE_WSP_REORG_ROLLBACK_DENIED")
                scanner.close()
                scanner=Scanner(a_dir/"b06-original-wsp.sqlite",(account,))
                replay=scanner.sync(reader)
                if replay.blocks!=0 or scanner.store.tip()!=(a.height(),a.tip()):
                    raise B06LabError("B06_WSP_SQLITE_RESTART_DENIED")
                rounds.append({"depth":depth,"independent_live_forks":True,
                               "orphaned_branch_replaced":True,
                               "wsp_sqlite_rollback_blocks":new.rollback,
                               "old_branch_bip352_payment_removed":bool(fixture_on_old_branch),
                               "reopened_original_wsp_scanner":True})
            # Stop/restart ONLY the owned node-B process, preserving its
            # disposable datadir, then prove chain and peer reconnection.
            saved=a.tip()
            _unlink(a,b)
            b.stop()
            b.start()
            if b.tip()!=saved or b.height()!=a.height():
                raise B06LabError("B06_NATIVE_CORE_RESTART_CONTINUITY_DENIED")
            _peer(a,b);_converge(a,b)
            last=scanner.sync(reader)
            if last.blocks!=0 or scanner.store.tip()!=(a.height(),a.tip()):
                raise B06LabError("B06_FINAL_RECONNECT_SCAN_DENIED")
            return {
                "schema":"wam-fusion-issue45-b06-two-node/v1",
                "status":"B06_MACOS_REAL_TWO_NODE_WSP_REORG_E2E_PASS",
                "platform":"macos-arm64", "network":"regtest",
                "core_version":"v0.1.11",
                "verified_core_sha256":receipt["wamd_sha256"],
                "verified_cli_sha256":receipt["wam_cli_sha256"],
                "wsp_source_commit":receipt.get("wsp_source_commit", "ac55f13423620252bdbf848c7e8a280c3b84721e"),
                "two_distinct_live_wamd_processes":True,
                "private_isolated_datadirs":True,
                "loopback_p2p_only":True,
                "genuine_core_rpc":True,
                "synthetic_rpc":False,
                "genuine_wsp_sqlite_rescan":True,
                "node_restart_and_reconnect":True,
                "reorgs":rounds,
                "physical_or_owner_accepted":False,
                "windows_linux_multinode_qualified":False,
                "full_b06_p0_qualified":False,
                "mainnet_allowed":False,
            }
        finally:
            if scanner is not None:scanner.close()
            b.stop();a.stop()


def main():
    p=argparse.ArgumentParser(description="Two-node isolated WAM REGTEST lab")
    p.add_argument("--core-dir",type=Path,required=True)
    p.add_argument("--wsp-source",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--confirm-disposable-regtest",action="store_true")
    args=p.parse_args()
    try:
        if args.output.exists() or args.output.is_symlink():
            raise B06LabError("B06_PUBLIC_RECEIPT_ALREADY_EXISTS")
        result=genuine_two_node_lab(args.core_dir.absolute(),args.wsp_source.absolute(),
                                    authorized=args.confirm_disposable_regtest)
        # Only public non-secret evidence, never datadirs, RPC credentials
        # or temporary sqlite/wallet state.
        with args.output.open("x",encoding="utf-8") as output:
            json.dump(result,output,sort_keys=True,indent=2)
            output.write("\n")
        print(result["status"])
        return 0
    except (B06LabError,OSError,ValueError):
        print("B06_DISPOSABLE_MULTINODE_FAILED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
