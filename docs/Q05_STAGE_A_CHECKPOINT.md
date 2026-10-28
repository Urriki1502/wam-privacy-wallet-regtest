# Latest persistence checkpoint — journal v2 stable native identity

Source **264faa2b2db6aa717312cd1a984c15e01d2cbd04**. Official engineering lease
was reacquired normally after the prior session/host exited; no lock deletion.
Same PR #138 and feature branch, origin/main still 4bc6f658. 87 Q05 contracts PASS.

Observed real post-restart gap: two preserved legacy v1 profiles record device
16777233 but now have device 16777230, with the SAME inode. Host boot time is
1793183156. See `docs/evidence/q05/native-mount-device-observation.json`.
The old device/inode binding is fail-closed but cannot prove a legitimate
persistent directory after mount renumbering. No legacy journal was modified.

Fresh v2 journal identity uses macOS native volume UUID + file ID + birth time;
Linux fstatvfs filesystem ID + statx inode/birth time; Windows native volume serial
+ file ID + creation FILETIME, all from guarded descriptors/handles. There is NO
st_dev/path fallback. V1 records keep v1 schema/MAC/device-inode checks, append
v1 on a valid same-mount reopen, and refuse changed binding. No auto migration,
relabeling, custody/KDF/AEAD/vault change or PID authority is introduced.
New tests prove stable identity despite simulated transient-device change,
actual child-content change, wrong volume/file/birth refusal, unavailable native
API refusal, strict v1 compatibility and mixed-schema-chain refusal.

New signed macOS ARM64 native probes at this exact clean source PASS:
- `docs/evidence/q05/native-identity-crash-264faa2.json`: genuine original owned
  Core crash/recovery, same datadir and clean reopen, journal v2.
- `docs/evidence/q05/native-identity-wallet-264faa2.json`: genuine Core + pinned
  WSP wallet, wrong-password and duplicate refusal, public fixture funding,
  native signature and real accepted submission before caller-result loss;
  uncertain reservation/balance/history preserved across owner/Core reopen,
  exactly one wallet submission, no automatic replay, journal v2.
The receipts bind critical source-file hashes; no old profile or failed receipt
was reused. Actual post-reboot v2 and all-OS native/frozen cases remain PENDING.
Do NOT call the simulated device test or same-boot reopen a real reboot PASS.

Prior published source 88f7ace completed all six workflow runs SUCCESS: macOS
40647391379, Linux Q04/frozen 40647391496, Windows credential/native/frozen
40647391362, Linux Q05 source 40647391452, Windows Core 40647391580, WSP 40647391493.
These do not qualify changed v2 runtime. Push the combined source/evidence batch
and inspect its own Windows/Linux native identity tests before broader work.

Next: native interrupted checkpoint publication/runtime-ownership reconciliation
without auto-deleting SQLite, forgetting reservations or advancing an unknown
native anchor. Cross-process dirty-owner recovery, actual host reboot, normal
packaged onboarding/GUI and three-platform Q05 qualification remain incomplete.
All 37 canonical cases and G0–G7 PENDING, accepted=false; Q04 G6/G7 BLOCKED.

---

# Latest reservation checkpoint — real signed and uncertain native PASS

Runtime summary source **49f7fec**, corrected probe/source **3436ab7082831b5cd4122ce7bd1e29fa1a58b88b**.
80 Q05 source/security tests PASS after keeping getrawmempool outside scanner
scope. Same Draft PR #138 / feature/issue45-q05-managed-core-stage-a-20261027.

Actual signed macOS ARM64 Core v0.1.11 + literal ac55f134 WSP:
- Signed reservation PASS at 49f7fec, receipt
  `docs/evidence/q05/q05-signed-reservation-49f7fec.json`, SHA-256
  f1592f8365e80acba49d202d08e9e4f2c3352ac325fb751aaeed8256c599689b.
  Genuine wallet signature, irreversible draft-release refusal, same reservation
  fingerprint/reserved balance after clean Core/owner reopen; zero submissions.
- Uncertain reservation initial observation FAIL retained at 49f7fec (scanner
  method correctly denied getrawmempool; no allowlist expansion). New profile
  retest PASS at 3436ab7, receipt
  `docs/evidence/q05/q05-uncertain-reservation-3436ab7.json`. Actual signed CLI
  submission returned Core's matching txid before the probe deliberately lost
  the caller result. Existing signed CLI read confirms actual mempool presence.
  Durable uncertain fingerprint/reserved balance and identity/history survive
  live checkpoint resync and clean Core/owner reopen. Exactly ONE wallet
  submission total; no automatic transaction replay. This is caller-result fault
  injection AFTER real acceptance, not physical/TCP fault proof or GUI acceptance.

Native probe uses existing WalletSession prepare/sign/broadcast under original
Popen scope and native anchor lease. No new production signing/IPC endpoint,
password transport, format/KDF migration or native-anchor recovery shortcut.
All new test owners/Core shut down normally; profiles/evidence remain preserved.
Legacy 48111/48112 and childless 48993 observations are not termination targets.

