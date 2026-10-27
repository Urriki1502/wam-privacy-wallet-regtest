# Q05 Stage A checkpoint — 27 October 2026

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
