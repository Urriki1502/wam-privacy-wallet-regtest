# Current A06-A/B/C continuation — owner-authorized recovery policy

Baseline Draft120 `5130e432eaa440cc4723dd02b2e67aeb2579a462`; new focused branch
`feature/issue45-a06-recovery-aware-gate-20261022`. Preserve original114rawFAIL,
parent120, main/RC1 and independent branch work. Acquire engineering lease first.
No automatic merge. REGTEST only, qualified pinnedv0.1.11;v0.1.12candidate-only.

Owner explicitly replaces the obsolete release requirement that101fresh blocks
must survive SIGKILL without recovery. New mandatory native+frozen gates are
A06-A graceful/no-reindex, A06-B explicitly authorized exact-chain/wallet reindex,
and A06-C genuine owned recovery-child interruption/fail-closed/explicit continuation.
See [exact policy, scope and limitations](ISSUE45_A06_RECOVERY_ACCEPTANCE.md).
Historical diagnostic rawFAIL remains immutable; it cannot count as recovery PASS.
All ordinary gates and exact-head artifact assertions remain mandatory. Platform
CI PASS never implies fullQ05/V1, physical/clean-device or independent review.

Resume from the current live Draft description and
`outputs/codex_acceptance_resume.json`; inspect actual CI before further work.
Do not rerun unchanged predecessor tests or create a second branch/PR for this
same task. Fix current genuine failures sequentially on this focused branch.

# Historical records — superseded policy and checkpoints follow

# Current acceptance continuation — 22 October 2026

Latest reviewed parent is Draft119 `3adb5a2fc7f2181dec8f3eb1de6cbe65be66a7e5`.
The historical PR67 and earlier handoffs below do not override the current live
Issue45/PR graph or `outputs/codex_acceptance_resume.json` audit checkpoint.
Acquire a NEW engineering lease before work; refuse concurrent engineering.
No automatic merge or schedule recreation. Main/RC1 and independent branches
remain unchanged. REGTEST only, qualified pinned v0.1.11; v0.1.12 candidate-only.

Current unit: `audit/issue45-bip39-index-recovery-20261022`, one Q05 acceptance
coverage task on119. Existing native/frozen recovery gates covered legacy WSP32,
while managed BIP39 12/24 crash/reindex had only independent Mac evidence. Add
real64-byte wallet/native-anchor/IPC/signed+uncertain/history checks to the same
native and final frozen test invocations. Exact source/frozen Windows/Linux
qualification is pending until new CI/artifacts are independently inspected.
See [scoped test and limitations](ISSUE45_BIP39_INDEX_RECOVERY.md).

Preserve Draft114 and all original A06 FAIL evidence; original no-reindex gate
and all three release aggregates remain mandatory and nonpassing. New explicit
recovery components never waive those gates or claim full Q05/V1 acceptance.
A fresh parent1191001-block observer reproduces fail-closed HTTP response-read
TimeoutError. No global timeout/retry relaxation, automatic reindex, data erasure,
post-crash mining, transaction replay, anchor reset or upstream Core change.

# Historical records — superseded checkpoints follow

# Latest PR67 regression fix — native image exit race

41c14bd all10CI SUCCESS is verified predecessor evidence. Successor6f973d1
real independentGUIprocess proof passes Mac native/source and Linux nativeQt,
but Linuxfrozen desktop failed at actual startup collision: Core exits between
poll() and /proc/PID/exe readlink, FileNotFoundError escaped the ownership-denial
handler. Fix normalizes native image lookup OSError to CoreBindingError, NEVER
accepts ownership. Existing startup handler retries ONLY actual exited+private
bind-denial proof, zero auth bytes to competitor; other failure denies. Native
regression verifies missing image is denied/redacted. No new retry after yield.
Inspect newest actualHEAD/CI; do not infer successor qualification from41c14bd.

Latest source/runtime fix requires new exact-head real collision/native/frozen
qualification on allOS. Do not expandQ05 until CI recovered. Same existingPR67
only, no auto-merge/otherbranch/Core/ownerwallet changes. Lease and logs below.

# Current checkpoint — PR67 native Qt crash fixed; Q05 remains partial

