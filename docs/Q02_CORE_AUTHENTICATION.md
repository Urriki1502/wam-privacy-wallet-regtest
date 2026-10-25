# Q02 — authenticated genuine Core, identity and fail-closed CLI

Scope: Issue #45 Q02 under owner Q-GATE v2, based on main
`a6148dde377e00bdb63458fc50826e83ecd5c8a9`. One main-based Draft PR;
no automatic merge or Q03 activation. The only case ledger is
`tests/acceptance/issue45.json` (134 cases including external gates).
Q01 full acceptance and V1 remain blocked. Historical Q01/A06 evidence is intact.

## Reviewed findings and implementation

- **F1 PARTIAL:** the POSIX/Windows method validation asymmetry is confirmed
  by source inspection. Existing wallet/scanner callers construct fixed methods;
  arbitrary owner-supplied CLI options are not an established reachable exploit.
  No claim that a post-method option actually overrides this pinned CLI has been
  made. Both platforms now use one finite method/parameter boundary. Only
  `-rpcwallet=test getnewaddress` is accepted as a wallet selector. Bare hash,
  address and stop results remain text; JSON methods reject malformed/duplicate/
  nonfinite/incorrectly typed results. Output is bounded **during** pipe draining,
  stderr is private and bounded, the child has a total deadline and is reaped.
- **F2 CONFIRMED (source):** Core smoke checked chain but not genesis. It now
  independently reads `getblockhash 0`, compares the exact WAM REGTEST genesis
  `b88f3d262f285e38e184f50bf3eea1c8e615486ae67d3d9eaf0976fbd6d3d30d`,
  and checks observed `111 / /WAM:0.1.11/ / 70016`. Receipt fields contain the
  observed values. Existing WSP chain/genesis/zero-peer checks remain; a failed
  new attestation clears the previous grant, and a replaced owned-process scope
  invalidates an old read client.
- **F3 CONFIRMED (baseline evidence gap):** main had no enumerated/executed Q02
  cases. The first Q02 commit recorded 128 cases before runtime work; the review
  added three GUI fault-latch cases and three unexpected-peer cases. No old Q01
  PASS is reused as Q02 qualification. Native/frozen results stay PENDING until
  exact-source receipts and shipped bytes have been inspected.
- **Additional hypothesis:** mapped process and socket ownership now bind each
  CLI call to the original live creator Popen, approved loopback port and
  independently pinned Core/CLI files. Native metadata is checked per call,
  without introducing repeated full binary hashing. A zero-byte socket probe
  precedes the CLI invocation. This is **not** an atomic socket-to-CLI handoff,
  hardened loader/DLL attestation or protection against same-user/OS compromise.

No persistent HTTP/shared JSON-RPC architecture from Q03 is implemented. The
uncommitted early HTTP experiment and its supplemental local receipts were
retained outside the repository for audit, then superseded. Those receipts
never qualify this candidate. No entire legacy branch was imported.

## Post-audit fixes and current evidence (2026-10-25)

After the independent source audit three reproducible medium defects were fixed
at source commit `913da26e0d36017b29bbc4841a495d4b1b6a7f27` on the Q02 branch:

1. **macOS socket-probe failure handling** (`src/wam_regtest/core_process.py`).
   The `lsof` ESTABLISHED-socket probe now translates `subprocess.SubprocessError`
   and stdout decode failures into `CoreBindingError('RPC_SOCKET_PROOF_DENIED')`,
   instead of leaking raw exceptions that could bypass the fail-closed boundary.
2. **Headless Core reauthentication approval** (`src/wam_regtest/linux_headless.py`).
   Interactive `unlock` and `recover` now explicitly prompt the operator to type
   `REAUTH` when `_core_reauthentication_required` is set. Approval alone does not
   unlock the wallet; the wallet passphrase/custody check is still required. This
   prevents a silent transport-only reauthentication from reactivating a faulted
   session.