The 37 canonical Q05 cases remain PENDING, accepted=false, G0–G7 PENDING.
Native successes are supplemental local_requalification only. Q04 G6/G7 stay
BLOCKED. New current-HEAD CI is required; 88f7ace native Windows contract/vault/
Qt steps had passed while its final frozen step was still running at observation.
Linux Q05 88f7ace job 122679273036 PASS, 79 tests; this is source/native storage,
not integrated genuine Q05 Core/frozen qualification. Do not attribute it to a
later HEAD or to the new 80th test.

Next exact unit: interrupted native checkpoint/publication reconciliation with
strict original-runtime identity, unchanged native anchor and no forgotten
signed/uncertain reservations. Existing behavior preserves ambiguous runtime/
orphan ciphertext and refuses; do NOT delete unknown SQLite, reset/advance an
anchor based only on newest filename/password, replace vault/datadir, or grant
new controller ownership from PID/journal alone. Reviewed cross-process owner
architecture, normal packaged GUI and three-platform qualification remain open.
Inspect current CI first; do not rerun unchanged native probes or redo reuse
research. Standing bounded-test authority remains active; merge/release/formal
handoff still require separate owner approval.

---

# Reservation probe checkpoint — signed PASS, uncertain observation repair

Runtime summary source 49f7fec adds nonsecret signed/uncertain reservation
fingerprint/count/state/balance observations, no spending or IPC capability.
Actual native signed-wallet reservation + original-owner/Core reopen PASS,
receipt `docs/evidence/q05/q05-signed-reservation-49f7fec.json`. No wallet broadcast.
Native uncertain probe FAIL at REAL_BROADCAST_CALLER_RESULT_LOSS observation,
receipt `docs/evidence/q05/q05-uncertain-reservation-49f7fec.json`; profile retained.
Source diagnosis: probe used a new scanner client's public call(getrawmempool),
which intentionally refuses this method. Fix uses existing original-owner signed
CLI read solely for fixture mempool observation. Scanner HTTP/method allowlist
is unchanged; regression requires its denial before sending. Fresh-profile
bounded uncertain retest is next; no rerun/reuse of the failed profile.
Windows 88f7ace native source/storage step passed after journal test repair;
full native/frozen workflows remain separate. Do not assume final-head CI.

---

# Exact-HEAD CI follow-up — Windows journal test fix

Published checkpoint 45e81f3: Linux Q05 native source/storage job **122678431135**,
run **40647125974**, PASS: 79 tests, no skipped Q05 tests. This is native storage
and mocked-Core contract proof, not genuine Linux supervisor Core E2E.
Windows job **122678431002**, run **40647125911**, FAIL in one of 79 Q05 tests:
WinError 32 prevented the test's attempted live datadir rename while native
lease handles remained pinned. Runtime custody was stricter than the POSIX-style
test assumption. Repair **1966094** now asserts that Windows pinning prevents
live rename, then closes owner/lease normally and actually replaces the datadir
to verify journal identity-drift refusal. No skip and no weakened assertion.
79 focused macOS Q05 tests PASS after this test-only fix; runtime source remains
fca3115 with its genuine native receipts. New exact-HEAD Windows CI is required.
Retained failure: `docs/evidence/q05/windows-q05-45e81f3-failure.json`; full log
outside checkout `work/q05-ci-investigation/job-122678431002.log`.

Do not start broad GUI/spending work before this cross-platform source/storage
CI recheck. Same PR/branch, no new native retest needed for this test-only edit.

---

# Latest saved checkpoint — native wallet continuity verified, final CI next

Runtime source: `fca311526f8503776e5b40a39279d00519294c6c` (adapter introduced
at a87772b, funded history probe 3d4f1d9). Same branch/Draft PR #138.
**169 targeted local tests PASS**: 79 Q05, 20 Q04, 35 Q03, 6 external-Core,
5 contention, 13 ledger, 3 encrypted storage and 8 wallet-session contracts.
Sequential execution, Python 3.12.15 / coincurve 21.0.0 / cryptography 50.0.0.

New actual signed-Core/pinned-WSP macOS ARM64 probe:
`docs/evidence/q05/native-wallet-fca3115.json`, SHA-256
`543872b472b21a498becab7d5bd6ca792eff6d9f778b9b6924ca6ed0dae7581e`.
Four observations PASS: create empty anchored generation 1; wrong-password
refusal without anchor/reference/ciphertext mutation; explicitly opted-in PUBLIC
REGTEST fixture payment scanned at height 102 (4,749,990,000 atoms, one history
row); clean owner/Core reopen with same wallet/payment code, exact history
fingerprint and balance, anchored generation 3, old ciphertext preserved.
No wallet signing/spending occurred. Public fixture signing/broadcast is recorded
separately and exists ONLY in the native probe, never onboarding/adapter code.
New Core/owners shut down normally. Earlier empty-wallet 59e073f and funded
3d4f1d9 receipts remain preserved too. Their legacy schema label contains
`empty-wallet`; actual funding flags/observations determine scope. The final
receipt uses explicit `wallet_fixture` and generic checkpoint schema.

