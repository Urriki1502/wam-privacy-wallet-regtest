# V1-NET local engineering — scoped evidence, remaining blockers

Canonical workspace: `/Users/dinhdang/Documents/WAM-Q06-Audit-20261102`.
Branch: `feature/v1-net-shared-regtest-20261104`, based on Q06 documentation commit `03208bc`. Core/profile implementation commit `9baac93`; GUI/custody integration commit `84249fe`.
No push, PR, merge, remote CI, consensus change, mainnet or acceptance-ledger change is authorized or performed.

## Qualified Q06 checkpoint retained

See `Q06_LOCAL_STABILIZATION_20261104.md`. Latest runtime/build source `e48d6cc23eeb36e279611608f6021291142a0e04`; qualified distribution is preserved at `build/qualified-q06-e48d6cc/package-output/`.
DMG SHA256: `961bdc61c2c69ef15e3fd6d3719602b67a21653dc512854a80d42b113ac2acd0`; executable `5c3b14ad06a9b22e2074668f8313d3e10d9bc0f19989ca20ed7f073efcee25d7`. All 54 manifest members, ZIP executable/stamp and read-only-mounted DMG executable/Core/stamp independently matched. Own image detached. This artifact is standalone isolated Q06 and must not be presented as a shared-network build.
Previous qualified aaf2de2 distribution remains preserved at `build/qualified-q06-aaf2de2/package-output/`, DMG SHA256 `d482f8c2562a7f4c2162d58595ad808357b74ad7c0555419c08df23f4f227f43` (rehash matched after interrupted session).
Q06 remains `accepted=false`; owner G6 retest and independent G7 remain open.

## Architecture and changes

`shared_regtest.py` defines an explicit immutable manual peer profile. `CoreSupervisor` writes a distinct profile schema for NEW shared profiles, pins config/Core/CLI/genesis, and refuses isolated/shared reinterpretation. Default isolated settings are unchanged.

`network_policy.py`, `rpc_credentials.py`, `rpc_scope.py`, `json_rpc.py`, and `wsp_live.py` admit the exact shared config only with the registered original owned process and matching explicit profile. RPC stays on 127.0.0.1. Peer observations are bounded to the configured counterpart; completed Core handshake uses version 70016 and `/WAM:0.1.11/`. This is advertised peer identity, not cryptographic remote-host authentication.

Core alone owns TCP P2P, handshake, relay and consensus. The config uses existing `addnode`, `connect=0`, DNS/discovery disabled. No GUI P2P, remote wallet RPC, custom handshake, discovery service or second Core manager is introduced. The same `WalletExecutor`, BIP39 custody, BIP352 scanner, send engine, native checkpoint and reservation logic are reused.

`ManagedWalletBackend.network_status` reports verified genesis/height/tip/manual peer metadata/mempool, and `network_active` invokes one explicitly requested Core network toggle. No uncertain transaction write is retried. Mining is denied unless the profile is coordinator AND a configured peer has completed handshake. Participant mining is denied in both wallet dispatch and owned CLI boundary.

`managed_onboarding.py` adds an unchecked Shared REGTEST selection; `shared_regtest_gui.py` requests literal private IPs, bind interface, ports and explicit coordinator consent. Shared mode uses separate profile data. `Bip39FusionWindow` retains the theme selector, shows network controls and denies sends while observed disconnected; backend connection checks remain authoritative. DNS names and public IP endpoints are not supported in this minimal private/LAN/VPN mode.

## Actual bundled-Core compatibility

Signed Core v0.1.11 binaries remain unchanged:

- wamd SHA256 `7298de701e467eb28b4806cbcbe35edb393861b4b97117017fee4c1b194e3068`.
- wam-cli SHA256 `81a031ebf9b3060b19061b29756d43bcd09b32ad778348b8c3d8321397076e82`.
- WSP source `ac55f13423620252bdbf848c7e8a280c3b84721e`.
- Required and observed genesis `b88f3d262f285e38e184f50bf3eea1c8e615486ae67d3d9eaf0976fbd6d3d30d`.
- Required magic bytes `57414d52` (WAMR): checked against local Core block-record framing after applying Core's local XOR mask; mask is not printed. This is not a passive TCP packet capture. Actual Core handshake proves interoperation.
- Actual `-help` supports manual addnode and standard REGTEST P2P 29555 / RPC 29554; evidence `build/local-evidence-20261104/core-help.txt`.
- First P2P smoke with `maxconnections=1` failed: no inbound slots. `maxconnections=12` permits Core's reserved outbound budget and two inbound slots; only the one manually configured counterpart is admitted by wallet attestation. Failure retained in `shared-smoke-fail1.json` and `shared-smoke.log`; actual zero-height handshake PASS in `shared-smoke.json` / `shared-smoke2.log`.

## Native two-node evidence (development working tree)

`shared_network_probe.py` uses two original Core processes, normal Cocoa GUI windows, fresh native-keychain-backed BIP39 profiles and real operator approval widgets. This run occurred on a dirty development tree and is NOT exact-commit/final-frozen qualification.

Evidence: `build/local-evidence-20261104/shared-native2.log` and `bundle-input/shared-regtest-0c17bcbc94a9ea9c/public-evidence.json`. V1–V16 PASS in that scoped run: both genesis values, handshake before mining, coordinator-only mature funding, block synchronization, BIP352 receiving address, Prepare/Sign/explicit Broadcast, peer mempool relay, block confirmation, both GUI histories, disconnect/reconnect and same-profile/Core restart with unchanged reservations.

Public transaction ID: `82bbb3b636e98be59c49fb9bf16aba6f8f23c2ae215a1062f7acd98f56cec6ed`. Receipt contains exact confirmation tip/height, public peer metadata, and private lab path. Screenshots remain inside that retained lab. V17 reorg was NOT EXECUTED by this successful run; V18 needs exact-new-source isolated/frozen regression; V19 physical two-computer execution is BLOCKED.

## Interruptions and reorg finding

Sanitized crash reconciliation: `build/local-evidence-20261104/resume-crash-reconciliation.json`. macOS reports SIGSEGV (exit 139) in Qt object destruction; sandbox Cocoa initialization also produced SIGABRT. A distinct command-level cause for reported exit -1 is MISSING EVIDENCE. No transaction outcome is inferred from an exit code.

The first shared GUI attempt stopped both original Core processes cleanly (debug logs `Shutdown: done`) before a Qt cleanup crash, and has no signed-payment evidence records. It is retained at `bundle-input/shared-regtest-145796506b0774ac`. Fixes parent the parked legacy widget to the real window, explicitly destroy retired windows while QApplication is alive, and write failure receipts BEFORE GUI cleanup. The second shared native run exited 0.

A subsequent targeted reorg on the second run's retained disposable profiles exposed Q06's deliberate descendant-only checkpoint floor. Live rollback cannot advance the anchored native checkpoint; custody fails closed and retains runtime. The first probe cleanup incorrectly let `session.lock()` mask the initiating failure and skipped Core shutdown. Evidence `shared-reorg-native.log`; two original Popen handles were lost when its Python process exited. Owner exception/manual intervention is requested before any process action. No PID adoption, lock deletion, journal reset, reservation release or checkpoint bypass is performed. The probe has been corrected to attempt original-owner shutdown even when session locking retains an uncertain runtime.

This is a real limitation: automatic wallet recovery onto a competing branch is NOT implemented or qualified. A fail-closed reorg-safety test must say so; it cannot be presented as successful automatic recovery. Existing custody floors are preserved.

Native source references: `bip39_native_checkpoint._require_confirmed_descendant` explicitly denies checkpoint-crossing reorgs; `Q06OwnedSpendSession._save` faults custody and retains runtime after refused publication. The updated probe records V17 **BLOCKED**, even if its narrower fail-closed safety assertions succeed. V1-NET is not engineering-complete.