Use ONLY existing branch feature/issue45-t05-gui-continuity-q05-20261017,
DraftPR67, basePR66/71a1e7b. User explicitly authorized takeover. Do not create
PR68 or change PR66/61/60/main/RC1/upstream/owner data/anchors. REGTEST only,
v0.1.11 independent pins unchanged, no merge/rebase/force-push or T06 attach.
Acquire engineering lease before work; refuse concurrent work. Current turn's
tracked lease87623 is not evidence of a future holder; actual release in
outputs/pr67-qt-20261017/RESUME_LOG.md. Earlier checkpoints below are historical.

41c14bd687a5f6fbda066d3d1e306e1e8f1d2177 fixed the native shutdown crash.
ResponsiveRow had left panels unparented until resizeEvent; hidden windows left
independent widgets for PySide's unordered destruction visitor. Eager layout
ownership fixes it, retaining QApplication.shutdown and native destruction.
Mac native OS stack and baseline5tests exit139 reproduced; fixed targeted8,
full209(175PASS/34platformSKIP),10independent runner exits and Cocoa8 all exit0.
See docs/PR67_QT_LIFETIME.md. Actual41c14bd all10CI jobs SUCCESS independently
verified, including Windows native/frozen, Mac native/frozen, Linux native,
frozen desktop/headless and developer-Core rebuild. Committed exact snapshot
PR67_41C14BD_ALL_CI.json is predecessor evidence, not successor qualification.

Local41c14bd finalMac app/DMG actually ran Core/WSP/SQLite/Qt operational,
security/recovery/reorg E2E and exited0; bytes/hashes/source provenance verified.
Original Core pair unchanged. Mac ZIPa0fe9088bd5798ef2ae68c960be025b56ba606edea1ac59fc77c0e3432ea17ff,
DMGbcc351718b5b16359150278482684c929775b64b86c63097e2b1a658a763337c.
ActualLinux downloaded archives inspected193headless/454desktop file hashes,
25safe desktop links, x86_64ELF/Core pins and exact41c14bd/8ae4141 checkout.
No localWindows/Linux execution or physical approval claimed. Windowsfrozen
artifact12097376351 downloadexec12663 in progress at checkpoint; inspect once
complete, never hash partialfile. All receipt/public logs in separate outputdir.

Additional real defect: downloadedWindows nativeT05 JSON has literal backslash-n
trailer and cannot parse; operational JSON is valid. Successor fixes newline and
adds actual JSON round-trip assertion. Do not relabel that oldT05 receipt valid.

Next acceptance unit adds THREE genuine independent nativeQt GUI processes:
clean close, abrupt kill AFTER authenticated status/Qt readiness, clean reconnect;
assert original supervisor and same chain tip survive. Prior client os._exit test
remains a separate IPC-disconnect case. No signing/network retry or wallet
adoption. New public receipt records independent Core pair and reused clean-source
provenance before/after native probe. Probe is explicitly consented, control/status
only, not runtime wallet authority. Local realCore three-GUI proof passed before
source-provenance additions; exact committed-head rerun and successorCI pending.

Next: inspect latest67 CI, fix failures first. Verify actual successor nativeCore
three-GUI proof on Mac/Win/Linux and source/artifact identities. Only then extend
managed WSP wallet reopen preserving identity/history/irreversible reservations
and permission-scoped IPC capability. Current managed GUI still session=None,
snapshot=None; full_gui_q05_qualified=false is mandatory. No fresh-wallet creation,
reset, automatic adoption or releasing uncertain reservations to make Q05 pass.
Final frozen managed-Q05 and operator/physical remain PENDING.

# Historical records

# Final current checkpoint — own Draft60 / Draft61

2026-10-17 resumed at01:52:55Z. Active branch
feature/issue45-build-source-provenance-20261017, based on own60/db12108.
Runtime/startup60 remote=db12108e784f1f21680d463d25ec4c751e9c6dc6.
Provenance61 runtime=0d111f804e9dfcc02af88ccca7dd1c8bffc2efd6; Windows-only
native-source-read correction=e35e78041001f43a41857ed72c40306da78d3a76;
following checkpoint adds docs/evidence only. Verify actual current HEAD and CI.
Never merge automatically, rebase/force-push or edit independent55–59. main/RC1,
owner data/anchors/miners and upstream Core unchanged. Official v0.1.11 Core/CLI
pins unchanged; v0.1.12 is candidate-only, Update Manager remains deferred P1.

