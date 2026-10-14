"""Fresh disposable REGTEST wallet coordinator with intent-verified signing.

Pinned WSP owns derivation/PSBT/signatures/coin reservations. Every operation
is serialized; encrypted reservation state is anchored before signed bytes or
network submission. No external seed import or production keys are accepted.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import secrets
import threading
from wam_regtest.core import verified_core_paths
from wam_regtest.wsp_live import LiveCoreReadOnlyCli, _pinned_source, _public_fixture_payment
from wam_regtest.vault import CheckpointVault, KeychainAnchor
from wam_regtest.wallet_read import HistoryRow, WalletReadSnapshot


class WalletSessionError(ValueError):
    pass


@dataclass(frozen=True)
class PaymentReview:
    code: str
    atoms: int
    fee: int
    change_atoms: int
    input_count: int
    commitment: str


class WalletCoreCli(LiveCoreReadOnlyCli):
    """Write capabilities granted only to this disposable session coordinator."""
    def call(self, method, params=None):
        if method not in ("gettxout", "testmempoolaccept", "sendrawtransaction"):
            return super().call(method, params)
        self.attest()
        def raw(value):
            return (type(value) is str and 1 <= len(value) <= 800000
                    and len(value) % 2 == 0 and re.fullmatch(r"[0-9a-f]+", value))
        if type(params) is not list:
            raise WalletSessionError("WALLET_RPC_PARAMS_DENIED")
        if method == "gettxout":
            if (len(params) != 3 or type(params[0]) is not str
                    or not re.fullmatch(r"[0-9a-f]{64}", params[0])
                    or type(params[1]) is not int or not 0 <= params[1] < 2**32
                    or params[2] is not True):
                raise WalletSessionError("WALLET_RPC_PARAMS_DENIED")
            return self._call(method, [params[0], str(params[1]), "true"])
        if method == "testmempoolaccept":
            if (len(params) != 1 or type(params[0]) is not list
                    or len(params[0]) != 1 or not raw(params[0][0])):
                raise WalletSessionError("WALLET_RPC_PARAMS_DENIED")
            reply = self._call(method, [json.dumps(params[0], separators=(",", ":"))])
            if (type(reply) is not list or len(reply) != 1
                    or type(reply[0]) is not dict or type(reply[0].get("allowed")) is not bool):
                raise WalletSessionError("WALLET_MEMPOOL_REPLY_DENIED")
            return reply
        if len(params) != 1 or not raw(params[0]):
            raise WalletSessionError("WALLET_RPC_PARAMS_DENIED")
        reply = self._call(method, params)
        if type(reply) is not str or not re.fullmatch(r"[0-9a-f]{64}", reply):
            raise WalletSessionError("WALLET_BROADCAST_UNCERTAIN")
        return reply


class WalletSession:
    def __init__(self, core_dir, datadir, source, ring, scanner, vault, password, mining_address):
        self.core_dir, self.datadir, self.source = core_dir, datadir, source
        self.ring, self.scanner, self.vault = ring, scanner, vault
        self._password = password
        self.mining_address = mining_address
        self._lock = threading.RLock()
        self._prepared = self._signed = self._review = self._tip = None
        self.faulted = False
        self.runtime = scanner.store.path

    @classmethod
    def create(cls, core_dir, datadir, source, password, mining_address, *, authorized, keychain=None):
        if authorized is not True:
            raise WalletSessionError("WALLET_DISPOSABLE_CONSENT_DENIED")
        _pinned_source(source)
        from wam_sp.keystore import Keyring
        from wam_sp.scanner import Scanner
        _, cli, receipt = verified_core_paths(core_dir)
        if receipt["platform"] != "macos-arm64":
            raise WalletSessionError("WALLET_MACOS_CORE_DENIED")
        rpc = WalletCoreCli(cli, datadir)
        rpc.attest()
        height = rpc.call("getblockcount")
        if height not in (102, 103):
            raise WalletSessionError("WALLET_FRESH_TEST_CHAIN_REQUIRED")
        folder = datadir / "wallet-vault"
        folder.mkdir(mode=0o700)
        ring = Keyring()
        scanner = None
        try:
            # Validate passphrase before any funding or signing.
            ring.backup(password)
            _public_fixture_payment(rpc, ring.accounts()[0], mining_address,
                                    funding_height=height-100, expected_before_height=height)
            scanner = Scanner(datadir / "wallet-runtime.sqlite", ring.accounts())
            scanner.sync(rpc)
            anchor = KeychainAnchor(secrets.token_hex(16), keychain)
            vault = CheckpointVault(folder, anchor, source)
            session = cls(core_dir,datadir,source,ring,scanner,vault,password,mining_address)
            vault.save(ring,scanner,password)
            return session
        except Exception:
            if scanner is not None:
                scanner.close()
            ring.close()
            raise WalletSessionError("WALLET_CREATE_DENIED") from None

    @classmethod
    def from_backup(cls, core_dir, datadir, source, directory, name, password,
                    mining_address, *, authorized, keychain=None):
        """Recover test keys on a fresh real chain against the existing anchor.

        Keep all old irreversible reservations. Rotate a new testing epoch for
        fresh-chain funding rather than guessing that old signed locks expired.
        """
        if authorized is not True:
            raise WalletSessionError("WALLET_DISPOSABLE_CONSENT_DENIED")
        _pinned_source(source)
        from wam_regtest.encrypted_storage import read, publish
        from wam_sp.keystore import unseal
        from wam_sp.watcher import GENESIS
        ring=scanner=None
        try:
            ciphertext=read(directory,name)
            payload=json.loads(unseal(ciphertext,password,b"recovery"))
            if (type(payload) is not dict or payload.get("disposable_regtest") is not True
                    or payload.get("version")!=1 or payload.get("network")!=GENESIS
                    or type(payload.get("generation")) is not int):
                raise WalletSessionError("WALLET_BACKUP_PROFILE_DENIED")
            anchor=KeychainAnchor(payload["wallet_id"],keychain)
            record=payload["generation"],sha256(ciphertext).hexdigest()
            if anchor.read()!=record:
                raise WalletSessionError("WALLET_BACKUP_STALE_OR_TAMPERED")
            folder=datadir/"wallet-vault"
            folder.mkdir(mode=0o700)
            publish(folder,CheckpointVault._filename(record[0]),ciphertext)
            vault=CheckpointVault(folder,anchor,source)
            ring,scanner=vault.restore(datadir/"wallet-runtime.sqlite",password)
            _,cli,receipt=verified_core_paths(core_dir)
            if receipt["platform"]!="macos-arm64":
                raise WalletSessionError("WALLET_MACOS_CORE_DENIED")
            rpc=WalletCoreCli(cli,datadir)
            rpc.attest()
            height=rpc.call("getblockcount")
            if height not in (102,103):
                raise WalletSessionError("WALLET_FRESH_TEST_CHAIN_REQUIRED")
            scanner.sync(rpc)
            account=ring.rotate(height+1)
            scanner.reconfigure(ring.accounts())
            _public_fixture_payment(rpc,account,mining_address,funding_height=height-100,
                                    expected_before_height=height)
            scanner.sync(rpc)
            session=cls(core_dir,datadir,source,ring,scanner,vault,password,mining_address)
            session._save()
            return session
        except Exception:
            if scanner is not None:
                scanner.close()
            if ring is not None:
                ring.close()
            raise WalletSessionError("WALLET_CROSS_SESSION_RECOVERY_DENIED") from None

    @property
    def locked(self):
        return self.ring is None

    def _rpc(self):
        if self.locked or self.faulted:
            raise WalletSessionError("WALLET_LOCKED_OR_FAULTED")
        if self.vault.anchor.read()!=self.vault._expected:
            self.faulted=True
            raise WalletSessionError("WALLET_STALE_SESSION_DENIED")
        _pinned_source(self.source)
        _, cli, _ = verified_core_paths(self.core_dir)
        rpc = WalletCoreCli(cli, self.datadir)
        rpc.attest()
        return rpc

    def _save(self):
        try:
            self.vault.save(self.ring, self.scanner, self._password)
        except Exception:
            self.faulted = True
            raise WalletSessionError("WALLET_ANCHORED_SAVE_FAILED") from None

    def snapshot(self):
        from wam_sp.wallet import Wallet
        with self._lock:
            rpc = self._rpc()
            result = self.scanner.sync(rpc)
            self.scanner.assert_current()
            tip = self.scanner.store.tip()
            if tip != (rpc.call("getblockcount"),rpc.call("getbestblockhash")):
                raise WalletSessionError("WALLET_CHAIN_CHANGED_DENIED")
            if result.blocks or result.rollback:
                self._save()
            wallet = Wallet(self.scanner)
            balance = wallet.balance()
            history = tuple(HistoryRow(r["txid"],r["height"],r["confirmations"],r["credit"],r["debit"])
                            for r in reversed(wallet.history()))
            return WalletReadSnapshot(
                "regtest",tip[0],tip[1],self.ring.accounts()[-1].payment_code(),
                balance["confirmed_atoms"],len(self.scanner.coins()),history,
                verified_core_paths(self.core_dir)[2]["wamd_sha256"],
                signer_allowed=True,broadcast_allowed=True,
            )

    def prepare(self, code, atoms, fee):
        from wam_sp.wallet import Wallet, Intent, Signer
        with self._lock:
            if self._prepared is not None:
                raise WalletSessionError("WALLET_PAYMENT_ALREADY_PENDING")
            self.snapshot()
            intent = Intent(code, atoms)
            intent.validate()
            wallet = Wallet(self.scanner)
            proposal = wallet.propose((intent,),fee)
            try:
                prepared = Signer(self.ring).prepare(proposal)
                self._save()  # Reservation is durable before exposing review.
            except Exception:
                # No signature or network action happened; draft can be
                # conservatively retained on encrypted persistence failure.
                raise WalletSessionError("WALLET_PREPARE_DENIED") from None
            commitment = sha256(prepared.psbt).hexdigest()
            change = sum(c["atoms"] for c in proposal.coins)-atoms-fee
            review = PaymentReview(code,atoms,fee,change,len(proposal.coins),commitment)
            self._prepared,self._review,self._tip = prepared,review,self.scanner.store.tip()
            return review

    def _unchanged_inputs(self, rpc):
        from wam_sp.scanner import atoms
        if self.scanner.store.tip() != self._tip or rpc.call("getbestblockhash") != self._tip[1]:
            raise WalletSessionError("WALLET_REVIEW_CHAIN_CHANGED")
        for c in self._prepared.proposal.coins:
            actual = rpc.call("gettxout",[c["txid"],c["vout"],True])
            if (type(actual) is not dict or atoms(actual.get("value")) != c["atoms"]
                    or actual.get("scriptPubKey",{}).get("hex") != "5120"+c["public_key"]):
                raise WalletSessionError("WALLET_REVIEW_UTXO_CHANGED")

    def sign(self, commitment):
        from wam_sp.wallet import Signer, Wallet
        from wam_sp.psbt import PSBT
        with self._lock, self.vault.anchor.lease():
            if self._review is None or commitment != self._review.commitment or self._signed is not None:
                raise WalletSessionError("WALLET_EXACT_INTENT_APPROVAL_REQUIRED")
            rpc=self._rpc()
            self._unchanged_inputs(rpc)
            proposal=self._prepared.proposal
            # Approving Sign makes this reservation irreversible BEFORE
            # entering native crypto. A crash/failure cannot restore a draft
            # that is cancelable, even if no signature was returned.
            Wallet(self.scanner).mark_signed(proposal.token)
            self._save()
            try:
                signed=Signer(self.ring).sign(self._prepared,proposal.intents,self._review.fee)
                PSBT.decode(signed).finalize()  # Verify signatures and sender proof.
            except Exception:
                self.faulted=True
                raise WalletSessionError("WALLET_SIGN_UNCERTAIN_LOCK_RETAINED") from None
            self._signed=signed
            return self._review

    def broadcast(self, commitment):
        from wam_sp.wallet import Wallet
        with self._lock, self.vault.anchor.lease():
            if self._review is None or self._signed is None or commitment != self._review.commitment:
                raise WalletSessionError("WALLET_BROADCAST_APPROVAL_REQUIRED")
            rpc=self._rpc()
            self._unchanged_inputs(rpc)
            token=self._prepared.proposal.token
            # Retain irreversible uncertainty in encrypted storage BEFORE RPC.
            self.scanner.store.db.execute("UPDATE reservations SET state='uncertain' WHERE token=?",(token,))
            self._save()
            try:
                txid=Wallet(self.scanner).broadcast(self._signed,token,rpc)
                self._save()
            except Exception:
                self.faulted=True
                self._signed=None
                raise WalletSessionError("WALLET_BROADCAST_UNCERTAIN_LOCK_RETAINED") from None
            self._prepared=self._signed=self._review=self._tip=None
            return txid

    def cancel(self):
        from wam_sp.wallet import Wallet
        with self._lock:
            self._rpc()
            if self._prepared is None or self._signed is not None:
                raise WalletSessionError("WALLET_ONLY_UNSIGNED_DRAFT_CAN_CANCEL")
            Wallet(self.scanner).release_draft(self._prepared.proposal.token)
            self._save()
            self._prepared=self._review=self._tip=None

    def mine(self):
        with self._lock:
            rpc=self._rpc()
            result=rpc._call("generatetoaddress",["1",self.mining_address])
            if type(result) is not list or len(result)!=1:
                raise WalletSessionError("WALLET_TEST_MINING_DENIED")
            return self.snapshot()

    def backup(self, directory, name):
        with self._lock:
            self.snapshot()
            self._save()
            return self.vault.backup(directory,name)

    def lock(self):
        with self._lock:
            if self.locked:
                return
            self.scanner.close()
            self.ring.close()
            self.scanner=self.ring=None
            self._password=None
            self._prepared=self._signed=self._review=self._tip=None
            # This path was created only by this disposable session. No user DB.
            self.runtime.unlink(missing_ok=True)

    def unlock(self, password):
        with self._lock:
            if not self.locked:
                raise WalletSessionError("WALLET_ALREADY_UNLOCKED")
            ring,scanner=self.vault.restore(self.runtime,password)
            self.ring,self.scanner,self._password=ring,scanner,password
            self.faulted=False
            try:
                return self.snapshot()
            except Exception:
                self.faulted=True
                self.lock()
                raise WalletSessionError("WALLET_RECOVERY_LIVE_SYNC_DENIED") from None

    def recover_backup(self, directory, name, password):
        from wam_regtest.encrypted_storage import read, publish
        with self._lock:
            if not self.locked:
                raise WalletSessionError("WALLET_LOCK_BEFORE_RECOVERY")
            record=self.vault.anchor.read()
            ciphertext=read(directory,name)
            if record is None or sha256(ciphertext).hexdigest()!=record[1]:
                raise WalletSessionError("WALLET_BACKUP_STALE_OR_TAMPERED")
            folder=self.datadir/("recovered-vault-"+secrets.token_hex(8))
            folder.mkdir(mode=0o700)
            publish(folder,self.vault._filename(record[0]),ciphertext)
            self.vault=CheckpointVault(folder,self.vault.anchor,self.source)
            return self.unlock(password)

    def close(self):
        self.lock()
