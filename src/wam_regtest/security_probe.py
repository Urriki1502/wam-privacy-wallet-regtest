"""Mandatory security qualification on official Core and native macOS Keychain.

Only fresh disposable REGTEST keys, an isolated test keychain and real Core
invalidate/reconsider operations. No mocks, keychain-search-list changes or
personal wallet/key operations. Output is a fixed non-secret status record.
"""
import os
from pathlib import Path
import secrets
import subprocess
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
        second = vault.save(ring, scanner, password)
        assert second[0] == first[0] + 1 and first_bytes != read(private, vault._filename(second[0]))
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
        return {
            "status": "REAL_CORE_MACOS_KEYCHAIN_ENCRYPTED_RECOVERY_REORG_PASS",
            "real_core_rpc": True, "synthetic_rpc": False, "mainnet_allowed": False,
            "encrypted_key_backup": True, "authenticated_checkpoint": True,
            "wrong_password_denied": True, "wallet_directory_rollback_denied": True,
            "independent_native_keychain_anchor": True,
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
