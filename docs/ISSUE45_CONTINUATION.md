# Issue45 continuation — owned HTTP qualified components, V1 still pending

Read the FULL live Issue45 and refresh actual Git/PR/CI, not just this snapshot.
Core Update Manager remains DEFERRED P1. REGTEST only; no owner data/anchors,
mainnet, upstream Core edit, main/RC1 change, force push or automatic merge.
Reuse existing Draft53; do not recreate merged/ancestor Security/Send/Recovery.

## Workspace and exclusive lease

work/production-v1, feature/issue45-http-scanner-20261016, official origin.
Current runtime5555df8acab1e6512271be409a8f4ca673143692; following checkpoint
commits contain docs/evidence only. Check actual HEAD before execution.
This continuation held OS lease94867, including the scheduled heartbeat; no
second writer was started. Actual release is recorded in separate logs under
outputs/issue45-session-20261016T154758 and issue45-heartbeat-20261016T204821.
Acquire a NEW lease via scripts/engineering_lease.py --hold; exit73 means REFUSE
concurrent engineering. This document never proves current lock ownership.

Main50e1ea94df61b8400cbab3bffe0fbdd285c6b419 and immutable RC1
144d87700b87a241467172adfad3692b41e1d273 remain unchanged. Native WSP pin
ac55f13423620252bdbf848c7e8a280c3b84721e; Core remains independently pinned
v0.1.11. Linux is the separately approved developer build, not signed official.
Tool venv: sibling wam-privacy-wallet-regtest/.venv. Use PYTHONPATH=src plus
outputs/production-v1-20261016/reference-deps when needed; do not modify that
old editable install or upstream. Native tests use QT_QPA_PLATFORM=offscreen.

## Existing stack — do not replay

PR46 historical modal race was fixed once in48.47–50 native/frozen green history
is retained, not qualification for later code.51 feature/issue45-core-miner-
accounting-20261016 at516b4f26ca7ec343a489754a0b472c9aaaa41979 and52 test/issue45-
pinned-subsidy-vectors-20261016 atc877705581d585499d7796caaa50f58fad33a348 each
had all10 checks PASS.53 stacks on52 and now contains:

-03d0db7: Linux test timer stopped at signal delivery; exact-one snapshot
 assertion retained. Earlier Linux multi-window lifetime fix remains.
-527fb72: operational snapshots/background Qt/lock/unlock/recovery reads borrow
 the actual owned process's shared HTTP capability. Missing/wrong scope is
 refused before wallet keys/backup access. No HTTP write/failure-to-CLI path.
-9ba9cfc: real config-tamper negative caught cached-config regression. Native
 private config custody plus exact4KiB digest rechecked before any request or
 capability loan. Exact-original restoration requires a subsequent explicit
 read; no new auth/port adopted. Unrelated speculative64b929c/7acf495 harness
 changes were removed normally; historical FAIL logs remain.
-42cb9a8: genuine queue32 produces20 HTTP200/12 HTTP503. At most3 positively
 rejected idempotent-read attempts with bounded jitter; session recovers when
 queue drains. Invalid auth/config/reply/connection uncertainty and all writes
 are never replayed. All native/frozen gates require the busy proof.
-bb28a1a: queue stress only in explicit acceptance, not interactive startup;
 actual frozen Mac E2E JSON is retained in artifact with source/checkout IDs.
-8b50296: reviewed basename:line diagnostics localize Windows failure safely.
-5555df8: idle socket expiration5s BEFORE request, fresh OS endpoint proof before
 auth, no failed request replay. Genuine5.1s idle probe. Fixes absolute import in
 PyInstaller __main__ that caused Mac frozen UNKNOWN after full wallet tests.
 Sign/Broadcast independent CLI hashes/approval/OS lease/irreversible locks stay.

## Exact evidence and limits

162units=129PASS/33platformSKIP/0FAIL. At5555, actual downloaded Windows native
Core/WSP/Qt receipt PASS including stale pre-sign/pre-broadcast, custody and
recovery. Linux native headless/Qt and frozen headless/desktop CI PASS under
independent root witness. Mac native and frozen CI PASS (run38965264090).
Windows final package aggregate and separate Linux developer-Core rebuild were
still RUNNING at last snapshot; refresh them first. Cancelled obsolete-head
runs are not PASS, and docs-only new HEAD still requires its current CI.

