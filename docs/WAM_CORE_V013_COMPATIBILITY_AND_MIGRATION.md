# WAM Core v0.1.13 compatibility and migration

Candidate baseline: bd783d7 (docs-only child of qualified c61e3c5).
New profiles only. Stage A order: Linux, Windows, macOS, common exact-source
native/frozen qualification. Stage B remains separate and fail-closed.

## Upstream behavior and ABI

v0.1.11 tag commit 8a3f4fe4f1d804c378f795d4cc281ec5125f75f3;
v0.1.12 bbe584f5befe378657c7287c3149a613d2cd5eef;
v0.1.13 b3fb899ddb1ceab7e9b3b12ccd034ad1b4be8186.
Upstream v0.1.12 corrects uninitialized enforce_BIP94 (REGTEST true,
main/test false); identical behavior to v0.1.11 must not be assumed.
v0.1.12 GitHub Release API currently returns 404; source-tag inspection
is required to substantiate the research description before qualification.
v0.1.13 release adds five ZMQ publishers/HWM options and runtime-library
packaging checks. Its no-consensus-change statement is relative to v0.1.12.
Fusion continues authenticated loopback RPC only; no ZMQ, discovery, remote
RPC, consensus edits or WSP migration. Observe actual native RPC tuple and
peer subversion before changing assertions. WSP remains ac55f13423620252bdbf848c7e8a280c3b84721e.

## Pin audit and threat boundaries

Active release.py intake, windows_release_preflight.py, Core receipts,
core.py/json_rpc.py/wsp_live.py/q02_probe.py RPC tuples, shared_regtest.py
peer version, core_supervisor.py new-profile identity, q05_platforms.py,
Linux runtime and builders/workflows require scoped updates. GUI environment
labels and new receipts must describe the actual new runtime.
linux_developer_core.py, its build script/tests and prior manifests stay
historical reviewed developer policy; they must not become an official policy
by toggling a boolean. A separate signed Linux verifier must independently
pin archive/member identity AND retain loader/library checks, no-follow file
custody, private datadir, root witness, original owner and checkpoint CAS.

Historical docs/evidence/acceptance case proofs, tests/source_contract/v0.1.11,
RC1 and package inventories are immutable references, not new qualification.
Profile version/core_sha256 is an old-format compatibility guard, not a value
to rewrite during startup. Scoped test expectations must distinguish
intentional v0.1.11 rejection fixtures from active v0.1.13 expectations.

Storage compatibility is unproven for retained chains/wallets. Fresh Core
mining, BIP352, native custody and frozen probes must establish behavior.
Ubuntu24.04/glibc >=2.38 remains the Fusion minimum even if Core needs less.
Cocoa PaymentApproval.open(), separate Sign/Broadcast consent, one-sign,
commitment equality, signed/uncertain reservations and antirollback stay.

## Stage B threat model / decision

MIGRATION_PENDING. No conversion entry point or owner-profile mutation.
A fixture-only candidate requires authenticated original profile+anchor,
provable original Popen shutdown and lease release, durable checkpoint/native
CAS, exact old/new signed binary and REGTEST genesis/chain identities,
immutable old-to-new identity journal and crash-cut recovery. Unknown owner,
wrong credential/genesis/hash, stale checkpoint, partial journal, signed or
uncertain locks lost, downgrade, orphan adoption or native-anchor reset deny.
No seed generation/export, WAL deletion, rebroadcast or wallet database rewrite.
Core migratewallet is BDB-to-descriptor conversion, not this identity protocol.
Until positive monotonic/crash-safe evidence exists, keep default rejection;
new-profile success cannot qualify old-profile migration. Artificial fixtures
may be created later; the approximately 42 retained test profiles are excluded.
