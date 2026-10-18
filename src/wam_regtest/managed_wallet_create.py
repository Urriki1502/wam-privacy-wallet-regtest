"""Create ONE genuine native-anchored WSP REGTEST wallet for Fusion's owned Core.

No Core wallet RPC, test funding, mock data, external node, signer session,
broadcast or automatic wallet replacement. Creation is an explicit operator
action, separate from read/sync and subsequent spending authorization.
"""
from __future__ import annotations

import secrets
from pathlib import Path


class ManagedWalletCreateError(ValueError):
    pass


def create_managed_wallet(root, core_dir, wsp_source, password, *,
                          authorized=False, keychain=None,
                          bip39_phrase=None, bip39_passphrase=None):
    """Create-only native vault + encrypted account locator, fail closed.

    On a crash midway the private vault/runtime may remain. This is deliberate:
    NEVER silently delete, overwrite, regenerate or claim recovery of a wallet
    whose native anchor publication may be ambiguous.
    """
    if authorized is not True:
        raise ManagedWalletCreateError("MANAGED_WALLET_CREATE_CONSENT_REQUIRED")
    if (type(root) is not type(Path()) or not root.is_absolute()
            or type(core_dir) is not type(Path()) or not core_dir.is_absolute()
            or type(wsp_source) is not type(Path()) or not wsp_source.is_absolute()
            or type(password) is not bytes or not 12 <= len(password) <= 1024):
        raise ManagedWalletCreateError("MANAGED_WALLET_CREATE_INPUT_DENIED")
    # No ambiguous legacy-vs-BIP39 conversion. New 64-byte profile requires
    # explicitly supplied BIP39 phrase/passphrase and never mutates old wallets.
    if (bip39_phrase is None and bip39_passphrase is not None or
            bip39_phrase is not None and
            (type(bip39_phrase) is not str or
             type(bip39_passphrase) is not str or
             len(bip39_passphrase)>1024)):
        raise ManagedWalletCreateError("MANAGED_WALLET_BIP39_INPUT_DENIED")
    ring=scanner=rpc=None
    runtime=root/"chain"/"wallet-runtime.sqlite"
    runtime_created=False
    try:
        from . import custody
        from .supervisor_store import _root
        from .supervisor_client import control
        from .core_supervisor import _profile_read
        from .core import verified_core_paths
        from .wsp_live import _pinned_source,REGTEST_GENESIS
        from .managed_scan_client import ManagedScanRpc
        from .managed_wallet_reopen import make,publish,read
        from .vault import CheckpointVault
        from wam_sp.keystore import Keyring
        from wam_sp.scanner import Scanner

        _root(root)
        _pinned_source(wsp_source)
        first=control(root,"status",timeout=3)
        if (first["state"]!="ready" or first["core_process_owned"] is not True
                or type(first["height"]) is not int):
            raise ManagedWalletCreateError("MANAGED_WALLET_OWNED_CORE_NOT_READY")
        profile=_profile_read(root)
        _,_,receipt=verified_core_paths(core_dir)
        if (profile["network"]!="regtest" or profile["genesis"]!=REGTEST_GENESIS
                or profile["core_sha256"]!=receipt["wamd_sha256"]
                or profile["cli_sha256"]!=receipt["wam_cli_sha256"]
                or receipt["platform"]!=custody.platform_name()):
            raise ManagedWalletCreateError("MANAGED_WALLET_CORE_IDENTITY_DENIED")
        store=custody.storage()
        data_dir=root/"chain"
        store.validate_directory(data_dir)
        vault_dir=data_dir/"wallet-vault"
        # Existing folder (even empty) can represent a crash in progress.
        # Unknown encrypted material is never adopted as a new wallet.
        if vault_dir.exists() or vault_dir.is_symlink():
            raise ManagedWalletCreateError("MANAGED_WALLET_ALREADY_OR_UNCERTAIN")
        for suffix in ("","-journal","-wal","-shm"):
            member=runtime.with_name(runtime.name+suffix)
            if member.exists() or member.is_symlink():
                raise ManagedWalletCreateError("MANAGED_WALLET_RUNTIME_EXISTS_DENIED")
        rpc=ManagedScanRpc(root,authorized_readonly=True)
        attested=rpc.attest()
        if (attested["chain"]!="regtest" or
                attested["blocks"]!=first["height"] or
                rpc.call("getbestblockhash")!=rpc.call(
                    "getblockhash",[first["height"]])):
            raise ManagedWalletCreateError("MANAGED_WALLET_CHAIN_UNVERIFIED")
        # Atomic private mkdir is also our create-once collision gate.
        if bip39_phrase is None:
            ring=Keyring()
        else:
            # K-03: 64-byte BIP39 seed is kept ONLY in the separately typed
            # encrypted keys envelope of this native-anchored recovery vault.
            # No mnemonic/passphrase is published to Core, IPC, filesystem or
            # GUI result; preflight before creating the vault directory.
            from .bip39_durable import Bip39DurableKeyring
            ring=Bip39DurableKeyring.from_phrase(
                bip39_phrase,source=wsp_source,
                passphrase=bip39_passphrase,authorized=True)
        ring.backup(password)
        accounts=ring.accounts()
        custody.create_directory(vault_dir)
        if not accounts:
            raise ManagedWalletCreateError("MANAGED_WALLET_ACCOUNT_DENIED")
        scanner=Scanner(runtime,accounts)
        runtime_created=True
        scanner.sync(rpc)
        scanner.assert_current()
        height,tip=scanner.store.tip()
        if (height!=first["height"] or
                height!=rpc.call("getblockcount") or
                tip!=rpc.call("getbestblockhash") or
                tip!=rpc.call("getblockhash",[height])):
            raise ManagedWalletCreateError("MANAGED_WALLET_SCAN_UNVERIFIED")
        wallet_id=secrets.token_hex(16)
        anchor=custody.anchor(wallet_id,keychain)
        vault=CheckpointVault(vault_dir,anchor,wsp_source)
        if vault._expected is not None:
            raise ManagedWalletCreateError("MANAGED_WALLET_ANCHOR_EXISTS_DENIED")
        vault.save(ring,scanner,password)
        expected=make(wallet_id,receipt)
        publish(vault_dir,expected,password)
        if read(vault_dir,password)!=expected:
            raise ManagedWalletCreateError("MANAGED_WALLET_LOCATOR_UNVERIFIED")
        final=control(root,"status",timeout=3)
        if (final!=first or _profile_read(root)!=profile
                or rpc.call("getbestblockhash")!=tip
                or anchor.read()!=vault._expected):
            raise ManagedWalletCreateError("MANAGED_WALLET_CREATION_STATE_CHANGED")
        # No keys or address are returned through an interprocess channel.
        return {"status":"MANAGED_REGTEST_WSP_WALLET_CREATED_LOCKED",
                "network":"regtest","wallet_locked":True,
                "signer_allowed":False,"broadcast_allowed":False,
                "mainnet_allowed":False}
    except ManagedWalletCreateError:
        raise
    except Exception:
        # The GUI receives a constant class; no seed, identifier, private
        # path, password, Core credentials or OS errors are disclosed.
        raise ManagedWalletCreateError("MANAGED_WALLET_CREATE_UNVERIFIED") from None
    finally:
        if scanner is not None:
            scanner.close()
        if ring is not None:
            ring.close()
        if rpc is not None:
            rpc.close()
        if runtime_created:
            # Only the fresh runtime created inside this invocation may be
            # deleted. No automatic cleanup of unexplained prior remnants.
            for suffix in ("-shm","-wal","-journal",""):
                runtime.with_name(runtime.name+suffix).unlink(missing_ok=True)
