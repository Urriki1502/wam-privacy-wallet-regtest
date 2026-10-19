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

## Required stage 2 before any operator cleanup (P0 PENDING)

1. Prove exact native file identity and owner ACL/UID protections for candidate source and quarantine destination with **native OS handles** on all three platforms. Include POSIX race/hardlink semantics and Windows NTFS DACL/reparse/rename identity. A read-only inventory never establishes later write authority.
2. Independently authenticate/attest anchored keyring, scanner checkpoint and **all signed/uncertain reservations and broadcast/reorg information** with real pinned WSP, signed REGTEST Core and owner consent. DEV's observation that unanchored generations never became the native anchor is not a substitute for proving whether such a generation contains a signed transaction that affected an external node/peer.
3. Preview candidate **set** and consequences to the owner, require an explicit fresh authorization, and use native fail-closed quarantine/discard only when every set member is provably redundant; preserve a recoverable sealed copy if uncertainty remains. Never delete a hardlinked source whose identity changed, lower native anti-rollback generation or silently regenerate Core/WSP accounts. Never advise owner to manually remove files.
4. Inject SIGKILL and real power-loss/restart at every write/fsync/link/unlink/anchor advance window on real platform binaries; test two consecutive crashes, disk-full, lost/wrong password, wrong chain, anchor swap, source race/symlink, receipt loss, and frozen GUI recovery. Report skipped/untested cases as **PENDING**, never PASS.
5. Actual real user keys/wallet.dat/mainnet, spontaneous signer/broadcast access and auto-sweep remain forbidden.

The final BDB→SQLite migration task remains deferred at the end of #45. The separately tracked metadata pin and PayJoin source attribution P1 fixes are outside K-09's P0 disaster scope.
