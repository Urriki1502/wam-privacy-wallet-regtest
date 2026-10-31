> **ARCHIVED LOCAL FUNDING DIAGNOSTIC — original evidence retained, current status updated 31 October 2026.** This dated document preserves historical diagnostic findings, original FAIL receipts and their contemporaneous assumptions. It is **not** the current Q05 acceptance ledger, not a live STOP instruction, and not a basis to re-run completed smoke tests. Current Q05: **32 technical PASS / 4 external BLOCKED / 1 owner PENDING**, G0–G5 PASS, G6–G7 BLOCKED, `accepted=false`; qualified runtime source `4f7d4ed42e5fdeb5ea91712dea70ea4653bce0f5`, PR #138 DRAFT. See [current checkpoint](Q05_STAGE_A_CHECKPOINT.md) and `tests/acceptance/issue45.json`. Any 0/37 PENDING or unfinished-CI wording below refers only to the original dated test observation.

---

# Q05 local funding diagnosis — 29 October 2026

This is a local diagnostic report, not an acceptance ledger or a native receipt.
The only case ledger remains `tests/acceptance/issue45.json`, unchanged.

Branch `local/q05-development`, base/HEAD
`93c5c68666c7760fa84735eb0ca96f0ef6246dc8`; the correction is an uncommitted diff.
Local interpreter `.venv/bin/python`: CPython 3.12.15. Pinned WSP checkout
`wsp-upstream` is clean at `ac55f13423620252bdbf848c7e8a280c3b84721e`.
The declared final macOS frozen baseline remains CPython 3.12.10.

Preflight found a clean tracked/untracked tree, no unrelated plan file.
The official engineering lease was already exclusively held. Read-only `lsof`
identified same-user Python PID 11811, this repository as cwd, Terminal
`/dev/ttys001`, and fd 3 on `.git/wam-engineering.lock`. A nonblocking flock
check confirmed exclusivity; it did not acquire, remove or bypass that lease.
`ps` was denied by the sandbox. No other engineering process was observed with
the available evidence; a complete process inventory could not be established.

## Preserved qualification failures

Owner-supplied exact-source evidence at 93c5c686:

- Run 40865990290, native macOS job 123420773519: FAIL at funding,
  `WALLET_OPERATION_DENIED_STATE_RETAINED`, then exceeded eight-minute bound.
- Same run, frozen macOS job 123423045464: FAIL at funding, same public error,
  then exceeded approximately 420 seconds.
- Run 40863103886, macOS job 123411012919: CANCELLED, not PASS.

These facts are retained as supplied; full job logs were not obtained in this
session. `gh api` could not connect to api.github.com. The available web reader
returned cache misses for the failed job, PR138 and live main. The canonical
Issue #45 and standing authorization were readable through the web reader.
Cached local `origin/main` is `fe6a9e93903800743a1b0e5f87658f71524d57e5`;
it is not a freshly verified live-main SHA. No fetch/push/dispatch was performed.

## Trace and conclusions

`Driver.tick` starts `network` with the qualification-only LabBackend funding
flag. The normal temporary Qt worker calls ManagedWalletProxy; WalletExecutor
serializes the operation on its persistent owner thread. LabBackend checks the
managed session (thread, original process, runtime/container/reference/anchor
floor), constructs WalletCoreCli and attests the real local chain, genesis,
peers and version. Read RPCs use the bound HTTP transport. `generatetoaddress`
and fixture `sendrawtransaction` use the signed CLI through `_read_cli` /
`rpc_scope.route`: original image/endpoint/credentials and disposable mutation
consent remain required. The public fixture spends scalar 31's REGTEST coinbase
to the disposable account, then confirms with another generated block.

**PROVEN, deterministic source contracts:** CLI failure can quarantine the
shared RPC scope while `CoreSupervisor._faulted` remains false. CLI timeout is
one demonstrated injection producing this state. The old backend selected
normal shutdown solely from the supervisor latch. Normal shutdown then refuses
the quarantined scope, never executes CLI stop, and retains the owner/process.
The GUI clears its quit request after that failure; the non-daemon executor
remains alive. This is a reproducible cleanup defect, not proof that CI had the
same initiating error. Two new routing assertions failed before correction;
the corrected tests pass. A separate test exercises the actual normal shutdown
method against a quarantined scope and verifies retained ownership/no signal.

**HYPOTHESIS for CI funding:** the single 101-block `generatetoaddress` uses the
generic ten-second CLI deadline. A timeout would yield the reported generic
public error and the cleanup defect above. No real timing/log evidence proves
that CI timed out there. Authentication, native endpoint attestation and fixture
payment failures remain alternatives. No mining deadline, RPC grant, method
surface, retries or acceptance assertions were changed.

**UNKNOWN:** exact initial funding failure and exact shutdown error on either
macOS CI job. Native replay is required before claiming their resolution.

## Focused correction

- `wallet_executor.py`: on explicit quit/restart, a quarantined shared scope
  selects the existing original-owner `recover_stop` path even when the
  supervisor latch has not yet observed the failure. It freshly verifies profile,
  binaries, original Popen/native image, endpoint, credentials, REGTEST genesis,
  version and peers before graceful signed-CLI stop. Reattestation failure
  propagates; there is no kill, automatic transaction replay or replacement.