## Source regression and Qt cleanup

`build/local-evidence-20261104/v1-source-suite1.log`: 601 discovered, two fixture schema errors, 33 skips; interpreter teardown also exited 139. Both old Q05 fixtures now explicitly carry `shared_profile=None` rather than weakening production scope checks.

`v1-source-suite2.log`: 602 discovered, one obsolete source-string assertion after the explicit-profile correction, 33 skips; exit 139 despite holding QApplication and flushing deferred events. The obsolete assertion is replaced with a guard against remembered-path override and an actual routing regression test.

`v1-source-suite3.log`: **602 discovered, 569 PASS / 33 SKIP, zero failures/errors, process exit 0**. The runner explicitly destroys test widget parents while Cocoa/QApplication still lives. `scripts/run_macos_source_tests.py` preserves this repeatable lifetime; its focused invocation also exited 0. `shared-policy-runner2.log`: **8 source-policy/cleanup tests PASS**, including the newly added uncertain-session-lock cleanup regression. These are source/fixture results, never network acceptance.

`Bip39FusionWindow` now parents its parked legacy widget to the actual window. The shared lab deletes retired GUI windows only after the executor and its original Core have exited. The public failure receipt is written before cleanup. Source-suite widget disposal is fixture cleanup, not permission to destroy a live wallet owner.

Follow-up source commit `7ba9d3a` retains a failed-stop original owner using the existing authenticated `CoreSupervisor.serve` on a non-daemon control thread, rather than losing the Popen handle on Python exit. No PID adoption or new Core manager is introduced. Future non-frozen shared probes require clean, literal source verification and record source inventory; the earlier development-tree run is not retroactively upgraded. Commit `cbfafee` tests the real native Qt manual peer dialog (public IP rejected, private endpoint and explicit coordinator consent accepted) and bounds modal test duration. Latest `shared-policy-runner5.log`: **10 PASS, exit 0**. This includes fixtures and native configuration widgets, not a rerun of Core network acceptance.

The explicit-profile correction removes two unsafe redirects in `launch_bip39_trial`: remembered seed folders no longer replace the supervisor root selected by the owner; sibling seed-folder selection no longer mutates that root after executor construction. The existing backend remains the authority for unique original seed/profile verification. Shared and isolated remembered path hints use distinct keys. No original wallet data or QSettings history is migrated or deleted.

## Current local engineering blockers

1. The targeted reorg's two orphaned Core processes were observed as PID 7234 and 7250 (PPID 1). They belong to the retained `shared-regtest-0c17bcbc94a9ea9c` lab. Their original Popen handles are gone. A narrow owner exception/manual stop is pending; no adoption or process action is performed. Standard P2P/RPC ports cannot be reused until reconciled. PIDs must be revalidated before any authorized action, never blindly reused.
2. Exact-commit/final-frozen V1 qualification has **NOT EXECUTED**. The successful V1–V16 native run was a development working tree. New source commits do not retroactively qualify that run.
3. Reorg wallet continuation remains BLOCKED by the deliberate native descendant-only floor. A separate authenticated reconciliation design and regression proof is required; automatic rollback/reanchor, reservation release and signed-transaction retry remain forbidden.
4. V19 physical two-machine evidence is BLOCKED; only a preparation architecture is supplied. Windows/Linux shared-mode qualification is NOT EXECUTED.
5. Owner G6 / independent G7 / formal integration remain unresolved. The versioned acceptance ledger is unchanged (blob `0e93a2b213d7dab6d0f5bc9c26997c68493aed8a`).

No newly qualified V1 DMG exists. The retained Q06 DMG above is the last verified artifact, not a V1 delivery.

## Handoff state and exact next actions

