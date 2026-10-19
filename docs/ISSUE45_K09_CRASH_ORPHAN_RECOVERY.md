# Issue #45 — K-09 Power-loss disaster recovery: orphan sets and stage files

**Draft implementation / P0 NOT ACCEPTED.** Based on DEV WAM's actual source review, not a claim of power-loss testing or recovery readiness. One K-09 PR stacked on K-08 #89.

## Both crash windows (not just snapshot N+1)

`encrypted_storage.publish` creates `.stage-<32 lower hex>`, writes arbitrary-length encrypted ciphertext and fsyncs, publishes a final filename with `os.link`, then removes the stage with `os.unlink`. SIGKILL/power loss does **not** run finally cleanup. A crash during write or fsync leaves stage-only residue (the larger window); a crash between link/unlink can leave both names referencing the same inode; a crash after link/unlink and before native Keychain/Credential Manager/root-witness anchor advance can leave an unanchored `snapshot-N+1.enc`. Repeated failed saves can yield **multiple unanchored generations** and multiple staging files.

These conditions **currently block vault restore** via `_reject_unanchored_publication` by design. Never eliminate this block without independent owner authorization and proof of post-crash transaction safety.

## Current K-09 stage 1 implementation — authenticated read-only inventory

- `crash_recovery.py` accepts only an existing, correctly typed, pinned `CheckpointVault`, explicit operator consent and original vault password. It acquires original OS-native same-wallet lease and `.vault.lock`, verifies private vault directory, checks exact OS anchor generation and ciphertext SHA-256, cryptographically authenticates the original REGTEST owner checkpoint and rereads unchanged anchor after candidate inventory. It **never** calls Core RPC, wallet signer or a mutation-capable vault method.
- Only native-private directory file **names and metadata** for exact `.stage-<32hex>` and future `snapshot-<9 digits>.enc` are considered. Bounded to 32, reject malformed candidates/irregular files/symlinks, refuse metadata changed between scans. The result contains only counts, a boolean for future generation multiplicity and number of possible POSIX `stage→snapshot` hardlink pairs; **no filenames, private paths, hashes, serialized checkpoint data, transaction values, keys, addresses or plaintext**.
- The returned status is `K09_OWNER_VERIFIED_READ_ONLY_RESIDUE_PREVIEW`. `safe_to_discard_proven`, `candidates_authenticated`, `signed_or_uncertain_reservations_reconciled`, `operator_discard_available`, `signer_allowed` and `automatic_cleanup_allowed` are ALWAYS **false**. No positive file-cleanup action exists.
- Unit tests model stage-only write crash, link/unlink window with both hardlinked names, two future orphan generations, mixed multi-stage + multi-orphan set, anchored older snapshots, symlink, extraneous hardlink, bounded file count, wrong anchor and missing owner password. These use disposable fake ciphertext and are **NOT** real Core or power-loss qualification.


## Stage 1b — native process-termination injection and ambiguous-name refusal

- `tests/test_v1_k09_native_process_kill.py` starts **a separate native OS process** using disposable fixture bytes. The parent kills it at (a) partial stage write, (b) staged ciphertext fsync, (c) POSIX hardlink-before-stage-unlink, (d) completed snapshot publication-before-native anchor advance, and (e) two consecutive failed generations. Windows follows its **rename** publication semantics and skips only the POSIX-specific link/unlink case. Files remain present and `CheckpointVault._reject_unanchored_publication` must keep restore locked after interruption.
- Reserved publication prefixes with malformed names or generation zero are now **hard refusals** in both the authenticated preview and normal vault restore blocker. No ambiguous/partially named residue may be treated as evidence of a clean directory.
- The subprocess tests use actual OS file operations and ungraceful process termination, but only a **sentinel** instead of a native Keychain/Credential/root witness anchor. They do **not** establish physical power-loss durability, genuine-Core signed/uncertain reservation reconciliation, OS-level ACL/handle race safety, frozen GUI recovery, or permission to quarantine, discard, sign, or broadcast.
- Before claiming Stage 2 completion, obtain precise native file-handle/ACL proof, full WSP signed/uncertain ledger and rescan/reorg reconciliation on disposable **real Core REGTEST**, consent-bound owner decisions, and independent three-OS frozen/physical evidence. Tests passing are **engineering coverage**, not P0 acceptance.

