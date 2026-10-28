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