Current exclusive engineering lease53937; NOT proof of a future holder. Read
outputs/issue45-session-20261017T015255/RESUME_LOG.md for actual release/final CI.
Acquire NEW scripts/engineering_lease.py --hold before engineering, exit73 REFUSE.
Keep the existing recurring5h schedule anchored at original23:39:35Z16Oct;
nominal next04:39:35Z17Oct (11:39:35 UTC+7), do not create duplicates or shiftT0.

## Newly verified evidence

-54/bfd2400 all10 native/frozen SUCCESS; downloaded actual Windows package354
 files, Core pair, AMD64PE,7 pages, mining99/100/101,DPI125/150 verified. See
 PR54_BFD2400_WINDOWS_FROZEN_INSPECTION.json. Not successor qualification.
-55–59 reviewed read-only as independent c5edaef sibling stack.59/d26fc8f actual
 Linux v0.1.12 signed Core→WSP→SQLite receipt downloaded, matching source and
 independent node/CLI/manifest pins,4749990000 atoms at102, restart no duplicate.
 Latest59 has10SUCCESS/1conditional developer-Core SKIP. Its Windows/macOS
 regression jobs exercise v0.1.11, not v0.1.12 runtime/frozen acceptance.
-60/db12108 Mac native/frozen and Linux native headless/Qt/frozen PASS. Windows
 actual native operational source step PASS; downloaded artifact12086002886
 outer8727aa5b307e1acc3fbbb6f4244c8d4848c5f86e8740bb016a19864569cd54b9,
 actual source=db12108 and startup6 reaped/0 competitor bytes/no restart, plus
 actual signing/confirmed change/recovery/stale-before-sign/broadcast verified.
 Windows final frozen aggregate and developer-Core rebuild still running at last
 snapshot. Do not count them PASS yet. Native socket/ACL/signing gates retained.
-61/0d111f8 COMPLETE local Mac build exited0: final .app actually executed genuine
 Core/WSP/Qt/startup/mining/operational/security/recovery/new-Core/reorg1/12/100,
 DMG verified, source identity checked before frozen execution and after E2E.
 Source=checkout=0d111f8;258 native tracked files unchanged. Actual archive bytes,
 ARM64 MachO, safe bundle links, independent Core pair and manifests inspected.
 ZIP2b18e08b6f882a623d3adcc1dc0d4d01be4808edc2fd6fcd79e1ae2cf20f9733;
 DMGc55fae4d849a96d4b45749924b6e00954ea77ff55b1338688d43f4c3e0318185.
 Files under outputs/.../LOCAL_MACOS_0D111F8; public evidence filenames
 STARTUP_BUILD_0D111F8_*, BUILD_SOURCE_0D111F8_MAC_RECEIPT.json.
-61/e35e780 Windows native source unit/custody step PASS, including actual native
 source handle writer-refusal test; actual Core vault/reorg step PASS, operational
 Qt/final frozen still pending. CI at this newer SHA must be refreshed, not
 relabelled from0d111. Mac182 supplemental units148PASS34platformSKIP0FAIL.
 Native Windows-only handle test is skipped on this Mac; actual runner executes it.

## Observed failures/fixes and next work

Initial startup extraction lost function-local sys import; d905 fixed platform
scope, actual full Mac source rerun PASS. Windows raw TCP readiness failed before
any auth; c33c3ba permits bounded pre-auth TCP timeout polling, never HTTP replay,
retains permission/unknown/uncertain failure. db12108 uses exclusive Windows
collision-fixture bind. No post-start retry, attached node, wallet keys or owner
configuration exposed by the disposable context. T05 persistent lifecycle NOT
implemented by this helper. Exact warmup-28 is startup-only; runtime positive503
retry policy/sign/broadcast and native custody/reservations remain unchanged.

Windows61 initial units failed lstat-vs-CRT-fstat metadata comparison on recently
written fixtures. e35 reads via ONE native handle API, holds parent handles and
refuses reparse/hardlinks and write/delete sharing. No wallet-custody code changed,
no source gate disabled. Real Windows source unit step now PASS. Build source
checks are not host attestation or dependency/production qualification.

1.Refresh final exact-head60/61 CI, fix genuine failures in existing own PRs.
 Inspect real latest Windows/Linux frozen receipts and full artifact hashes;
 never infer from green unit/source checks or conditional SKIP.
