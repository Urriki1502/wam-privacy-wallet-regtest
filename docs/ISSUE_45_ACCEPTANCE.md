Current resume checkpoint: [Issue45 continuation](ISSUE45_CONTINUATION.md).

# Issue45 execution and acceptance registry

Canonical scope: [Issue45](https://github.com/Urriki1502/wam-privacy-wallet-regtest/issues/45), read in full, observed 2026-10-16T09:57:52.013008+00:00.
This registry is evidence bookkeeping, never an alternative specification or
production/mainnet permission. [Machine registry](../tests/acceptance/issue45.json)
contains the task/Q IDs including the new F-01a/F-01b subcases; original42 task IDs and20 Q IDs with separate SOURCE/CORE_E2E/FROZEN/
PHYSICAL/DEV_REVIEWED slots for all3OS. All integrated-V1 gates remain PENDING.
No aggregate95% or inherited RC1 PASS is asserted. Missing/SKIP is PENDING;
changed tested source/OS/Core/WSP invalidates prior PASS to STALE.
`acceptance_evidence.py` tests these rules without treating JSON as a trust oracle.

## B-01 branch/inspection evidence

Clean integration from PR43 `125dbd6`, containing PR41/39/38 by ancestry.
PR44 `1ace4e2` has merge-base995ff12 and was NOT an ancestor; its single Windows
fix was integrated once as90ed9be. Original heads remain untouched. Read-only
RPC code4c630306489df241077615e6058dc81024475d11. Main50e1ea94 and RC1144d877
unchanged. Public branch map in registry. No force push/merge to main/upstream edit.

## Implemented components, not completed P0 gates

- PR41 bcc9858: exact profile/account boundaries; real Mac SQLite Core backup/
  restore and unchanged source; Core permits duplicate key clones, so application
  identity checks are required. Full global/partial-overlap protection PENDING.
- PR43 125dbd6: BIP39 reference engine, full64byte native HD,16 literal public
  receive-code vectors required across OS; local Core/WSP receive+SQLite proof.
  Its current clean-clone native checks are recorded in PR43 snapshot. This is
  NOT GUI/anchored/persistent BIP39 qualification. No old32byte seed reinterpretation.
- PR44 1ace4e2: CREATE_NO_WINDOW mitigation. Native/frozen results in snapshot;
  physical absence of console flashes/main-window crash remains PENDING_OPERATOR.
- T-01/T-02 initial code: shared Python HTTP session, fixed127.0.0.1, bounded
  private config/auth, owner/ACL/no-follow checks, strict three-read method/param/
  response scope, bounded IO, static errors, serialized connection/teardown.
  Exact Core pair verified once at open; chain/genesis reattested without CLI/hash
  per read. No proxies/redirects/remote fallback/wallet selector/write API.
- [Actual Mac HTTP/Core proof](evidence/issue45/T01_MACOS_COMPONENT.json): correct
  chain/genesis,8 repeated reads under spawn/rehash guards, real invalid-auth
  refusal and write refusal before wire. No Core/RPC responses were mocked.
  Supplemental malformed/wrong-network/duplicate/oversize/closed tests are UNIT
  evidence and cannot substitute for native Core. Existing application transport
  is unchanged; scanner/GUI still use CLI pending T-03/T-04 and integration.

## Next unblocked critical path

1. Finish B-02 current-head native jobs; never count predecessor/artifact success
   for changed RPC code. Re-run exact-head WSP/custody regressions, inspect receipts.
2. Expand T-03 intended managed daemon/PID/startup/version/capability attestation;
   T-04 native executable replacement and trust-session boundaries, residual
   same-user/OS and TOCTOU limits. Current constructor authenticates protected
   config+chain, not a complete OS process identity proof.
3. Exercise direct HTTP against real Core on Windows/Linux in existing jobs,
   preserving Linux root witness. Add cookie/read-only attachment separately;
   currently only the strict existing managed config profile is accepted.
4. Expand typed read methods for scanner/GUI and lifecycle-owned cached transport;
   then T-07 busy/coalescing/backoff with no automatic uncertain write replay.
5. T-05/T-06/T-08, private multi-node B-06. Existing strict zero-peer config must
   not be silently weakened to admit arbitrary peers. Use a separately scoped lab.
6. Only then Phase2 GUI/custody/persistent-profile recovery. No new BIP39 signing
   or arbitrary .dat import exists; no real owner backup is ever opened.

## Mandatory unresolved evidence

Future integrated Q01–Q20 all PENDING. New HTTP feature frozen/physical tests,
wrong-cookie/native failures/all3OS, process replacement, multi-node, contention,
long-duration and scanner/GUI migration are pending. Core SQLite pairwise transport
must not leak private fixture DBs in artifacts. Platform-bound anchors cannot be
copied/reset to claim cold-device recovery. DEV mainnet derivation/compatibility,
external security review, vendor signing/notarization and physical Win/Linux
operator acceptance are separate gates; no reviewer is assumed to run binaries.

Lease63300 is held through this engineering run. Future resumes must inspect
actual holder/thread/worktree state and acquire their own lease; never infer
ownership from this document. Separate local run log:
outputs/production-v1-20261016/RESUME_LOG.txt. No scheduled retry/reset/purchase.

## T-03/T-04 owned endpoint slice (2026-10-16)

New branch `feature/issue45-owned-rpc-endpoint-20261016` stacks on PR46
90561d159cf3e79cd4d4c60cd5f04c491c108718. Before any Basic auth/HTTP bytes,
require the exact owned Popen argv, live OS image, independently pinned Core
pair and kernel ownership of the server half of this established TCP socket.
macOS uses trusted system lsof/proc_pidpath; Linux uses proc executable/fd/TCP
inodes; Windows uses QueryFullProcessImageNameW/GetExtendedTcpTable. Unknown or
unavailable proof refuses; no fallback. Each new connection rechecks ownership;
reused requests recheck process/file metadata without CLI/full hash per read.

The actual Mac component probe passed authenticated reads and a wrong-process
byte-collector endpoint which received zero HTTP bytes, plus genuine Core401.
The collector never supplies synthetic RPC results. Existing native and frozen
acceptance entrypoints now run this same probe and require its receipt. This is
not scanner/GUI migration or full T-03 completion: supported RPC capability/
version checks, cookie attachment, persistent lifecycle, tamper/loader races,
contention and multi-node testing remain pending. No claim of hardened loader
attestation or resistance to a compromised same-UID process/kernel. Windows and
Linux results for this changed code are PENDING until exact-head CI completes.

Local unit result:149 run,116 PASS,33 SKIP,0 FAIL. These skips are not native
platform acceptance. PR46 Windows run38884448364 FAILED in the operational GUI
probe (missing modal Sign after screenshot capture); its source/frozen Windows
qualification is FAIL. Do not count other green jobs as a replacement. Review
worker/timer scheduling in a separate focused fix without relaxing approvals.
All integrated-V1 registry gates remain PENDING; historical receipts unchanged.

## F-08/B-04 approval-sync regression (Draft48)

Runtime3ea32b8 on47/cad7785. Actual Mac Core/WSP/Qt reproducer confirmed a
refresh worker enters the modal approval before the fix, and cannot after.
Timer and manual refresh are now emitted inside every actual approval in the
shared source/frozen E2E harness; a worker or changed review fails acceptance.
The application serializes this modal interval, retains the exact commitment
and default Cancel, and preserves backend live-chain/security checks. Probe
waits boundedly for background completion before clicking native actions.

[Actual Mac full E2E](evidence/issue45/APPROVAL_MACOS_COMPONENT.json): genuine
Send/Sign/Broadcast, confirmed recipient100000atoms/change, lost actual reply
retains reservations, backup/lock/wrong password/recovery, fresh Core recovery,
reorg1/12/100 and native HTTP endpoint component PASS. Offscreen Qt is not Cocoa
Auto/physical acceptance; receipt flags not exercised remain false, including
additional stale-before-sign/broadcast recovery assertions in that local mode.
149 units:116PASS/33SKIP. New Windows/Linux/frozen CI remains PENDING until
exact-head results; parent46 failure is preserved, not retroactively PASS.

## T-03 compatibility / T-04 failure paths (next Draft)

Runtime ea5ff6c incorporates47/e61ed4b and48/17ccbbd by normal merge ancestry,
without force-push or replay. The exact genuine Mac Core RPC observation is
version111,subversion/WAM:0.1.11/,protocol70016. Typed getnetworkinfo now refuses
unknown/malformed profiles, and chain/genesis/version are reattested before
reads. These are measured WAM values, not Bitcoin defaults. Existing native
and final frozen probes execute the same compatibility check; other platform
results are PENDING until their exact-head jobs complete.

[Mac authenticated compatibility proof](evidence/issue45/T03_RPC_COMPAT_MACOS.json)
and [copied-executable failures](evidence/issue45/T04_EXEC_FAILURES_MACOS.json)
PASS: CLI tamper, node file replacement, owned process exit all quarantine the
session. Tests mutate only disposable copies; no changed executable is launched;
original signed Core pair hashes are reverified unchanged. This does not prove
hardened fd-to-loader binding, compromised-same-user/OS resistance or Windows/
Linux replacement coverage.149 prior tests plus1 version negative =150 run,
117PASS/33SKIP/0FAIL. Wrong-version units supplement, not replace genuine Core.

PR47/cad7785 Windows operational gate failed at process-image spelling before
GUI. e61ed4b compares native file identity on Windows (short/long aliases) plus
unchanged independently pinned metadata; no path-match bypass or weaker hash.
New CI must verify this fix, not treat earlier successful staged-binary probes
as all-path qualification. Shared transport/V1 test-only changes now trigger
existing Windows native/frozen and Linux jobs; no new job/workflow added.

## F-01/F-02 priority continuation — 16 October 2026

Owner prioritizes treasury/miner accounting and maturity; Core Update Manager
remains deferredP1, no implementation. [Live46–50 review](evidence/issue45/PR46_50_REVIEW.json)
verified47/49/50 all native/frozen gatesSUCCESS;48 has one conditional developer
buildSKIP, not a PASS.46 historical GUI raceFAIL was fixed and qualified in48,
not replayed. All50 ancestors included once; main and RC1 are unchanged.

Runtime8789176 adds a REGTEST-only miner read model: treasury from subsidy only,
100%fees miner-owned, exact output-script ownership and independent gettxout,
trusted/pending/immature/available separated, depth101 wallet eligibility, safe/
solvable/spendable gating, locked UTXOs not guessed from trusted total. This is
not a GUI account integration, global reservation authority or import custody.

[Actual Mac Core proof](evidence/issue45/F01_F02_MACOS_COMPONENT.json): depth99/
100 sends rejected with47.5immature and0available; depth101 accepted and confirmed.
First miner47.5/treasury2.5, fee1410atoms entirely added to miner coinbase,
confirmed change reconciled, native Core lock makes available0 while trusted
remains unchanged. No Fusion signed/uncertain reservation is released. Actual
REGTEST blocks150/151,300/301,450/451 match exact Core devfee audit and ownership.
Same fixture is required by existing source/frozen wallet acceptance entrypoints,
not interactive startup. New native/frozen threeOS results PENDING on this code.
154local unit tests121PASS/33SKIP/0FAIL; units supplement real Core.

**Important measured parameter distinction:** pinned v0.1.11 REGTEST uses
halving interval150, not200000. Thus at301 treasury is0.625 on subsidy12.5;
sunset remains independent height400000. Do not display the production schedule
as REGTEST balances. Native source vectors for200000/400000/600000 are separate
source-contract evidence; no mainnet binary/network is launched. High-height
nonzero-subsidy sunset runtime proof remains PENDING because the unchanged
REGTEST binary exhausts subsidy at4951. F01/F02/Q11 integrated V1 remain PENDING
until matching platform/frozen/UI and remaining boundary evidence is complete.

## F-01 independent height/source vectors

Code193aa4e compiles original v0.1.11 subsidy.cpp/.h and wam-params.h, checks
Git blob5659e868f191f2c497950d690829f0369aa912d1 /43e2e8c11a58b1b56141c63de470acb4743544ad /
d798155e1964adbdb3ccc48b44dd48fcde3b1602. Minimal explicit test type/parameter
shims are documented, not presented as node validation. [Mac native64 source
receipt](evidence/issue45/F01_PINNED_SOURCE_MACOS.json) PASSED production-parameter
vectors0(genesis separate),1,200000,200001,399999,400000,400001,600000,600001;
750000WAM lifetime treasury, independent cutoff with fixed nonzero subsidy,
REGTEST150interval and source lifetime749.99998050WAM. No mainnet process or
network, no upstream modification and no Core Update Manager. Existing native
jobs compile and publish this separate source-contract receipt on eachOS.
Windows/Linux source contract and changed-code native/frozen checks PENDING.

This does NOT qualify runtime400000 sunset or a full mining-account GUI. Source
contract, genuine REGTEST block/UTXO proof, packaged app and physical acceptance
remain independent layers. Owner's new DEV test-host agreement in Issue45 is
acknowledged: only clean isolated hosts, never a treasury-signing computer;
actual external execution still PENDING until evidence is received.

## T-01 scanner vertical slice and regression

46a7493 adds typed getblock(hash,3)/best-hash/peer-count HTTP reads. Blocks have
32MiB explicit reply bound, other replies retain1MiB. Validate requested hash,
height/list shape; WSP remains the pinned independent transaction/crypto/scanner
validator. Chain/genesis/version/zero peers and native owned process/socket
remain required. Scoped session receipt does not rehash full Core per read.
No HTTP failure falls back to CLI. Existing explicit fixture write operations
retain their previous transport and approvals; no HTTP write API added.

Genuine source/frozen scanner acceptance now requires owned HTTP, with guards
that raise on any CLI/Core-full-hash call inside WSP scan/SQLite replay. Guards
return no fake Core result. [Full Mac Core/WSP/Qt regression](evidence/issue45/HTTP_SCANNER_MACOS_CORE_QT.json)
PASS at e8e75ff:101blocks,actual BIP352 receive102,4749990000atoms,zero replay,
mining maturity/fees/ownership, native Send/Sign/Broadcast/confirmed change,
uncertain locks, recovery and reorg1/12/100.156units123PASS/33SKIP/0FAIL. Later
comment-only edits and Linux-only acceptance lifecycle fix are not silently
claimed as newly tested frozen/platform evidence; exact-head CI remains required.
That earlier scanner-only slice did not migrate WalletSession; the later operational slice below supplies separate evidence. T01/integrated V1 still require the remaining paths and exact-platform qualification.

PR51 Windows first failure was a test-wallet selector/method scope mismatch.
9f8402e reuses protected native RPC only in its owned fresh fixture, retains exact
binary/config custody, fixed fixture method scope and unchanged application
allowlist. PR52 first byte-pin failure was Windows checkout newline conversion;
.gitattributes preserves exact upstream bytes, not a relaxed pin. Native compiled
source receipts from [Windows](evidence/issue45/PR52_WINDOWS_SOURCE.json) and
[Linux](evidence/issue45/PR52_LINUX_SOURCE.json) verify the pinned source vectors;
these are SOURCE-only, never node binary E2E.

Linux Qt fresh-Core recovery failure was localized to background_snapshot's
exact-one-result assertion (linux_qt_probe.py:32).516b4f2 keeps the multi-window
acceptance QApplication alive through its deliberate no-window interval, restores
interactive shutdown policy afterward, and retains all assertions. Safe counts/
reviewed file:line diagnostics aid any remaining failure; no arbitrary exception,
secret or path is logged. Latest native/frozen qualification PENDING, no prior
FAIL rewritten as PASS. Old-head runs were cancelled only after replacement;
latest-head required checks remain active, cancellation is not qualification.

Checkpoint: PR51/Linux Qt fresh-Core recovery and headless source gates PASS at516b4f2; PR52/Linux Qt still required at its own HEAD. Full latest native/frozen matrix remains in progress. Core updater remains deferredP1. See ISSUE45_CONTINUATION.md.


## 2026-10-16 session T0 15:47:58 UTC — operational HTTP and queue contention

Existing Draft53 is reused; no new PR, auto merge, main/RC1 or upstream change.
Refresh found51(516b4f2) and52(c877705) all10 exact-head checks SUCCESS.
53/c478db1 Linux Qt reported two snapshots;03d0db7 stops the accelerated test
sync timer at signal delivery, preserving exact-one assertion. Linux native Qt
and frozen desktop then PASS at that historical head; cancelled obsolete runs
are not PASS.

527fb72 migrates operational WalletSession snapshots, background Qt sync, lock/
unlock/recovery snapshots and privacy diagnostics to the owned HTTP capability
borrowed explicitly from the actual process owner. Create/recover refuses missing
or unrelated capability before key/backup access. Core process owner closes the
shared connection before Core shutdown. No attach-by-PID, HTTP writes or CLI
fallback is added. Independent signing/broadcast CLI hash/approval/reservation
checks remain. Legacy public read-only demo and fixture setup paths are not all
migrated; persistent managed Core and external read-only attachment remain open.

The unchanged real-Core config-tamper negative test exposed a security regression:
HTTP cached its original config and accepted a later read after the protected
file was changed to a proxy profile.9ba9cfc restores native private-file custody
and exact bounded-config digest checks before any HTTP bytes or capability loan.
No new credentials/port are adopted. A later explicit read can proceed only when
the exact protected original configuration is restored. Unrelated speculative
Qt harness changes were removed, preserving the recorded failing revisions.
[Mac full Core/WSP/SQLite/Qt receipt](evidence/issue45/HTTP_OPERATIONAL_MACOS_CORE_QT.json)
is PASS at9ba9cfc: repeated/actual-worker snapshots run with CLI/full-Core hash
paths forbidden, config tamper denied, original restored, Send/Sign/Broadcast,
uncertain locks, latest recovery/fresh Core, reorg1/12/100. Offscreen/source only;
this is not frozen, physical, Cocoa Auto or production qualification.

T07: real disposable Core RPC queue saturation reproduced20 successful long-poll
reads and12 HTTP503 responses. Baseline closed its entire read session after503.
The next component permits at most3 positively rejected idempotent-read attempts
with bounded exponential jitter, preserves the session after busy, and reconnects
only through fresh OS socket/process proof. Invalid auth, malformed replies,
config drift and connection uncertainty are not retried; no HTTP write API or
uncertain broadcast retry exists. A genuine32-client owned-node gate verifies
three rejected attempts, complete bounded cleanup, then successful reads without
restarting Core. Same native/frozen entrypoints require its receipt. Solo-miner
coexistence, broad refresh coalescing, peer lab and full T07/Q04 remain PENDING.

[Actual Windows52 frozen inspection](evidence/issue45/WINDOWS_C877_FROZEN_INSPECTION.json):
artifact12054979956, sourcec877705/checkout01edf096, outer SHA256
9f042124bf4ee6c478eac4cf5b53e0f335802e358232ffeafc37d6959c08de04;
inner4e038edc053ac423fc0b8908d9cd4804cdc410a7394167cb2deb8f30c76e1074.
All354 actual packaged files and independently pinned Core pair match. Frozen
receipt confirms maturity99/100 refused and101 accepted,1410atom fee to miner,
treasury excluded, reorg1/12/100. Inspection on Mac is not execution on Windows;
this historical component does not qualify the changed HTTP runtime.

T0 Vietnam22:47:58 on16Oct; requested next execution03:47:58 on17Oct2026 UTC+7
(20:47:58UTC16Oct). Existing linux-regtest-single-continuation automation updated
ACTIVE as a single next continuation, checkpoint changed to Issue45/production-v1.
No duplicate automation or recurring credit retry. Stored ACTIVE/wall-clock
schedule verified; tool does not expose a computed runtime nextRun field.


## Current runtime5555df8 — repaired native/frozen gates

Windows8b50296 failed its first operational HTTP snapshot with a stale socket
send error after lengthy CLI/custody setup.5555df8 expires idle connections after
5seconds BEFORE sending; a fresh connection still proves exact native server
ownership before credentials. No failed request is replayed, and uncertainty
still quarantines the session. Genuine5.1second idle/reconnect plus queue32/read
recovery now run only in explicit acceptance; normal interactive startup never
runs this stress gate. Windows5555 native real Core/WSP/Qt/reservation/stale
signing/recovery receipt is downloaded and hash verified. Final Windows package
CI remains PENDING at this snapshot; source success cannot qualify it.

The Mac frozen failure was a relative import in the PyInstaller __main__ entry.
An absolute import fixes it. The actual final5555 app ran successfully on the
local ARM64 MacBook with offscreen Qt, original signed Core, native WSP and
isolated test Keychain: receive, sign/broadcast/change, denied approvals,
config tamper, idle/busy, backup/lock/recovery, fresh Core and reorg1/12/100.
DMG hdiutil verification succeeded. The local builder's final manifest-only step
initially selected the reused venv's old editable package; it was completed with
PYTHONPATH=src after source/checkout/payload/Core digest checks. No binary/gate
changed. Reproduction must install this checkout or set PYTHONPATH=src.
AppZIP56c7526dc4092867359eb3b133502df84ce276463946d65cd2b06866089b0aff;
DMG7ff2acbade4be94344916517bf289c5600e26dfe98c55c9b0acf5749cf5ed061.
[Local final executable receipt](evidence/issue45/HTTP_IDLE_BUSY_5555_LOCAL_FROZEN.json).
Mac runner native and frozen5555 gates also PASS independently (run38965264090).

[Windows native](evidence/issue45/WINDOWS_5555_NATIVE_CORE_QT.json),
[Linux native Qt](evidence/issue45/LINUX_5555_NATIVE_QT.json) and
[Linux no-Qt](evidence/issue45/LINUX_5555_NATIVE_HEADLESS.json) actual artifact
receipts confirm the5555 source head, owned HTTP guards, real idle/busy proof
and preserved signing/recovery. Linux5555 frozen headless/desktop CI PASS;
independent developer-Core rebuild and Windows frozen aggregate still running
at this snapshot. None is physical acceptance; Linux remains a separately
reviewed developer binary with root witness, never an official signed release.
162units=129PASS/33platformSKIP/0FAIL. Full Issue45 integrated V1 stays PENDING.

The requested one-shot heartbeat arrived20:48:21.727UTC16Oct (03:48:21.727UTC+7
17Oct),23.727seconds after the scheduled20:47:58UTC. It was coalesced into the
same still-held lease94867, without a second writer. The same automation is now
verified PAUSED; no future run or recurring retry was created. Current native/
frozen evidence is preserved separately from latest docs-only checkpoint CI.

## Mining Account GUI component (17Oct2026, qualification in progress)

PR53 exact head c5edaeff086947f25dd673955846c5c7615c4634 now has10/10 checks
SUCCESS. Downloaded Windows artifact12076012325 actual354 members/AMD64 PE/Core
pair, inner archive f5b5e90f34db6a073b072c3b94f5c3d08de722f9d1fff1569754d9ca79e35858,
125/150% actual frozen receipts inspected; see separate evidence JSON. This does
not qualify the successor runtime.

New fixed owned-Core read-only Mining Account page is a focused F01/F02/Q11
component. Core eligible/trusted/untrusted/immature projections are separate from
WSP payment funds; treasury ownership overlaps and moving snapshots are denied.
No Core signer/import/transfer capability added. First actual mining GUI maturity
probe passed;167 supplemental tests134PASS/33platformSKIP. Source full recovery
assertion updated for seventh page after observed first-run FAIL. Native/frozen
successor evidence remains pending; no global Q or physical status promoted.