The adapter is owner-local API only. No wallet passwords, seeds or checkpoints
are sent over the HMAC-only control protocol. Native vault/KDF/AEAD/keyring
formats are unchanged. `supervisor.wallet` is nonsecret HMAC-bound reference;
the native anchor remains authoritative for generation. Failed publication or
leftover runtimes are preserved/refused. History summary currently refuses
1000-row ambiguity; complete pagination is still needed before ordinary use.

Q04 repair run 40645229982 at ef700da is PASS for native/contention and both
frozen modes. Final pushed HEAD must get its OWN CI, including new Linux Q05
unit/native-storage workflow and Windows Q05 native tests. Do not infer Q05
integrated packaged qualification from Q04 frozen jobs. No full matrix was
manually redispatched; pushes are batched, Core builder recipe is unchanged.

Canonical Q05 remains **0 PASS / 0 FAIL / 37 PENDING / 0 BLOCKED / 0 STALE**;
G0–G7 PENDING, accepted=false. Q04 G6/G7 BLOCKED unchanged. Supplemental local
proof is recorded only as local_requalification. Handoff/full acceptance NO.

Next exact actions after verifying HEAD/clean tree/official lease:
1. Inspect new exact-HEAD CI; fix any Q04/source/native-storage regression first.
2. Test signed/uncertain reservation preservation, interrupted checkpoint/
   native-anchor publication, exact-checkpoint refusal/reconciliation and
   concurrency using actual WSP under the same original Core owner.
3. Finish reviewed persistent ownership architecture. New controllers still
   refuse dirty live-orphan state; no PID adoption or Popen facade is permitted.
4. Design secure wallet/GUI bridge separately (control HMAC is NOT encryption),
   then normal packaged onboarding/read/Send/Sign/Broadcast, all three native/
   frozen hosts and Windows 125% DPI. No vault or KDF migration.
5. Preserve legacy profiles/controllers; no generic kill/repair or lock deletion.
   Owner approval remains necessary for merge/release/formal Q-GATE transition;
   physical and independent acceptance remain separate. Routine bounded
   documented-fix tests are already authorized.

Reproduce only when affected source changes: use Python 3.12.15 with the pinned
Q01 dependencies, PYTHONPATH containing this repository's src and the actual
ac55f134 WSP src, then `scripts/probe_q05_wallet_checkpoint.py --core-dir
<verified signed v0.1.11 ARM64 dir> --wsp-source <literal pinned Git checkout>
--root <NEW private wam-fusion-core-16hex path> --receipt <NEW JSON path>
--confirm-disposable-regtest --fund-disposable-wallet`. Require a clean committed
checkout; never reuse/overwrite any old profile or receipt. All receipts contain
exact source, binary digests, WSP pin and actual outcomes.

---

# Work in progress: owner-local checkpoint adapter added

Runtime commit `a87772b` adds `managed_wallet_checkpoint.py` and
`scripts/probe_q05_wallet_checkpoint.py`. 78 Q05 unit/security contracts PASS.
This is a direct owner-local create/reopen API, not a GUI/control-IPC endpoint.
It preserves current vault envelopes, native anchor, pinned 32-byte Keyring and
original Q03 owned scope; no funding/mining/spending. A native empty-wallet
probe on a NEW profile/receipt with the pinned WSP and separate disposable
Keychain is next. Do not claim continuity until that actual probe succeeds.
Failure preserves protected vault/runtime residue for explicit reconciliation.
Existing/runtime/sidecar or ambiguous create state is refused, never repaired.

---

# Latest checkpoint update — current runtime 7c03988, Q04 repair rechecked

This update supersedes stale CI-pending statements below. Current local runtime
`7c03988f9ee382dbde47474cccc4fb7ded6ad8ac` adds native executable custody before
Popen and restricts recovery attestation to the current STARTING-delimited launch
(PID-reuse negative regression). **70 Q05 tests PASS**; earlier full 151-test
batch at 7eea2f7 PASS. Signed macOS native custody lifecycle at 7eea2f7 PASS
(receipt SHA cc94a957e326257ca3bad5d0d6217171c7b1ea0dcdb8b36ce1bfd8d2d96453a2);
actual original-Popen Core crash/recovery at 7c03988 PASS (receipt SHA
e1b970fe8a409db0d946e3d10495cf8e67b82198c31d75054b54c16f529bc8b1).