2.Keep source/native/frozen/physical layers separate. Offscreen Mac != Finder /
 Cocoa Auto / owner visual acceptance; Windows/Linux physical remain pending.
 No integrated Issue45/Q11/R04 final PASS or real-fund/mainnet qualification.
3.Then next unblocked P0: persistent owned Core lifecycle T05, explicit safe
 read-only attach T06, >=2 genuine peer-node lab, durable BIP39/import/custody
 and operational funds reconciliation; do not redo55–59 candidate or MiningGUI.

Separate resume log records latest usage/schedule/lease. Ordinary usage remained
allowed at last query82%,weekly44%,credits0; no actual usage-limit failure,
reset assumption or purchase. Leave checkpoint before capacity ends. This owner
request was immediate; existing recurring execution remains separately authorized.

## Historical engineering checkpoints

# Current next unit — frozen source provenance (R03/R04), stacked on Draft60

Own active branch feature/issue45-build-source-provenance-20261017. Read FULL
live Issue45 and refresh exact-head CI before engineering. Acquire exclusive lease
first, refuse exit73; current session PTY53937, actual release in separate log.
Second P0 unit: docs/ISSUE45_BUILD_PROVENANCE.md. All181 supplemental units
148PASS33platformSKIP; source dirty-tree denial tested without deleting work.
Source/native/frozen/physical statuses are separate; new frozen builds pending.
Do not modify/rebase/merge independent55–59, upstream Core, main/RC1 or owner data.
No automatic merge. v0.1.12 candidate-only; Core Update Manager remains deferred.

Draft60 own startup unit:7f13cd1 +d905f3e platform-scope fix, c33c3ba raw TCP
readiness timeout correction, db12108 exclusive Windows collision-fixture port.
PR60 remote head=db12108 (verify live). Local owned-startup branch pointer may
lag remote because isolated fixes were fast-forward pushed from the common
successor HEAD before its own changes were committed. No rebase/merge/force push.
Actual Mac full Core/WSP/Qt operational/security/new-Core recovery/reorg source
PASS after platform fix; actual startup6-process/zero-auth-byte proof PASS. First
Windows CI failed generic raw TCP readiness category; positive pre-auth raw TCP
timeouts may now wait (never HTTP request replay), permission errors fail with
safe numeric category. Collision fixture uses Windows exclusive bind. Native
Mac/Linux checks passed atd905; successor Windows/frozen checks must be refreshed.

PR54 bfd2400 all10 native/frozen SUCCESS. Actual downloaded Windows package
12082059503 outer0e3f4661b9a58eacb4a8c255db725e0897198ea190e7372cd1d81ae14c7f6482;
inner048671e4d066806fe1e61bdca3b6eff82e55db69bca12132a7d71293acee1af1.
354 file hashes, independent Core pair,7 pages, actual mining GUI99/100/101,
125/150% frozen receipts inspected; NO local Windows execution/physical claim.
PR59 actual candidate receipt retained separately; its Linux native WSP proof is
NOT Fusion WalletSession/GUI/frozen/signing activation. No pin advances.

Continue exact-head regression/frozen testing and fixes on existing own PRs.
Existing recurring5h schedule remains anchored at original T0, no duplicates or
rescheduling. Separate outputs/issue45-session-20261017T015255/RESUME_LOG.md
records actual final SHA/CI/artifacts/usage/lease. Next after qualified current
units: persistent owned lifecycle T05, explicit safe attach T06, real peer-node
lab and remaining durable wallet/custody/import workflows; do not duplicate
already verified Mining Account or v0.1.12 candidate components.

## Historical startup and Mining Account checkpoints

# Current resume — owned startup component after qualified Draft54

2026-10-17T01:52:55Z session. Refresh actual branch/HEAD/CI; this checkpoint is
not a current lock. Acquire scripts/engineering_lease.py --hold (exit73 REFUSE).
Current branch feature/issue45-owned-startup-20261017 stacks on54/bfd2400.
New component: docs/ISSUE45_OWNED_STARTUP.md. Preliminary172units139PASS33SKIP;
actual six-process Core collision/pre-auth/cleanup probe PASS. Exact source,
native/frozen cross-platform successor CI remains pending at this commit.
No main/RC1/owner data/upstream/other branch changes, force push or auto-merge.

