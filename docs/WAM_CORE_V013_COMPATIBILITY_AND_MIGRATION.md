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
v0.1.12 GitHub Release API currently returns 404; source-tag compare inspected on 2026-11-05 confirms all three assignments in
[chainparams.cpp](https://github.com/wamcoin-Project/wam-coin/compare/v0.1.11...v0.1.12).
The release API absence does not imply the source tag is absent.
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

## Reviewed code-site classification

| Site | Category / treatment |
|---|---|
| release.py VERSION/ARCHIVES/CLI_SHA256/MEMBER_ROOT and downloads | Active official tar intake; migrate exact authenticated bytes, preserve old evidence in Git/history |
| windows_release_preflight.py ASSET/ROOT/ARCHIVE_SHA256/BINARY_SHA256 | Active PE/archive source pins; Stage A2 pending |
| windows_core_transport.py | Active DACL/no-reparse private read/write and immutable member comparison via preflight pins; preserve |
| core.py, json_rpc.py, wsp_live.py, q02_probe.py | Active native RPC allowlist; observed Linux tuple 113,/WAM:0.1.13/,70016; wrong versions still refuse |
| shared_regtest.py | Active strict peer subver; update exact observed version, no discovery/network identity changes |
| core_supervisor.py profile read and fresh create | Active profile guard/new format identity; v0.1.11 remains rejected, never rewritten |
| linux_developer_core.py, build_linux_developer_core.sh, test_linux_developer_core.py | Historical separately reviewed developer policy/helpers, retained unchanged; not new official trust |
| linux_official_core.py, linux_runtime.py | New candidate signed member pins plus immutable reviewed loader closure; root witness still required |
| build_linux_wallet.py, linux_headless_acceptance.py, q01_core_negatives.py, qualify_q05_native.py / frozen.py, qualify_q06_frozen.py | Active new candidate inputs and qualification; original developer artifacts retained |
| q05_platforms.py / gui_scenario.py / checkpoint_scenario.py / security_scenario.py | Active platform adapters/current receipts; actual native proofs remain OS-specific |
| build_windows_bundle.py and Windows workflow download stanzas | Active Stage A2 inputs; must use signed v0.1.13 URL and exact pinned root |
| build_macos_bundle.sh, audit_wallet_security.py, macOS workflows | Active Stage A3 intake and frozen byte preservation; Stage A3 pending |
| package_entry.py, desktop_probe.py, core.py V0_1_11 status strings | Legacy version-labelled result tokens in active producers; must become current version at integration; old receipts immutable |
| fusion_ui.py, bip39_fusion_gui.py, desktop.py, operational_gui.py, cli.py | Current UI/help labels; describe official candidate, independent witness and actual identity |
| build_provenance.py tests/source_contract/v0.1.11 path | Historical literal-source corpus allowlist; preserve directory identity |
| q_gate.py and update_q03_ledger.py / update_q04_ledger.py old proof validation | Historical integrated-Q evidence contracts, not candidate Core authority; do not use these scripts to relabel new receipts |
| tests/acceptance/issue45.json existing case evidence | Historical case-level ledger; no blanket PASS transfer to changed candidate; Q06 accepted=false |
| docs/evidence, prior audits and public RC manifests | Immutable historical evidence; leave original hashes/failures and source attribution intact |

The intermediate Linux receipt retains inherited V0_1_11 status-token spelling,
but independently reports observed_core_version=113 and subver /WAM:0.1.13/.
Do not interpret that inherited token as an execution of the old Core. Correct
active producer tokens and rerun the final common-source matrix before completion.
