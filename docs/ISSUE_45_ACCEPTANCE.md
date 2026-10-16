# Issue45 execution and acceptance registry

Canonical scope: [Issue45](https://github.com/Urriki1502/wam-privacy-wallet-regtest/issues/45), read in full, observed 2026-10-16T09:57:52.013008+00:00.
This registry is evidence bookkeeping, never an alternative specification or
production/mainnet permission. [Machine registry](../tests/acceptance/issue45.json)
contains all42 task IDs and20 Q IDs with separate SOURCE/CORE_E2E/FROZEN/
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