3. **Owner acceptance scope registration** (`scripts/owner_acceptance.py`).
   The disposable native Core launched by the owner/UX audit now registers the
   owned process scope with `register(..., authorized_disposable_mutation=True)`
   and unregisters it in `finally`, so subsequent `_read_cli` calls in the same
   harness use the authenticated binding.

Regression contracts for the three fixes were added to
`tests/test_q02_contracts.py`. The full source test suite on the fix commit
reports **146 pass, 33 skip, 0 fail**.

Local genuine Core smoke on macOS ARM64 after the fixes produced 33/33 Q02 case
PASS and full wallet/security E2E PASS. The local receipt is retained at
`/private/var/folders/3l/hqzxttpd0rx2hp38q52pkb240000gn/T/opencode/wam-q02-9985e44/local-real-core-evidence-2.json`.

Exact-head CI artifacts after the push were downloaded and inspected:

| Platform | Artifact | SHA-256 | Status |
|---|---|---|---|
| macOS ARM64 | `WAM-Fusion-REGTEST-RC1-macos-arm64-f669152f...` | app.zip `240828c2a5cdac4501e71c178cfe11d78b703220eefa3ea70f4016be0abfd416`, DMG `0e6dea188c400ffd10ce3f62b602c5e2c269246d964377f537f81c39ef565c11` | **PASS** at exact-head CI run 40182785805 |
| Windows x64 | `WAM-Privacy-Wallet-REGTEST-windows-x64-9985e443...zip` | `af1894e165af08d84a72623eaaba9f75800b91479f43501f47e32aa19ca103b6` | PASS at exact-head CI run 40151555639 |
| Linux x86_64 desktop | `wam-regtest-desktop-linux-x86_64-9985e443...tar.gz` | `f1305891dd857c52dc06be02fad699bd35299a555e638cc20eb137cbcaa9e32a` | PASS at exact-head CI run 40151555636 |
| Linux x86_64 headless | `wam-regtest-headless-linux-x86_64-9985e443...tar.gz` | `f4a6ff49d9f09efcd7a68ff0ad42b07d54cd2eef6cccbd1065f9db1110dfac7b` | PASS at exact-head CI run 40151555636 |

**Rerun note:** the first native-app-dmg attempt at the new exact-head flaked on
`WALLET_E2E_STAGE=REOPEN_ON_NEW_CORE` (likely a scheduler/timing issue during
cross-session recovery). No source change occurred between the two attempts; a
rerun of the same job with the same commit succeeded. The failed attempt remains
in CI history; only the green exact-head run is used as ledger evidence.

Ledger validation (`python -m wam_regtest.q_gate --ledger tests/acceptance/issue45.json`)
now reports: **PASS 126, STALE 0, BLOCKED 8, FAIL 0, coverage 134**.
Gates: G0/G1/G2/G3/G4/G5 PASS; G6/G7 BLOCKED
(external independent review/physical operator and owner merge authorization).

## Identity, credentials and mutation rights

Only an explicitly consented disposable fixture's original process is registered.
Registration authenticates the original Core pair once; process liveness/image,
unchanged native binary metadata, protected config/cookie identity, and kernel
endpoint ownership are checked at the boundary. Linux uses the independently
reviewed developer manifest and existing runtime policy, not an official-signed
Linux claim. Missing/native-unsafe/replaced credentials deny without fallback.
Cookie mode permits only Core's fixed `regtest/.cookie` path. Native config,
vault, anchor and witness protections are not relaxed. The sole inherited-DACL
case is Core's own cookie under the protected Windows datadir, still restricted
to the exact owner/one ACE/native file identity.

Read-only scanner `call()` has no writes. The separate existing disposable
coordinator's mutation permission must be explicit; successful authentication
alone does not grant it. Session write approvals, anchored signed/uncertain
reservations, native leases and exact intent/sign/broadcast boundaries remain.
Requests are never automatically replayed after an ambiguous response.