Live Issue45 unchanged from last full read (updated2026-10-16T14:26:40Z,54004
characters). Draft54 bfd2400 all10 checks SUCCESS, now historical qualification
for the new runtime. Independent55–59 fork fromc5edaef, NOT descendants of54.
Reviewed intake/candidate RPC/WSP scope and actual source diff; no merges/rebases
or edits to their branches.59 d26fc8f genuine Linux signed v0.1.12→WSP BIP352→
SQLite job38992178458 PASS. Downloaded actual artifact12085985164 outerSHA
18fcd64bf08318d0caba0493c509c3befeb9aa9b9e92e3dd3caa2abbce344283; receipt
source=d26fc8f, amount4749990000 at102, restart no duplicate. Signed node/CLI
9d13b329f451486930a3cf799b360237bcc7e858e94a964f817df520428374db /
455d85aa1ce35f70c71da6947a79b549f33c4116168ff7ecdc41b067a3fbe907.
Candidate-only: Fusion activation/signing/frozen/physical false.59 Windows still
running at last refresh. v0.1.11 runtime pins stay unchanged. Core Update Manager
remains deferred P1. Do not duplicate the candidate work or promote v0.1.12.

Current lease PTY53937. Separate outputs/issue45-session-20261017T015255/
RESUME_LOG.md records exact final CI/artifacts and actual lease release. Existing
5-hour recurring schedule remains authorized; do not shift original T0 or create
another task. Usage read ordinaryAllowed=true,primary1%,weekly31%,credits0;
no reset/purchase performed or assumed. This is an owner-requested immediate run,
not an early scheduled dispatch; the next recurring nominal boundary remains
2026-10-17T04:39:35Z (11:39:35 UTC+7).

Next: complete current real-Core source/frozen qualification, fix actual CI on
same branch/PR; then next unblocked P0 real multi-node lab / persistent owned Core
lifecycle, explicit read-only attach and durable wallet/custody workflows. Do not
call the disposable startup helper a persistent wallet or replace T05/T06 gates.

## Historical Mining Account checkpoint (superseded CI snapshot)

# Issue45 continuation — Mining Account read GUI; integrated V1 still pending

Refresh FULL live Issue45, actual Git/PR graph and exact-head CI first. REGTEST
only, no main/RC1/upstream Core/owner data/owner anchors/automatic merge/force push.
Core Update Manager remains deferred P1. Never count SKIP or historical PASS as
qualification of a changed runtime. Cross-platform physical tests remain pending.

## Exclusive engineering and recurring execution

Workspace: work/production-v1, official Urriki1502/wam-privacy-wallet-regtest.
Acquire scripts/engineering_lease.py --hold BEFORE engineering. Exit73 means
REFUSE concurrent work, never delete/bypass lease. Current session holds PTY62414;
actual release is recorded separately under outputs/issue45-session-20261016T233935.
A handoff/session ID never proves a current lease. Preserve uncommitted changes.

Owner now explicitly authorized recurring execution every5h until Issue45 is
actually completed or owner requests stop. Same automation ID
linux-regtest-single-continuation was UPDATED, not duplicated; ACTIVE verified
through app tool, persisted config and read-only scheduler row. T0:
2026-10-16T23:39:35Z =17Oct06:39:35 UTC+7. First nominal next:
2026-10-17T04:39:35Z =17Oct11:39:35 UTC+7, then every5h without daily reset.
Desktop scheduler has early dispatch jitter: actual stored next_run_at was
04:34:58Z =11:34:58 UTC+7. Prompt requires bounded waiting until the nominal
T0-anchored boundary BEFORE engineering, then exclusive lease acquisition. Do
not shift phase, create duplicate retries or buy credits. Pause this automation
only when Issue45 is really completed or owner requests stop. This supersedes
old one-shot/PAUSED schedule text in the c5edaef historical handoff.

## Verified immutable baseline and existing stack

Main50e1ea94df61b8400cbab3bffe0fbdd285c6b419; immutable RC1
144d87700b87a241467172adfad3692b41e1d273 unchanged. Native WSP pin
ac55f13423620252bdbf848c7e8a280c3b84721e. Official signed Core v0.1.11 remains
independently pinned node AND CLI. Linux remains separately approved developer
build under independent root witness, NOT official-signed. No v0.1.12 activation.

