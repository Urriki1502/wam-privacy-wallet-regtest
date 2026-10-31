# Q05 — Current engineering checkpoint

**Checked:** 31 October 2026  
**PR:** [#138](https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/138) — OPEN / DRAFT  
**Runtime source qualified:** `4f7d4ed42e5fdeb5ea91712dea70ea4653bce0f5`  
**Last checked GitHub HEAD (before this documentation update):** `5e60f1b04555f74060ae81c7ced24fe75b5e500a`  
**Canonical case ledger:** `tests/acceptance/issue45.json`

## Current Q05 acceptance

| Measure | Status |
| --- | --- |
| Case-level coverage | **32 PASS / 4 BLOCKED / 1 PENDING** (37 total) |
| Engineering execution | ACTIVE |
| Gates | **G0–G5 PASS; G6–G7 BLOCKED** |
| Full acceptance | **NO (`accepted=false`)** |
| Owner merge authorization | PENDING, not granted |
| Merge / postmerge exact-main | Not merged / not performed |
| Engineering handoff / Q06 | NO / QUEUED |
| Release and mainnet | Not authorized |

These 32 PASS results are scoped **technical** case records, not full Q05 or production acceptance.

## Native and final frozen proof

| OS | Native | Frozen app | Core trust | Source-bound CI |
| --- | --- | --- | --- | --- |
| macOS ARM64 | PASS | PASS (.app/.dmg) | Official signed v0.1.11 | [41086424222](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/41086424222) |
| Windows x64 | PASS | PASS | Official signed v0.1.11 | [41086424220](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/41086424220) |
| Linux x86_64 | PASS | PASS (desktop/headless) | Reviewed developer Core, **unsigned** | [41086424586](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/41086424586) |

The original receipts are bound to runtime source `4f7d4ed42e5fdeb5ea91712dea70ea4653bce0f5`, test merge checkout `44d3f344d0c762b916ef329522ea40ff48462627`, WSP source pin `ac55f13423620252bdbf848c7e8a280c3b84721e`, Core digests and final-executable SHA-256. A successful run on a different source or checkout is **not** interchangeable evidence.

**Latest checked HEAD `5e60f1b04555f74060ae81c7ced24fe75b5e500a`: 7/7 workflows SUCCESS, 21 PASS jobs and one conditionally SKIPPED Linux developer-Core rebuild** (wallet-only inputs did not require a new Core build). This SKIP is not fresh Core compilation or an officially signed Linux release.

- [macOS managed GUI/Core/frozen](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/41149902367)
- [Windows signed Core/Q04](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/41149902366)
- [Windows credential/SQLite/Q05](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/41149902391)
- [Windows Qt/WSP](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/41149902392)
- [Linux native/frozen/Q04](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/41149902414)
- [Linux supervisor contracts](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/41149902478)
- [WSP-1 28 canonical vectors](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/41149902412)

## Qualified technical scope and limits

Persistent managed wallet onboarding; serialized native owner-thread Core/GUI operation; protected platform storage; real REGTEST funding and BIP352 receive; prepare/sign/broadcast/confirm; durable history, pagination and irreversible reservation fingerprints; authenticated `BEGIN/COMMIT` recovery and positive original-owner shutdown; security-negative and final-frozen package qualification.

Preserve exact `active_location`/native anchor floor, original `Popen`, single owner authority and verified Core/WSP identities. No external-miner shutdown, orphan/sidecar auto-adoption, generic privileged IPC, replay of uncertain submissions, wallet/datadir replacement or silent key regeneration.

**Crash limitation:** positive recovery evidence follows **clean Core flush**; preflush power loss is not transparent-recovery PASS. Supervisor-process death with a live Core remains fail-closed, not an adopted/recovered Core. Historical failure receipts are preserved.

## Remaining five cases

| Case | State | Required evidence |
| --- | --- | --- |
| `Q05-PHYSICAL-MACOS` | BLOCKED | Clean native macOS operator run: custody, frozen wallet and state |
| `Q05-PHYSICAL-WINDOWS` | BLOCKED | Clean Windows x64 operator run, 125% DPI/no flicker and wallet lifecycle |
| `Q05-PHYSICAL-LINUX` | BLOCKED | Clean Linux x86_64 operator run and native/frozen custody |
| `Q05-INDEPENDENT` | BLOCKED | Source-specific independent architecture/security review and signoff |
| `Q05-MERGE-AUTH` | PENDING | Explicit owner merge decision, then exact-main postmerge CI/receipts |

Q04 external G6/G7 remains separately blocked. Linux Core upstream HTTP 404 is a future rebuild dependency, not a reason to relabel already qualified immutable Core artifacts.

## Next approved work boundary

Review the final source/security diff; obtain physical clean-device evidence and independent review; request explicit separate owner merge authorization. If authorized, merge and qualify the actual main SHA before reconsidering full acceptance/handoff. **No automatic merge, Q06 activation, extra speculative features or mainnet release.**

## Source-of-truth rule

This file and `tests/acceptance/issue45.json` are the current Q05 checkpoint. Other dated `docs/Q05_*.md` reports are archived **historical diagnostics**, not live STOP instructions or up-to-date PENDING counts. Preserve historical FAIL/INCOMPLETE receipt artifacts and Git commit history.
