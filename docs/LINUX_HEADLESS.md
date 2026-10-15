# Experimental Linux headless candidate

Linux x86_64 only; no Qt, display session or OS keyring. The same WalletSession,
Scanner, native WSP PSBTv2/Signer, vault, reservations and Core RPC coordinator
are reused. There is no independent CLI signer. macOS/Windows retain their
signed Core and native-anchor policies. Linux backups use an authenticated v3
profile bound to linux-x86_64/root-witness-v1; old platform backups remain bound.

Prerequisites: independently reviewed developer Core manifest SHA256, exact
qualified binaries/library closure, pinned WSP checkout and an administratively
provisioned root witness. No witness or explicit policy means refusal. The
wallet never installs a service, invokes sudo or sends keys to the witness.

```bash
wam-regtest linux-wallet --core-dir /absolute/qualified/linux-core \
  --manifest-sha256 e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806 \
  --anchor-socket /absolute/root-owned-witness/anchor.sock \
  --wsp-source-root /absolute/pinned/wsp-upstream \
  --confirm-experimental-developer-regtest
```

Passphrases use getpass only with private interactive terminals; no non-terminal
echo fallback or secret command-line/environment parameter. A fresh disposable
real Core chain is created, receive fixture verified, then fresh test keys.
Commands: receive/balance/history/sync; prepare recipient WAM fee; sign;
broadcast; cancel (unsigned only); backup new-private-directory; lock; unlock;
recover backup-directory; mine; quit. Review prints exact recipient, amount,
fee, change and commitment. Signing requires typed SIGN plus exact commitment;
Broadcast separately requires BROADCAST plus that commitment. No automatic retry.

Quit closes keys/SQLite and stops/removes the owned disposable Core chain. Latest
encrypted backup and independent root witness are required for recovery. Start with `--recover-backup /absolute/private-directory/wallet-backup.enc`
to recover the latest same-host anchored backup instead of creating new keys.
The encrypted file is read through the same owner/ACL/no-follow guard. A wrong
password, lost witness, stale generation or exhausted epoch limit refuses
startup; it never falls back to new keys. Recovery retains irreversible
reservations and creates the existing fresh-chain receive epoch. This is not
cross-host or cross-platform recovery. Native acceptance uses this exact
startup session selector on two new real chains. Unlocked SQLite and best-effort memory clearing retain the
existing explicit limits. Never personal keys, mainnet or real funds.

Native acceptance launches the actual CLI subprocess with only source/WSP
dependencies, explicitly drives its HeadlessWallet approval methods, actual
PSBT signing, real mempool/confirmation/change, reorg1/12/100, dropped reply
after actual acceptance, encrypted recovery on fresh chains, same test keys,
irreversible locks and stale rejection before signer/network. Boundary
instrumentation delegates to actual crypto/RPC; it substitutes no blockchain.
It asserts PySide6 was never imported. Source acceptance is not a frozen Linux
executable/desktop/portable-backup PASS. Those remain separate pending gates.
