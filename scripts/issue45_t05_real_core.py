"""Real signed WAM Core v0.1.11 T05 lifecycle: no mock RPC or secret output.

The enclosing CI uses a disposable test root. The *managed Core itself* never
deletes its datadir, including clean close and simulated daemon crash.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
import tempfile
from wam_regtest.core_supervisor import CoreSupervisor,ManagedCoreError
from wam_regtest.core import _read_cli


def _closed(owner):
    owner.close_listener()
    owner.stack.close()


def _qt_reopen_probe(root, expected_height):
    """Drive actual Fusion widgets with genuine supervisor IPC; no wallet mock."""
    from wam_regtest.desktop import qt_application
    from wam_regtest.managed_gui import ManagedCoreWindow
    app=qt_application()
    for reopen in range(2):
        window=ManagedCoreWindow(root)
        window.show()
        try:
            window.request_sync()
            deadline=time.monotonic()+25
            while time.monotonic()<deadline:
                app.processEvents()
                if window._worker is None:
                    if window._managed_authenticated and window._managed_state=="ready":
                        break
                    raise AssertionError("T05_FUSION_GUI_CORE_UNVERIFIED")
                time.sleep(.01)
            else:raise AssertionError("T05_FUSION_GUI_SYNC_TIMEOUT")
            assert "READY" in window.verification_badge.text()
            assert " · height "+str(expected_height)+" · " in window.status.text()
            assert window._snapshot is None and window.session is None
            assert window.dashboard.go_send.isEnabled() is False
        finally:
            if not window.close():
                raise AssertionError("T05_FUSION_GUI_CLOSE_DENIED")
            # Deterministically release QWidget before Python's Qt teardown.
            from shiboken6 import delete
            delete(window)
            app.processEvents()


def _qt_process_probe(root, expected_height):
    """Three real GUI interpreters: clean close, abrupt crash, verified reopen."""
    import queue
    import threading
    command = [sys.executable, "-m", "wam_regtest.managed_gui_probe",
        "--root", str(root), "--expected-height", str(expected_height),
        "--confirm-disposable-regtest-probe"]
    expected = {"height": expected_height, "wallet_adopted": False,
                "authenticated_gui_ready": True}
    def clean():
        result = subprocess.run(command, stdin=subprocess.DEVNULL,
            capture_output=True, timeout=40)
        if result.returncode != 0:
            raise AssertionError("T05_GUI_CLEAN_PROCESS_EXIT_DENIED")
        assert json.loads(result.stdout) == {**expected, "native_shutdown_completed": True}
    clean()
    child = subprocess.Popen(command + ["--wait-for-crash"],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    line = queue.Queue(maxsize=1)
    # Portable bounded pipe readiness; Windows does not support select on pipes.
    reader = threading.Thread(target=lambda: line.put(child.stdout.readline(1025)), daemon=True)
    reader.start()
    try:
        ready = line.get(timeout=35)
        assert len(ready) <= 1024 and json.loads(ready) == expected
        assert child.poll() is None
        # Kill only the actual GUI Popen created above, after real Qt and IPC
        # verification. No synthetic os._exit stand-in for this acceptance case.
        child.kill()
        assert child.wait(timeout=10) != 0
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
        reader.join(timeout=3)
        child.stdout.close()
        assert not reader.is_alive()
    clean()



def _qt_original_wallet_live_read_probe(root, core, expected_height, funding_address):
    """Actual macOS WSP encrypted wallet -> native GUI -> managed Core IPC.

    Builds a fresh disposable WSP account on the already independently owned
    REGTEST chain, stores its *real* Keyring and Scanner in a native-anchored
    encrypted checkpoint, and opens the real Fusion GUI twice. No mocks of
    RPC, scanner, Core, wallet state or Qt. Only the user password dialog is
    provided by the explicit test operator harness.
    """
    if sys.platform!="darwin":
        raise AssertionError("Q05_MACOS_NATIVE_ONLY")
    from unittest.mock import patch
    from shiboken6 import delete
    from wam_regtest import custody
    from wam_regtest.core import verified_core_paths
    from wam_regtest.managed_wallet_create import create_managed_wallet
    from wam_regtest.managed_wallet_reopen import read
    from wam_regtest.vault import CheckpointVault
    from wam_regtest.managed_scan_client import ManagedScanRpc
    from wam_regtest.wsp_live import _pinned_source
    from wam_regtest.desktop import qt_application
    from wam_regtest.managed_gui import ManagedCoreWindow
    from wam_regtest.supervisor_client import control
    from wam_sp.keystore import Keyring

    wsp=Path(__file__).resolve().parents[1]/"wsp-upstream"
    _pinned_source(wsp)
    _,native_cli,receipt=verified_core_paths(core)
    password=b"q05-disposable-native-verified-regtest-only"
    directory=root/"chain"
    vault_dir=directory/"wallet-vault"
    runtime=directory/"wallet-runtime.sqlite"

    # This is now the SAME operator-facing create-once path used by Fusion.
    # No manual test-only Keyring/Scanner provisioning or direct supervisor
    # wallet creation is substituted. A real native Keychain anchor is written.
    created=create_managed_wallet(root,core,wsp,password,authorized=True)
    assert created=={
        "status":"MANAGED_REGTEST_WSP_WALLET_CREATED_LOCKED",
        "network":"regtest","wallet_locked":True,
        "signer_allowed":False,"broadcast_allowed":False,"mainnet_allowed":False}
    profile=read(vault_dir,password)
    wallet_id=profile["wallet_id"]
    anchor=custody.anchor(wallet_id)
    vault=CheckpointVault(vault_dir,anchor,wsp)
    ring=scanner=None
    try:
        ring,scanner=vault.restore(runtime,password)
        original_receive=ring.accounts()[-1].payment_code()
        payment_account=ring.accounts()[-1]
        assert vault._expected==anchor.read()
    finally:
        if scanner is not None:scanner.close()
        if ring is not None:ring.close()
        if scanner is not None:runtime.unlink(missing_ok=True)

    # The public REGTEST miner coinbase was generated to scalar=31 at height
    # 1. This submits and CONFIRMS a genuine BIP352 payment to the ORIGINAL
    # encrypted WSP account after its initial checkpoint was sealed.
    from wam_regtest.wallet_session import WalletCoreCli
    from wam_regtest.wsp_live import _public_fixture_payment
    payment_rpc=WalletCoreCli(native_cli,directory)
    payment_rpc.attest()
    txid,expected_atoms,funded_height=_public_fixture_payment(
        payment_rpc,payment_account,funding_address,
        funding_height=1,expected_before_height=expected_height)
    assert funded_height==expected_height+1 and expected_atoms>0
    payment_account=None

    # Native WSP reservation: prepare a disposable signed PSBT from a
    # GENUINE confirmed coin, anchor the irreversible lock BEFORE signing,
    # and never broadcast it. The supervisor never sees the spending key.
    from wam_sp.wallet import Wallet,Intent,Signer
    from wam_sp.psbt import PSBT
    locked_ring=locked_scanner=locked_rpc=recipient=None
    try:
        locked_ring,locked_scanner=vault.restore(runtime,password)
        locked_rpc=ManagedScanRpc(root,authorized_readonly=True)
        locked_scanner.sync(locked_rpc)
        locked_scanner.assert_current()
        locked_wallet=Wallet(locked_scanner)
        assert locked_wallet.balance()["confirmed_atoms"]==expected_atoms
        recipient=Keyring()
        approved_intent=Intent(recipient.accounts()[0].payment_code(),100_000)
        approved_fee=10_000
        proposal=locked_wallet.propose((approved_intent,),approved_fee)
        prepared=Signer(locked_ring).prepare(proposal)
        locked_wallet.mark_signed(proposal.token)
        vault.save(locked_ring,locked_scanner,password)
        signed=Signer(locked_ring).sign(
            prepared,proposal.intents,approved_fee)
        assert PSBT.decode(signed).finalize()
        reservation_rows=tuple(locked_scanner.store.db.execute(
            "SELECT txid,vout,token,state FROM reservations ORDER BY txid,vout"))
        assert len(reservation_rows)==1
        assert reservation_rows[0][2]==proposal.token
        assert reservation_rows[0][3]=="signed"
        assert locked_wallet.balance()["available_atoms"]==0
        anchored_reservation=anchor.read()
        assert anchored_reservation==vault._expected
    finally:
        if locked_scanner is not None:locked_scanner.close()
        if locked_ring is not None:locked_ring.close()
        if locked_rpc is not None:locked_rpc.close()
        if recipient is not None:recipient.close()
        if locked_scanner is not None:runtime.unlink(missing_ok=True)
    assert not runtime.exists()

    # A THIRD interpreter holds a REAL native GUI, reads the encrypted
    # original wallet through authenticated supervisor RPC, then terminates
    # abruptly. It sends no transaction and does not control/stop Core.
    # Password travels only through a bounded private test stdin pipe, never
    # in process arguments, logs, CLI flags or the supervisor protocol.
    crashed_gui=r'''
import json,os,sys,time
from pathlib import Path
from unittest.mock import patch
from wam_regtest.desktop import qt_application
from wam_regtest.managed_gui import ManagedCoreWindow
from wam_regtest.supervisor_client import control
root,core,wsp=(Path(x) for x in sys.argv[1:4])
password=sys.stdin.buffer.readline(1025).strip()
if not 12<=len(password)<=1024:raise SystemExit(2)
app=qt_application()
window=ManagedCoreWindow(root,core_dir=core,wsp_source=wsp)
window.show()
window._apply_managed_status(control(root,"status",timeout=10))
if not window.view_wallet_button.isEnabled():raise SystemExit(2)
with patch("wam_regtest.managed_gui.QInputDialog.getText",
           return_value=(password.decode("ascii"),True)):
    window.view_wallet_button.click()
deadline=time.monotonic()+90
while window._worker is not None and time.monotonic()<deadline:
    app.processEvents()
    time.sleep(.01)
app.processEvents()
snap=window._snapshot
if (snap is None or snap.signer_allowed or snap.broadcast_allowed
        or snap.demo_account_only or snap.synthetic_rpc
        or window.session is not None):raise SystemExit(2)
print(json.dumps({"status":"Q05_REAL_ORIGINAL_WALLET_GUI_READY_BEFORE_KILL",
                  "height":snap.height,"confirmed_atoms":snap.confirmed_atoms,
                  "history_txid":snap.history[0].txid if snap.history else None,
                  "mainnet_allowed":False},sort_keys=True),flush=True)
os._exit(41)
'''
    killed=subprocess.run(
        [sys.executable,"-X","faulthandler","-c",crashed_gui,
         str(root),str(core),str(wsp)],
        input=password+b"\n",stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
        timeout=110,check=False)
    assert killed.returncode==41
    killed_receipt=json.loads(killed.stdout)
    assert killed_receipt=={
        "status":"Q05_REAL_ORIGINAL_WALLET_GUI_READY_BEFORE_KILL",
        "height":funded_height,
        "confirmed_atoms":expected_atoms,
        "history_txid":txid,"mainnet_allowed":False,
    }
    assert not runtime.exists()
    assert control(root,"status",timeout=10)["height"]==funded_height
    assert _read_cli([str(native_cli),f"-datadir={directory}",
                     "getblockhash",str(funded_height)])==payment_rpc.call(
                         "getblockhash",[funded_height])

    app=qt_application()
    original_tip=control(root,"status",timeout=10)["height"]
    assert original_tip==funded_height
    for i in range(2):
        window=ManagedCoreWindow(root,core_dir=core,wsp_source=wsp)
        window.show()
        try:
            window._apply_managed_status(control(root,"status",timeout=10))
            assert window.view_wallet_button.isEnabled()
            with patch("wam_regtest.managed_gui.QInputDialog.getText",
                       return_value=(password.decode("ascii"),True)):
                window.view_wallet_button.click()
                assert window._worker is not None
                deadline=time.monotonic()+90
                while window._worker is not None and time.monotonic()<deadline:
                    app.processEvents()
                    time.sleep(.01)
            if window._worker is not None:
                raise AssertionError("Q05_REAL_NATIVE_WALLET_GUI_WORKER_TIMEOUT")
            app.processEvents()
            snapshot=window._snapshot
            assert snapshot is not None
            assert snapshot.demo_account_only is False
            assert snapshot.synthetic_rpc is False
            assert snapshot.signer_allowed is False
            assert snapshot.broadcast_allowed is False
            assert snapshot.mainnet_allowed is False
            assert snapshot.height==funded_height
            assert snapshot.receive_code==original_receive
            assert snapshot.confirmed_atoms==expected_atoms
            assert snapshot.confirmed_utxos==1
            assert len(snapshot.history)==1
            assert snapshot.history[0].txid==txid
            assert snapshot.history[0].credit_atoms==expected_atoms
            assert snapshot.history[0].confirmations==1
            assert window.history_page.table.rowCount()==1
            assert window.receive_page.code==original_receive
            assert window.session is None
            assert window.dashboard.go_send.isEnabled() is False
            assert control(root,"status",timeout=10)["height"]==funded_height
        finally:
            if not window.close():
                raise AssertionError("Q05_REAL_NATIVE_WALLET_GUI_CLOSE_DENIED")
            delete(window)
            app.processEvents()
    assert not runtime.exists()
    assert control(root,"status",timeout=10)["height"]==funded_height
    assert anchor.read()==anchored_reservation
    # Prove that both GUI reads and an abrupt GUI death preserved the actual
    # committed WSP signed reservation. A new process may restore this state,
    # but NO GUI action may release/retry an uncertain transaction.
    verify_ring=verify_scan=None
    try:
        verify_ring,verify_scan=vault.restore(runtime,password)
        current_rows=tuple(verify_scan.store.db.execute(
            "SELECT txid,vout,token,state FROM reservations ORDER BY txid,vout"))
        assert current_rows==reservation_rows
    finally:
        if verify_scan is not None:verify_scan.close()
        if verify_ring is not None:verify_ring.close()
        if verify_scan is not None:runtime.unlink(missing_ok=True)
    assert not runtime.exists()

    # Kill a DIFFERENT interpreter inside an open genuine SQLite write
    # transaction after restoring the original encrypted/anchored WSP state.
    # A rollback journal/private runtime may remain. Neither our GUI nor
    # vault is permitted to "repair" that unexplained file automatically.
    sqlite_crash=r'''
import os,sys
from pathlib import Path
from wam_regtest import custody
from wam_regtest.vault import CheckpointVault
root=Path(sys.argv[1])
wsp=Path(sys.argv[2])
wallet_id=sys.argv[3]
password=sys.stdin.buffer.readline(1025).strip()
if not 12<=len(password)<=1024:raise SystemExit(2)
folder=root/"chain"/"wallet-vault"
runtime=root/"chain"/"wallet-runtime.sqlite"
anchor=custody.anchor(wallet_id)
vault=CheckpointVault(folder,anchor,wsp)
ring,scanner=vault.restore(runtime,password)
with scanner.store.transaction():
    scanner.store.db.execute(
        "INSERT INTO contacts(id,name,code) VALUES(?,?,?)",
        ("crash-test-contact","NOT_COMMITTED",ring.accounts()[-1].payment_code()))
    print("Q05_REAL_SQLITE_TRANSACTION_OPEN_BEFORE_COMMIT",flush=True)
    os._exit(42)
'''
    from hashlib import sha256 as _sha256
    checkpoint_file=vault_dir/CheckpointVault._filename(anchored_reservation[0])
    checkpoint_digest=_sha256(checkpoint_file.read_bytes()).hexdigest()
    crashed_sqlite=subprocess.run(
        [sys.executable,"-c",sqlite_crash,str(root),str(wsp),wallet_id],
        input=password+b"\n",stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
        timeout=90,check=False)
    assert crashed_sqlite.returncode==42
    assert crashed_sqlite.stdout.strip()==b"Q05_REAL_SQLITE_TRANSACTION_OPEN_BEFORE_COMMIT"
    assert runtime.is_file()
    sqlite_leftover=_sha256(runtime.read_bytes()).hexdigest()
    assert anchor.read()==anchored_reservation
    assert _sha256(checkpoint_file.read_bytes()).hexdigest()==checkpoint_digest
    # A real native GUI must reject the unexplained plaintext runtime and
    # clear balance, even though the sealed checkpoint is otherwise valid.
    denied_window=ManagedCoreWindow(root,core_dir=core,wsp_source=wsp)
    denied_window.show()
    try:
        denied_window._apply_managed_status(control(root,"status",timeout=10))
        with patch("wam_regtest.managed_gui.QInputDialog.getText",
                   return_value=(password.decode("ascii"),True)):
            denied_window.view_wallet_button.click()
            deadline=time.monotonic()+90
            while denied_window._worker is not None and time.monotonic()<deadline:
                app.processEvents()
                time.sleep(.01)
        assert denied_window._worker is None
        assert denied_window._snapshot is None
        assert not denied_window.dashboard.go_send.isEnabled()
        assert "UNVERIFIED" in denied_window.status.text()
        assert _sha256(runtime.read_bytes()).hexdigest()==sqlite_leftover
    finally:
        assert denied_window.close()
        delete(denied_window)
        app.processEvents()

    # Inject a second native-process crash precisely AFTER atomic encrypted
    # generation publication but BEFORE Keychain CAS. Never mutate production
    # vault code for tests: patch only the child process's anchor write point.
    envelope_crash=r'''
import os,sys
from pathlib import Path
from wam_regtest import custody
from wam_regtest.vault import CheckpointVault
from wam_regtest.managed_scan_client import ManagedScanRpc
root,wsp=map(Path,sys.argv[1:3])
wallet_id=sys.argv[3]
password=sys.stdin.buffer.readline(1025).strip()
if not 12<=len(password)<=1024:raise SystemExit(2)
anchor=custody.anchor(wallet_id)
vault=CheckpointVault(root/"chain"/"wallet-vault",anchor,wsp)
runtime=root/"chain"/"crash-envelope-runtime.sqlite"
ring,scanner=vault.restore(runtime,password)
rpc=ManagedScanRpc(root,authorized_readonly=True)
scanner.sync(rpc)
scanner.assert_current()
def kill_before_anchor(previous,current):
    assert current[0]==previous[0]+1
    assert (root/"chain"/"wallet-vault"/CheckpointVault._filename(current[0])).is_file()
    print("Q05_NATIVE_ENVELOPE_PUBLISHED_BEFORE_ANCHOR_CAS",flush=True)
    os._exit(43)
anchor._advance_unlocked=kill_before_anchor
vault.save(ring,scanner,password)
raise SystemExit(2)
'''
    pending_serial=anchored_reservation[0]+1
    assert not (vault_dir/CheckpointVault._filename(pending_serial)).exists()
    crash_envelope=subprocess.run(
        [sys.executable,"-c",envelope_crash,str(root),str(wsp),wallet_id],
        input=password+b"\n",stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
        timeout=110,check=False)
    assert crash_envelope.returncode==43
    assert crash_envelope.stdout.strip()==b"Q05_NATIVE_ENVELOPE_PUBLISHED_BEFORE_ANCHOR_CAS"
    orphan=vault_dir/CheckpointVault._filename(pending_serial)
    assert orphan.is_file()
    orphan_hash=_sha256(orphan.read_bytes()).hexdigest()
    assert anchor.read()==anchored_reservation
    assert _sha256(checkpoint_file.read_bytes()).hexdigest()==checkpoint_digest
    from wam_regtest.vault import VaultError
    from wam_regtest.managed_wallet_reopen import preflight_existing_checkpoint,ManagedWalletReopenError
    try:
        with anchor.lease():
            vault._load_payload(password,anchored_reservation)
    except VaultError as error:
        assert str(error)=="VAULT_UNANCHORED_GENERATION_DENIED"
    else:
        raise AssertionError("Q05_ORPHAN_CHECKPOINT_INCORRECTLY_ACCEPTED")
    try:
        preflight_existing_checkpoint(core,directory,wsp,password,authorized=True)
    except ManagedWalletReopenError as error:
        assert str(error)=="MANAGED_WALLET_PREFLIGHT_DENIED"
    else:
        raise AssertionError("Q05_ORPHAN_CHECKPOINT_PREFLIGHT_ACCEPTED")
    assert orphan.is_file() and _sha256(orphan.read_bytes()).hexdigest()==orphan_hash
    assert _sha256(runtime.read_bytes()).hexdigest()==sqlite_leftover
    assert anchor.read()==anchored_reservation
    assert control(root,"status",timeout=10)["height"]==funded_height

    return {
        "real_sqlite_crash_during_uncommitted_transaction":True,
        "unexplained_runtime_gui_fail_closed":True,
        "runtime_not_silently_deleted":True,
        "real_encrypted_envelope_crash_before_native_anchor":True,
        "unanchored_future_generation_rejected":True,
        "anchor_and_signed_reservations_preserved":True,
        "real_application_wallet_create_on_owned_core":True,
        "real_encrypted_native_checkpoint":True,
        "genuine_wsp_original_account":True,
        "actual_signed_core_regtest_ipc":True,
        "same_receive_code_two_qt_windows":True,
        "genuine_bip352_funded_receive_history_verified":True,
        "real_native_gui_killed_after_wallet_verification":True,
        "real_native_gui_reopened_after_kill_same_wallet":True,
        "actual_signed_psbt_reservation_anchored_before_crypto":True,
        "irreversible_signed_utxo_reserved_after_gui_crash":True,
        "confirmed_real_payment_txid":txid,
        "confirmed_atoms":expected_atoms,
        "actual_chain_height":funded_height,
        "signer_allowed":False,
        "broadcast_allowed":False,
        "mainnet_allowed":False,
        "wallet_gui_process_crash_recovery_qualified":False,
    }

def prove(core, *, qt=False, linux_manifest=None, linux_witness=None):
    # Native acceptance source identity only, never a runtime wallet authority.
    from wam_regtest.build_provenance import capture, verify, public_receipt
    source_root = Path(__file__).resolve().parents[1]
    source = capture(source_root)
    if sys.platform=="linux":
        if type(linux_manifest) is not str or linux_witness is None:
            raise ManagedCoreError("T05_LINUX_NATIVE_WITNESS_REQUIRED")
        # Same verified developer-Core policy as existing Linux wallet; no
        # foreign signer, backup or weaker root anchor.
        from wam_regtest.linux_runtime import configure
        configure(core,linux_manifest,linux_witness,authorized=True)
    evidence={"schema":"wam-t05-real-owned-core/v1","chain":"regtest",
              "synthetic_rpc":False,"mainnet_allowed":False,
              "full_gui_q05_qualified":False,
              "test_source_provenance":public_receipt(source,
                  source_head=os.environ.get("WAM_SOURCE_HEAD"))}
    # The testing harness deletes its private disposable fixture after
    # the test, NOT the actual managed Core lifecycle.
    with tempfile.TemporaryDirectory(prefix="wam-t05-public-fixture-") as temporary:
        root=Path(temporary).resolve()/"wam-fusion-core-0123456789abcdef"
        # Native Windows requires explicit owner-only NTFS DACL, not mkdir's
        # inherited permissions or chmod emulation. POSIX retains mode 0700.
        if sys.platform=="win32":
            from wam_regtest.custody import create_directory
            create_directory(root)
        else:
            root.mkdir(mode=0o700)
        owner=CoreSupervisor(root,core,authorized=True)
        evidence["wamd_sha256"] = owner.receipt["wamd_sha256"]
        evidence["wam_cli_sha256"] = owner.receipt["wam_cli_sha256"]
        try:
            # Distinct supervisor must not acquire an existing owner lock.
            try:CoreSupervisor(root,core,authorized=True)
            except Exception:evidence["simultaneous_owner_denied"]=True
            else:raise AssertionError("T05_CONCURRENT_SUPERVISOR_ACCEPTED")
            # T-08: REAL managed REGTEST profile has a create-once RPC
            # port. A competing local listener MUST prevent Core launch
            # before any auth bytes, CLI/wallet mutation or daemon signal.
            from wam_regtest.network_policy import local_rpc_port
            from wam_regtest.json_rpc import _private_config
            from hashlib import sha256 as t08_sha256
            import socket
            original_config=t08_sha256(_private_config(owner.directory)).digest()
            configured_rpc=local_rpc_port(owner.directory)
            with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as competing:
                if sys.platform=="win32":
                    competing.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
                competing.bind(("127.0.0.1",configured_rpc))
                competing.listen(1)
                try:owner.start()
                except ManagedCoreError as error:
                    assert error.args==("MANAGED_RPC_PORT_OCCUPIED",)
                else:raise AssertionError("T08_FOREIGN_PORT_ADOPTED")
                assert owner.process is None and owner.read is None
                assert owner.status()["state"]=="recovery-needed"
                assert t08_sha256(_private_config(owner.directory)).digest()==original_config
            # Retry is explicit only AFTER that foreign listener is gone:
            # original datadir, credentials and port are never rewritten.
            owner.start()
            assert owner.status()["core_process_owned"] is True
            assert t08_sha256(_private_config(owner.directory)).digest()==original_config
            evidence["t08_foreign_rpc_port_prelaunch_denied"]=True
            evidence["t08_same_config_safe_restart_after_port_release"]=True
            prefix=[str(owner.cli),f"-datadir={owner.directory}"]
            _read_cli(prefix+["createwallet","test"])
            address=_read_cli(prefix+["-rpcwallet=test","getnewaddress"])
            if sys.platform=="darwin" and qt:
                # Dedicated Q05 funded-wallet proof uses a globally known
                # test-only scalar. Never run the signer fixture on mainnet.
                from wam_regtest.wsp_live import public_regtest_mining_address
                address=public_regtest_mining_address(source_root/"wsp-upstream")
            blocks=_read_cli(prefix+["generatetoaddress","101",address],timeout=90)
            assert len(blocks)==101
            height=owner.read.call("getblockcount",[])
            assert height==101
            tip=owner.read.call("getblockhash",[height])
            evidence["original_height"]=height
            # T-06: ANOTHER interpreter attaches read-only to this already
            # running, independently pinned REGTEST Core by observed PID.
            # It neither owns this Popen nor knows a process-control token.
            # No daemon restart, Core config edit, mining or wallet RPC.
            from hashlib import sha256 as _public_fixture_sha
            from wam_regtest.json_rpc import _private_config
            config_before=_public_fixture_sha(
                _private_config(owner.directory)).digest()
            attached_cmd=[
                sys.executable,"-m","wam_regtest.attached_core_cli",
                "--core-dir",str(core),"--datadir",str(owner.directory),
                "--pid",str(owner.process.pid),
                "--confirm-disposable-regtest-readonly-attach",
            ]
            if sys.platform=="linux":
                attached_cmd.extend([
                    "--linux-developer-manifest",linux_manifest,
                    "--linux-root-witness",str(linux_witness),
                ])
            observed_pid=owner.process.pid
            attached=subprocess.run(attached_cmd,stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                    timeout=55,check=False)
            if attached.returncode:
                raise AssertionError("T06_INDEPENDENT_READONLY_ATTACH_DENIED")
            observed_attach=json.loads(attached.stdout)
            assert observed_attach["status"]=="T06_EXISTING_CORE_REGTEST_READONLY_PASS"
            assert observed_attach["height"]==height and observed_attach["tip"]==tip
            assert observed_attach["read_only"] is True
            assert observed_attach["process_owned_by_fusion"] is False
            assert observed_attach["wallet_mutation"] is False
            assert observed_attach["core_lifecycle_mutation"] is False
            assert observed_attach["signer_allowed"] is False
            assert observed_attach["broadcast_allowed"] is False
            assert observed_attach["mainnet_allowed"] is False
            assert observed_attach["synthetic_rpc"] is False
            assert owner.process.pid==observed_pid and owner.process.poll() is None
            assert owner.read.call("getblockcount",[])==height
            assert owner.read.call("getblockhash",[height])==tip
            assert _public_fixture_sha(_private_config(owner.directory)).digest()==config_before
            evidence["t06_existing_core_independent_readonly_attach_no_mutation"]=True
            if qt and sys.platform=="darwin":
                # Same REAL externally-running Core through the production
                # read-only GUI. No wallet keys, mining, Sign or stop buttons.
                from wam_regtest.attached_core_gui import ExistingCoreReadOnlyWindow
                from wam_regtest.desktop import qt_application
                app=qt_application()
                inspector=ExistingCoreReadOnlyWindow(
                    core,owner.directory,owner.process.pid)
                inspector.show()
                inspector.request_refresh()
                deadline=time.monotonic()+25
                while (inspector._worker is not None or inspector._proof is None) and time.monotonic()<deadline:
                    app.processEvents()
                    time.sleep(.02)
                app.processEvents()
                proof=inspector._proof
                assert proof is not None
                assert proof["chain"]=="regtest" and proof["height"]==height
                assert proof["tip"]==tip and proof["read_only"] is True
                assert proof["mainnet_allowed"] is False
                assert not hasattr(inspector,"start_core")
                assert not hasattr(inspector,"stop_core")
                assert not hasattr(inspector,"spend_wallet_button")
                assert not hasattr(inspector,"create_wallet_button")
                inspector.close()
                app.processEvents()
                assert owner.process.pid==observed_pid and owner.process.poll() is None
                assert _public_fixture_sha(_private_config(owner.directory)).digest()==config_before
                evidence["t06_existing_core_real_gui_readonly_macos"]=True
            owner.shutdown()
            assert owner.directory.is_dir()
            assert (owner.directory/"regtest").is_dir()
            assert owner.process is None
        finally:_closed(owner)
        # New application session; existing protected chain is reused.
        restarted=CoreSupervisor(root,core,authorized=True)
        try:
            assert restarted.directory==root/"chain"
            restarted.start()
            assert restarted.read.call("getblockcount",[])==height
            assert restarted.read.call("getblockhash",[height])==tip
            evidence["clean_restart_same_tip"]=True
            # A real crash of the owned Core does not erase the chain.
            restarted.process.kill()
            restarted.process.wait(timeout=15)
            assert restarted.status()["state"]=="recovery-needed"
            assert restarted.directory.is_dir()
            restarted.start()
            assert restarted.read.call("getblockcount",[])==height
            assert restarted.read.call("getblockhash",[height])==tip
            evidence["daemon_crash_recovery_same_tip"]=True
            restarted.shutdown()
        finally:_closed(restarted)
        # Independently launched owner stays alive across disposable GUI/client exits.
        # No Core adoption: the new supervisor owns a newly started Popen itself.
        from wam_regtest.supervisor_client import control
        command=[sys.executable,"-m","wam_regtest.supervisor_cli","serve",
            "--root",str(root),"--core-dir",str(core),
            "--confirm-regtest-managed-core"]
        if sys.platform=="linux":
            command.extend(["--linux-developer-manifest",linux_manifest,
                            "--linux-root-witness",str(linux_witness)])
        server=subprocess.Popen(command,
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        stopped=False
        try:
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                if server.poll() is not None:
                    raise AssertionError("T05_SUPERVISOR_PROCESS_DIED")
                try:
                    state=control(root,"status",timeout=3)
                    if state["state"]=="stopped":break
                except Exception:time.sleep(.1)
            else:raise AssertionError("T05_SUPERVISOR_IPC_NOT_READY")
            state=control(root,"start",authorized=True,timeout=15)
            assert state["core_process_owned"] is True
            assert state["height"]==height
            if qt:
                # Two independent REAL WSP-1 scanner interpreters. They share
                # only the OS-protected SQLite fixture, not an RPC object,
                # memory account, Core PID handle or process lifetime.
                # This still proves a public scanner fixture, NOT owner-wallet
                # restore, signer activation or complete Q05.
                wsp_source=source_root/"wsp-upstream"
                command=[sys.executable,"-m","wam_regtest.managed_scan_probe",
                    "--root",str(root),"--wsp-source",str(wsp_source),
                    "--confirm-public-regtest-scan"]
                if sys.platform=="linux":
                    command.extend(["--core-dir",str(core),
                        "--linux-developer-manifest",linux_manifest,
                        "--linux-root-witness",str(linux_witness)])
                def scan_child(before,count):
                    args=command+["--expected-before",str(before),
                                  "--max-blocks",str(count)]
                    reply=subprocess.run(args,stdin=subprocess.DEVNULL,
                        capture_output=True,timeout=100,check=False)
                    if reply.returncode!=0:
                        raise AssertionError("Q05_REAL_WSP_INDEPENDENT_PROCESS_DENIED")
                    evidence=json.loads(reply.stdout)
                    assert evidence["status"]=="Q05_INDEPENDENT_REAL_WSP_SCAN_PASS"
                    assert evidence["before"]==before
                    assert evidence["processed"]==count
                    assert evidence["height"]==before+count
                    assert evidence["core_height"]==height
                    assert evidence["read_only"] is True
                    assert evidence["wallet_adopted"] is False
                    assert evidence["signer_allowed"] is False
                    assert evidence["broadcast_allowed"] is False
                    assert evidence["mainnet_allowed"] is False
                    assert evidence["synthetic_rpc"] is False
                    return evidence
                scan1=scan_child(0,3)
                assert scan1["scanner_ready"] is False
                assert scan1["tip"]==_read_cli([str(restarted.cli),
                    f"-datadir={root/'chain'}","getblockhash","3"])
                assert server.poll() is None
                scan2=scan_child(3,5)
                assert scan2["scanner_ready"] is False
                assert scan2["tip"]==_read_cli([str(restarted.cli),
                    f"-datadir={root/'chain'}","getblockhash","8"])
                assert scan1["tip"]!=scan2["tip"]
                assert server.poll() is None
                assert control(root,"status",timeout=15)["height"]==height
                evidence["authenticated_wsp_scan_first_three_real_blocks"]=True
                evidence["authenticated_wsp_sqlite_resume_same_tip"]=True
                evidence["authenticated_wsp_reopened_client_same_supervisor"]=True
                evidence["two_independent_wsp_scanner_processes_same_sqlite"]=True
                evidence["scanner_read_only_partial_sync_only"]=True
            # This second, independent interpreter represents a GUI re-open.
            client=subprocess.run([
                sys.executable,"-m","wam_regtest.supervisor_cli",
                "status","--root",str(root)],
                stdin=subprocess.DEVNULL,capture_output=True,timeout=20)
            assert client.returncode==0
            observed=json.loads(client.stdout)
            assert observed["core_process_owned"] is True
            assert observed["height"]==height
            assert _read_cli([str(restarted.cli),f"-datadir={root/'chain'}",
                              "getblockhash",str(height)])==tip
            evidence["independent_gui_client_reopen_same_chain"]=True
            # A GUI crash must not terminate the independent supervisor.
            crashed=subprocess.run([
                sys.executable,"-c",
                "import os,sys;from wam_regtest.supervisor_client import control;"
                "control(__import__('pathlib').Path(sys.argv[1]));os._exit(41)",str(root)],
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,timeout=20)
            assert crashed.returncode==41
            assert server.poll() is None
            assert control(root,"status",timeout=15)["height"]==height
            evidence["disconnected_gui_client_core_survived"]=True
            if qt:
                _qt_reopen_probe(root,height)
                assert server.poll() is None
                assert control(root,"status",timeout=15)["height"]==height
                evidence["real_qt_gui_close_reopen_same_core"]=True
                _qt_process_probe(root,height)
                assert server.poll() is None
                assert control(root,"status",timeout=15)["height"]==height
                assert _read_cli([str(restarted.cli),f"-datadir={root/'chain'}",
                                  "getblockhash",str(height)])==tip
                evidence["independent_qt_process_reopen_same_chain"]=True
                evidence["actual_qt_process_killed_after_authenticated_ready"]=True
                evidence["actual_qt_crash_reconnect_same_tip"]=True
                if sys.platform=="darwin":
                    actual_wallet=_qt_original_wallet_live_read_probe(
                        root,core,height,address)
                    evidence["real_original_wallet_readonly_gui_macos"]=actual_wallet
            state=control(root,"shutdown",authorized=True,timeout=15)
            stopped=(state["state"]=="stopped" and state["core_process_owned"] is False)
            assert stopped
        finally:
            # Never terminate an unverified live Core owner to hide a test fail.
            if not stopped and server.poll() is None:
                try:
                    state=control(root,"shutdown",authorized=True,timeout=15)
                    stopped=(state["state"]=="stopped" and state["core_process_owned"] is False)
                except Exception:pass
            if stopped and server.poll() is None:
                server.terminate()
                server.wait(timeout=15)
            if not stopped:
                raise AssertionError("T05_SUPERVISOR_SHUTDOWN_UNVERIFIED")
        assert (root/"supervisor.profile").is_file()
        assert (root/"supervisor.token").is_file()
        evidence["persistent_datadir_reused"]=True
        evidence["unrelated_core_stopped"]=False
        evidence["verified_core_version"]="v0.1.11"
        evidence["real_process_lifecycle_pass"]=True
    verify(source_root, source)
    return evidence


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--core-dir",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--qt-e2e",action="store_true")
    p.add_argument("--linux-developer-manifest")
    p.add_argument("--linux-root-witness",type=Path)
    args=p.parse_args()
    result=prove(args.core_dir.resolve(strict=True),qt=args.qt_e2e,
                 linux_manifest=args.linux_developer_manifest,
                 linux_witness=args.linux_root_witness)
    with args.output.open("x") as f:json.dump(result,f,sort_keys=True,indent=2);f.write("\n")
    print("T05_REAL_CORE_PERSISTENT_DATADIR_CLEAN_AND_CRASH_RESTART_PASS")


if __name__=="__main__":main()
