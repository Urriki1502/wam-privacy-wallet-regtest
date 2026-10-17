"""Isolated Linux WAM Core v0.1.12 REGTEST native-smoke gate (Issue #45 R-02).

This is an explicit *disposable CI test*, NOT a wallet Core loader or update.
Only signed release WAM binaries are executed; the owner's datadir/miner is
never accepted as input. Native macOS, Windows and Fusion wallet remain PENDING.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import argparse
import json
import os
from pathlib import Path
import platform
import stat
import subprocess
import sys
import tarfile
import tempfile
import time

from wam_regtest.core import _port, _write_private_config
from wam_regtest.core_release_preflight import ASSETS, review_offline
from wam_regtest.mining_account import CoinbaseAudit, RewardSplit
from wam_regtest.v1_contracts import rpc_atoms
from wam_regtest.wsp_live import REGTEST_GENESIS
from wam_regtest.v012_candidate_http import probe_candidate_http
from scripts.verify_v012_signed_release import KEY, RELEASE, _RestrictedRedirect, _download, LIMITS
from urllib import request


class Native012Denied(ValueError):
    """Fixed failure categories, never expose response values or private paths."""


def _deny(code: str) -> None:
    raise Native012Denied(code)


def _prerequisites(authorized: bool) -> None:
    if not (authorized is True and sys.platform == "linux"
            and platform.machine() in ("x86_64", "AMD64")
            and os.environ.get("CI") == "true"
            and os.environ.get("GITHUB_ACTIONS") == "true"
            and os.environ.get("WAM_SOURCE_HEAD", "")):
        _deny("V012_NATIVE_RUNNER_SCOPE_DENIED")
    actual = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                            text=True, timeout=10, check=False)
    if actual.returncode or actual.stdout.strip() != os.environ["WAM_SOURCE_HEAD"]:
        _deny("V012_NATIVE_HEAD_DENIED")


def _member_copy(archive: Path, folder: Path) -> tuple[Path, Path, dict]:
    """No bulk extraction, symlinks, paths, or inherited executable state."""
    suffix = "wam-coin-v0.1.12/bin/"
    names = {"wamd": "wamd", "wam-cli": "wam-cli"}
    results = {}
    with tarfile.open(archive, "r:gz") as tar:
        for name in names:
            member = tar.getmember(suffix + name)
            if (not member.isfile() or member.issym() or member.islnk()
                    or not 0 < member.size <= 128 * 1024 * 1024):
                _deny("V012_NATIVE_BINARY_MEMBER_DENIED")
            src = tar.extractfile(member)
            if src is None:
                _deny("V012_NATIVE_BINARY_MEMBER_DENIED")
            dst = folder / name
            fd = os.open(dst, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o700)
            h = sha256()
            with src, os.fdopen(fd, "wb") as out:
                remaining = member.size
                while remaining:
                    chunk = src.read(min(1024 * 1024, remaining))
                    if not chunk:
                        _deny("V012_NATIVE_BINARY_TRUNCATED")
                    h.update(chunk)
                    out.write(chunk)
                    remaining -= len(chunk)
                out.flush()
                os.fsync(out.fileno())
            with dst.open("rb") as inp:
                header = inp.read(20)
            if (header[:5] != b"\x7fELF\x02" or header[5] != 1
                    or header[18:20] != b"\x3e\x00"):
                _deny("V012_NATIVE_ELF_AMD64_DENIED")
            results[name] = {"sha256": h.hexdigest(), "size": member.size}
    return folder / "wamd", folder / "wam-cli", results


def _private_rpc(cli: Path, directory: Path, rpc_port: int, env: dict):
    def call(*parts: str, timeout: int = 25):
        cmd = [str(cli), "-datadir=" + str(directory), "-regtest",
               "-rpcconnect=127.0.0.1", "-rpcport=" + str(rpc_port), *parts]
        try:
            done = subprocess.run(cmd, capture_output=True, env=env,
                                  stdin=subprocess.DEVNULL, timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired):
            _deny("V012_NATIVE_RPC_TIMEOUT_DENIED")
        if done.returncode or len(done.stdout) > 2 * 1024 * 1024:
            _deny("V012_NATIVE_RPC_DENIED")
        value = done.stdout.decode("utf-8", "strict").strip()
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return call


def _verify_native(node: Path, cli: Path, hashes: dict, *, head: str,
                   signer: str, archive_sha: str, signed_archive_verified: bool) -> dict:
    with tempfile.TemporaryDirectory(prefix="wam-v012-exclusive-regtest-") as td:
        directory = Path(td).resolve(strict=True)
        directory.chmod(0o700)
        rpc_port = _port()
        p2p_port = _port()
        while rpc_port == p2p_port:
            p2p_port = _port()
        _write_private_config(directory, rpc_port, p2p_port)
        env = {"PATH": "/usr/bin:/bin", "HOME": str(directory), "LC_ALL": "C"}
        rpc = _private_rpc(cli, directory, rpc_port, env)
        proc = None
        try:
            with (directory / "daemon-output.log").open("xb") as output:
                proc = subprocess.Popen(
                    [str(node), "-datadir=" + str(directory), "-regtest",
                     "-daemon=0", "-printtoconsole=1"], stdin=subprocess.DEVNULL,
                    stdout=output, stderr=subprocess.STDOUT, env=env, cwd=directory)
            deadline = time.monotonic() + 90
            while True:
                if proc.poll() is not None:
                    # Only publish safe error categories and exit code. Raw Core
                    # output remains sealed in the disposable datadir.
                    raw = (directory / "daemon-output.log").read_bytes()[:65536].lower()
                    if b"error while loading shared libraries" in raw:
                        # Public ELF soname only; never print arbitrary daemon
                        # output or any filesystem/credential details.
                        import re
                        m = re.search(
                            rb"error while loading shared libraries: ([a-z0-9_+.-]{1,100}\.so(?:\.[0-9]+)*)",
                            raw)
                        if m:
                            print("V012_NATIVE_MISSING_SONAME=" +
                                  m.group(1).decode("ascii"), file=sys.stderr)
                        _deny("V012_NATIVE_LOADER_DEPENDENCY_DENIED")
                    if b"illegal instruction" in raw or proc.returncode == -4:
                        _deny("V012_NATIVE_CPU_INSTRUCTION_DENIED")
                    if b"segmentation fault" in raw or proc.returncode == -11:
                        _deny("V012_NATIVE_PROCESS_CRASH_DENIED")
                    if b"cannot obtain a lock" in raw or b"already running" in raw:
                        _deny("V012_NATIVE_DATADIR_LOCK_DENIED")
                    if b"failed to bind" in raw or b"address already in use" in raw:
                        _deny("V012_NATIVE_BIND_DENIED")
                    if b"error parsing" in raw or b"not allowed in the default section" in raw:
                        _deny("V012_NATIVE_CONFIG_PARSE_DENIED")
                    if b"cannot open" in raw or b"no such file" in raw:
                        _deny("V012_NATIVE_RESOURCE_DENIED")
                    _deny("V012_NATIVE_CORE_EARLY_EXIT_RC_" + str(abs(proc.returncode)))
                try:
                    chain = rpc("getblockchaininfo")
                    break
                except Native012Denied:
                    if time.monotonic() >= deadline:
                        _deny("V012_NATIVE_CORE_START_TIMEOUT")
                    time.sleep(.3)
            network = rpc("getnetworkinfo")
            if (chain.get("chain") != "regtest" or
                    rpc("getblockhash", "0") != REGTEST_GENESIS or
                    rpc("getconnectioncount") != 0 or
                    network.get("subversion") != "/WAM:0.1.12/" or
                    type(network.get("version")) is not int or
                    network["version"] < 112):
                _deny("V012_NATIVE_CHAIN_VERSION_DENIED")
            rpc("createwallet", "miner")
            rpc("createwallet", "other")
            def miner(*items): return rpc("-rpcwallet=miner", *items)
            def other(*items): return rpc("-rpcwallet=other", *items)
            address = miner("getnewaddress")
            external = other("getnewaddress")
            owned = miner("getaddressinfo", address)
            if owned.get("ismine") is not True:
                _deny("V012_NATIVE_MINER_ADDRESS_DENIED")
            treasury = rpc("getdevfeeinfo")
            if miner("getaddressinfo", treasury["address"]).get("ismine") is not False:
                _deny("V012_NATIVE_TREASURY_OWNERSHIP_DENIED")
            def audit(blockhash: str, height: int) -> dict:
                block = rpc("getblock", blockhash, "2")
                upstream = rpc("getdevfeeinfo", blockhash)["block"]
                result = CoinbaseAudit.from_core(
                    chain="regtest", genesis=REGTEST_GENESIS,
                    block=block, treasury_info=treasury,
                    owned_address_infos=[owned], fees=0)
                split = RewardSplit.regtest(height)
                if (block["height"] != height or
                        result.owned_miner_atoms != split.miner_atoms or
                        result.treasury_paid_atoms != split.treasury_atoms or
                        upstream.get("compliant") is not True or
                        rpc_atoms(upstream["subsidy"]) != result.subsidy_atoms or
                        rpc_atoms(upstream["paid"]) != result.treasury_paid_atoms):
                    _deny("V012_NATIVE_COINBASE_CONSENSUS_DENIED")
                return {"height": height, "subsidy_atoms": result.subsidy_atoms,
                        "miner_atoms": result.owned_miner_atoms,
                        "treasury_atoms": result.treasury_paid_atoms}
            first = rpc("generatetoaddress", "1", address)[0]
            block = rpc("getblock", first, "2")
            first_record = audit(first, 1)
            own_script = owned["scriptPubKey"]
            coinbase = block["tx"][0]
            own_vout = next((v["n"] for v in coinbase["vout"]
                             if v["scriptPubKey"]["hex"] == own_script), None)
            if own_vout is None:
                _deny("V012_NATIVE_COINBASE_OWNER_DENIED")
            rpc("generatetoaddress", "98", external, timeout=90)
            maturity = []
            for depth in (99, 100, 101):
                if rpc("getblockcount") != depth:
                    _deny("V012_NATIVE_MATURITY_HEIGHT_DENIED")
                out = rpc("gettxout", coinbase["txid"], str(own_vout))
                balances = miner("getbalances")["mine"]
                unspent = miner("listunspent", "0")
                included = any(u["txid"] == coinbase["txid"]
                               and u["vout"] == own_vout for u in unspent)
                if (not isinstance(out, dict) or out.get("coinbase") is not True
                        or out.get("confirmations") != depth
                        or included != (depth == 101)):
                    _deny("V012_NATIVE_MATURITY_ELIGIBILITY_DENIED")
                expected_trusted = "47.50000000" if depth == 101 else "0.00000000"
                expected_immature = "0.00000000" if depth == 101 else "47.50000000"
                if (rpc_atoms(balances["trusted"]) != rpc_atoms(expected_trusted)
                        or rpc_atoms(balances["immature"]) != rpc_atoms(expected_immature)):
                    _deny("V012_NATIVE_MATURITY_BALANCE_DENIED")
                maturity.append({"depth": depth, "eligible": included})
                if depth != 101:
                    rpc("generatetoaddress", "1", external)
            boundary = [first_record]
            for height in (149, 150, 151):
                count = height - rpc("getblockcount")
                if count <= 0:
                    _deny("V012_NATIVE_BOUNDARY_HEIGHT_DENIED")
                mined_blocks = rpc("generatetoaddress", str(count), address, timeout=90)
                boundary.append(audit(mined_blocks[-1], height))
            schedule = rpc("getemissionschedule")
            if ([(e["first_height"], e["last_height"]) for e in schedule[:3]]
                    != [(1, 150), (151, 300), (301, 450)] or
                    rpc("getconnectioncount") != 0):
                _deny("V012_NATIVE_REGTEST_SCHEDULE_DENIED")
            # Probe genuine Core 0.1.12 authenticated HTTP via a separately
            # pinned, test-only candidate path. Never relax ManagedReadRpc.
            http_read = probe_candidate_http(
                node=node, process=proc, directory=directory, port=rpc_port,
                official_signer=signer, official_archive_sha=archive_sha,
                signed_archive_verified=signed_archive_verified,
                node_sha=hashes["wamd"]["sha256"], cli_sha=hashes["wam-cli"]["sha256"],
                expected_height=151)
            return {
                "schema": "wam-v012-official-linux-regtest-smoke/v1",
                "v012_http_candidate": http_read,
                "status": "V012_SIGNED_LINUX_CORE_REGTEST_COMPONENT_PASS",
                "observed_utc": datetime.now(timezone.utc).isoformat(),
                "source_head": head, "core_version": "v0.1.12",
                "networkinfo": {"version": network["version"],
                                "subversion": network["subversion"],
                                "protocolversion": network.get("protocolversion")},
                "genesis": REGTEST_GENESIS, "network": "regtest",
                "linux_binary_sha256": hashes,
                "real_disposable_core": True,
                "synthetic_rpc": False,
                "mined_block_count": 151,
                "maturity": maturity,
                "coinbase_boundaries": boundary,
                "regtest_halving_interval": 150,
                "treasury_cutoff_tested_at_400001": False,
                "zero_external_peers": True,
                "macos_v012_qualified": False,
                "windows_v012_qualified": False,
                "wallet_fusion_v012_runtime_authorized": False,
                "bip94_regtest_full_qualified": False,
                "regtest_fusion_e2e_qualified": False,
                "frozen_v012_qualified": False,
                "physical_reviewed": False,
                "mainnet_allowed": False,
            }
        finally:
            if proc is not None and proc.poll() is None:
                try:
                    rpc("stop", timeout=10)
                    proc.wait(timeout=15)
                except (Native012Denied, OSError, subprocess.TimeoutExpired):
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=10)
            if proc is not None and proc.poll() is None:
                _deny("V012_NATIVE_PROCESS_CLEANUP_DENIED")


def run(*, authorized: bool) -> dict:
    _prerequisites(authorized)
    opener = request.build_opener(request.ProxyHandler({}), _RestrictedRedirect())
    with tempfile.TemporaryDirectory(prefix="wam-v012-native-intake-") as td:
        stage = Path(td).resolve(strict=True)
        stage.chmod(0o700)
        key, sums, sig = (stage / s for s in ("SIGNING-KEY.asc", "SHA256SUMS", "SHA256SUMS.asc"))
        archive = stage / ASSETS["linux-x64"]
        for path, url in ((key, KEY), (sums, RELEASE + sums.name),
                          (sig, RELEASE + sig.name), (archive, RELEASE + archive.name)):
            _download(opener, url, path, LIMITS[path.name])
        trust = review_offline(
            archive, key, sums, sig, "linux-x64",
            installed="v0.1.11", minimum="v0.1.11")
        if (trust["signed_archive_verified"] is not True or
                trust["installation_authorized"] is not False or
                trust["core_version_profile_qualified"] is not False):
            _deny("V012_NATIVE_ARCHIVE_TRUST_DENIED")
        binary_dir = stage / "bins"
        binary_dir.mkdir(mode=0o700)
        node, cli, hashes = _member_copy(archive, binary_dir)
        outcome = _verify_native(node, cli, hashes, head=os.environ["WAM_SOURCE_HEAD"],
                                 signer=trust["signer_fingerprint"],
                                 archive_sha=trust["archive_sha256"],
                                 signed_archive_verified=trust["signed_archive_verified"])
        outcome.update({
            "signer_fingerprint": trust["signer_fingerprint"],
            "official_archive_sha256": trust["archive_sha256"],
            "signed_release_cryptographic_verification": True,
        })
        return outcome


def main() -> int:
    ap = argparse.ArgumentParser(description="Disposable official v0.1.12 Linux REGTEST probe")
    ap.add_argument("--confirm-isolated-disposable-ci-regtest",
                    action="store_true", required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    try:
        proof = run(authorized=args.confirm_isolated_disposable_ci_regtest)
        if args.output.exists() or not args.output.parent.is_dir():
            _deny("V012_NATIVE_EVIDENCE_DESTINATION_DENIED")
        with args.output.open("x") as output:
            json.dump(proof, output, sort_keys=True, indent=2)
            output.write("\n")
        print(proof["status"])
        return 0
    except Native012Denied as error:
        print(str(error), file=sys.stderr)
        return 2
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, IndexError,
            tarfile.TarError, subprocess.SubprocessError):
        print("V012_NATIVE_REGTEST_NOT_QUALIFIED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
