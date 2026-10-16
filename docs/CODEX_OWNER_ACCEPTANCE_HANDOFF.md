# Owner acceptance/UX audit checkpoint — 16 October 2026

Only wam-privacy-wallet-regtest. Worktree work/owner-acceptance, new branch
 audit/rc1-owner-acceptance-20261016 based on docsD10fa54/PR37. Preserve qualified
RC1 144d87700b87a241467172adfad3692b41e1d273, PR36, main50e1ea94, original wallet
and owner Keychain. No automatic merge/release or message to DEV.

Exclusive common-Git lease session9827 held. Refuse concurrent engineering;
future resume must inspect active threads/processes and acquire fresh lease if
this session ended. Owner app/Core PIDs5770/5772 were already running; do not
close, mine, inspect private config/DB or mutate that session. Native live AX
selection timed out; no owner window actions taken. All tests use owned chains,
fresh disposable keys and explicitly named test Keychains only.

Completed baseline43:39PASS/4UXFAIL. Proposed fix43/43PASS local Cocoa. Native
shared probe/security/reorg/stale/uncertainty Cocoa PASS;132 contracts PASS with
33 platform skips; independent wallet auditor PASS. Details/evidence/screenshots:
docs/OWNER_ACCEPTANCE_AUDIT.md and docs/evidence/owner-audit/.

Changed runtime: only fixed public GUI error classification, Last verified for
known pre-mutation input failures, last-submitted confirmation feedback. Unknown/
Core/custody/locked/faulted failures still redact. No backend crypto/storage/RPC/
lease/reservation policy changes. Native probes preserve existing assertions and
add7 live invalid-input cases + submitted/confirmed checks on all GUI platforms.
Owner audit script independently decodes rendered QR using audit-only zxing2.3.0.

NEXT: inspect current HEAD/status, commit/push proposed code; create a focused
Draft PR stacked on PR37 and attach it. Run all8 existing workflow_dispatch gates
at SAME exact new code SHA. Do not use old RC1 artifacts as fix acceptance.
Download/inspect all four new native packages; execute new downloaded Mac Cocoa
and verify DMG/Core hashes/cleanup. Windows/Linux native runner evidence remains
separate from physical review. Keep the RC1 baseline unchanged. Publish final
exact-source CI/artifact links in separate docs-only evidence branch so code SHA
stays immutable, then update this checkpoint. Never auto merge.

Private test temps are cleaned by drivers. Separate resume log and full local
outputs: outputs/owner-acceptance-20261016/. First three harness framing/pixel
attempts are partial diagnostic runs, not full acceptance. Only completed baseline
and fixed43 matrices are used. No mocks in real-Core acceptance. PhysicalLinux
PENDING_OPERATOR per prior owner answer. No scheduler updates, recurring retries,
credit resets or paid actions authorized. Preserve originalWSP/Core/branding pins.

## Live continuation checkpoint — exact code427d3b0

CODE committed/pushed:427d3b0789d0b7e2da1f506c8dde860b5c6b4575.
Draft PR38 https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/38,
base docs/wam-fusion-regtest-rc1-evidence (#37); attached to this chat.
Current branch docs/rc1-owner-acceptance-evidence-20261016 is documentation only;
keep the audit code branch at427d3b0. All49 local owner technical checks PASS
(43 original +6 actual keyboard/masked-password-dialog cases). Baseline45PASS /
4UXFAIL of49; baseline keyboard tests used preserved RC1 source via PYTHONPATH.
Full exact427d3b0 rerun43/43PASS. No owner app/session data changed.

Eight workflow_dispatch runs at EXACT427d3b0:
vectors38843576037, macOS38843580133, Windows38843585494,
Linux38843589482, Win-preflight38843594122, Win-Core38843598553,
Win-receive38843604563, Win-readQt38843609070.
Vectors +four Windows supplemental source gates PASS. Mac source+final app/DMG
PASS and Linux source+both frozen PASS at current snapshot. Linux repeated Core
build and Windows frozen/scaling are still in progress; do NOT assume success.
Manual dispatch vs synthetic PR checkout must remain distinct.

Published new artifact IDs so far: Mac12022821744, Linux desktop12022432490,
Linux headless12022796655, all source427d3b0, expire30October2026. Downloads in
progress: sessions71711Mac,22280Linuxheadless,11020Linuxdesktop. Independent
validators and run_macbook_qa.py have been adapted to exact427d3b0 in the output
folder. Mac QA has not yet run for the newly downloaded binary. Windows package
not yet available; fetch only after actual final gate succeeds.

NEXT EXACT ACTION: wait/poll download sessions, run verify_linux.py and
verify_common_manifest.py for completed Linux downloads. Execute run_macbook_qa.py
on the NEW Mac artifact with escalation, not the owner's running RC1. Inspect
live Windows run38843585494 and Linux38843589482. Fix real failures, never reduce
gates. Download Windows after success; verify all4 common/manifests/Core/WSP/
member hashes. Save final8 native results/logs, record artifacts/checksums/expiry,
new Mac Cocoa/DMG/clean exit, update OWNER_ACCEPTANCE_AUDIT.md and this handoff.
Then commit/push docs-only final evidence, create Draft evidence PR stacked on
PR38 and attach it. Do not merge. Update PR38 body with final actual proof.
Lease9827 remains held; release only after completed checkpoint/log. No scheduler,
credit reset or main/legacy/upstream edits. Physical Linux remains unavailable.
