# Phase 4 — production runtime inventory, packaging policy, memory method (2026-11-07)

Design record only. It grants no runtime, release, merge, mainnet, budget or
acceptance authority. Measurements are in the ignored evidence directory, bound
to the exact HEAD they ran at. Q06 `accepted=false`; G6/G7/V19 BLOCKED;
Q07/Q08/Q09/Q17 OWNER_DE_SCOPED. Nothing was deleted or refactored.

## 1. Inventory (src/wam_regtest, 123 modules)

| Class | Modules |
|---|---|
| Production wallet engine | pinned WSP `wam_sp`; `wallet_session`, `bip39_spend_session`, `wallet_read`, `amounts`, `history_pages`, `disclosure` |
| Core supervisor | `core_supervisor`, `core_process`, `core`, `rpc_scope`, `cli_rpc`, `json_rpc`, `rpc_credentials`, `network_policy`, `official_core_v013`, `release`, `supervisor_*`, `windows_core_*`, `linux_runtime`, `linux_official_core`, `linux_developer_core`, `external_core`, `external_recovery` |
| Native custody | `custody`, `vault`, `encrypted_storage`, `private_directory`, `bip39_seed_vault`, `bip39_native_checkpoint`, `managed_wallet_checkpoint`, `managed_wallet_session`, `wallet_recovery`, `windows_private_storage`, `windows_checkpoint_anchor`, `linux_private_storage`, `linux_anchor_witness` |
| BIP352 scanner / checkpoint | WSP `scanner`/`store`; `bip39_12`, `bip39_scanner_checkpoint`, `bip39_reconciliation`, `bip39_recovery_proof` |
| Transaction / reservation engine | WSP `wallet`/`psbt`; `wallet_session`, `bip39_spend_session`, `bip39_scanner_checkpoint.require_irreversible_preserved` |
| GUI | `bip39_owner_gui`, `bip39_fusion_gui`, `fusion_ui`, `fusion_pages`, `fusion_motion`, `fusion_status`, `bip39_backup_page`, `bip39_locale`, `gui_errors`, `desktop`, `branding`, `managed_gui`, `managed_onboarding`, `operational_gui`, `windows_read_gui`, `external_core_gui`, `shared_regtest_gui`, `wallet_executor` |
| REGTEST-only developer tools | `shared_regtest`, `q04_miner_loop`, `q04_runner`, `wsp_live.public_regtest_mining_address`, `recovery_metadata` (detached), `v1_scope`, `q_gate`, `telemetry` (in-process counters only) |
| Test fixtures / probes (27) | `desktop_probe`, `linux_core_probe`, `linux_headless_probe`, `linux_qt_probe`, `onboarding_probe`, `probe_source`, `q02_probe`, `q03_probe`, `q04_busy_probe`, `q04_fixture`, `q05_checkpoint_scenario`, `q05_gui_scenario`, `q05_security_scenario`, `q06_history_probe`, `q06_owner_probe`, `q06_platform_probe`, `q06_same_chain_restore_probe`, `q06_spend_probe`, `reopen_probe`, `security_probe`, `shared_network_probe`, `ui_layout_probe`, `wallet_probe`, `windows_core_regtest_smoke`, `windows_vault_probe`, plus `q04_miner_loop`/`q04_runner` |
| Build / CI | `build_provenance`, `package_manifest`, `package_entry`, `linux_package_entry`, `windows_package_entry`, `macos_build_layout`, `qt_bundle_prune`, `distribution_notices`, `release_candidate`, `q05_package_provenance`, `q05_packaged`, `windows_release_preflight`, `scripts/`, `.github/workflows/` |

Demonstrably unused or duplicated:

- `bip39_reconcile.py`: no runtime importer; only `tests/test_q06_bip39_reconcile.py`.
  It is nevertheless inside the frozen macOS package (verified in the PYZ table).
- Reservation-map helper in three places (see Phase 3 record); two native
  checkpoint writers (Q05 `vault`, Q06 `bip39_native_checkpoint`).
- Windows/Linux modules ship in the macOS package and vice versa (inert there).

Frozen macOS package facts (verified from the built artifact, not the script):
`scripts/build_macos_bundle.sh` uses `--collect-submodules wam_regtest`, so the
PYZ contains 122 `wam_regtest` modules including all 27 probes/scenarios and
`bip39_reconcile`. `package_entry.main` runs a `--ci-*` qualification mode on
exact argv alone, without a CI/environment gate, so the shipped binary can be
asked to create disposable REGTEST wallets and mine in its working directory.

## 2. Minimal production packaging policy (PROPOSED, needs owner approval)

1. Keep every test, probe and fixture in the repository; do not delete history.
2. Production artifact: package only the wallet engine, supervisor, custody,
   scanner, transaction engine and GUI classes above; exclude probes, scenarios,
   `bip39_reconcile` and other-platform modules via an explicit allowlist
   instead of `--collect-submodules`.
3. Build a separate qualification artifact (current behaviour, clearly labelled
   "qualification build") for frozen self-tests, so production bytes do not
   change whenever a probe changes.
4. If a single artifact must remain, gate every `--ci-*` mode behind an explicit
   build-time qualification flag recorded in the package manifest.
5. Any change here alters frozen bytes and requires full macOS frozen
   requalification plus Windows/Linux native execution before claims.

## 3. Q18 memory method and proposed cache-aware budget (PROPOSED)

The approved budget (Core 512 MiB, Python 1 GiB, combined 1.5 GiB) and its
original FAIL stay unchanged. Method used by `scripts/probe_memory_profile.py`:

- Metrics per PID from `proc_pid_rusage(RUSAGE_INFO_V4)`: resident size,
  current physical footprint, and kernel lifetime-max physical footprint (which
  captures transients between samples). Concurrent sums only from one 50 ms
  sample of all PIDs; per-process lifetime maxima are never summed as concurrent.
- Core alone: idle, then every few blocks across REGTEST RandomX key changes
  (epoch 64, lag 4 → heights 68, 132, 196, 260, 324).
- Scanner: WSP full scan, no-op re-sync and second full rescan in one process
  with `tracemalloc` peak.
- App: real Q06 backend + Cocoa window, activation, quit, same-profile restart.

Proposed budget formula for owner review:

`Core ≤ N_cache × 256 MiB + measured non-RandomX overhead + stated headroom`

where `N_cache` is the number of light-verification caches Core actually keeps
resident (measured, not inferred). Python and combined limits are derived the
same way from measured GUI, scanner and SQLite components. No limit is adopted
and Q18 is not marked PASS by this record.

## 4. Q16 / Q20 design findings (no writer, no anchor change)

- Q16: every Q06 checkpoint fault (corrupt, missing, stale generation, future
  orphan, crash stage file, wrong directory mode, signed reservation) is refused
  with one fixed code `Q06_SPEND_OPEN_DENIED`; files and anchors stay untouched.
  An interrupted write (ENOSPC or crash) therefore leaves the wallet refusing
  activation with no in-app recovery: recovery remains a design gate.
- Q20: the unlocked/preserved runtime SQLite is plaintext (mode 0600 in a 0700
  directory) and contains output public keys and BIP352 tweaks, amounts,
  history and reservations. Encrypting or shredding it is a design decision.
- Q20: the recovery-phrase Paste left the BIP39 phrase in the system
  pasteboard; fixed in this phase by clearing it after a consumed paste.
