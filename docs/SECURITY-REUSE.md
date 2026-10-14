# REGTEST security reuse audit (2026-10-14)

All runtime work is macOS ARM64, official publisher-signed WAM Core v0.1.11,
no upstream Core modifications, no mainnet or personal keys/funds. New keys are
fresh disposable research keys. This is internal engineering qualification.

| Reviewed source | Exact commit | Reuse decision |
| --- | --- | --- |
| wam-privacy-wallet | acfdb18d079617e0899c7cdf6a870b6598e4096f | Reuse MIT macOS no-follow directory/ACL custody and create-only ciphertext publication pattern. Do not import Linux-only persistence or synthetic recovery models as real acceptance. |
| wam-security | c9b1ce872c2b0b65276883d4e210b6a2f7c96467 | Keep signed binary provenance, real process/RPC and public evidence boundaries. Its broad audit framework is not a wallet keystore, so no runtime dependency. |
| wam-privacy | db3d2dcaa540f1129d540101813b761167d33174 | Reuse the real reorg qualification approach. Earlier source-built Core hash differs from the required official release; do not reuse that executable or broad Rust proof architecture. |
| wam-silent-payments | ac55f13423620252bdbf848c7e8a280c3b84721e | Directly use native secp256k1, AES-GCM/scrypt Keyring, network-bound key backup, checkpoint schema validation, durable scanner reorg undo, coin reservations and intent-verifying signer. Keep exact source pin. |

## Implemented security boundary

- Private macOS owner-only 0700 directory, ancestor no-follow descriptor walk,
  absent extended ACL, regular 0600 single-link envelope reads, bounded I/O,
  create-only publication after fsync; no silent overwrites.
- Encrypted key backup and checkpoint reuse WSP's authenticated, purpose-bound
  AES-GCM envelope and scrypt. No new cipher or key hierarchy.
- Versioned snapshot generation and ciphertext SHA-256 are anchored in a
  separate macOS Keychain generic-password item. The item contains only the
  public generation/digest, never the wallet seed or passphrase.
- An OS lease keyed by wallet ID serializes anchor updates across different
  vault directories. A writer must still match the generation it previously
  read; stale writers fail before publication or signature exposure/network submission.
  Sign and Broadcast hold that lease through approval verification, persistence,
  native crypto and RPC, so another cooperating session cannot advance the
  anchor between the guard and the sensitive operation. Reentry is limited
  to the exact anchor object on the thread that already owns its OS lease.
- Both official macOS node and CLI member hashes are independently pinned;
  changing a receipt cannot authorize a substituted CLI.
- Missing/mismatched anchor, older ciphertext under the latest name, wrong
  passphrase, malformed recovery and nonempty restore destination fail closed.
- Recovery preserves irreversible reservations and requires a fresh scanner
  runtime. No restored balance is current until real REGTEST RPC attestation
  and Scanner.sync. Live reorg undo is independently exercised on actual Core.
- Failure after snapshot publication/anchor update is ambiguous and fails
  closed for the writer. An unanchored snapshot blocks a retry at that
  create-only filename; it is retained for deliberate diagnosis. The previous
  anchored snapshot remains the only accepted generation if the anchor did not
  advance. No signed bytes or network submission occur before an irreversible
  anchored reservation exists. Automatic overwrite/downgrade or anchor deletion
  is not allowed. There is no automated orphan reconciliation or claim of
  hardware power-loss qualification.
- Sign approval persists an irreversible reservation before native crypto.
  Crypto failure/crash can conservatively retain a lock even if no signature
  was returned. Lost broadcast replies fault the session; Lock/Unlock rescans
  genuine Core while keeping uncertain locks. They cannot be canceled as drafts.
- Failed authenticated checkpoint restore closes keys/SQLite and removes only
  its newly created private disposable runtime and sidecars; it does not erase
  a supplied existing database. This allows safe retry after failure.

## Limits that remain explicit

This protects rollback of the wallet directory while the Keychain anchor
remains intact. It cannot protect against rollback/removal of both stores,
same-user malware that changes Keychain, a compromised OS, or loss of the
passphrase. Older backups are rejected when a newer anchor exists; the user
must keep the latest anchored backup. Cross-Mac recovery needs a separately
reviewed anchor migration policy and is not automatically allowed.

The vault stores ciphertext only. While unlocked, scanner SQLite is plaintext
in an owner-only disposable runtime, not SQLCipher; no claim of encrypted
unlocked SQLite or guaranteed secure erase. Keyring.close is best-effort memory
clearing; interpreter/native copies may remain. No production-custody claim.

## Real acceptance

`--confirm-security-e2e` runs inside an actual signed Core disposable session.
It funds a fresh test Keyring at block 103, saves two authenticated snapshots,
uses an isolated native test Keychain (without changing the default/search
list), rejects a wrong password and wallet-file rollback, restores a backup,
blocks coin reads before RPC sync, rejects a stale writer, and exercises real
invalidate/reconsider reorg depths 1, 12 and 100. It also kills an owned
separate OS lease-holder process, confirms lease release, rejects missing or
replaced native anchors, and rejects invalid authenticated inner checkpoints
without leaving plaintext runtime debris. Boundary fault injection after
ciphertext publication verifies that unanchored files cannot be overwritten
or advance the anchor silently. This is not a hardware power-loss test.

The operational probe inspects real encrypted reservation state at native
signer entry, verifies another anchor cannot acquire the lease during Sign
or Broadcast, and drops a local reply only after actual Core accepts a second
transaction. Real mempool observation and native Lock/Unlock prove uncertain
reservations remain irreversible. No fake RPC, signature or chain substitutes
for the real acceptance. All gates repeat in the final PyInstaller executable.
Mock unit contracts are not counted as real E2E.
