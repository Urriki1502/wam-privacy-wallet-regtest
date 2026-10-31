# Q05 — Current engineering checkpoint (owner-review preparation)

**Status as of 31 October 2026:** Source technical receipts reconciled for Draft PR #138. This note replaces the superseded 1,028-line rolling chronology; the original remains at
https://github.com/Urriki1502/wam-privacy-wallet-regtest/blob/4f7d4ed42e5fdeb5ea91712dea70ea4653bce0f5/docs/Q05_STAGE_A_CHECKPOINT.md

**Qualified runtime candidate SHA:** `4f7d4ed42e5fdeb5ea91712dea70ea4653bce0f5`
**Branch:** `feature/issue45-q05-managed-core-stage-a-20261027`
**Canonical case-level source:** `tests/acceptance/issue45.json`.
**Ledger:** 32 technical cases PASS (evidence from native/frozen 3-OS CI), 4 external cases BLOCKED, 1 owner merge/integration case PENDING. `accepted=false`; engineering handoff NO; `main` unchanged.

## Actual native/frozen qualification

| OS | Workflow (all SUCCESS at source SHA) | Native | Final frozen | Core trust |
|---|---|---|---|---|
| macOS ARM64 | https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/41086424222 | PASS | PASS | official signed v0.1.11 |
| Windows x64 | https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/41086424220 | PASS | PASS | official signed v0.1.11 |
| Linux x86_64 | https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/41086424586 | PASS | PASS desktop/headless | reviewed developer Core, **not** signed |

Other successful workflows at this candidate: 41086424280 (Linux supervisor contracts), 41086424207 (WSP 28 vectors), 41086424328 (Windows WSP/Qt), 41086424389 (signed Windows Core smoke). The Linux developer-Core **rebuild job was conditionally SKIPPED** because wallet-only changes do not change reviewed build inputs; this is not a fresh upstream-source qualification. Upstream source availability (HTTP 404) remains a future rebuild dependency.

GitHub Actions frozen receipts bind `source_sha=4f7d4ed42e5fdeb5ea91712dea70ea4653bce0f5` while their `checkout_sha=44d3f344d0c762b916ef329522ea40ff48462627` is the generated PR test merge tree. Source inventory, Core digests, WSP pin and final executable SHA are included in the signed/Core native/frozen receipts. Do not replace real evidence with generic green CI claims.

## Critical security boundaries (retain)

- Manage only the authenticated owner/original `Popen`, never adopt a foreign Core or shutdown an external miner.
- Keep encrypted vault generation CAS, platform-native anchor, persistent datadir identity and fail-closed lease/supervisor lock.
- Keep signed/uncertain reservation history, no silent recovery, no replay, no orphan/sidecar auto-adoption.
- Preserve cross-platform security negative tests and native/frozen qualification, even when names resemble duplicates.
- Core-crash injection in these receipts follows an explicit Core flush; **not** physical power-loss qualification or takeover after supervisor process death.
- macOS 101-block disposable funding uses 90s deadline, other RPCs retain ordinary deadline; uncertain timed-out mutation never retried automatically.
- Linux native witness preserves application exceptions while still verifying native lease acquisition, ping/release and root peer.
- Windows Q05 recovery-equivalence fixtures do not reread exclusive `supervisor.lock` and close SQLite connections before cleanup.

## Open decisions and external acceptance

1. **Owner merge:** Separate review/authorization required. No automatic merge, no Q06.
2. **Exact-main checks:** Postmerge run/receipts required; PR SUCCESS is not exact-main proof.
3. **Clean-machine physical:** macOS, Windows (including 125% DPI/no-flicker), Linux independent native operator receipts not yet collected.
4. **Independent architecture/security:** Separate reviewer approval not granted by AI-generated reports.
5. **Release/mainnet:** Remains explicitly denied until every mandatory gate is complete.

## Cleanup and historical record

The superseded status chronology was consolidated into this snapshot rather than preserved as 1,028 lines of repeated future instructions. All existing `docs/evidence/q05/**` FAIL/PASS receipts remain in PR #138; no evidence deletions. Earlier chronology is immutable in Git at the link above. **No runtime/security code, negative tests, or Core trust boundaries are removed** in this housekeeping step. Further deletions require an actual redundancy proof and risk assessment.
