# A06 recovery-aware acceptance — owner-authorized policy, 22 October 2026

Baseline: Draft120 `5130e432eaa440cc4723dd02b2e67aeb2579a462`.
One focused Draft on that exact baseline; no automatic merge. Original Draft114
`7f208984ad61cffcfa77ca029fbe9ea85acc7c4e`, its probe and all historical raw FAIL
receipts remain unchanged. No upstream Core/consensus or binary-pin modification.

DEV WAM independently attributes fresh SIGKILL index loss to inherited delayed
LevelDB block-index flushing. The owner now explicitly replaces the old shipping
assumption that fresh101blocks MUST survive SIGKILL without recovery. Historical
101→0 evidence stays FAIL under its original predicate; it is neither rewritten
nor a new recovery PASS. `ci_a06_observation.py` records that raw result separately.
Only complete native provenance/pins, owned exit, intact block bytes and verified
cleanup with a classified observation are RECORDED. ERROR, unknown failure,
invalid source, damaged data or missing cleanup fail the diagnostic job.

## Mandatory new platform CI contract

| Gate | Required genuine evidence |
|---|---|
| A06-A | Direct `stop` RPC on all3OS and genuine SIGTERM on POSIX; clean exit0, original101height/tip, datadir/profile and original funded Core-wallet address/balance on restart, **without reindex** |
| A06-B | Actual owned-node kill, observed index loss, separately explicitly authorized `-reindex`, exact original101Core-wallet and104nativeWSP32/BIP39 chain; full block bytes, native anchors/ciphertext, identity, scanner history, signed/uncertain reservations preserved |
| A06-C | Kill/wait the verified owned reindex Popen after durable intent publication and before application completion observation; normal Start spawns no child, missing consent and wrong checkpoint cannot mutate journal; a new explicit exact-target invocation restores original chain and typed64-byte wallet/state, resolving both pending journals only after verification |

A06-C is exercised on both fresh12/no-passphrase and24/test-passphrase managed
BIP39 fixtures inside every existing native and final frozen wallet lane. The
fault hook replaces only the completion observer to kill the actual verified
child. Core, RPC, cryptography, storage, native lease and anchor are genuine and
unchanged. The original signed and actual-Core-accepted uncertain reservations
are compared exactly after continuation. No transaction is automatically resent.

The covered C fault window includes crash before the application verifies or
journals completion. It does **not** attest a precise LevelDB write instruction,
every possible crash point, native physical power loss, new-device anchor
bootstrap or full Q05. The earlier1001-block RPC-observer timeout FAIL remains
preserved; no automatic transport retry or relaxed per-operation timeout is added.
Existing separate POSIX log-phase interruption evidence remains narrower evidence.

## Strict evidence gate and provenance

The same three platform workflows download their **current run's exact-head**
native and final frozen artifacts. There are no new workflows or acceptance
jobs. The existing aggregate now requires the ordinary job results AND actual
A/B/C artifacts; missing, skipped, canceled, corrupt, stale or unverified proof
cannot pass. Every required Linux frontend and Windows default/125%/150% frozen
report is mandatory. The historical diagnostic job must still successfully
validate/publish its raw observation, but a classified raw continuity FAIL is not
confused with a failed graceful or explicitly authorized recovery path.

`a06_acceptance.py` independently rederives A/B/C from the underlying component
receipts, including the platform-specific Core pair and full identity/state
assertions. It cannot accept a source receipt as frozen. Native reports include
clean source inventory checked before and after execution. Frozen reports bind
to the exact source/CI checkout via the release manifest, complete R04 inventory
and SHA256SUMS, independently pinned Core/WSP and actual payload executable hash
matching the genuine self-executable operator test. Hashes alone are not publisher
signatures or host-tamper attestation; the authenticated CI checkout/run and code
review remain part of this evidence trust boundary.

The aggregate schema is `wam-platform-ci-release-gate/v2`. PASS means the required
**platform CI components** and A06-A/B/C contract passed. It always retains
`automatic_release_authorized=false`, `physical_accepted=false` and
`dev_reviewed=false`; the nested A06 verdict retains `full_q05_qualified=false`
and `full_v1_qualified=false`. Existing product/startup/clean-device/K09/physical
and independent-review requirements remain separate, nonpassing until proven.

Mac/Windows retain the exact official signed v0.1.11 daemon and independently
pinned CLI. Linux retains the reviewed immutable developer Core/root witness,
not an official signed Linux release. v0.1.12 remains candidate-only. No owner
wallet/anchor/miner, attached/external Core, mainnet, real funds, upstream edits,
anchor reset, reservation release, re-mining, wallet replacement or data erasure.

## Qualification at this commit

Native Mac12/24 interruption/continuation has genuine local receipts. Supplemental
policy/mutation tests are separate from Core E2E. Exact-head three-OS CI and
downloaded final package/aggregate evidence are required before platform PASS;
the Draft description and durable audit checkpoint record the actual latest
SHA, workflow/artifact links, failures and remaining limitations. No predecessor
green check substitutes for this new policy or interruption test.
