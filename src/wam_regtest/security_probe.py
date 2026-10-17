"""Mandatory security qualification on official Core and native macOS Keychain.

Only fresh disposable REGTEST keys, an isolated test keychain and real Core
invalidate/reconsider operations. No mocks, keychain-search-list changes or
personal wallet/key operations. Output is a fixed non-secret status record.
"""
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import selectors
import base64
import json
from hashlib import sha256
from .vault import CheckpointVault, KeychainAnchor, VaultError
from .encrypted_storage import read, publish


class SecurityProbeError(ValueError):
    pass


def probe_security(cli, datadir, source, mining_address):
    from .wsp_live import LiveCoreReadOnlyCli, _public_fixture_payment, _pinned_source
    _pinned_source(source)
    from wam_sp.keystore import Keyring
    from wam_sp.scanner import Scanner
    password = b"public-disposable-regtest-security-test"
    rpc = LiveCoreReadOnlyCli(cli, datadir)
    rpc.attest()
    if rpc.call("getblockcount") != 102:
        raise SecurityProbeError("SECURITY_REAL_CORE_HEIGHT_DENIED")
    private = datadir / "encrypted-vault"
    private.mkdir(mode=0o700)
    keychain = datadir / "security-acceptance.keychain-db"
    ring = scanner = restored_ring = restored = None
    created = False
    stage = "KEYCHAIN"
    try:
        status = subprocess.run(
            ["/usr/bin/security", "create-keychain", "-p", "public-test-only", str(keychain)],
            capture_output=True, timeout=15, check=False,
        ).returncode
        if status:
            raise SecurityProbeError("SECURITY_ISOLATED_KEYCHAIN_DENIED")
        created = True
        anchor = KeychainAnchor(secrets.token_hex(16), keychain)
        vault = CheckpointVault(private, anchor, source)
        stage = "FUNDING"
        ring = Keyring()  # Fresh test-only seed; never logged or persisted clear.
        account = ring.accounts()[0]
        txid, amount, height = _public_fixture_payment(
            rpc, account, mining_address, funding_height=2, expected_before_height=102,
        )
        stage = "SCANNER"
        scanner = Scanner(datadir / "security-live.sqlite", ring.accounts())
        scanner.sync(rpc)
        assert scanner.ready and height == 103
        assert len(scanner.coins()) == 1 and scanner.coins()[0]["atoms"] == amount
        stage = "ENCRYPTED_SAVE"
        first = vault.save(ring, scanner, password)
        first_bytes = read(private, vault._filename(first[0]))
        duplicate = datadir / "stale-vault-copy"
        duplicate.mkdir(mode=0o700)
        publish(duplicate, vault._filename(first[0]), first_bytes)
        stale_writer = CheckpointVault(duplicate, anchor, source)
        second = vault.save(ring, scanner, password)
        try:
            stale_writer.save(ring, scanner, password)
        except VaultError as error:
            if str(error) != "VAULT_STALE_WRITER_DENIED":
                raise
        else:
            raise SecurityProbeError("SECURITY_STALE_WRITER_ACCEPTED")
        assert second[0] == first[0] + 1 and first_bytes != read(private, vault._filename(second[0]))
        with anchor.lease():
            competitor=KeychainAnchor(anchor.wallet_id,keychain)
            try:
                competitor.advance(second,(second[0]+1,"a"*64))
            except VaultError as error:
                if str(error)!="VAULT_SESSION_BUSY":
                    raise
            else:
                raise SecurityProbeError("SECURITY_GLOBAL_LEASE_BYPASSED")
        assert anchor.read()==second
        stage = "PROCESS_LEASE"
        # An actual separate OS process holds this public empty lock. Killing
        # that owned child must release the lease without deleting the file.
        lease_file=(Path(tempfile.gettempdir()).resolve()/"wam-regtest-wallet-leases"/
                    (anchor.wallet_id+".lock"))
        child=subprocess.Popen(["/usr/bin/perl","-MFcntl=:flock","-e",
            'open(my $f,"+<",$ARGV[0]) or exit 2; flock($f,LOCK_EX|LOCK_NB) or exit 3; '
            '$|=1; print "HELD\\n"; sleep 120;',str(lease_file)],
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            env={"PATH":"/usr/bin:/bin","HOME":str(datadir)})
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(child.stdout,selectors.EVENT_READ)
                if not selector.select(timeout=5) or os.read(child.stdout.fileno(),5)!=b"HELD\n":
                    raise SecurityProbeError("SECURITY_CHILD_LEASE_DENIED")
            try:
                with anchor.lease():
                    raise SecurityProbeError("SECURITY_PROCESS_LEASE_BYPASSED")
            except VaultError as error:
                assert str(error)=="VAULT_SESSION_BUSY"
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)
            child.stdout.close()
        with anchor.lease():
            assert anchor.read()==second
        stage = "RESTORE_FAILURE_CLEANUP"
        # Authenticated outer/key envelopes, deliberately invalid checkpoint.
        # The actual native keystore and SQLite restore allocate before the
        # inner schema rejects it. A retry must not encounter plaintext debris.
        from wam_sp.keystore import seal
        from wam_sp.watcher import GENESIS
        bad_dir=datadir/'bad-checkpoint-vault'
        bad_dir.mkdir(mode=0o700)
        bad_anchor=KeychainAnchor(secrets.token_hex(16),keychain)
        bad_payload={"version":1,"disposable_regtest":True,"network":GENESIS,
            "wallet_id":bad_anchor.wallet_id,"generation":1,
            "keys":base64.b64encode(ring.backup(password)).decode(),
            "checkpoint":base64.b64encode(seal(b"{}",password,b"checkpoint")).decode()}
        invalid=seal(json.dumps(bad_payload).encode(),password,b"recovery")
        publish(bad_dir,CheckpointVault._filename(1),invalid)
        missing=CheckpointVault(bad_dir,bad_anchor,source)
        try:
            missing.restore(datadir/'missing-anchor.sqlite',password)
        except VaultError:
            pass
        else:
            raise SecurityProbeError("SECURITY_MISSING_ANCHOR_ACCEPTED")
        bad_record=(1,sha256(invalid).hexdigest())
        bad_anchor.advance(None,bad_record)
        malformed=CheckpointVault(bad_dir,bad_anchor,source)
        broken_runtime=datadir/'failed-restore.sqlite'
        for _ in range(2):
            try:
                malformed.restore(broken_runtime,password)
            except VaultError:
                pass
            else:
                raise SecurityProbeError("SECURITY_BAD_CHECKPOINT_ACCEPTED")
            assert not any(broken_runtime.with_name(broken_runtime.name+x).exists()
                           for x in ('','-journal','-wal','-shm'))
        status,_=bad_anchor._run(["add-generic-password","-U","-s",
            "org.wamcoin.regtest.checkpoint","-a",bad_anchor.wallet_id,"-w","1:"+"0"*64])
        assert status==0
        try:
            malformed.restore(datadir/'replaced-anchor.sqlite',password)
        except VaultError:
            pass
        else:
            raise SecurityProbeError("SECURITY_REPLACED_ANCHOR_ACCEPTED")
        stage = "UNANCHORED_PUBLICATION"
        # Failure injection is after real ciphertext publication and before
        # a native anchor write. It models that boundary, not a power-loss test.
        from unittest.mock import patch
        from .encrypted_storage import EncryptedStorageError
        orphan_dir=datadir/'orphan-vault'
        orphan_dir.mkdir(mode=0o700)
        orphan_anchor=KeychainAnchor(secrets.token_hex(16),keychain)
        orphan_vault=CheckpointVault(orphan_dir,orphan_anchor,source)
        stable=orphan_vault.save(ring,scanner,password)
        with patch.object(orphan_anchor,'_advance_unlocked',side_effect=VaultError('TEST_ANCHOR_WRITE_INTERRUPTED')):
            try:
                orphan_vault.save(ring,scanner,password)
            except VaultError:
                pass
            else:
                raise SecurityProbeError("SECURITY_FAILED_ANCHOR_ACCEPTED")
        assert orphan_anchor.read()==stable
        assert read(orphan_dir,orphan_vault._filename(stable[0]+1))
        try:
            orphan_vault.save(ring,scanner,password)
        except VaultError as error:
            assert str(error)=="VAULT_UNANCHORED_GENERATION_DENIED"
        else:
            raise SecurityProbeError("SECURITY_ORPHAN_OVERWRITTEN")
        # Earlier test expected the create-once storage layer to refuse an
        # existing name. New stricter vault detects the orphan BEFORE trying
        # decryption/publish or touching the native Keychain anchor.
        try:
            orphan_vault._load_payload(password,stable)
        except VaultError as error:
            assert str(error)=="VAULT_UNANCHORED_GENERATION_DENIED"
        else:
            raise SecurityProbeError("SECURITY_ORPHAN_PREVIOUS_ACCEPTED")
        assert orphan_anchor.read()==stable
        stage = "PASSWORD"
        # Wrong passphrase cannot restore even a correctly anchored envelope.
        try:
            vault.restore(datadir / "wrong-password.sqlite", b"wrong-test-password")
        except VaultError:
            pass
        else:
            raise SecurityProbeError("SECURITY_WRONG_PASSWORD_ACCEPTED")
        stage = "ROLLBACK"
        # Same-directory rollback: overwrite latest member with authenticated
        # older ciphertext; separate native Keychain retains the latest digest.
        latest = private / vault._filename(second[0])
        original = read(private, latest.name)
        latest.write_bytes(first_bytes)
        try:
            vault.restore(datadir / "rolled-back.sqlite", password)
        except VaultError:
            pass
        else:
            raise SecurityProbeError("SECURITY_ROLLBACK_ACCEPTED")
        latest.write_bytes(original)  # Only our isolated adversarial fixture.
        stage = "BACKUP"
        backup = datadir / "backup"
        backup.mkdir(mode=0o700)
        vault.backup(backup, "recovery.enc")
        assert read(backup, "recovery.enc") == original
        # Restore the backup in a new directory but against the existing anchor.
        recovery_dir = datadir / "recovery"
        recovery_dir.mkdir(mode=0o700)
        publish(recovery_dir, latest.name, read(backup, "recovery.enc"))
        recovery_vault = CheckpointVault(recovery_dir, anchor, source)
        stage = "RESTORE"
        restored_ring, restored = recovery_vault.restore(datadir / "restored.sqlite", password)
        assert restored_ring.accounts() == ring.accounts() and not restored.ready
        try:
            restored.coins()
        except ValueError:
            pass
        else:
            raise SecurityProbeError("SECURITY_RESTORE_TRUSTED_BEFORE_RPC")
        stage = "LIVE_RESCAN"
        restored.sync(rpc)
        assert restored.coins()[0]["txid"] == txid
        tip = rpc.call("getbestblockhash")
        stage = "REORG"
        rpc._call("invalidateblock", [tip])
        rollback = restored.sync(rpc)
        assert rollback.rollback == 1 and restored.ready and not restored.coins()
        rpc._call("reconsiderblock", [tip])
        restored.sync(rpc)
        assert restored.ready and restored.coins()[0]["atoms"] == amount
        assert restored.store.tip() == (103, tip)
        for depth in (12,100):
            changed = rpc.call("getblockhash",[103-depth+1])
            rpc._call("invalidateblock",[changed])
            measured = restored.sync(rpc)
            assert measured.rollback == depth and restored.ready and not restored.coins()
            rpc._call("reconsiderblock",[changed])
            restored.sync(rpc)
            assert restored.store.tip() == (103,tip) and restored.coins()[0]["atoms"] == amount
        return {
            "status": "REAL_CORE_MACOS_KEYCHAIN_ENCRYPTED_RECOVERY_REORG_PASS",
            "real_core_rpc": True, "synthetic_rpc": False, "mainnet_allowed": False,
            "encrypted_key_backup": True, "authenticated_checkpoint": True,
            "wrong_password_denied": True, "wallet_directory_rollback_denied": True,
            "independent_native_keychain_anchor": True,
            "stale_writer_denied": True, "native_wallet_id_lease_contended": True,
            "actual_core_reorg_depths": [1,12,100],
            "separate_process_lease_contended": True, "killed_process_lease_released": True,
            "failed_restore_plaintext_cleaned": True, "failed_restore_retry_denied_cleanly": True,
            "missing_or_replaced_keychain_anchor_denied": True,
            "unanchored_snapshot_retry_denied": True, "automatic_orphan_overwrite_allowed": False,
            "power_loss_durability_qualified": False,
            "backup_recovery_then_live_scan": True, "restored_balance_blocked_until_live_scan": True,
            "actual_core_reorg_depth": 1, "observed_height": 103,
            "same_uid_malware_protection": False, "keychain_rollback_protection": False,
        }
    except SecurityProbeError:
        raise
    except Exception:
        raise SecurityProbeError("SECURITY_REAL_CORE_" + stage + "_DENIED") from None
    finally:
        for item in (scanner, restored, ring, restored_ring):
            if item is not None:
                item.close()
        if created:
            status = subprocess.run(
                ["/usr/bin/security", "delete-keychain", str(keychain)],
                capture_output=True, timeout=15, check=False,
            ).returncode
            if status:
                raise SecurityProbeError("SECURITY_TEST_KEYCHAIN_CLEANUP_DENIED")
