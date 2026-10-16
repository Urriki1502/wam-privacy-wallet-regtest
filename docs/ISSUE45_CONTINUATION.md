# Issue45 resumable checkpoint — F01/F02 and Core integration

Refresh the FULL live Issue45 and PR46–53; latest owner priorities F01/F02,
remaining Core integration. Core Update Manager remains DEFERRED P1; do not
implement it. No mainnet, owner keys/data/miner, upstream Core edit, automatic
merge, force push or RC1/main change. Only owned disposable REGTEST fixtures.

## Workspace / lease / exact heads

work/production-v1, branch feature/issue45-http-scanner-20261016.
This run held exclusive lease93427. Release is recorded in the separate
outputs/issue45-funds-20261016/RESUME_LOG.txt; acquire a NEW exclusive lease via
scripts/engineering_lease.py --hold and refuse concurrency. This document never
proves lock ownership. Existing uncommitted/user work was preserved.

PR50 baseline a9d96ac6b13c647ee5ee865f569abd0d40ccdc8a fully green native/frozen,
including Windows. PR46 historical modal race red was fixed once in48; do not
replay. All46–50 ancestors verified included. Main50e1ea94df61b8400cbab3bffe0fbdd285c6b419
and immutable RC1144d87700b87a241467172adfad3692b41e1d273 unchanged.

-51 feature/issue45-core-miner-accounting-20261016,
 516b4f26ca7ec343a489754a0b472c9aaaa41979. New REGTEST miner reward/fee/ownership
 and balance read model; genuine isolated Core maturity99/100/101, output audit,
 fee100%miner, lock eligibility, actual halvings150/151,300/301,450/451. Not a
 full mining-account GUI or import/signing authority. Initial8789176 Mac proof
 committed. Windows fixture selector/method mismatch fixed9f8402e with a PRIVATE
 fixture RPC scope; application windows_core_transport allowlist unchanged.
 LinuxQt fresh-Core failure localized background_snapshot exact-one-result
 assertion.516b4f2 prevents the acceptance QApplication quitting in its deliberate
 no-window interval; default interactive shutdown restored, assertions retained.
 Latest Linux source/headless/Qt and Mac source PASS at checkpoint; frozen and
 Windows aggregate still pending. Diagnostics emit only reviewed file:line and
 fixed public failure codes/counts, never arbitrary exception/key/config text.
-52 test/issue45-pinned-subsidy-vectors-20261016,
 c877705581d585499d7796caaa50f58fad33a348. Compile unchanged pinned WAM subsidy
 functions with explicit type/parameter SHIMS, SOURCE CONTRACT ONLY, never Core
 binary/mainnet E2E. Mac/Win/Linux native64 source receipts PASS. Windows CRLF pin
 mismatch fixed by .gitattributes preserving exact bytes, not a relaxed hash.
 Production-parameter200000 boundary vectors incl0/1/200000/200001/399999/400000/
 400001/600000/600001 and750000WAM lifetime; independent cutoff tests with fixed
 nonzero subsidy. Source.blobs d798155e1964adbdb3ccc48b44dd48fcde3b1602(params),
 5659e868f191f2c497950d690829f0369aa912d1(cpp),43e2e8c11a58b1b56141c63de470acb4743544ad(h).
 Source receipts pin actual merge checkout0c839153c02b876b4aecc75007897fa199042098;
 not silently relabelled current runtime. Latest Mac/Linux source PASS, native/
 frozen rest pending; refresh exact heads. Prior failures remain historical.
-53 feature/issue45-http-scanner-20261016, runtime30300a5eb07c74c435c1a3eb13d460e92e45f8d8
 plus this checkpoint docs. Owned shared HTTP scanner via typed block(hash,3),
 best-hash and peer-count;32MiB block bound,1MiB otherwise; chain/genesis/version/
 zero peers/OS-owned socket preserved. No HTTP write API or failure-to-CLI
 fallback. Genuine WSP scan/SQLite replay guards RAISE on CLI/full-Core-hash;
 they never return mock RPC results. Same source/frozen acceptance requires
 owned-http receipt. GUI/WalletSession normal reads STILL CLI: T01 incomplete.

## Proven observations and truthful limits

156local tests=123PASS/33platformSKIP/0FAIL. Actual Mac full Core/WSP/SQLite/Qt
 E2E PASS at e8e75ff: mining maturity/ownership/fee, BIP3524749990000atoms/102,
 replay0, native Send/Sign/Broadcast/confirmed change, lost reply reservation,
 backup/lock/recovery/fresh Core, reorg1/12/100. Receipt/module hashes committed.
 Later docstrings and Linux-only harness changes are not new platform/frozen
 PASS. Offscreen is not Cocoa Auto/physical; false/not-exercised flags stay false.
 Native source-contract receipts remain distinct from binary qualification.

**Actual pinned REGTEST halving interval is150, not200000.** The independent
 treasury cutoff is400000. REGTEST subsidy is zero from4951, so a nonzero-subsidy
 high-height sunset cannot be demonstrated simply by mining this unchanged
 binary. Source contract complements real REGTEST outputs, not fabricated
 high-height Core PASS. Full F01/F02/Q11/UI/integrated V1 remain PENDING.

PR50 downloaded artifact outer digests and inner archive hashes were verified:
 Windows12042082405 outer5112eae40ecf89c33acaedc3e94b7c5b0b2b20157282321ceda7777a818b0475,
 inner4db4f0a1b23fc5404218bb60b4552fc911bcc078678cb24baa40b6b280b39698.
 Linux headless12040599834 outer2600c6101b1eaf5f0f1f79196415675fb2b0494375306583d33f7a7496643fa3,
 inner93eae5e127bb0013d6e7d702e8b56d7164048da9398f9b4f24b8e34946638a9d.
 Checked frozen receipts/Core pair/RPC111,/WAM:0.1.11/,70016, sourcea9d96ac,
 production/mainnet false. Native Linux metadata fix50 verified in actual JSON.
 These historical binaries do not qualify changed51–53; new artifact inspection pending.

## Next concrete actions

1.Refresh51/52/53 CI. Fix any red exact-head gate FIRST on existing branches;
 normal merge updates to descendants, never force-push/replay. Logs/diagnostics
 in outputs/issue45-funds-20261016. Old obsolete-head runs cancelled only after
 replacement, never counted as PASS; latest required runs remain active.
2.Inspect new actual frozen receipts: mining_account_component and owned HTTP
 WSP scan proof. Verify artifact source/checkout and SHA256. Do not mark skipped
 or running jobs PASS. All integrated-case registry states still PENDING.
3.Complete operational GUI/WalletSession shared owned HTTP, retaining independent
 signing/broadcast approvals, persistent unsigned/uncertain reservations, source
 pins and OS custody. Next bounded busy/coalesced reads with no uncertain write
 replay; persistent managed lifecycle/read-only attach/port recovery/multi-node.
4.Complete mining/Core account UI and funds reconciliation before DEV preflight.
 Owner Mac; DEV Win/Linux agreement only on clean isolated hosts, NEVER the
 treasury-signing computer. Physical tests and external review remain PENDING.

Usage last observed primary92%,weekly92%,ordinaryUsageAllowed=true,credits0.
No reset/purchase/recurring retry created or used. No claimed credit failure;
record any actual failure and never assume a reset. Checkpoint before exhaustion.