Q04 repair-source ef700da Linux run **40645229982**: native Q04 122673024761,
contention 122673024573, frozen headless 122673024621 and frozen desktop
122673024655 all PASS. Both frozen receipts independently record 4 actual
attachment 503s, worker-dequeue readiness, backoff/coalescing/recovery/write
refusal; GUI coalescing PASS on desktop. Full logs were read. See
`docs/evidence/q05/q04-repair-ef700da.json`. Prior failures remain retained.
No new integrated Q05/final-artifact acceptance is inferred from these Q04 jobs.
New Q05 Linux source/native-storage workflow is separate from the unchanged
Core-builder workflow to avoid rebuilding immutable Core for unit coverage;
Windows native contract job now calls Q05 tests too. These additions still need
actual OS CI results. Existing custody AST/model audit at ef700da PASS is only
internal review; read `docs/Q05_INTERNAL_SECURITY_REVIEW.md` for scope and gaps.

Next unit: narrow create-once native wallet/checkpoint adapter in the original
owner process, no fixture funding, no IPC secrets, no vault/KDF migration. Keep
supervisor-process-crash/live-orphan reattachment fail-closed and all 37 Q05
cases PENDING. Same Draft PR/branch; standing owner authority remains active.

---

# Current Q05 checkpoint — 28 October 2026, autonomous authority active

This section supersedes every STOP/one-retest instruction in the historical
checkpoints below. Owner standing authorization:
https://github.com/Urriki1502/wam-privacy-wallet-regtest/issues/45#issuecomment-6458347904.
Continue the SAME Draft PR #138 / branch
`feature/issue45-q05-managed-core-stage-a-20261027`, worktree `work/q05-stage-a`.
Main remains `4bc6f658e4c00e0a8c5d3c9da7d79aab0a54dfae`; Q05 sole ACTIVE,
Q04 ENGINEERING_DONE with G6/G7 BLOCKED and accepted=false. No merge/handoff.

## Completed source units and reproducible evidence

- `9152214`: private fixed startup diagnostics and original-Popen recover-stop.
  A fresh diagnostic reproduced RPC_HTTP_DENIED, before HTTP readiness; that
  profile's original Popen subsequently reattested and gracefully stopped Core.
- `3c40a1d`: signed scoped CLI bootstrap readiness, then unchanged Q03 HTTP.
- `2850be6`: create-only HMAC chained lifecycle journal; clean/dirty reentry,
  identity, sequence, truncated/partial/foreign state refusal. No PID adoption.
- `c8b812825c32eddbc6d314b9f564b687ffbb8f86`: explicit recovery of positively
  exited original Popen, same registered scope and owner, unchanged original
  datadir/config/Core pins, no authenticated height regression. Authenticated
  `release` exits an owner only after no live child remains.
- `056d770`: Q04 workload waits for its first long-poll to enter the actual Core
  worker before filling its bounded queue. Six sent + a raw 503 alone could
  race worker dequeue and leave a slot. Thirty-second long-polls / bounded
  100-second drain, no change to product RPC timeout, assertions or trust.
- `0620564f9f203f1c79142cb32848fa330cb54436`: reverify signed pinned Core and
  profile digests immediately BEFORE Popen, not only after launch.

Sequential focused regression batch: **150 tests PASS** (68 Q05, 20 Q04,
35 Q03, 6 external attachment, 5 contention, 13 ledger, 3 encrypted storage).
Genuine signed macOS ARM64 source-only receipts in `docs/evidence/q05/`:

| Receipt | Actual source | Outcome | SHA-256 |
|---|---|---|---|
| native-core-crash-c8b8128.json | c8b8128 | PASS: real original-owned Core SIGKILL, explicit same-owner recovery, no height regression, clean reopen | 3c42133c52ec61b6c601f11bc628ed66aecb4af5dddd4e2815f1d7583bea9c0c |
| native-ipc-release-c8b8128.json | c8b8128 | PASS: four lifecycle observations, authenticated normal owner release | 122e43741df49cf059ca0bd33a5141f92d62594a422e74f6348dccdf4121bd85 |
| native-preflight-0620564.json | 0620564 | PASS: four lifecycle observations after pre-spawn check | f1c62da77ce888afecb44d9140e57ae5ae72ff9f68569604805d5d658b430479 |
| q04-worker-dequeue-native-056d770.json | Q04 module snapshot 056d770 | PASS: four actual attachment 503s, backoff/coalescing/recovery/write refusal; standalone source probe | 5776840e40428442ae8bd16b8e682972876e6fbe56e0010e228a692ee8748b1d |

The Q04 standalone receipt itself does not embed source SHA; its module snapshot
and execution are recorded here, not retroactively written into that receipt.
The supervisor receipts embed exact clean source/probe hashes. Wamd SHA-256
`7298de701e467eb28b4806cbcbe35edb393861b4b97117017fee4c1b194e3068`,
CLI `81a031ebf9b3060b19061b29756d43bcd09b32ad778348b8c3d8321397076e82`;
WSP pin `ac55f13423620252bdbf848c7e8a280c3b84721e` recorded but not executed by
these Core-only probes. No source probe proves integrated frozen GUI/wallet use.
All older FAIL receipts/profiles remain preserved.