- Q06 local branch: `feature/issue45-q06-bip39-12word-20261031`, documentation HEAD `f9c23f3`, qualified code `e48d6cc`. Its separate 104/104 scoped source run and final frozen Core/GUI/Q05 qualification passed. The first builder stopped at an existing-receipt guard; the same already-tested binary completed Q05 into fresh receipts and was packaged without rerunning passed modules. The resume receipt is in the new qualified distribution.
- V1 local branch: `feature/v1-net-shared-regtest-20261104`; implementation `9baac93`, GUI/profile integration `84249fe`, retained evidence/blocked cases `ba0c823`, original-owner/source-proof fix `7ba9d3a`, native dialog test `cbfafee`. No merge or history rewrite joined these branches; the Q06 root/widget fix was independently applied on Q06, with equivalent changes already on V1.
- Required process action: narrow owner exception or manual graceful shutdown of ONLY the two revalidated disposable Core instances. Read-only `lsof` matched PID 7234 to `wam-fusion-core-ae71f10558d7da35/chain`, and PID 7250 to `wam-fusion-core-d1205025070f3f86/chain`, both under the named failed lab; latest journals record those exact RUNNING PIDs and the executable is canonical `core/wamd`. Revalidate at action time. Do not clear their stale journals or retained runtime.
- Once standard ports are safely free, run the remaining exact-commit two-Core probe, including the repaired cleanup path; record V17 BLOCKED for unavailable wallet reorg recovery. Preserve all prior failures. Source/fixture tests cannot close this step.
- Qualify a final frozen V1 candidate separately and replay the isolated workflow against those exact bytes (V18). Use fresh public receipt paths, since both Q05 harness and release manifest deliberately reject pre-existing receipts. Preserve old output generations. Do not rebuild passed modules solely to repair an output-path collision.
- Design authenticated checkpoint reconciliation for a genuine competing branch without weakening native floors, irreversible reservations or explicit broadcast consent. Until implemented and genuinely tested, Shared mode is not engineering-complete after checkpoint-crossing reorgs.
- Execute V19 on two actual computers, then obtain owner physical G6 and genuinely independent G7 as separate authorities. Neither is self-declared here.

## Two-machine preparation (NOT a physical PASS)

Both computers need this same qualified build, unchanged v0.1.11 Core and the same required genesis. Use separate new Shared REGTEST profiles; retain isolated profiles separately. Use private LAN/VPN literal IPs, not remote RPC credentials.

| Setting | Node A | Node B |
|---|---|---|
| Role | sole mining coordinator | participant; mining disabled |
| Local RPC | 127.0.0.1:29554 | 127.0.0.1:29554 |
| Local P2P | own LAN/VPN interface:29555 | own LAN/VPN interface:29555 |
| Manual peer | B's LAN/VPN IP:29555 | A's LAN/VPN IP:29555 |
| Wallet/Core data | A-only protected profile | B-only protected profile |

Authorize TCP 29555 only between these hosts as needed. RPC remains loopback-only. Configure exactly one coordinator. Verify both peer handshakes/genesis BEFORE mining; use existing fallback fee and 100-block coinbase maturity. No genesis premine spend is attempted. On one Mac, A uses RPC/P2P 29554/29555 and B uses 29556/29557, with reciprocal manual peer ports. Configuration is immutable per profile: reopening requires exact original settings and authenticated native custody.

After local final qualification, physical V19 must independently record both machines/OS, artifact hashes, Core/genesis, peer handshake, common tips, mempool relay, explicit payment TXID, confirmation, both GUI histories and restart/reconnect evidence. No second computer has been exercised here.

## Keep / simplify / remove

KEEP original signed Core/RPC, original-process ownership, BIP39/BIP352, reservation/PSBT/checkpoint machinery and existing macOS packaging. SIMPLIFY shared state to immutable profile + existing executor observations; reuse normal widgets and one shared probe. REMOVE only newly introduced redundant code if demonstrated unnecessary. Historical workspaces, original owner wallet data, journals, old builds, failed labs and evidence remain preserved.
