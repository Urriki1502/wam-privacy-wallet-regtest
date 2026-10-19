"""K-10 encrypted K-03 WSP seed portability, strictly read-only in memory.

An authenticated K-03 backup can reproduce the same pinned BIP39/WSP
public account on a different host, but it is NOT a Fusion CheckpointVault
restore: it cannot prove a native OS anchor, prior reservations/history,
complete chain rescan or signed/broadcast payment safety.

No Core RPC, SQLite, filesystem write, private seed serialization,
wallet creation, signer unlock, automatic anchor creation or broadcast.
"""
from __future__ import annotations

from .k10_portability import K10PortabilityError, SCHEMA, _sha_public
from .v1_contracts import (
    BIP39_PROFILE, REGTEST_ACCOUNT_LIMIT, derivation_paths,
    derivation_profile_receipt, require_derivation_profile_receipt,
    metadata,
)
from .wsp_live import REGTEST_GENESIS


def inspect_portable_k03_backup(encrypted_backup, password, *, account,
                                prior_trusted_public, authorized=False):
    """Reopen encrypted K-03 BIP39/WSP keys in memory; never expose secrets.

    Caller must obtain prior_trusted_public via independently authenticated
    original wallet. An attacker-supplied new public receipt is not owner
    authentication or a cross-OS anti-rollback proof.
    """
    if authorized is not True:
        raise K10PortabilityError("K10_PORTABLE_BACKUP_CONSENT_REQUIRED")
    if (type(encrypted_backup) is not bytes or
            not 52 <= len(encrypted_backup) <= 16*1024*1024
            or type(password) is not bytes or not 12<=len(password)<=1024
            or type(account) is not int or not 0<=account<REGTEST_ACCOUNT_LIMIT
            or type(prior_trusted_public) is not dict):
        raise K10PortabilityError("K10_PORTABLE_BACKUP_SCOPE_DENIED")
    from .bip39_durable import Bip39DurableKeyring
    ring=None
    try:
        # Only v4 BIP39 64-byte-seed backups. This refuses legacy 32-byte
        # Keyring envelopes; no silent RC1 conversion or profile fallback.
        ring=Bip39DurableKeyring.restore(encrypted_backup,password)
        public_accounts=ring.accounts()
        if len(public_accounts)!=1 or public_accounts[0].epoch!=account:
            raise ValueError
        native=public_accounts[0]
        expected={
            **metadata(BIP39_PROFILE),
            "account":account,
            "paths":derivation_paths(BIP39_PROFILE,account),
            "derivation_contract":derivation_profile_receipt(
                BIP39_PROFILE,account),
            "account_id":native.account_id,
            "receive_code":native.payment_code(),
        }
        require_derivation_profile_receipt(expected["derivation_contract"],
                                           account=account)
        if (set(prior_trusted_public)!=set(expected)
                or any(type(prior_trusted_public[k]) is not type(v)
                       for k,v in expected.items())
                or prior_trusted_public!=expected
                or type(native.account_id) is not str
                or not native.payment_code().startswith("wamrtsp1")
                or expected["genesis"]!=REGTEST_GENESIS
                or expected["chain"]!="regtest"
                or expected["mainnet_allowed"] is not False):
            raise ValueError
        # Public identity digest mirrors normal K-10 mnemonic derivation.
        return {
            "schema":SCHEMA,
            "status":"K10_K03_BACKUP_PUBLIC_IDENTITY_MATCHED_LOCKED",
            "network":"regtest",
            "account_index":account,
            "public_identity_sha256":_sha_public(expected),
            "k03_encrypted_envelope_authenticated":True,
            "original_public_identity_matched":True,
            "source_k03_v4_only":True,
            "legacy_wsp32_conversion_allowed":False,
            "wallet_created":False,
            "new_os_native_anchor_created":False,
            "old_os_anchor_transplanted":False,
            "core_wallet_restored":False,
            "fusion_checkpoint_restored":False,
            "reservation_history_reconciled":False,
            "blockchain_rescan_complete":False,
            "frozen_gui_recovery_qualified":False,
            "safe_to_sign":False,
            "signer_allowed":False,
            "broadcast_allowed":False,
            "mainnet_allowed":False,
        }
    except K10PortabilityError:
        raise
    except Exception:
        raise K10PortabilityError("K10_PORTABLE_BACKUP_UNVERIFIED") from None
    finally:
        if ring is not None:
            ring.close()