## CI requiring current repair-source qualification

Latest published source at this checkpoint was 55beb7e. Linux run 40643772393:
native Q04 122668260484, contention 122668260574 and frozen desktop 122668369466
PASS; **frozen headless 122668369581 FAIL**, TimeoutError after 10.017 seconds
on attempt 3, with 2 actual attachment 503 replies. This is a real unresolved
qualification failure, not infrastructure-only. Earlier 3c40a1d desktop had
3 busy replies and one unreachable transport; unreachable is now correctly
propagated, never fabricated as NODE BUSY. Full failure history is in the ledger.
The worker-dequeue race exists in upstream WorkQueue semantics; old CI did not
record worker timing, so that historical scheduling trace cannot be proved.
Native macOS recheck supports the repair; new exact-source Linux frozen/native
CI is still required before broader Q05 integration. Do not replay full CI
manually or count old green jobs as qualification of changed source.

## Remaining security and integration gaps

Journal is an authenticated create-only chain under native profile lease, not
an independent antirollback witness against same-user/OS/full snapshot rollback.
Tail-prefix rollback and long-term journal compaction remain design gaps.
100,000 lifecycle-event cap is fail-closed with reserved stop/failure capacity;
status requests do not consume that cap. No vault format/KDF/AEAD migration.

A supervisor-process crash loses the original Popen capability. New owners
refuse dirty state and DO NOT adopt a PID. Positive live-orphan reattachment
needs a reviewed retained original-owner/service architecture; Core-only
same-owner restart is narrower and must not be presented as that case PASS.
Wallet/scanner/SQLite/native-anchor/checkpoint and uncertain reservation
continuity, ordinary packaged onboarding/Send/Sign/Broadcast, three-platform
native/frozen, Windows 125% DPI, physical and independent gates remain incomplete.
Use `docs/Q05_VAULT_COMPATIBILITY_REVIEW.md` before Stage C; preserve legacy
32-byte Keyring and vault envelope, exclude historical account/KDF migrations.

Legacy profile `wam-fusion-core-2f8b039e7c6145ad` has old owner/runtime without
an original-Popen recovery endpoint. Historical PIDs 48111/48112 are observations,
not termination targets. Do not adopt, signal, delete locks, overwrite profile
or patch a running interpreter. Diagnostic profile 85e926b3d4071cfa's Core was
stopped by its original owner; its old Python controller may remain. A later
strict executable comparison refused a proposed signal BEFORE sending it.
These action-specific blocks do not prevent isolated safe engineering.

## Next exact actions

1. Verify current branch/remote HEAD, clean tree and official engineering lease;
   continue/acquire normally, never delete locks. Check current quota.
2. Inspect the automatic CI for the next pushed HEAD, especially Linux native
   Q04/contention and both frozen variants. Read full failed job logs and keep
   diagnostics/evidence. Fix a new regression before broad Q05 work.
3. Once Q04 requalification is sound, complete persistent original-owner/service
   recovery design and tests, then create-once managed wallet integration without
   fixture funding or height-102 assumptions. Keep original vault/native-anchor
   custody and signed/uncertain reservations; no fake owned RPC context.
4. All 37 canonical Q05 cases remain PENDING; G0–G7 PENDING, accepted=false.
   Local source successes are supplemental only. ENGINEERING HANDOFF NO,
   FULL ACCEPTED NO. No new routine native-test approval is needed.

---

# Historical checkpoints (superseded where noted)

# Q05 Stage A checkpoint — 28 October 2026: STOP after authorized native retest FAIL

**This update supersedes the earlier checkpoints below. Do not retry or start
the journal milestone.** Same Draft PR #138 and branch; repair source
`a89848b22cae85d766310687fe968157f35657e8`, based on original d521878 checkpoint.
The owner authorized ONE additional native lifecycle; that allowance is consumed.

## Native retest and live owner blocker

Fresh profile `wam-fusion-core-2f8b039e7c6145ad`, new receipt
`docs/evidence/q05/stage-a-native-retest-a89848b.json`, SHA-256
`48e9f32e511a569738d577b833ab0df89c44f2f6785e032d8d350030317150f6`.
Exactly one retest was run from clean committed source with the original signed
v0.1.11 ARM64 binary hashes. Corrected stop allowlist tests passed first.

Result **FAIL at authenticated start: MANAGED_CLIENT_REPLY_DENIED**, zero
completed lifecycle observations. Shutdown and supervisor reopen were not reached.
Read-only postmortem: host `MacBook-Pro-cua-ang`, original supervisor **48111**,
its Core child **48112**, RPC port **60219**; authenticated status recovery-needed,
height null, core_process_owned=false. Both were alive at observation, with no
shutdown-start/done log marker. This reports an unresolved startup failure;
there is no evidence to call it a warmup/timing-only fault. Inner error is hidden
by current control reply handling and has not been diagnosed. Reverify PIDs and
native identity before any later action; never treat this snapshot as a kill list.

