# Q04 interrupted-engineering recovery

Existing Draft #133 only. Engineering is REGTEST-only; no owner node, miner,
wallet, funds, mainnet or release action. Root active-Q note is reconciled with
the canonical Q04 ledger. Q05 remains queued.

## Reproduced frozen failures

At 423bd9dc, Linux frozen desktop/headless returned2 because its separate process
never received explicit developer-Core trust and a live root witness. The native
wallet acceptance process's policy cannot transfer to the new executable, and
its witness had been torn down. The existing operator harness now keeps its
provisioned witness alive, supplies the pinned manifest/socket/explicit consent,
and the frozen CLI independently configures policy before starting the fixture.
The application never installs a privileged service or inherits an unverified
policy. Missing trust still fails closed. Only typed fixed public error codes
are reported; no raw exceptions, credentials or paths are emitted.

Mac PyInstaller executes package_entry.py as a script without a package parent.
Its relative external_core import failed at startup. Both Mac and Windows Q04
entries also lacked run_q04_scenario. They now use explicit absolute imports.
Windows build_windows_bundle.main had conditional inner import re statements,
so re was local and unbound on the later Q04 refusal path. The module-level
import is now used throughout. The refusal receipt remains nonpassing; adding
Q04 fixed diagnostic tokens does not convert a failure into success.

## Genuine busy and actual Qt refresh

The former script observed raw Core503 separately but used injected busy signals
for retry/coalescing. Those contracts remain supplemental. A new bounded probe
occupies the owned disposable fixture's worker/queue with genuine long-poll
reads. The actual ExternalCoreAttachment receives four HTTP503 replies through
fresh process/socket proof; observed retry intervals must meet jittered minimum
backoffs. A hot coalescer causes zero further RPC calls, then a real read recovers.
A write reaches only the read-only denial boundary once and is never replayed.
No simulated busy response qualifies the positive case.

ExternalNodeWindow is an operator-approved read-only monitor exposed through
`attach-core-readonly`; consent, native Core/cookie custody and REGTEST identity
are checked before use. It has no wallet/write/stop controls. During cooldown,
refresh rechecks process identity, clears height and shows Node busy. Closing
only closes observation; it never stops the external Core or miner. The actual
Qt class is exercised with genuine busy in final Mac/Windows/Linux desktop
executables; Linux no-Qt headless is separately qualified and cannot satisfy GUI
acceptance. No source/server result is mocked by the positive probe.

The fixture drives sustained mining using a thread and independent Core CLI
processes. This is an isolated lab, not physical observation of the owner's
miner. Source/negative contracts are supplemental; physical and independent
acceptance stay separate.

## Provenance and acceptance boundaries

Initial repaired runtime: e16b80b24d056ae8fb96bbb1d13285187a2c1fc1. The later
credential-pin and actual reconnect repair requires fresh qualification before
case promotion; the importer requires the exact runtime-source SHA explicitly. The canonical ledger records the
actual artifact-qualified workflow source and merge checkout, not a later ledger
commit. All artifact ZIP hashes, internal manifests, final payload hashes and
actual nested Core binaries must match live Actions metadata. Native Q04 and
frozen Q04 receipts are distinct. Linux desktop/headless variants stay separate;
Linux Core remains reviewed-developer-source-build, never official-signed.

scripts/update_q04_ledger.py verifies five successful same-source workflows,
three native receipts and four final packages before any promotion. It reuses
the strict Q03 manifest/payload verifier without modifying Q03 records. Missing,
wrong-platform, synthetic busy, headless-as-GUI or stale proof aborts without
writing. check-only verifies later governance descendants without relabeling
immutable receipts. Earlier frozen failures and native snapshots are preserved.

Physical uninterrupted solo-miner observation needs an authorized operator.
Independent architecture/security review needs a separate reviewer. Owner merge
authorization and exact-main postmerge checks are outstanding. G6/G7 stay
BLOCKED and accepted=false. No Q05 engineering handoff is implied by green CI.

The operator source entry is:
`wam-regtest attach-core-readonly --core-dir APPROVED_CORE --datadir REGTEST_DIR
--pid DECLARED_PID --rpc-port DECLARED_PORT --confirm-readonly-regtest-attachment`.
Linux also requires its reviewed `--manifest-sha256`, live `--anchor-socket` and
`--confirm-experimental-developer-regtest`. No password/token is accepted on the
command line. This does not authorize attaching to an owner's mainnet miner.

The first repaired runtime snapshot e16b80b completed the Mac frozen Q04 job,
but the workflow's explicit upload list omitted q04-frozen-evidence.json even
though the release manifest included its hash. This is missing acceptance proof,
not a qualified artifact. The upload list now includes that exact receipt;
a fresh same-runtime source snapshot must pass before ledger promotion. Linux
frozen desktop/headless outer/payload/Core evidence from e16 was verified.

## Reconnect and credential continuity correction

The old reconnect scenario created a session but never exercised its disconnect
branch. The probe now aborts one real client TCP connection to the genuine Core
using SO_LINGER, restores the socket factory in finally, and requires a fresh
fully attested attachment and real response. This is explicit transport fault
injection, not a fabricated RPC server or result.

A new negative contract reproduced that reconnect adopted changed cookie bytes
under the same PID/port. ExternalCoreSession now pins a credential digest, and
the attachment compares it BEFORE sending any authentication. Changed bytes
revoke recovery; restoring the old cookie does not resume the revoked session.
Closing an attachment clears its cached auth. The genuine-Core fixture operator
also changes/restores ONLY its disposable node cookie and verifies both refusals.
Product external attachment never edits the cookie, datadir or node. Independent
security approval remains outstanding.