PR51 at516b4f2, PR52 atc877705 already prove mining accounting/source vectors.
PR53 atc5edaeff086947f25dd673955846c5c7615c4634 now has all10 native/frozen checks
SUCCESS, including Windows and developer-Core rebuild. Runtime5555df8 implements
owned protected HTTP scanner/operational snapshots, exact config custody,
OS endpoint proof before auth, bounded positive503 read retries and idle socket
expiry BEFORE a request. Signing/broadcast keep independent CLI hashes, exact
approval, native OS lease and irreversible reservations. Do not repeat this work.
No PR has been merged. New focused Mining Account branch stacks on qualified53;
reuse Draft54 for fixes, never duplicate the PR. Branch
feature/issue45-mining-account-gui-20261017. Runtime91988714ccf8ae07b1457a3d50e64a4b815e22c1;
test-only correction1ed3b34d119ec5ff8014207ce695ba310769c24b; following checkpoint
adds packaging preflight/docs only. Refresh actual branch/HEAD now.

Actual downloaded PR53 Windows frozen artifact12076012325 (run38966708823):
outer224d1dcd0bf8d535797ebf38e38788cc48b15818cd9934e2ac873484e4b6bd73,
innerf5b5e90f34db6a073b072c3b94f5c3d08de722f9d1fff1569754d9ca79e35858;
354 actual member hashes, AMD64 PE, independent Core pair,125%/150% frozen E2E
receipts verified locally WITHOUT executing Windows. Actual checkout
c39b40050b0c2f4de0fdd6647e8f216b30e1e9e2 differs from source head as documented.
See docs/evidence/issue45/PR53_WINDOWS_C5EDA_FROZEN_INSPECTION.json.
Historical local5555 Mac frozen app/DMG proof and Linux5555 headless inspection
remain in docs/evidence/issue45 and outputs/issue45-heartbeat-20261016T204821;
NOT qualification for the new mining GUI runtime.

## Current focused engineering unit: F01/F02/Q11 partial

- Fixed owned /wallet/test read-only scope on shared protected HTTP connection.
 No caller wallet selector, attach, keys/descriptors export, import or writes.
 Ordinary scanner call allowlist unchanged. Same config/process/socket gates and
 bounded busy-read policy; no CLI fallback or write retry.
- Reuse MiningWalletBalance. Get Core balances, safe/spendable UTXOs and exact
 gettxout amount/script/depth plus getaddressinfo ownership. Treasury ownership
 overlap rejected.512-UTXO/1MiB read bounds fail closed. Repeat balance/UTXO reads
 and verify unchanged tip/genesis/zero peers before publishing a complete model.
- Seventh native Qt Mining Account page: eligible/trusted/pending/immature kept
 separate from WSP payment funds. Next-block split explicitly a REGTEST network
 rule, not owned income. Correct150-block REGTEST halving;120s probabilistic
 target, treasury5% of subsidy only through400000, all fees miner.
- Snapshot integrates with existing background worker, clears on lock/read
 failure, recovers only after verified read. No new Core signer/transfer authority.
- Genuine Core mining probe compares independent CLI vs protected HTTP under
 no-CLI/no-full-hash guards; actual99/100/101 GUI amount/clear tests and screenshots.
 Final platform entrypoints require the new HTTP/maturity-GUI receipts.

Supplemental167 tests:134PASS/33platformSKIP/0FAIL. Actual mining GUI
probe PASS. Full source first run FAILED only at old6-page assertion on fresh
Core recovery; corrected to7 plus mining-state assertion without changing custody
or recovery gate. Full second source run PASS. Actual final local Mac9198871 app PASS with
Core/WSP/Qt/mining maturity/sign/broadcast/backup/lock/recovery/new Core and
reorg1/12/100; hdiutil DMG verified. Full build exited1 at old5555 manifest
create-only refusal; preserved that old manifest, verified current payloads,
completed metadata only. Never claim original whole-build exit0. Added early
nonempty-output refusal and checkout-change guard for clean future builds.
Local ZIPc8416160e728436fefc3b934d049a4af9899a452ce7afeb54637fc7b651c804f;
DMGfe17981ad3854efa14e66f35cf05284613f7a6a430a1f811e164e479ea0e3594.
See MINING_9198871_MACOS_FROZEN_E2E.json and matching inspection. Actual frozen
checkout1ed3b34 is test-only child of runtime9198871; not relabelled later HEAD.