No retry, adoption, kill, lock deletion, repair or journal implementation followed
this FAIL. Original failed profile `wam-fusion-core-71c40b6258a3d9e0` and its first
FAIL receipt remain preserved. The new profile retains the live original owner
and its per-profile lease; the repository engineering lease is released at stop.

Owner action: authorize a focused diagnostic and verified safe-release plan using
the original test owner/Popen. Current faulted shutdown API refuses operation;
safe persistent recovery is not implemented. Do not switch to external attach
to obtain stop authority or start replacement Core. No further native lifecycle
until separately authorized after that diagnosis and safe release.

## Q04 CI disposition

Read full logs for d521878 Linux run 40539812345: native Q04 failed
Q04_BUSY_NOT_OBSERVED; desktop frozen passed native wallet stages then failed its
Q04 command with UNCLASSIFIED. Q04 source and dependencies were unchanged from
qualified main and the successful d624abc3 run. No infrastructure-only claim.
See `docs/Q05_Q04_CI_INVESTIGATION.md` for exact comparison and limitations.

Repair a89848b replaces guessed `.5`-second load readiness with all six requests
sent plus an actual Core load-channel 503, with bounded readiness/long-poll time.
All four attachment busy/backoff/coalescing/recovery/write-refusal assertions stay
unchanged. Frozen reporting now exposes only fixed RpcContentionError codes and
still exits 2. Sixteen Q04 supplemental tests passed before push. Automatic
exact-head Linux repair run 40615131718 completed SUCCESS: native Q04 and
contention, frozen headless and desktop all PASS. Each frozen log records four
actual attachment 503 replies; desktop GUI coalescing PASS. Evidence summary is
`docs/evidence/q05/q04-repair-a89848b.json`. Earlier failed jobs stay in Q04
failure_history, with the old desktop inner exception still unknown. New source is not
qualified from old main/PR PASS, and Q05 journal work cannot resume from generic CI.

## Current case state and next action

Q05 ACTIVE but engineering stopped: **0 PASS / 1 FAIL / 36 PENDING / 0 BLOCKED /
0 STALE**, accepted=false. Q05-MANAGED-START-MACOS FAIL; G0/G2 FAIL, other Q05
gates PENDING. All unqualified cases remain PENDING. Q04 G6/G7 BLOCKED unchanged.
Native failure history and owner/action are in the canonical ledger. Validator
and 13 governance tests pass after accurately recording the failure; the earlier
runtime/source regression batch passed 123 tests before the native run.

Next session: inspect exact-head CI and the retained two FAIL receipts, reverify
the original owner/Core and both leases, obtain owner direction for diagnosis /
safe release, then address startup error reporting/root cause. Only after safe
native lifecycle and Q04 requalification may persistent clean/dirty ownership /
recovery journal work resume. Same PR/branch, no broad GUI/scanner/spending work.

## Previous checkpoint — retained history, superseded above

# Q05 Stage A checkpoint — 27 October 2026 (continued)