Actual local5555 final .app ran on MacBook ARM64 with offscreen Qt and an isolated
fixture Keychain: config-tamper denial/restoration, idle/busy, actual BIP352,
Receive/History, exact approvals, Send/Sign/Broadcast/confirmed change, uncertain
locks, backup/lock/wrong-password/recovery/fresh Core, reorg1/12/100. DMG verified.
Manifest tail initially imported reused venv's old package; completed with
PYTHONPATH=src after source/checkout/payload/Core digest checks. No binary/gate
changed. Full reproduction must use this checkout or PYTHONPATH=src.

Local artifacts: outputs/issue45-heartbeat-20261016T204821/LOCAL_MACOS_5555.
AppZIP SHA25656c7526dc4092867359eb3b133502df84ce276463946d65cd2b06866089b0aff;
DMG7ff2acbade4be94344916517bf289c5600e26dfe98c55c9b0acf5749cf5ed061.
See docs/evidence/issue45/HTTP_IDLE_BUSY_5555_LOCAL_FROZEN.json and platform
5555 native receipts. Earlier9ba/42cb/bb28 Mac source PASS and historical c478
Mac/c877 Windows artifact inspection stay separately labelled. Windows c877
archive354 actual file hashes/Core pair verified, not new runtime qualification.
Linux5555 frozen download/inspection progress is in the separate heartbeat log.

Offscreen is not Finder/Cocoa Auto/physical signoff. Mac fresh-recovery flags
not exercised remain false. Linux is never relabelled official-signed. Physical
Mac/Windows/Linux and external review remain PENDING_OPERATOR/DEV_REVIEWED.
DEV agreement permits clean isolated hosts only, NEVER treasury-signing machine.

F01/F02 component: actual REGTEST halving interval150, not production parameter
200000. Coinbase99/100 unavailable,101 eligible; subsidy-only treasury independent
cutoff400000; all fees miner; locked/immature/untrusted not available. At4951
REGTEST subsidy is zero, so nonzero-subsidy sunset400001 runtime proof cannot be
fabricated from unchanged binary. Pinned original C++ functions + explicit type/
parameter SHIMS provide SOURCE vectors and750000WAM production-parameter lifetime,
not mainnet/Core binary high-height PASS. Full mining account UI/Q11 remains open.

## Next unblocked P0 work

1.Refresh53 exact-head CI. Fix genuine failures on this branch before features.
 Inspect actual latest frozen receipts and hashes, especially Windows5555 or
 successor, and root/developer-Core job. No merge/readiness promotion from SKIP.
2.F01/F02 native Core mining-account GUI and funds reconciliation remain missing;
 reuse mining_account.py read model, maintain separate Core/WSP ownership and
 signing authority. Complete legacy read-only/fixture scanner CLI migration only
 where needed; do not repeat already proven operational HTTP migration.
3.Persistent owned Core lifecycle, explicit read-only external REGTEST attachment,
 bounded port-collision recovery, broader coalescing/busy UI and mandatory >=2
 genuine peer-node lab remain open. No uncertain write retry or custody reset.
4.BIP39 GUI/durable custody/import/recovery and remaining K/F/R/Q gates follow
 canonical order. All integrated V1 registry cases remain PENDING until complete
 matching source/Core/frozen/physical evidence. Never declare production Final.

## Schedule and usage

T0=2026-10-16T15:47:58Z (22:47:58UTC+7). Same existing automation was updated
ACTIVE for the one requested next run20:47:58Z (03:47:58 on17OctUTC+7). Heartbeat
actually arrived20:48:21.727Z,23.727s later, and coalesced into the held lease.
It is now tool/config-verified PAUSED; no next run, duplicate or recurring retry.
Observed usage at heartbeat primary1%,weekly16%,ordinaryAllowed=true,credits0;
no purchase/reset performed or assumed. Record any actual quota failure, not
an inferred one. Leave a checkpoint before stopping; do not schedule more work
without a new explicit owner request.