## Stage 1c — sealed WSP ledger inspection (diagnostics only)

An explicit `inspect_owner_crash_residue(vault, password, authorized=True, audit_reservations=True)` now performs a *separate*, bounded, read-only inspection under the **original** native wallet lease and vault file lock:

1. Re-authenticates the OS-anchored REGTEST snapshot, then uses the pinned native WSP Keyring + authenticated scanner checkpoint to derive the exact WSP account identity and reservation projection **in memory**. No new SQLite scanner is created.
2. Reads at most eight future published snapshot files, with a combined 64 MiB ciphertext read budget, through the platform's original native custody reader (POSIX no-follow/UID/ACL checks or Windows handle/DACL checks). POSIX stage hardlinks that cannot satisfy the original reader remain **unverifiable**; arbitrary partial `.stage` ciphertext is never treated as a completed checkpoint.
3. Verifies each candidate's authenticated outer owner wallet ID, native-platform profile, REGTEST network and exact generation; independently opens nested WSP account/checkpoint envelopes. Returns **only counts and booleans** for unverifiable ciphertext, account mismatch, reservation-set changes and irreversible signed/uncertain/broadcast/manual reservation deltas. Never exports names, transaction IDs, tokens, seed bytes, addresses, private paths or keys.
4. Preserves `safe_to_discard_proven=False`, `operator_discard_available=False`, `signer_allowed=False`, `broadcast_allowed=False` unconditionally. Even two matching sealed ledgers cannot prove that external peers have not observed a transaction, that source handles will survive a later rename, or that a crash-stage file contains no irreversible data.

The default inventory API remains unchanged unless the operator explicitly requests the additional forensic pass. The new pass is **not a chain rescan, file mutation, OS-reinstall workaround, physical fault/power-loss test or native Core E2E**. Source-only tests exercise legitimate nested pinned WSP backups and a signed-only-in-future reservation; independent Codex/DEV acceptance and physical OS qualifications remain PENDING.

## Stage 1d — native stage-file forensic read (not recovery)

New platform-specific `read_crash_residue(directory, name)` methods live in
the existing macOS, Linux and Windows ciphertext storage modules. These do
**not** change normal `read()`, `publish()`, vault restore, custody anchors
or sender/signer permissions.

- macOS/Linux: Native private-directory descriptor with no-follow, owner,
  mode 0600, no ACL, metadata stability, and forensic-only one/two hardlink
  support after POSIX link-before-unlink crashes. Normal restore still
  refuses hardlinked ciphertext.
- Windows: Original guarded NTFS directory, reparse and DACL protections,
  held handle, and strict one-link rule (rename rather than POSIX linking).
- Explicit `audit_reservations=True` authenticates complete stage and future
  snapshot envelopes and compares WSP reservation *records*, including
  status/token/created timestamps, detecting signed-only-in-stage evidence.
  Torn ciphertext, altered identity, and unchecked native files remain
  unverifiable, never presumed redundant.
- Bounded diagnostics only: up to eight stages, eight future snapshots,
  64 MiB combined ciphertext metadata budget, redacted counters without
  exposing paths, txids, reservation tokens, keys or seeds.

**No quarantine, discard, anchor promotion, unlock, sign or broadcast.**
Same reservation ledger does not prove absent external broadcasts or
reorg safety. Full real-Core reconciliation, OS-native quarantine
authorization, Windows NTFS positive stage fixture, physical power loss,
frozen GUI recovery and independent Codex/DEV acceptance remain PENDING.
## Stage 1e — owner-consented bounded REGTEST chain-spend risk observation

New `crash_chain_evidence.py` uses **only** the concrete authenticated
`ManagedScanRpc` and its existing read-only `getblockcount`, `getbestblockhash`,
`getblockhash` and `getblock` (verbosity 3) methods. The operator must request
the sealed WSP ledger audit AND independently authorize Core observation.
No new RPC method, wallet RPC, signer, mempool RPC, broadcast, seed or network
discovery channel is permitted.