Latest development state; the first checkpoint below is retained as history.
Continue SAME branch and [Draft PR #138](https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/138).
Previous HEAD `d624abc3d04fbb7954fb5897deea9dd5f1f8ee3a`; committed native source
`88b8b4bc995dbb7e5e502c1f7abbac349932541b`. Get final HEAD with `git rev-parse HEAD`.

**Current ledger: 0 PASS / 0 FAIL / 37 PENDING / 0 BLOCKED / 0 STALE**, Q05
ACTIVE, accepted=false. One failed narrow native attempt is retained in the
macOS shutdown case failure history. PENDING does not erase its FAIL or imply
the correction has native proof. Q04 ENGINEERING_DONE and G6/G7 BLOCKED unchanged.

## Latest completed work

- Replay guard uses fresh single-use connection challenges, 5-second TTL,
  bounded live pending capacity and locked atomic consumption. No lifetime
  4,096-request limit. Grant is bound to the exact server-side connection;
  expired, used, discarded, wrong-connection and previous-instance grants refuse.
  Failed auth consumes its grant; disconnect always discards it. HMAC and strict
  frame parsing remain intact. Guard thread safety does not enable parallel
  Core lifecycle handlers: the server remains sequential.
- **107/107 targeted tests PASS on macOS**, including 45 Q05 tests. Adversarial
  cases cover 5,000 requests after capacity turnover, exhaustion/recovery,
  expiry/discard, cross-connection replay, independent concurrent clients,
  100-way replay race with one winner, restart replay and modified HMAC. Startup
  fixtures cover scope registration, warmup, spoofed socket, wrong chain/auth,
  config/binary drift, timeout and retained uncertain child/datadir, with no
  replacement, foreign adoption or unverified kill. Other suites: Q03 RPC, Q04
  external/contention, governance, encrypted storage. Validator PASS.
- Vault design review: `docs/Q05_VAULT_COMPATIBILITY_REVIEW.md`. Legacy versions,
  implicit scrypt parameters, monolithic AES-GCM versus authenticated chunking,
  publication/anchor atomicity and clean-device restore gaps are explicit.
  No vault/KDF/AEAD/native-custody code changed.

## Exactly one genuine macOS ARM64 lifecycle: FAIL, preserved

Clean source `88b8b4bc…`; script `scripts/probe_q05_macos_lifecycle.py`;
receipt `docs/evidence/q05/stage-a-native-macos-88b8b4b.json`, SHA-256
`b9bcaf21bc5f7bfd87daf96ec7f557e28f0bf4d6af5f42ebe0dd1b8344155656`.
Authenticated start at height 0, actual Popen/image/kernel-socket ownership and
Core continuing across control disconnect were observed. Shutdown returned
`MANAGED_CLIENT_REPLY_DENIED`; graceful completion and supervisor reopen were
NOT proven. Debug log had Shutdown: In progress, without a verified done marker.
No matching test owner/Core or profile-lock holder was observed afterward; that
absence does not prove graceful shutdown. Original profile/logs are retained.

Verified mismatch: signed pinned Core contains `WAM Coin stopping`, whereas CLI
decode accepted only `WAM Core stopping`. Corrected strict allowlist accepts
these two exact literals and rejects arbitrary text; process/auth/method scope
unchanged. Unit/regression PASS, **native retest PENDING**. The failed receipt
does not qualify the corrected source. No second native lifecycle was run:
owner instruction authorized ONE. Request approval for one bounded follow-up.
Harness now starts its exact owner in a separate session, preserving independent
lifetime on uncertainty; no guessed/unverified PID termination or auto repair.

Core SHA-256: wamd `7298de701e467eb28b4806cbcbe35edb393861b4b97117017fee4c1b194e3068`;
CLI `81a031ebf9b3060b19061b29756d43bcd09b32ad778348b8c3d8321397076e82`.
Configured WSP pin `ac55f13423620252bdbf848c7e8a280c3b84721e`; WSP not executed
in this control-only native probe. No wallet/mining/frozen acceptance implied.

## Next exact action (supersedes the historical sequence below)

Inspect final #138 exact-head CI without duplicate dispatch. Verify main/Q05,
known working-tree changes and acquire lease officially on the SAME branch.
Obtain owner approval for one bounded native follow-up on corrected source and
a fresh isolated profile, proving safe shutdown and same-profile supervisor
reopen. Preserve the old FAIL. Do not promote other Q05 cases from that probe.

Then design/test a persistent clean/dirty ownership/recovery journal before
Stage B scanner/vault integration. Live-Core orphan reentry remains refused on
port/native ownership conflict; no PID adoption or automatic replacement.
Cross-restart dirty detection/reattach/crash recovery are not implemented.
Normal packaged managed onboarding, wallet/history/uncertain reservations,
three-OS native/final frozen, Windows DPI and independent/physical remain open.
Generic macOS/Linux frozen CI does not qualify this integrated supervisor;
Windows Q05 native/frozen remains outstanding. No merge or second Q05 PR.

## Historical first checkpoint (superseded by the update above)

This is a resumable development checkpoint, not an acceptance dashboard.
`tests/acceptance/issue45.json` remains authoritative and unchanged: Q05 ACTIVE,
all 37 Q05 cases PENDING, accepted=false. Q04 remains ENGINEERING_DONE with its
physical/independent blockers intact. No Q05 handoff or merge is authorized.

## Resume this branch

- Branch: `feature/issue45-q05-managed-core-stage-a-20261027`.
- Base main/handoff: `4bc6f658e4c00e0a8c5d3c9da7d79aab0a54dfae` (#137).
- Workspace: `work/q05-stage-a` beneath the current Codex task directory.
- Find the checkpoint commit with `git log -1 --format=%H -- docs/Q05_STAGE_A_CHECKPOINT.md`.
- Recheck live main, Q05 ACTIVE, clean/known changes, open PR and the official
  `scripts/engineering_lease.py --hold` before continuing. Use this branch and
  the single Q05 Draft PR; do not recreate an ancient historical branch.

## Implemented, still unqualified

An opt-in standalone control-only supervisor; ordinary GUI and frozen entry
points are deliberately not connected at this stage. The owner process holds
the native profile lock and the actual Core Popen. GUI/client disconnection does
not stop Core. Stable create-once profile, config and token survive supervisor
reopen. Partial profiles/config drift/binary changes/competing locks refuse
without repair, deletion, port rewriting or foreign PID adoption.

The loopback control protocol exposes only status/start/shutdown, with bounded
frames/deadlines, strict schemas/duplicate-field refusal, request/response HMAC,
a fresh authenticated boot challenge and a bounded replay cache. The control
token is a same-OS-user capability, not protection from a compromised OS user.
It is separate from wallet custody and never appears in argv or public status.

Core reads use unchanged Q03 `ManagedReadRpc`/`OwnedCoreBinding`; the existing
signed CLI and registered owned scope perform explicit stop. There is no HTTP
write API, external-Core adoption, wallet/seed/scanner IPC or spending exposure.
Q04 external attachment code, Q01–Q03 custody/transport code, workflows and the
canonical ledger are unchanged. Linux still needs explicit developer manifest
and native root-witness policy; no signed-Linux claim or custody fallback.

Historical sources selectively reviewed: PR #66–#73 and #122 at
`522b36e6e10c47f97f36e9cd3a6bab6eb8fef50e`. Control protocol/store/client were
adapted; the stacked supervisor/wallet/recovery code was not merged wholesale.
The earlier reuse assessment remains valid: do not import historical HTTP
writes, BIP39/account-isolation dependencies, disposable normal launcher or
historical PASS receipts as current qualification. New protocol v2 adds boot
binding; historical v1 profiles are not silently upgraded.

## Tests completed locally

Use Python 3.12 with `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src`.

```
python3.12 -m unittest discover -s tests -p 'test_q05_*.py' -v
```

33 Q05 tests PASS: native private-store locking/create-once/refusal, control
authentication/replay/boot binding/client response validation, profile reopen,
config/binary drift, lifecycle authority, RPC busy coalescing, failed auth,
crashed Core refusal and uncertain shutdown retention. Core process/RPC are
fixtures in the lifecycle suite; these results do not prove genuine Core.

The sequential targeted regression suite also passed, 92 tests total, combining
the above with `test_q03_json_rpc.py`, `test_external_core.py`,
`test_rpc_contention.py` and `test_q_gate_ledger.py` (13 governance tests).
Q03's intentional dropped/timeout HTTP reply can print a fixture BrokenPipe;
the final unittest result was OK. No platform/native/frozen acceptance promoted.

Development history: the first local socket attempt was denied by the sandbox;
the same tests passed with authorized loopback access. A removed `re` import in
the new store caused a unit run to fail and was restored before the final PASS.
No tests were skipped to obtain PASS. No manual CI/E2E dispatch was performed.

## Exact next action and remaining work

1. Review the **new supervisor start path** with targeted positive/negative
   tests for Popen ownership registration, warmup, endpoint spoofing and startup
   failure retention. The existing stage tests do not exercise real Core start.
2. Run one bounded local genuine signed-Core REGTEST lifecycle on a newly
   created private test profile: authenticated start, client disconnect/reopen,
   explicit stop, supervisor reopen and same chain/datadir. Pin source/Core
   hashes and record a receipt; use only disposable data. If tooling is absent,
   record PENDING, not a synthetic PASS.
3. Extend the persistent owner state/recovery journal. A supervisor crash with
   Core still alive currently refuses reentry through port/ownership checks;
   no orphan adoption or cross-process reattach is implemented. A Core crash or
   uncertain stop latches recovery-needed in the current owner and requires
   later explicit recovery. Durable dirty-shutdown detection across supervisor
   restart is not implemented; do not qualify crash recovery from Stage A.
4. Then selectively integrate scanner/native vault lifetime and exact-checkpoint
   recovery, normal packaged onboarding, managed wallet continuity and spending.
   Preserve signed/uncertain reservations and never replay uncertain broadcast.
5. Only after source work, qualify genuine-Core native/final frozen on all three
   OS, Windows DPI cases, adversarial lifecycle/endpoint tests and exact artifact
   provenance. Physical operators and independent reviewer remain separate.

No mainnet, owner miner/wallet, release, merge or full-Q05 work was performed in
this bounded session. No implementation beyond Stage A should restart from
historical stacks; continue the pending steps above on this branch.

## Developer entry (not acceptance evidence)

Create a new private profile in an approved isolated test directory, named
`wam-fusion-core-` followed by 16 lowercase hex digits. In separate terminals:

```
python3.12 -m wam_regtest.supervisor_cli serve --root /ABS/TEST/PROFILE \
  --core-dir /ABS/VERIFIED/CORE --confirm-regtest-managed-core
python3.12 -m wam_regtest.supervisor_cli start --root /ABS/TEST/PROFILE \
  --confirm-regtest-managed-core
python3.12 -m wam_regtest.supervisor_cli status --root /ABS/TEST/PROFILE
python3.12 -m wam_regtest.supervisor_cli shutdown --root /ABS/TEST/PROFILE \
  --confirm-regtest-managed-core
```

Set `PYTHONPATH=src`. Linux serve additionally requires
`--linux-developer-manifest APPROVED_SHA256 --linux-root-witness /ABS/WITNESS`.
Stop only the owned Core via the authenticated shutdown command before ending
the serve process. Never delete locks, kill a guessed PID or use this developer
entry against an existing owner datadir. No automatic crash repair is provided.