CI919 native headless FAIL: a Qt negative unit was incorrectly placed in the
headless test_v1 suite. Moved UNCHANGED assertions into test_fusion_mining.py in
existing GUI suite, retaining mandatory genuine Qt/frozen maturity gates. At
1ed3b34 native-contracts/canonical SUCCESS; remaining platform jobs running at
checkpoint. Refresh exact new HEAD CI, do not infer final PASS from this text.
Separate session resume log records later exact-head results/artifact inspection.
No integrated V1/Q11 PASS or physical signoff is claimed.

## Next unblocked work / limits

1.Finish current unit's source/frozen Mac test, exact-head native/frozen Windows
 and Linux CI. Fix failures on the SAME branch; inspect actual receipts/hash
 manifests. No merge or qualification from parent PR53 alone.
2.Mining Core account is disposable and read-only; durable account import,
 Core-account signing/transfer, complete Core/WSP funds reconciliation remain
 open. Do not grant WSP signer access to unrelated Core keys or treasury funds.
3.T05 persistent owned Core lifecycle, T06 explicit read-only external REGTEST
 attach, T08 bounded port collision and >=2 genuine peer-node lab remain open.
 No uncertain write retry, external miner restart or arbitrary config editing.
4.BIP39 GUI/durable custody/import/portable clean-host recovery and all remaining
 K/F/R/Q cases follow Issue45. Physical Mac owner and authorized clean Windows/
 Linux hosts, external review, codesigning/notarization remain distinct gates.
 Never use treasury-signing computer or represent production/mainnet readiness.

F01 constraints: source production halving200000 != actual REGTEST150. Actual
coinbase99/100 unavailable,101 eligible. At4951 REGTEST subsidy is zero;
nonzero-subsidy sunset400001 cannot be fabricated from unchanged binary. Original
pinned C++ source functions with explicit type/parameter shims prove SOURCE
vectors and750000WAM production-parameter treasury total, not mainnet/runtime
high-height acceptance. Full integrated V1 registry remains PENDING.

Use sibling .venv Python3.12 with PYTHONPATH=src plus
../../outputs/production-v1-20261016/reference-deps, QT_QPA_PLATFORM=offscreen.
Reused venv editable install points at an old checkout; never omit PYTHONPATH or
modify that checkout/venv/upstream. Local Mac bundle builds likewise set
PYTHONPATH=src, PATH=<sibling .venv/bin>:$PATH. Generated old5555 artifacts were
preserved separately before rebuilding. Keep separate resume log and actual
usage failure evidence; do not assume reset or buy credits.

## Latest final validation checkpoint

Clean COMPLETE local Mac build at ebc5b0768d0fa6af8bea90df15223ce8a56a181d
completed exit0 including final frozen mining99/100/101, full Core/WSP/Qt security,
new-Core recovery and reorg gates, DMG verify and all manifests. Source/checkout
BOTHebc5b07, no metadata repair. MINING_EBC5_MACOS_FROZEN_E2E.json and inspection
record exact hashes; outputs/issue45-session-20261016T233935/LOCAL_MACOS_EBC5
contains actual packages. Previous919 build-tail failure remains historical.

CI1ed3 Linux headless/native Qt PASS, macOS underlying real E2E PASS but workflow
FAIL because its separate assertion still expected6 navigation pages. Updated
that workflow to require7 AND actual new mining GUI depths/HTTP comparison.
Executed all revised workflow assertions against the actual full-source-second
Core receipt successfully. Following commit is CI-only/evidence; refresh exact
HEAD CI, fix further failures on SAME Draft54. New Windows/frozen/Linux rebuild
and physical gates may still be pending; never promote from historical passes.
Usage last observed92%,ordinaryAllowed=true,weekly30%,credits0; no actual quota
failure or purchase/reset. Separate resume log holds final CI/schedule/lease
release facts after this commit. Keep recurring5h ACTIVE under latest owner
request; no second scheduler. Next P0 after current CI: persistent owned Core
lifecycle T05, explicit read-only existing-Core T06 and bounded port collision
T08; mining GUI is read-only and full custody/transfer/BIP39 integration remain.