The inspection gathers reservation outpoints from the independently
authenticated anchored and future/stage WSP checkpoints, caps observations
at 2048 outpoints and eight recent REGTEST blocks, verifies each block hash
and height, checks the original tip again, and returns redacted count of
outpoints visibly consumed by on-chain inputs. Any malformed input or tip
change fails closed. The original vault lease and file lock stay held.

**Critical distinction:** An on-chain spend is affirmative risk evidence;
the absence of a spend in the recent eight-block window is NOT evidence that
a transaction was never signed, broadcast, spent earlier, orphaned/reorged,
or observed by an external peer. The existing IPC scope does not expose
mempool status, raw tx archival proof, or global propagation. Consequently
`mempool_evidence_available`, `full_chain_reconciled`,
`signed_or_uncertain_reservations_reconciled`, `safe_to_discard_proven`,
`operator_discard_available`, `signer_allowed` and `broadcast_allowed`
remain **false** with or without observed spends. Never use this diagnostic
to authorize quarantine, discard or wallet restore.

Parser regression fixtures are synthetic RPC replies only; the actual
Mac/Windows/Linux WAM Core IPC process evidence, historical + mempool
completeness, rollback/reorg, physical crash and operator recovery decisions
remain for the consolidated Codex + DEV/physical acceptance.
## Stage 1f — original-owner GUI recovery preview (read-only)

The managed Fusion Qt toolbar now contains **Inspect crash recovery · READ
ONLY**. It requests the original wallet passphrase and a separate Yes/No
choice for the optional **last eight blocks** read through the existing
authenticated ManagedScanRpc; Cancel never opens the wallet. A short-lived
worker invokes `managed_wallet_crash_preview.py`, which validates the
original supervisor's ready/owned REGTEST state, immutable signed Core
binary identity, pinned WSP source, original sealed wallet locator, native
private vault and exact existing OS anchor before running sealed evidence.
Fresh supervisor status/profile checks surround the operation.

The UI displays only bounded numeric stage/future reservation risk counts,
possibly the count of on-chain spent reserved outpoints, and an unambiguous
**LOCKED / cleanup unavailable** warning. Invalid or malicious receipts
fail closed without reporting private identifiers. No file rename, delete,
restore, new wallet, anchor update, send, sign or broadcast control exists.

The Python/source GUI service tests verify explicit consent, original-wallet
scoping, optional real IPC selection, status change refusal and forged
unlocked receipts. They are **not** physical/frozen GUI acceptance. K-09
cannot be considered recovered or P0 PASS until signed/uncertain mempool/
broadcast/reorg continuity and safe native file quarantine are proven and
Codex/DEV/physical acceptance is completed.
## Required stage 2 before any operator cleanup (P0 PENDING)

1. Prove exact native file identity and owner ACL/UID protections for candidate source and quarantine destination with **native OS handles** on all three platforms. Include POSIX race/hardlink semantics and Windows NTFS DACL/reparse/rename identity. A read-only inventory never establishes later write authority.
2. Independently authenticate/attest anchored keyring, scanner checkpoint and **all signed/uncertain reservations and broadcast/reorg information** with real pinned WSP, signed REGTEST Core and owner consent. DEV's observation that unanchored generations never became the native anchor is not a substitute for proving whether such a generation contains a signed transaction that affected an external node/peer.
3. Preview candidate **set** and consequences to the owner, require an explicit fresh authorization, and use native fail-closed quarantine/discard only when every set member is provably redundant; preserve a recoverable sealed copy if uncertainty remains. Never delete a hardlinked source whose identity changed, lower native anti-rollback generation or silently regenerate Core/WSP accounts. Never advise owner to manually remove files.
4. Inject SIGKILL and real power-loss/restart at every write/fsync/link/unlink/anchor advance window on real platform binaries; test two consecutive crashes, disk-full, lost/wrong password, wrong chain, anchor swap, source race/symlink, receipt loss, and frozen GUI recovery. Report skipped/untested cases as **PENDING**, never PASS.
5. Actual real user keys/wallet.dat/mainnet, spontaneous signer/broadcast access and auto-sweep remain forbidden.

The final BDB→SQLite migration task remains deferred at the end of #45. The separately tracked metadata pin and PayJoin source attribution P1 fixes are outside K-09's P0 disaster scope.
