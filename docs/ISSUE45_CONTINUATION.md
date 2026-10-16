# Issue45 resumable checkpoint — 16 October 2026

Canonical contract: https://github.com/Urriki1502/wam-privacy-wallet-regtest/issues/45
Read it completely and refresh GitHub before engineering. Never auto-merge,
force-push, modify RC1/main/upstream Core or access owner data/mainnet.

## Current integration and lease

Workspace work/production-v1; branch fix/issue45-linux-evidence-identity-20261016.
Runtime460eceff6ffe36c638cfadce53e2016c9d3c6595, Draft50 on49.
Lease63300 was held for this run. Release is recorded in the separate local
outputs/production-v1-20261016/RESUME_LOG.txt. Acquire a new exclusive lease with
scripts/engineering_lease.py --hold; refuse concurrent engineering. Never infer
lease ownership from this document. Preserve all other worktrees/user files.

Main50e1ea94df61b8400cbab3bffe0fbdd285c6b419 and immutable RC1
144d87700b87a241467172adfad3692b41e1d273 were confirmed unchanged.

## New focused Draft stack, no merges to main

-46,90561d159cf3e79cd4d4c60cd5f04c491c108718: shared protected HTTP reads and
 complete42task/20Q acceptance registry; source/frozen Windows had a GUI race FAIL.
-47,e61ed4bd50f065d839c4e326ee4dcbeb42086f29: owned Core PID/image and kernel
 established socket before any HTTP/auth byte; no CLI/full hash per read.
 Windows aliases use same-file identity plus unchanged pinned metadata. Earlier
 cad7785 operational Windows image-string mismatch FAIL is retained, not waived.
-48,17ccbbd868ee0f10cd124f4cca61933ffb7f8c3d: real modal approval/background
 sync race reproduced and fixed; harness waits idle and emits timer/manual sync
 inside every actual modal, retains default Cancel/exact intent/backend gates.
-49,0ea42e61b638200e2f00c01fed3741c1642f0846: measured RPC111,/WAM:0.1.11/,
 protocol70016; typed compatibility refusal; actual copied-binary tamper,
 replacement and process-exit quarantine. Native/frozen-only path filters added
 to EXISTING workflows, no new job. Includes47/48 through normal merge ancestry.
-50,460eceff6ffe36c638cfadce53e2016c9d3c6595: Linux receipt provenance gap:
 emit independently pinned CLI hash, source/checkout, UTC environment and WSP.
 Validate declared source against checkout/direct raw parent without fetching
 history, including shallow CI. Native Linux/frozen proof PENDING on this SHA.

## Observed evidence (refresh; never inherit PASS for changed code)

150 local units=117PASS/33platformSKIP/0FAIL. Actual Mac full Core/WSP/SQLite/Qt
 Send/Sign/Broadcast,100000atoms confirmed/change, lost reply retains reservations,
 backup/lock/wrong-password/recovery/fresh Core and reorg1/12/100 PASS at3ea32b8.
 Offscreen is not Cocoa Auto or physical acceptance; false/not-exercised receipt
 flags remain false. Actual Mac RPC/version and copied-exec failure receipts at
 ea5ff6c are committed under docs/evidence/issue45. No mutated binary launched;
 originals rehashed unchanged. Latest metadata-only Core smoke460ecef PASS101
 blocks and version-bound HTTP; does not claim WSP/signing tested in that smoke.

PR48 run38889045778 has passed native operational Windows and is building/running
 actual packaged exe at checkpoint. Both Linux frozen gates in38889045717 PASS.
 PR49 runs38889211784(Mac),38889211782(Windows),38889211809(Linux) still in progress;
 native Mac/Linux source gates PASS, final frozen/Windows disposition PENDING.
 PR50 discovery/CI pending. Snapshot in separate outputs/ISSUE45_LIVE_PRS.json.
 Do not count missing/SKIP as PASS. All integrated-V1 Q rows remain PENDING.

Verified downloaded PR48 native receipts (archive SHA matches GitHub):
 Windows vault artifact12040279941,
 99d581b95dff4bea56bfbe5aab046fcb1afb1c272af7ce85ea835e00cc78932e;
 Linux headless artifact12041058114,
 f5ad7b348b338b583bdde7f3629e2cc750110fab49f6d1117785b0e9579b3fde.
 Both contain genuine owned-socket proof, real401 and zero-byte wrong-process
 refusal. Linux older JSON lacked source/CLI identity: preserved and fixed in50,
 not retroactively rewritten into qualification. Artifact links are under the
 corresponding GitHub run/artifact ID. Final new binary inspection still pending.

## Next unblocked order

1.Refresh47–50 exact-head CI, fix any red gate first. Inspect actual packaged
 manifests/HTTP receipts, download+verify SHA-256. Do not repeat old engineering.
2.Finish B03 native/frozen metadata proof50. Update registry snapshots truthfully.
3.T01 typed scanner block reads + lifecycle-owned reusable HTTP through genuine
 WSP/Qt, preserving source pins/zero-peer default; no per-read CLI/hash. Current
 GUI/scanner STILL use CLI; new HTTP is a tested component, not completedT01.
4.T07 bounded busy/coalesced idempotent reads; never auto replay uncertain writes.
 Then persistent managed Core/read-only cookie attach/port collision recovery and
 separately scoped mandatory multi-node private REGTEST lab. Follow45 dependency
 order before full BIP39 GUI/custody/import/recovery. Physical OS/operator,
 independent security review and production/mainnet remain separate gates.

Usage last observed primary96%,weekly77%,ordinaryUsageAllowed=true, credits0.
No reset/purchase/recurring retry was used or created. Leave checkpoint before
exhaustion; record any actual usage failure, never assume a reset. This file is
resumption evidence, not a claim that work continues after this turn.
