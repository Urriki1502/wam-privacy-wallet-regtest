# A06/Q05 — explicit owned REGTEST index recovery

The owner reports DEV independently reproduced delayed block-index flushing
and successful exact-tip reindex on v0.1.12. This is separate from qualification
of the unchanged pinned v0.1.11 pair. Original PR114 and its abrupt-no-reindex
FAIL receipts remain immutable. No Core/consensus change or upgrade is made.

## Operator workflow

1. Record the **original** trusted chain height and tip from the prior wallet/
   acceptance checkpoint. A low newly indexed chain is not a replacement.
2. Lock/close wallet clients. Shut down the Fusion-owned Core and supervisor.
   Recovery refuses an active native supervisor lease or occupied RPC port.
   No external/attached Core, PID adoption or new profile provisioning exists.
3. Explicitly authorize reindexing this existing owned REGTEST environment:

   ```sh
   python -m wam_regtest.supervisor_cli recover-index \
     --root /ABSOLUTE/PRIVATE/wam-fusion-core-0123456789abcdef \
     --core-dir /ABSOLUTE/PINNED/core \
     --expected-height ORIGINAL_HEIGHT --expected-tip ORIGINAL_TIP \
     --confirm-regtest-managed-core --confirm-reindex-existing-regtest
   ```

   Frozen Mac/Windows/Linux binaries accept `--recover-owned-regtest-index`
   with the same flags **except `--core-dir`**. Only their pinned bundled pair
   is allowed. Linux additionally requires the already approved developer
   manifest and independently provisioned witness via
   `--linux-developer-manifest` / `--linux-root-witness`. No helper installation.
4. Recovery launches only its own exact verified `Popen` with `-reindex=1`.
   Normal bindings still reject the extra argument. It attests native process,
   socket, REGTEST genesis/network and verifies exact original height/tip,
   unchanged profile/config/Core pins and datadir identity; then cleanly stops.
5. A success result means `VERIFIED_STOPPED`, not automatic reconnect/sign/send.
   Start the supervisor explicitly. Load only the original registered Core
   wallet if needed, then unlock the original native-anchored Fusion checkpoint.
   This command does not create, import, replace, reload or repair a wallet.

Wrong/missing consent or checkpoint fails before opening a profile. An unknown
profile cannot even create a lock file. Existing profile tokens, version,
native custody/lease and private network config are required; legacy incomplete
profiles are not upgraded during recovery. Reparse/symlink/hardlink/special
chain files are refused. No application deletion, wallet relocation, missing
block re-mining, resubmission or automatic broadcast occurs. Core's explicitly
authorized index regeneration is the only intended repair mutation.

## Interrupted and failed recovery

Create-only native-private, fsynced intent records precede Popen. Completion
requires exact original chain verification and clean owned shutdown. Pending,
truncated, orphan or incompatible records never authorize normal Start; wrong
targets cannot overwrite a pending target. An explicit retry may complete valid
pending attempts for the **same** exact checkpoint. No journal is erased or
automatically retried. Malformed records, incorrect supplied checkpoints and
capacity exhaustion require independent operator/developer review; no repair
or journal reset is provided. There is a bounded64-attempt profile lifetime
and20000-entry recovery tree limit. These are explicit REGTEST limitations.

The journal is process-lifecycle control, **not** a native wallet anti-rollback
anchor or protection against same-UID/OS compromise. It cannot establish an
unrecorded original tip. It never opens wallet keys, scanner DBs or native
anchors. An unexplained wallet residue/anchor mismatch remains a refusal.
Normal startup outside an interrupted recovery does not invent an original
checkpoint or auto-reindex; full supervised disaster/startup integration remains
a separate acceptance requirement.

## Acceptance scope

Genuine pinned Core tests cover fresh101 crash/index loss/reindex, identical
block bytes/tip/height and original funded Core wallet. A separate104-block
WSP case creates real signatures plus a lost reply **after real Core acceptance**,
then verifies original native anchor/encrypted-vault bytes, identity, confirmed
scanner history and signed+uncertain reservations through recovery/reopen.
The original Core wallet is explicitly loaded after restart, not replaced.
No RPC/blockchain substitute or native-anchor fallback authorizes success.

The component is required in existing native and actual final frozen probes on
Mac, Windows, Linux desktop/headless. Missing/skipped/failed paths stay nonpassing.
Original isolated no-reindex A06 and release gates are retained; this does not
silently turn old FAIL into PASS or qualify full Q05/V1/physical acceptance.
Host power-loss and actual termination halfway through reindex are not proven
by native journal negative tests. Independent security review remains pending.

Linux's initial run at2101882 rejected a tip that moved between read RPCs while
the index was being rebuilt. Global RPC attestation remains unchanged. Only
explicit recovery may discard positively classified warmup/busy/moving-tip
observations and open a NEW natively attested read connection within its fixed
deadline. Authentication, genesis, version, config, unknown refusal and uncertain
connections fail immediately; no wallet read/write/sign/broadcast retry is added.
The original checkpoint must pass the complete unchanged attestation before any
completion. Targets above the existing1million-block read limit are refused
before mutation. This is an observation correction, not an accepted stale tip.

Independent actual downloaded Mac CLI QA at2753bed additionally found that the
new flag branch used a package-relative import in the standalone PyInstaller
script. Self-check and internal CI Core probes did not cover that entry branch.
All three standalone entries now import the operator dispatcher absolutely;
standalone-context source contracts and NEW exact-head frozen artifacts are
required. The original2753bed operator FAIL receipts are preserved, not waived
by its successful internal Core/Cocoa E2E. This repair remains in the same task.

Frozen acceptance additionally launches its OWN final executable through the
operator flag (no system Python), checks missing approval is nonmutating, then
requires approved exit0 and independently restarts/reads the exact101 chain and
original funded Core wallet. The child mode returns before the CI probe, so it
cannot recurse. This runs inside existing Mac/Windows/Linux desktop/headless
frozen jobs, including the Windows DPI runs; receipt is required before package
publication. Native source probes cannot satisfy this distinct entry gate.
