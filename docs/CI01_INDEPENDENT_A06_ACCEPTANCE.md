# CI01 — isolate A06 without relaxing release qualification

Owner-directed correction,22October2026. Stable parent: Draft113
`ac0273c8438204b40e86fdfb66deda49201f854b`. PR114 remains unchanged at
`7f208984ad61cffcfa77ca029fbe9ea85acc7c4e`, including every original FAIL
receipt and job result. Its probe is copied byte-for-byte, not repaired.

## Reproduced orchestration defect

PR114 embedded A06 before other independent acceptance steps. Genuine A06
FAIL aborted the Mac/Windows native job; Linux aborted its native Qt runner.
The dependent frozen jobs were then SKIPPED and unrelated acceptance evidence
could not be collected. This is separate from the unresolved Core defect.

- [Mac failure119262757884 / frozen119263975170 skipped](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39611936102).
- [Linux nativeQt119263205574 failure / frozen119265116795 skipped](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39611936214).
- [Windows119262759697 stops at A06](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/39611936503).

## Focused correction

Keep every existing native/frozen job definition identical to the stable
parent. Add an independent `a06-core-crash` job in each existing platform
workflow, using the same original signed Mac/Windows pair or the immutable
reviewed Linux developer artifact. Linux reuses the existing ephemeral native
CI witness fixture in a separate interpreter; no app service is introduced.
No additional workflow or runtime module is added.

Each platform has an `always()` aggregate job requiring A06 **and** every
applicable existing native/frozen job. Failure, cancellation, skip or missing
required result fails aggregation. Optional Linux rebuild skip is recorded
only when its existing scope explicitly says no rebuild is required; all
required native/frozen jobs still authenticate the reviewed immutable Core.
A requested or failed rebuild cannot be ignored. All platform gates plus
WSP and independent acceptance are necessary for overall qualification.

Receipts are published on FAIL as well as PASS. Nothing uses
`continue-on-error`, and no failed A06 is reclassified PASS. A green unrelated
job/package is component evidence, not permission to release. The aggregate
receipt explicitly denies automatic release, mainnet, physical or DEV approval.
The existing broad Linux build-input scope is retained, not weakened.

No upstream Core or src/runtime edits, reindex, post-crash re-mining, wallet
deletion, anchor reset, reservation release or automatic transaction retry.
Initial mining belongs only to each unchanged disposable REGTEST fixture.

## Validation and identity

Seven supplemental checker contracts cover A06/other-job failure, omitted
A06, cancelled/skipped/missing results and conditional Linux build handling.
The real checker CLI returns1 with a FAIL receipt when native/frozen succeed
and A06 fails. YAML DAG comparison proves all original job definitions equal
the parent and no original job has A06 as an ancestor. These are scheduling
contracts, not genuine-Core PASS substitutes.

Native CI must demonstrate independent A06 FAIL while the original native and
final frozen jobs actually run and publish their own exact-head artifacts.
The aggregate must remain FAIL. Pending/skipped stages cannot be promoted.
Retain exact source/merge SHA, original Core/WSP pins, public artifact digests
and SOURCE/CORE_E2E/FROZEN/PHYSICAL/DEV_REVIEWED separation.
