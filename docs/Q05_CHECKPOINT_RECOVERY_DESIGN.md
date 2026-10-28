# Q05 interrupted-checkpoint recovery proposal — not implemented or approved

The current native API safely refuses ambiguous runtime/orphan state. Actual
publication-cut evidence is `evidence/q05/interrupted-publication-a77a78e.json`;
it is a safety-negative result, not successful recovery. This proposal keeps the
existing vault/KDF/AEAD, native anchor, original Core owner and wallet identity.
It does not authorize release/merge or claim independent review/acceptance.

## Authority and transaction

Recovery must be an explicit owner-local action with original verified Popen,
unchanged profile/datadir/Core/WSP, wallet password and the SAME native anchor
lease object/thread throughout. HMAC-only control IPC must not carry passwords
or seeds. No foreign PID adoption or new-wallet/seed path is available.

1. Authenticate the immutable wallet reference and the exact ciphertext named
   by the CURRENT native anchor. Wrong password, missing/foreign/divergent
   anchor or ciphertext must refuse before recovery reference mutation.
2. Preserve the original vault, unknown SQLite/sidecars and every orphan byte.
   Select a fresh private recovery container INSIDE THE SAME Core datadir and
   same wallet identity, not a replacement chain/profile/wallet. Unknown
   existing names are refused, never reused, swept or overwritten.
3. Publish a strict authenticated BEGIN reference binding source anchor,
   profile/wallet, target basename and its native volume/file/birth identity.
   A pending, truncated, mixed or unauthenticated reference denies ordinary
   opens. Do not fall back to the old folder or newest filename.
4. Copy the exact already-anchored ciphertext into the new container using
   existing native create-only publication. Restore via existing CheckpointVault
   to a fresh owned runtime, reattest/live-sync actual Core and retain every
   signed/uncertain reservation. No transaction is submitted by recovery.
5. Use existing vault.save/anchor CAS to publish the next generation in the
   fresh container. This avoids overwriting the old unanchored filename. No
   direct promotion of an arbitrary orphan or bypass of anchor sequencing.
6. Publish COMMIT only after the target's native identity, ciphertext and
   actual native anchor match. The reference selects a container, while the
   native anchor stays the authority for current generation/digest. A later
   legitimate generation does not authorize an older container copy.
7. Close keys/runtime and return a locked state. Future opens select only the
   authenticated committed container, require fresh runtime and live Core sync.
   Old evidence remains preserved; uncertainty is not canceled or replayed.

Reference publication and native anchor are separate durable resources. A crash
after anchor advance but before COMMIT must remain locked. Explicit completion
of a pending recovery requires its own exact-state design/tests; current code
must not guess, advance an unknown anchor or auto-complete it. Cross-process
Core ownership recovery is separate and still refuses without safe authority.

## Independent design model and tests required

`scripts/model_q05_checkpoint_recovery.py` symbolically checks nine boundaries
of this transaction and detects eight unsafe alternatives: early commit,
newest-orphan trust, forgotten uncertainty, overwrite of old evidence, replay,
unknown runtime deletion, foreign target identity and stale/nonmonotonic CAS.
This is a small single-owner/no-new-chain-events design model, not cryptographic,
native, process-crash, formal verification or independent DEV evidence.
`tests/test_q05_recovery_model.py` requires its mutation counterexamples and
explicitly denies any runtime-implemented/acceptance claim.

Before runtime integration: real native failures at every publication/anchor/
reference boundary; actual signed and uncertain locks; wrong password/custody/
wallet/Core/profile/source; concurrent writers/stale anchor; truncated/tampered
reference/envelope; native directory replacement; unknown SQLite sidecars;
pending-reference reopen and no extra submission. Then all three OS source and
final packaged tests. No normal GUI/spending integration may turn these missing
cases into PASS. Canonical ledger remains authoritative and unqualified.
