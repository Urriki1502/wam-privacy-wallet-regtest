# Issue #45 — R-03 evidence lifecycle, first strict schema and invalidation gate

**Scope:** R-03 [P0], one branch / one Draft PR stacked on green R-02
PR #103 exact HEAD `1351974fbca0164e7abecf851e9a3ff530d736d8`.

## Why this was necessary

The existing `acceptance_evidence.effective_status` (B-03) validated seven
baseline identities and basic layer requirements, but did not require
independent proof for a versioned receipt. New binary, signer, custody,
GUI, dependency, packaging or test-environment changes could invalidate a
former PASS without changing those seven fields.

## Implemented, conservative source-only scope

`r03_evidence_lifecycle.py` defines
`wam-fusion-r03-evidence-lifecycle/v1`. The original B-03 historical
format remains available, but any versioned receipt, including unknown
schema, cannot silently pass through that legacy compatibility path.

The new schema requires a full *exact* identity:

- Git source commit, OS, architecture;
- Core release version, REGTEST network, genesis hash and both binary hashes;
- canonical pinned WSP source commit;
- signer, custody and GUI source SHA-256;
- third-party dependency lock and package-manifest SHA-256;
- test-environment SHA-256.

A changed valid identity makes an old PASS or FAIL `STALE`; incomplete
identities, unverified runner receipts and SKIP become `PENDING`.
Evidence layer states remain distinct:
`SOURCE`, `CORE_E2E`, `FROZEN`, `PHYSICAL`, `DEV_REVIEWED`.
Real Core E2E requires `genuine_core=True`. Frozen requires its final
entrypoint. Frozen, physical and external-review evidence additionally
requires the **same exact artifact SHA-256** as the candidate build.
Physical/DEV status also requires a separate authenticated operator
receipt; no placeholder becomes an external review.

`receipt_verified=True` must only be supplied by an external caller that
has **independently verified** actual Git/build/run/receipt provenance. The
record itself cannot assert its own authenticity. This module NEVER
authenticates input files, accesses the network, starts Core, reads a
wallet, signs or broadcasts. Status is bookkeeping, **not release trust**.
Test IDs and exact receipts belong to the higher-level R-04/Q acceptance.

## Tests and acceptance

`tests/test_v1_r03_evidence_lifecycle.py` exercises stale transitions for
all material inputs, software-update version changes, different executable
hashes, artifact replacement, invalid network/platform, forged or malformed
receipts, missing operator review, unknown schemas and SOURCE vs native/
frozen/physical boundary. Historic B-03 tests still must pass.

**R-03 P0 is not fully qualified by this first slice:** wire actual CI
artifact provenance and signed runner attestation into the candidate
registry; emit/refresh exact-header receipts for all three OSs; prove
registry promotion from verified evidence, regression and repeated
release/rollback; check whether affected current Q gates should be STALE;
obtain real physical/DEV review separately. Existing
`tests/acceptance/issue45.json` is left untouched; its integrated V1
`PENDING` flags must not be casually overwritten by source-only tests.
No auto-merges, no Core upgrade, no privileged runtime behavior, no
mainnet, no secret bytes or wallet data.
