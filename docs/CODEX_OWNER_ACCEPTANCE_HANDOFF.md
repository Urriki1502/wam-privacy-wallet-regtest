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
