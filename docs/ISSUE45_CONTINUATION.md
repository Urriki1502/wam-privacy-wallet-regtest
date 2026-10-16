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
