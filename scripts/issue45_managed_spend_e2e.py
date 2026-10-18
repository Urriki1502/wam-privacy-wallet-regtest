"""Real original-WSP Send/Sign/Broadcast over owned persistent Core REGTEST.

Separate from public-demo, no mocked RPC/crypto, no user node, no mainnet.
Proves one confirmed BIP352 funding, exact-intent WSP PSBTv2 signing, owned
HTTP submission, native encrypted irreversible reservation, close/reopen.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from wam_regtest.core import _read_cli,verified_core_paths
from wam_regtest.wsp_live import public_regtest_mining_address,_public_fixture_payment
from wam_regtest.wallet_session import WalletCoreCli
from wam_regtest.core_supervisor import ManagedCoreError
from wam_regtest.supervisor_client import control
from wam_regtest.managed_wallet_create import create_managed_wallet
from wam_regtest.managed_spend_session import ManagedWalletSession
from wam_regtest.managed_wallet_reopen import read
from wam_regtest.vault import CheckpointVault
from wam_regtest import custody
from wam_sp.keystore import Keyring


def prove(core_dir,wsp_source):
    with tempfile.TemporaryDirectory(prefix="wam-managed-spend-e2e-") as temporary:
        root=Path(temporary).resolve()/"wam-fusion-core-0123456789abcdef"
        root.mkdir(mode=0o700)
        command=[sys.executable,"-m","wam_regtest.supervisor_cli","serve",
            "--root",str(root),"--core-dir",str(core_dir),
            "--confirm-regtest-managed-core"]
        server=subprocess.Popen(command,stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        stopped=False
        session=None
        recipient=None
        try:
            deadline=time.monotonic()+25
            while time.monotonic()<deadline:
                if server.poll() is not None:
                    raise AssertionError("MANAGED_SPEND_SUPERVISOR_EXITED")
                try:
                    state=control(root,"status",timeout=3)
                    if state["state"]=="stopped":break
                except Exception:time.sleep(.1)
            else:
                raise AssertionError("MANAGED_SPEND_SUPERVISOR_NOT_READY")
            result=control(root,"start",authorized=True,timeout=15)
            # A brand-new REGTEST chain at height 0 may report SYNCING
            # until the disposable 101 blocks exist. Core must nevertheless
            # be the exact owned process, never a foreign/attached daemon.
            assert (result["state"] in ("ready","syncing")
                    and result["core_process_owned"] is True
                    and result["height"]==0)
            _,cli,receipt=verified_core_paths(core_dir)
            directory=root/"chain"
            mine=public_regtest_mining_address(wsp_source)
            blocks=_read_cli([str(cli),f"-datadir={directory}",
                               "generatetoaddress","101",mine],timeout=90)
            assert len(blocks)==101
            assert control(root,"status",timeout=10)["height"]==101
            password=b"managed-regtest-spending-e2e-public-test"
            created=create_managed_wallet(
                root,core_dir,wsp_source,password,authorized=True)
            assert created["wallet_locked"] and not created["signer_allowed"]
            profile=read(directory/"wallet-vault",password)
            anchor=custody.anchor(profile["wallet_id"])
            record=anchor.read()
            assert record is not None
            # Retrieve only the public address from the original encrypted
            # checkpoint; close/delete this privately restored runtime.
            ring,scanner=CheckpointVault(
                directory/"wallet-vault",anchor,wsp_source).restore(
                    directory/"wallet-runtime.sqlite",password)
            try:original_code=ring.accounts()[-1].payment_code()
            finally:
                scanner.close();ring.close()
                (directory/"wallet-runtime.sqlite").unlink(missing_ok=True)
            # Public REGTEST fixture owns scalar 31; actual Core checks its
            # signature and confirms a BIP352 payment to the original wallet.
            rpc=WalletCoreCli(cli,directory);rpc.attest()
            from wam_sp.keystore import ScanAccount
            from wam_sp.core import pub
            # We need the original spend+scan secrets ONLY inside this
            # disposable test interpreter, not the supervisor.
            owner_ring,owner_scan=CheckpointVault(
                directory/"wallet-vault",anchor,wsp_source).restore(
                    directory/"wallet-runtime.sqlite",password)
            try:
                account=owner_ring.accounts()[-1]
                funded_txid,funded_atoms,funded_height=_public_fixture_payment(
                    rpc,account,mine,funding_height=1,expected_before_height=101)
                assert account.payment_code()==original_code
            finally:
                owner_scan.close();owner_ring.close()
                (directory/"wallet-runtime.sqlite").unlink(missing_ok=True)
            assert funded_height==102 and funded_atoms>110000
            # From HERE all native WSP send paths are identical to an
            # operator-unlocked original wallet, no test-only signer RPC.
            session=ManagedWalletSession.reopen_spending(
                root,core_dir,wsp_source,password,authorized=True)
            initial=session.snapshot()
            assert initial.confirmed_atoms==funded_atoms
            assert initial.receive_code==original_code
            assert initial.history and initial.history[0].txid==funded_txid
            recipient=Keyring()
            payment_code=recipient.accounts()[0].payment_code()
            review=session.prepare(payment_code,100000,10000)
            assert review.code==payment_code and review.input_count==1
            # Inherited WalletSession.sign marks selected UTXO 'signed' in
            # native encrypted checkpoint BEFORE calling real WSP Signer.
            session.sign(review.commitment)
            signed_locks=tuple(session.scanner.store.db.execute(
                "SELECT txid,vout,state FROM reservations ORDER BY txid,vout"))
            assert signed_locks and signed_locks[0][2]=="signed"
            signed_anchor=session.vault.anchor.read()
            assert signed_anchor and signed_anchor[0]>record[0]
            txid=session.broadcast(review.commitment)
            assert len(txid)==64 and txid in rpc._call("getrawmempool",[])
            pending=tuple(session.scanner.store.db.execute(
                "SELECT txid,vout,state FROM reservations ORDER BY txid,vout"))
            assert pending and pending[0][2]=="broadcast"
            last_anchor=session.vault.anchor.read()
            session.close();session=None
            assert not (directory/"wallet-runtime.sqlite").exists()
            # Read-only reconnect retains both original keys and the
            # irreversible reservation. No second broadcast or auto retry.
            session=ManagedWalletSession.reopen_spending(
                root,core_dir,wsp_source,password,authorized=True)
            assert session.ring.accounts()[-1].payment_code()==original_code
            assert session.vault.anchor.read()==last_anchor
            reopened=tuple(session.scanner.store.db.execute(
                "SELECT txid,vout,state FROM reservations ORDER BY txid,vout"))
            assert reopened==pending
            assert txid in rpc._call("getrawmempool",[])
            confirmed=_read_cli([str(cli),f"-datadir={directory}",
                "generatetoaddress","1",mine],timeout=45)
            assert len(confirmed)==1
            after=session.snapshot()
            assert after.height==103 and any(
                row.txid==txid and row.confirmations>0 for row in after.history)
            assert session.vault.anchor.read()[0]>=last_anchor[0]
            assert control(root,"status",timeout=10)["height"]==103
            return {"status":"MANAGED_ORIGINAL_WSP_REAL_SPEND_E2E_PASS",
                    "network":"regtest","synthetic_rpc":False,
                    "signed_core_sha256":receipt["wamd_sha256"],
                    "real_confirmed_bip352_funding":True,
                    "genuine_wsp_psbtv2_native_signature":True,
                    "send_via_authenticated_owned_http":True,
                    "signed_reservation_anchored_before_crypto":True,
                    "broadcast_reservation_persisted_before_rpc":True,
                    "exact_original_identity_after_close_reopen":True,
                    "real_core_mempool_and_confirmed":True,
                    "unattended_broadcast_retry":False,
                    "mainnet_allowed":False}
        finally:
            if session is not None:session.close()
            if recipient is not None:recipient.close()
            if server.poll() is None:
                try:
                    outcome=control(root,"shutdown",authorized=True,timeout=15)
                    stopped=outcome["state"]=="stopped"
                except Exception:pass
                if stopped:
                    server.terminate()
                    server.wait(timeout=15)
            if not stopped:
                raise AssertionError("MANAGED_SPEND_SUPERVISOR_STOP_UNVERIFIED")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--core-dir",type=Path,required=True)
    parser.add_argument("--wsp-source",type=Path,required=True)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    result=prove(args.core_dir.resolve(),args.wsp_source.resolve())
    if args.output:
        if args.output.exists():
            raise SystemExit("MANAGED_SPEND_RECEIPT_PATH_OCCUPIED")
        args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(result["status"],flush=True)


if __name__=="__main__":
    main()
