"""Actual original WSP transaction session against Fusion-owned REGTEST Core.

Reuses *existing* WSP PSBTv2, native Keyring, Scanner, CheckpointVault and
WalletSession's irreversible reservation/sign/broadcast state machine. The
narrow authenticated scanner and transaction IPC each require explicit consent.
Neither a CLI connection nor a new Core process may be opened by this wallet.
"""
from __future__ import annotations

from pathlib import Path
from .wallet_session import WalletSession,WalletSessionError
from .wallet_read import WalletReadSnapshot,HistoryRow
from .wsp_live import _pinned_source


class ManagedWalletSpendError(ValueError):pass


class ManagedWalletSession(WalletSession):
    @classmethod
    def reopen_spending(cls,root,core_dir,source,password,*,authorized=False):
        if (authorized is not True or type(root) is not type(Path())
                or not root.is_absolute() or type(core_dir) is not type(Path())
                or not core_dir.is_absolute() or type(source) is not type(Path())
                or not source.is_absolute() or type(password) is not bytes
                or not 12<=len(password)<=1024):
            raise ManagedWalletSpendError("MANAGED_SPENDING_CONSENT_REQUIRED")
        ring=scanner=reader=None
        session=None
        runtime=root/"chain"/"wallet-runtime.sqlite"
        try:
            from .managed_wallet_binding import verify_locked_wallet
            from .managed_wallet_reopen import read as read_locator,make
            from .vault import CheckpointVault
            from .core import verified_core_paths
            from .core_process import _metadata
            from .managed_scan_client import ManagedScanRpc
            from .supervisor_client import control
            from . import custody
            from wam_sp.wallet import Wallet

            _pinned_source(source)
            proof=verify_locked_wallet(root,core_dir,source,password,authorized=True)
            if (proof.get("status")!="MANAGED_WALLET_ORIGINAL_CHECKPOINT_VERIFIED_LOCKED"
                    or proof.get("signer_allowed") is not False
                    or proof.get("broadcast_allowed") is not False):
                raise ManagedWalletSpendError("MANAGED_WALLET_IDENTITY_UNVERIFIED")
            before=control(root,"status",timeout=3)
            if before["state"]!="ready" or before["core_process_owned"] is not True:
                raise ManagedWalletSpendError("MANAGED_CORE_NOT_READY")
            directory=root/"chain"
            folder=directory/"wallet-vault"
            custody.storage().validate_directory(directory)
            custody.storage().validate_directory(folder)
            # Authenticate Core/CLI bytes once on explicit wallet reopen.
            # The live supervisor subsequently proves native process/socket
            # ownership; ordinary snapshots must not rehash either binary.
            node,cli,receipt=verified_core_paths(core_dir)
            pair_metadata=(_metadata(node),_metadata(cli))
            identity=read_locator(folder,password)
            if (identity!=make(identity["wallet_id"],receipt)
                    or receipt["platform"]!=custody.platform_name()):
                raise ManagedWalletSpendError("MANAGED_SPEND_CORE_IDENTITY_DENIED")
            anchor=custody.anchor(identity["wallet_id"])
            vault=CheckpointVault(folder,anchor,source)
            with anchor.lease():
                record=anchor.read()
                if record is None or vault._expected!=record:
                    raise ManagedWalletSpendError("MANAGED_SPEND_ANCHOR_STALE")
                reader=ManagedScanRpc(root,authorized_readonly=True)
                reader.attest()
                ring,scanner=vault.restore(runtime,password)
                if ring.accounts()!=scanner.accounts or not ring.accounts():
                    raise ManagedWalletSpendError("MANAGED_SPEND_ACCOUNT_MISMATCH")
                # K-06: no Core .dat private keys, duplicated WSP accounts,
                # mistaken BIP39/legacy identities or swap of spend/scan keys
                # can be admitted as native WSP signing authority.
                from .account_isolation import require_native_wsp_accounts
                registry=require_native_wsp_accounts(
                    ring,scanner,identity["wallet_id"])
                if (not registry.wsp or registry.core
                        or registry.public_summary()["balances_aggregated"]):
                    raise ManagedWalletSpendError("K06_MANAGED_SPEND_ISOLATION_DENIED")
                session=cls(core_dir,directory,source,ring,scanner,vault,
                            password,"",reader)
                session._managed_root=root
                session._verified_core_receipt=dict(receipt)
                session._core_member_paths=(node,cli)
                session._core_member_metadata=pair_metadata
                snapshot=session.snapshot()  # Real Core + native checkpoint CAS
                if (snapshot.synthetic_rpc or snapshot.demo_account_only
                        or snapshot.signer_allowed is not True
                        or snapshot.broadcast_allowed is not True
                        or control(root,"status",timeout=3)!=before):
                    raise ManagedWalletSpendError("MANAGED_SPEND_LIVE_CHAIN_UNVERIFIED")
                return session
        except Exception:
            # Preserve ambiguous signed/uncertain reservations, original
            # encrypted checkpoint and any unexplained crash remnants.
            if session is not None:
                try:session.close()
                except Exception:pass
            else:
                if scanner is not None:
                    try:scanner.close()
                    except Exception:pass
                if ring is not None:
                    try:ring.close()
                    except Exception:pass
                if scanner is not None:
                    runtime.unlink(missing_ok=True)
            if reader is not None:reader.close()
            raise ManagedWalletSpendError("MANAGED_SPEND_SESSION_OPEN_DENIED") from None

    def _read(self):
        from .managed_scan_client import ManagedScanRpc
        from .core_process import _metadata
        from .supervisor_client import control
        from . import custody
        if (self.locked or self.faulted
                or type(self._read_rpc) is not ManagedScanRpc
                or self._read_rpc._root!=self._managed_root
                or self.vault.anchor.read()!=self.vault._expected):
            self.faulted=True
            raise ManagedWalletSpendError("MANAGED_SPEND_SESSION_STALE")
        _pinned_source(self.source)
        # Native file identity is checked on EVERY ordinary read, but the
        # expensive signed-byte SHA-256 qualification happens only once on
        # explicit reopen. The supervisor independently attests the owned
        # process, established socket, chain and protected RPC configuration.
        # Replacement/alias/metadata drift fails closed without CLI fallback.
        try:
            paths=self._core_member_paths
            receipt=self._verified_core_receipt
            if (type(paths) is not tuple or len(paths)!=2
                    or type(receipt) is not dict
                    or receipt["platform"]!=custody.platform_name()
                    or (_metadata(paths[0]),_metadata(paths[1]))
                       !=self._core_member_metadata):
                raise ValueError("CORE_FILE_IDENTITY_CHANGED")
        except Exception:
            self.faulted=True
            raise ManagedWalletSpendError("MANAGED_SPEND_CORE_CHANGED") from None
        status=control(self._managed_root,"status",timeout=3)
        if status["state"]!="ready" or status["core_process_owned"] is not True:
            self.faulted=True
            raise ManagedWalletSpendError("MANAGED_SPEND_CORE_NOT_OWNED")
        self._read_rpc.attest()
        return self._read_rpc,receipt

    def _rpc(self):
        from .managed_spend_client import ManagedSpendRpc
        self._read()
        return ManagedSpendRpc(self._managed_root,self._read_rpc,authorized=True)

    def snapshot(self):
        from wam_sp.wallet import Wallet
        with self._lock:
            rpc,receipt=self._read()
            from .account_isolation import require_native_wsp_accounts
            # Re-check account identity before reading/persisting scanner
            # state, not only during initial unlock.
            require_native_wsp_accounts(
                self.ring,self.scanner,self.vault.anchor.wallet_id)
            observed=rpc.attest()
            delta=self.scanner.sync(rpc)
            self.scanner.assert_current()
            height,tip=self.scanner.store.tip()
            if (height!=observed["blocks"] or
                    height!=rpc.call("getblockcount") or
                    tip!=rpc.call("getbestblockhash") or
                    tip!=rpc.call("getblockhash",[height])):
                self.faulted=True
                raise ManagedWalletSpendError("MANAGED_SPEND_CHAIN_MOVED")
            if delta.blocks or delta.rollback:
                self._save()
            wallet=Wallet(self.scanner)
            balance=wallet.balance()
            history=tuple(HistoryRow(r["txid"],r["height"],r["confirmations"],
                                     r["credit"],r["debit"])
                          for r in reversed(wallet.history()))
            return WalletReadSnapshot(
                chain="regtest",height=height,tip=tip,
                receive_code=self.ring.accounts()[-1].payment_code(),
                confirmed_atoms=balance["confirmed_atoms"],
                confirmed_utxos=len(self.scanner.coins()),history=history,
                core_sha256=receipt["wamd_sha256"],
                synthetic_rpc=False,demo_account_only=False,
                signer_allowed=True,broadcast_allowed=True,
                mainnet_allowed=False,mining=None)

    def mine(self):
        raise ManagedWalletSpendError("MANAGED_SPEND_MINING_DENIED")

    def recover_backup(self,directory,name,password):
        # No silent native profile/vault relocation. Explicit cross-host
        # recovery is a separate operator flow.
        raise ManagedWalletSpendError("MANAGED_SPEND_BACKUP_REPLACEMENT_DENIED")

    def lock(self):
        # Lock destroys native Keyring, scanner and transient plaintext SQLite,
        # but leaves the isolated read IPC handle available for explicit
        # passphrase-based unlock. No spend-capable session is kept.
        super().lock()

    def close(self):
        self.lock()
        if self._read_rpc is not None:self._read_rpc.close()