- `q05_gui_scenario.py`: qualification-only failure receipts now retain the
  failed session/attestation/generation/payment stage and finite typed error
  categories, including an allowlisted underlying CLI context when available.
  Unknown/private/foreign-subclass error text is never copied. The original
  exception is re-raised. Transport cleanup now also covers failed attestation.
- `test_q05_gui_funding.py`, `test_q05_wallet_executor.py`,
  `test_q05_managed_gui.py`: positive and negative authorization/funding-order,
  transport cleanup, scope quarantine, original-owner stop routing, refused
  reattestation and responsive failure/quit behavior. Qt tests use a fake backend
  with real offscreen Qt events; they do not qualify Core.

No custody/anchor/recovery formats, single-thread/native lease rules, identity,
journal, irreversible reservations, HTTP write boundary, timeout or Q01–Q04
implementation were altered. Existing FAIL receipts/profiles were not changed.

## Validation and limits

Final command (106 tests; see retained log):

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python -m unittest -v \
  test_q05_gui_funding test_q05_wallet_executor test_q05_managed_gui \
  test_q05_probe_source test_q05_packaged test_q05_history_helpers \
  test_q05_history_pagination test_q05_recovery_model test_q02_contracts \
  test_wallet_session_contracts test_q_gate_ledger
```

The initial new tests exposed two expected routing FAILs before correction.
During test authoring, fixture-only errors (non-indexable Mock accounts and a
missing `ready` field) were corrected; neither was a Core result. Earlier
94-test and 105-test batches and nine offscreen Qt tests passed. Do not sum
overlapping batches. The final log is
`docs/evidence/q05/local-funding-20261029-regression.txt`.

`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m wam_regtest.q_gate`
passes: Q05 sole ACTIVE, 0 PASS / 0 FAIL / 37 PENDING / 0 BLOCKED / 0 STALE,
G0–G7 PENDING, accepted=false. Physical/independent/merge evidence remains
missing; its ledger state was not relabeled. Q04 G6/G7 remain BLOCKED.

**Real Core native GUI: NOT EXECUTED. Frozen: NOT EXECUTED.** A direct
127.0.0.1 bind probe fails with PermissionError/errno 1 under this sandbox.
No verified signed Core staging directory is present in this checkout; the
local bootstrap explicitly did not download Core. No dependency was downloaded,
DMG mounted or sandbox restriction bypassed. No Core was launched or signaled,
and no REGTEST profile/keychain/datadir was created by this session. There is no
new Core executable measurement or native/frozen artifact hash to report.
Historical expected macOS hashes (not measured this session):
wamd `7298de701e467eb28b4806cbcbe35edb393861b4b97117017fee4c1b194e3068`,
CLI `81a031ebf9b3060b19061b29756d43bcd09b32ad778348b8c3d8321397076e82`.
Windows/Linux changed-source qualification and socket-based native/HTTP suites
are NOT EXECUTED here. CPython 3.12.15 never qualifies the final 3.12.10 build.

## Exact next engineering action

Local staging was attempted once and refused with `.git/index.lock: Operation
not permitted`. Nothing was staged or committed; no permission bypass was used.
After review, the exact manual local commit commands outside this restricted
session are:

```sh
git add -- src/wam_regtest/q05_gui_scenario.py src/wam_regtest/wallet_executor.py \
  tests/test_q05_gui_funding.py tests/test_q05_wallet_executor.py \
  tests/test_q05_managed_gui.py docs/Q05_STAGE_A_CHECKPOINT.md \
  docs/Q05_LOCAL_FUNDING_DIAGNOSIS_20261029.md \
  docs/evidence/q05/local-funding-20261029-regression.txt \
  docs/evidence/q05/local-funding-20261029.json
git commit -m 'fix(q05): reattest quarantined owner shutdown and retain funding diagnostics'
```

On an authorized macOS host with loopback/native ownership proof and the
verified signed v0.1.11 Core directory available, first review and commit this
exact diff on `local/q05-development` (never push in this local scope). The
existing native probe requires clean committed source; do not disable that
check. Hold the official lease through execution. Then execute:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:wsp-upstream/src .venv/bin/python \
  scripts/probe_q05_executor_gui.py \
  --core-dir /ABS/VERIFIED/SIGNED/CORE \
  --wsp-source "$PWD/wsp-upstream" \
  --root /private/tmp/wam-fusion-core-NEW_16_LOWERCASE_HEX \
  --receipt /ABS/NEW/q05-native-receipt.json \
  --confirm-disposable-regtest
```

Replace placeholders with verified Core and entirely new canonical disposable
paths; never reuse an old profile or receipt. Use the newly recorded
`fixture_funding_failure` to distinguish actual generation timeout, attestation,
consent or payment failure; preserve FAIL before any authenticated cleanup.
Repair only the demonstrated cause and replay impacted cases. If it passes,
qualify the final macOS frozen application on CPython 3.12.10 and changed-source
Windows/Linux separately. No automatic release, merge or Q06 work is authorized.

ENGINEERING HANDOFF: NO. FULL Q ACCEPTED: NO. V1 HOLD / MAINNET DENIED.
