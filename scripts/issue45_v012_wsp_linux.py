"""PR59: genuine pinned-WSP confirmed receive against signed WAM Core 0.1.12.

Opt-in isolated GitHub Linux REGTEST only. No user's datadir, keys, or mining
node. A second independently started/discarded Core instance keeps PR57/58
151-block miner/RPC checks untouched.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from scripts.issue45_v012_native_linux import (
    _prerequisites, _member_copy, _private_rpc,
    Native012Denied)
from scripts.verify_v012_signed_release import (
    KEY, RELEASE, _RestrictedRedirect, _download, LIMITS)
from wam_regtest.core import _port, _write_private_config
from wam_regtest.core_release_preflight import ASSETS, review_offline
from wam_regtest.v012_candidate_compat import (
    exact_signed_linux_candidate, CANDIDATE_VERSION)
from wam_regtest.v012_wsp_linux import prove_public_receive
from wam_regtest.wsp_live import (
    _pinned_source, public_regtest_mining_address, REGTEST_GENESIS)
from urllib import request


class Wsp012ProbeError(ValueError):
    pass


def _deny(code: str):
    raise Wsp012ProbeError(code)


def run_real_wsp(node, cli, hashes, trust, source, source_head) -> dict:
    _pinned_source(source)
    public_address = public_regtest_mining_address(source)
    if not public_address.startswith("wamrt1q"):
        _deny("V012_WSP_PUBLIC_MINING_ADDRESS_DENIED")
    with tempfile.TemporaryDirectory(prefix="wam-v012-wsp-e2e-regtest-") as t:
        directory = Path(t).resolve(strict=True)
        directory.chmod(0o700)
        rpc_port, peer_port = _port(), _port()
        while peer_port == rpc_port:
            peer_port = _port()
        _write_private_config(directory, rpc_port, peer_port)
        env = {"PATH": "/usr/bin:/bin", "HOME": str(directory), "LC_ALL": "C"}
        rpc = _private_rpc(cli, directory, rpc_port, env)
        proc = None
        try:
            with (directory / "core-redacted.log").open("xb") as log:
                proc = subprocess.Popen(
                    [str(node), "-datadir=" + str(directory),
                     "-regtest", "-daemon=0", "-printtoconsole=1"],
                    env=env, cwd=directory, stdin=subprocess.DEVNULL,
                    stdout=log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 90
            while True:
                if proc.poll() is not None:
                    _deny("V012_WSP_CORE_EARLY_EXIT_DENIED")
                try:
                    info = rpc("getblockchaininfo")
                    break
                except Native012Denied:
                    if time.monotonic() >= deadline:
                        _deny("V012_WSP_CORE_START_TIMEOUT")
                    time.sleep(.2)
            version = rpc("getnetworkinfo")
            genesis = rpc("getblockhash", "0")
            peers = rpc("getconnectioncount")
            triple=(version.get("version"),version.get("subversion"),
                    version.get("protocolversion"))
            exact_signed_linux_candidate(
                signed_archive=trust["signed_archive_verified"],
                signer=trust["signer_fingerprint"],
                archive_sha=trust["archive_sha256"],
                node_sha=hashes["wamd"]["sha256"],
                cli_sha=hashes["wam-cli"]["sha256"],
                process_is_owned=proc.poll() is None,
                chain=info.get("chain"), genesis=genesis, peers=peers)
            if triple != CANDIDATE_VERSION or info.get("blocks") != 0:
                _deny("V012_WSP_NETWORK_VERSION_DENIED")
            generated = rpc("generatetoaddress", "101", public_address, timeout=90)
            if (type(generated) is not list or len(generated) != 101 or
                    rpc("getblockcount") != 101 or rpc("getconnectioncount") != 0):
                _deny("V012_WSP_DISPOSABLE_MINE_DENIED")
            proof = prove_public_receive(rpc, directory, source, public_address)
            if (proof["confirmation_height"] != 102 or
                    rpc("getblockcount") != 102 or
                    rpc("getconnectioncount") != 0):
                _deny("V012_WSP_ONCHAIN_RECEIPT_DENIED")
            return {
                "schema": "wam-issue45-v012-linux-wsp-receive/v1",
                "source_head": source_head,
                "observed_utc": datetime.now(timezone.utc).isoformat(),
                "linux_real_signed_core_version": "v0.1.12",
                "network": "regtest",
                "genesis": REGTEST_GENESIS,
                "core_version_rpc": {"version":triple[0],"subversion":triple[1],
                                     "protocolversion":triple[2]},
                "signed_release_key": trust["signer_fingerprint"],
                "signed_archive_sha256": trust["archive_sha256"],
                "binary_sha256": hashes,
                "pinned_wsp_receipt": proof,
                "real_native_core_used": True,
                "real_signed_archive_verified": True,
                "public_fixture_disposable_datadir_only": True,
                "regtest_network_only": True,
                "synthetic_rpc": False,
                "linux_wsp_v012_component_qualified": True,
                "macos_wsp_v012_qualified": False,
                "windows_wsp_v012_qualified": False,
                "fusion_walletsession_v012_qualified": False,
                "operational_signer_authorized": False,
                "frozen_app_v012_qualified": False,
                "physical_dev_accepted": False,
                "mainnet_allowed": False,
            }
        finally:
            if proc is not None and proc.poll() is None:
                try:
                    rpc("stop", timeout=10)
                    proc.wait(timeout=20)
                except (Native012Denied, OSError, subprocess.TimeoutExpired):
                    proc.terminate()
                    try: proc.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=8)
            if proc is not None and proc.poll() is None:
                _deny("V012_WSP_CORE_CLEANUP_DENIED")


def run(source: Path) -> dict:
    _prerequisites(True)
    if (type(source) is not type(Path()) or not source.is_absolute()
            or not source.is_dir() or source.is_symlink()):
        _deny("V012_WSP_SOURCE_PATH_DENIED")
    _pinned_source(source)
    opener = request.build_opener(request.ProxyHandler({}), _RestrictedRedirect())
    with tempfile.TemporaryDirectory(prefix="wam-v012-wsp-signed-") as t:
        stage=Path(t).resolve(strict=True)
        stage.chmod(0o700)
        key,sums,sig=(stage/name for name in
                      ("SIGNING-KEY.asc","SHA256SUMS","SHA256SUMS.asc"))
        archive=stage/ASSETS["linux-x64"]
        for item,url in ((key,KEY),(sums,RELEASE+sums.name),
                         (sig,RELEASE+sig.name),(archive,RELEASE+archive.name)):
            _download(opener,url,item,LIMITS[item.name])
        proof=review_offline(archive,key,sums,sig,"linux-x64",
                             installed="v0.1.11",minimum="v0.1.11")
        if (proof["signed_archive_verified"] is not True or
                proof["installation_authorized"] is not False):
            _deny("V012_WSP_SIGNED_BINARY_DENIED")
        binary_dir=stage/"bins"
        binary_dir.mkdir(mode=0o700)
        node,cli,hashes=_member_copy(archive,binary_dir)
        return run_real_wsp(node,cli,hashes,proof,source,os.environ["WAM_SOURCE_HEAD"])


def main():
    ap=argparse.ArgumentParser(description="CI-only v0.1.12 signed Core real WSP public fixture")
    ap.add_argument("--confirm-disposable-ci-regtest",required=True,action="store_true")
    ap.add_argument("--wsp-source",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    try:
        proof=run(args.wsp_source)
        with args.output.open("x") as out:
            json.dump(proof,out,sort_keys=True,indent=2)
            out.write("\n")
        print("V012_LINUX_PINNED_WSP_BIP352_ONCHAIN_RECEIVE_COMPONENT_PASS")
        return 0
    except (Wsp012ProbeError, Native012Denied) as ex:
        print(str(ex),file=sys.stderr)
        return 2
    except Exception:
        print("V012_WSP_NATIVE_E2E_NOT_QUALIFIED",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