External process discovery/adoption is not introduced. An unregistered external
Core is refused even with a plausible config or binary path. The standalone
`gui --datadir` route therefore cannot authorize an external node through this
new boundary. Managed demo/wallet paths register their own node. Separately
qualified attached-Core integration belongs to the later Q04 scope; borrowed
reads never acquire node termination or recovery authority.

## Fail-closed wallet and explicit recovery

Authentication/chain/genesis/version/peer/process/config failures fault the
operational wallet, hide verified balance/QR/history and disable sensitive
controls. Public errors use finite categories, never Core stderr or arbitrary
exception text. Existing encrypted state and irreversible reservations are kept.

Restoring a credential file does not revive the quarantined scope. The operator
must Lock, Unlock with the native wallet passphrase/custody check, and explicitly
approve reauthentication of the **same** owned REGTEST process. Approval alone
or a wrong passphrase cannot initiate Core reauthentication. This neither adopts
another node nor resets anchors, replaces a wallet, rebroadcasts or re-mines data.
A transport-only explicit reauthentication leaves the old wallet faulted until
its separately authenticated reopening.

## Reproduction and evidence semantics

Native macOS/Windows smoke: add `--confirm-q02-auth-e2e` to the existing explicitly
consented `smoke` command. Linux's existing `--confirm-qt-e2e` / headless acceptance
modes and final frozen acceptance modes run the same Q02 probe. Ordinary
interactive launches never execute negative acceptance faults. Existing workflow
and packaging approaches/dependency locks are reused.

The 33 Core scenarios use fresh owned genuine v0.1.11 REGTEST processes. Negative
reply cases alter output **only after the actual signed CLI response was
observed and validated**. Receipts identify these as injected faults. Their ledger layer is NEGATIVE_INJECTION, with the same mandatory Core/WSP/OS/run provenance checks, rather than relabelling them genuine wrong-network Core E2E. No synthetic
RPC server, actual public-network node or fabricated positive chain is used.
The signed CLI handles HTTP envelopes; Q02 tests its exposed result boundary,
not a new Python HTTP implementation. Source contracts separately test overflow
with ordinary Python children; those are SOURCE tests, not real-Core acceptance.

The GUI regression changes credentials only inside its own disposable fixture,
observes the real Core authentication refusal, and checks retained accounts,
native anchor and reservation rows, hidden UI and disabled mutation controls.
Existing genuine WSP/BIP352/SQLite, stale-writer, reorg 1/12/100, wrong-passphrase,
lock/unlock/recovery and uncertain-broadcast tests remain mandatory.

No blanket technical PASS is derived from a green unrelated job, missing OS,
skipped test or source-only result. Final frozen qualification requires the new
candidate's native bootloaders, receipts, exact Core/WSP bytes and artifact
SHA-256. Physical clean-host/UX and genuinely independent security/provenance
review, owner merge and postmerge gates remain separate and nonpassing.

### Native Windows cookie fixture owner finding

Run 40150786617 on `f9f850744208e3dd4fbde673fbddeb1107594335`
confirmed that the fresh Core cookie inherited exactly one current-user FA ACE,
but the file owner did not match the current token user. The owner check correctly
refused it. The strict private parent alone was insufficient; this is retained
as FAIL evidence, not a credential/profile PASS.

The pinned upstream `src/rpc/request.cpp` at Bitcoin revision
`32efe850438ef22e2de39e562af557872a402c31` writes `.cookie.tmp` using `ofstream`
and renames it over `.cookie`. The acceptance fixture now uses the existing
native explicit-owner security descriptor to **create a new empty staging file**
before starting its own Core. Core still generates all random secret bytes.
The staging constructor refuses an existing file, holds the strict parent, checks
native file/owner/DACL metadata, flushes and closes before Core starts. Native
custody verification itself is unchanged. This neither repairs an existing
owner/external cookie nor weakens owner/ACL requirements. Missing/replacement
negative tests retain and restore the original actual cookie object, rather than
recreating it with an unqualified default Windows owner. Replay remains required.
