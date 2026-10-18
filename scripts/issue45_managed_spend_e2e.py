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


def prove(core_dir,wsp_source,*,bip39=False,
          linux_manifest=None,linux_witness=None):
    if sys.platform=="linux":
        # Same independent root witness and developer Core trust policy as
        # the existing real Linux xcb/headless wallet acceptance.
        if type(linux_manifest) is not str or linux_witness is None:
            raise ValueError("K03_LINUX_NATIVE_WITNESS_REQUIRED")
        from wam_regtest.linux_runtime import configure,policy
        from wam_regtest.linux_developer_core import LinuxCoreError
        try:
            existing=policy()
        except LinuxCoreError as error:
            if error.args!=('LINUX_EXPLICIT_CORE_AND_WITNESS_POLICY_REQUIRED',):
                raise
            configure(core_dir,linux_manifest,linux_witness,authorized=True)
        else:
            # Policy is immutable process-wide and already authenticated by
            # native Linux wallet acceptance. Reuse only the EXACT approved
            # pinned Core, immutable developer manifest and independent
            # root witness; never reset policy or accept foreign selectors.
            if (existing.core!=core_dir
                    or existing.manifest_sha256!=linux_manifest
                    or existing.witness!=linux_witness):
                raise ValueError('K03_LINUX_BOUND_POLICY_MISMATCH')
    with tempfile.TemporaryDirectory(prefix="wam-managed-spend-e2e-") as temporary:
        root=Path(temporary).resolve()/"wam-fusion-core-0123456789abcdef"
        if sys.platform=="win32":
            from wam_regtest.custody import create_directory
            create_directory(root)  # native NTFS DACL, not chmod emulation
        else:
            root.mkdir(mode=0o700)
        command=[sys.executable,"-m","wam_regtest.supervisor_cli","serve",
            "--root",str(root),"--core-dir",str(core_dir),
            "--confirm-regtest-managed-core"]
        if sys.platform=="linux":
            command.extend(["--linux-developer-manifest",linux_manifest,
                            "--linux-root-witness",str(linux_witness)])
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
            # T-02: exercise cross-capability refusal against the REAL,
            # native Core-owning supervisor socket before funding any wallet.
            # No Core JSON-RPC response is mocked and no transaction is sent.
            from wam_regtest.core_supervisor import _profile_read
            from wam_regtest.supervisor_store import read_exact
            from wam_regtest.managed_scan_protocol import encode_request as scan_request
            from wam_regtest.managed_spend_protocol import encode_request as spend_request
            from wam_regtest.supervisor_protocol import PROTOCOL,request_proof
            import secrets
            import socket
            profile_port=_profile_read(root)["control_port"]
            control_token=read_exact(root,"supervisor.token",length=32)
            scan_token=read_exact(root,"supervisor.scan.token",length=32)
            spend_token=read_exact(root,"supervisor.spend.token",length=32)
            assert len({control_token,scan_token,spend_token})==3
            nonce=secrets.token_hex(16)
            bad_control=(json.dumps({"protocol":PROTOCOL,"op":"shutdown",
                "nonce":nonce,"proof":request_proof(scan_token,"shutdown",nonce)},
                sort_keys=True,separators=(",",":"))+"\n").encode("ascii")
            invalid_frames=(
                spend_request(scan_token,"gettxout",["a"*64,0,True],
                              secrets.token_hex(16)),
                scan_request(spend_token,"getblockcount",[],secrets.token_hex(16)),
                bad_control,
            )
            before_cross_scope=control(root,"status",timeout=10)
            for frame in invalid_frames:
                with socket.create_connection(("127.0.0.1",profile_port),timeout=3) as conn:
                    conn.settimeout(3)
                    conn.sendall(frame)
                    received=bytearray()
                    while len(received)<1024:
                        chunk=conn.recv(min(1024-len(received),256))
                        if not chunk:break
                        received.extend(chunk)
                        if b"\n" in chunk:break
                refusal=json.loads(bytes(received).decode("ascii"))
                assert refusal["state"]=="error" and refusal["mainnet_allowed"] is False
            assert control(root,"status",timeout=10)==before_cross_scope
            password=b"managed-regtest-spending-e2e-public-test"
            k03_phrase=k03_passphrase=None
            if bip39:
                # Public deterministic REGTEST fixture ONLY; never private
                # owner words. Native K-03 wallet uses separate 64-byte keys,
                # authenticated native vault and the SAME real WSP signer.
                from mnemonic import Mnemonic
                k03_phrase=Mnemonic("english").to_mnemonic(bytes([0x42])*32)
                k03_passphrase="public-K03-bip39-test"
            created=create_managed_wallet(
                root,core_dir,wsp_source,password,authorized=True,
                bip39_phrase=k03_phrase,bip39_passphrase=k03_passphrase)
            k03_phrase=k03_passphrase=None
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
            try:
                original_code=ring.accounts()[-1].payment_code()
                if bip39:
                    from wam_regtest.bip39_durable import Bip39DurableKeyring
                    from wam_regtest.bip39_wallet import Bip39RegtestKeys
                    from mnemonic import Mnemonic
                    assert type(ring) is Bip39DurableKeyring
                    with Bip39RegtestKeys(
                        Mnemonic("english").to_mnemonic(bytes([0x42])*32),
                        source=wsp_source,passphrase="public-K03-bip39-test",
                        authorized_disposable=True) as independent:
                        assert original_code==independent.public_metadata(0)["receive_code"]
                        assert ring.spend_secret(0)==independent._key(0,"spend")
                else:
                    assert type(ring) is Keyring
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
            # T-01: genuine WSP Scanner/Qt-backed wallet observations reuse
            # authenticated HTTP over the existing Core supervisor. After the
            # one-time signed Core intake, block legacy CLI and Core/CLI hash
            # entrypoints in THIS interpreter (not in the real Core process).
            # No mocked RPC result, wallet balance or blockchain is supplied.
            from wam_regtest.http_session_probe import forbid_core_cli_reads
            with forbid_core_cli_reads():
                repeat_one=session.snapshot()
                repeat_two=session.snapshot()
            assert repeat_one==initial and repeat_two==initial
            assert initial.confirmed_atoms==funded_atoms
            assert initial.receive_code==original_code
            assert initial.history and initial.history[0].txid==funded_txid
            recipient=Keyring()
            payment_code=recipient.accounts()[0].payment_code()
            # Exercise the REAL Fusion Qt Send UI and its modal approval
            # dialogs. It invokes the inherited WSP coordinator, but only
            # through the dedicated authenticated owned-Core spend transport.
            from wam_regtest.desktop import qt_application
            from wam_regtest.managed_operational_gui import ManagedOperationalWalletWindow
            from wam_regtest.wallet_probe import _operation,_approve_dialog
            from shiboken6 import delete
            app=qt_application()
            window=ManagedOperationalWalletWindow(session)
            window.show()
            app.processEvents()
            window.apply_snapshot(initial)
            assert window._snapshot is initial
            assert window.prepare_button.isEnabled()
            assert not window.mine_button.isEnabled()
            assert not window.recover_button.isEnabled()
            window.recipient.setText(payment_code)
            window.amount.setText("0.00100000")
            window.fee.setText("0.00010000")
            review=_operation(app,window,"prepare",window.prepare_button.click)
            assert review.code==payment_code and review.input_count==1
            assert not window.broadcast_button.isEnabled()
            # Inherited WalletSession.sign marks selected UTXO 'signed' in
            # native encrypted checkpoint BEFORE calling real WSP Signer.
            signed_review=_operation(
                app,window,"sign",
                lambda:_approve_dialog(app,window,window.sign_button))
            assert signed_review.commitment==review.commitment
            signed_locks=tuple(session.scanner.store.db.execute(
                "SELECT txid,vout,state FROM reservations ORDER BY txid,vout"))
            assert signed_locks and signed_locks[0][2]=="signed"
            signed_anchor=session.vault.anchor.read()
            assert signed_anchor and signed_anchor[0]>record[0]
            txid=_operation(
                app,window,"broadcast",
                lambda:_approve_dialog(app,window,window.broadcast_button))
            assert len(txid)==64 and txid in rpc._call("getrawmempool",[])
            assert window._submitted_txid==txid
            pending=tuple(session.scanner.store.db.execute(
                "SELECT txid,vout,state FROM reservations ORDER BY txid,vout"))
            assert pending and pending[0][2]=="broadcast"
            last_anchor=session.vault.anchor.read()
            assert window.close()
            delete(window)
            app.processEvents()
            window=None
            session=None  # closeEvent locked and closed original WSP session
            assert not (directory/"wallet-runtime.sqlite").exists()
            # Read-only reconnect retains both original keys and the
            # irreversible reservation. No second broadcast or auto retry.
            session=ManagedWalletSession.reopen_spending(
                root,core_dir,wsp_source,password,authorized=True)
            assert session.ring.accounts()[-1].payment_code()==original_code
            if bip39:
                from wam_regtest.bip39_durable import Bip39DurableKeyring
                assert type(session.ring) is Bip39DurableKeyring
            else:
                assert type(session.ring) is Keyring
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
            return {"status":("K03_BIP39_DURABLE_REAL_WSP_SPEND_E2E_PASS"
                              if bip39 else
                              "MANAGED_ORIGINAL_WSP_REAL_SPEND_E2E_PASS"),
                    "k03_bip39_native_seed_to_signer":bip39,
                    "k03_legacy_wsp32_preserved":not bip39,
                    "network":"regtest","synthetic_rpc":False,
                    "signed_core_sha256":receipt["wamd_sha256"],
                    "real_confirmed_bip352_funding":True,
                    "genuine_wsp_psbtv2_native_signature":True,
                    "actual_native_fusion_qt_send_sign_broadcast":True,
                    "send_via_authenticated_owned_http":True,
                    "t01_managed_reads_without_cli_or_binary_rehash":True,
                    "t02_scoped_ipc_cross_authority_real_supervisor_denied":True,
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
    parser.add_argument("--bip39",action="store_true",
                        help="Only public deterministic BIP39 REGTEST test wallet")
    parser.add_argument("--linux-developer-manifest")
    parser.add_argument("--linux-root-witness",type=Path)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    from wam_regtest.desktop import shutdown_qt
    try:
        result=prove(args.core_dir.resolve(),args.wsp_source.resolve(),
                     bip39=args.bip39,
                     linux_manifest=args.linux_developer_manifest,
                     linux_witness=args.linux_root_witness)
    finally:
        shutdown_qt()
    if args.output:
        if args.output.exists():
            raise SystemExit("MANAGED_SPEND_RECEIPT_PATH_OCCUPIED")
        args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(result["status"],flush=True)


if __name__=="__main__":
    main()
