# Phase 5 — cross-platform production packaging and CI readiness (2026-11-08)

Design and readiness record only. It grants no runtime, release, merge, mainnet,
budget or acceptance authority. Q06 `accepted=false`; G6/G7/V19 BLOCKED;
Q07/Q08/Q09/Q17 OWNER_DE_SCOPED. Windows/Linux production bytes are NOT
EXECUTED until native frozen runs on those hosts.

## 1. Policy (scripts/production_packaging.py)

| Platform | Entry | Set | Added to the reviewed macOS runtime |
|---|---|---|---|
| macos | production_entry | RUNTIME (75) | — |
| windows | windows_production_entry | 77 | windows_core_stage, windows_core_regtest_smoke (win32 `_config`/`_host_env`/`_rpc` used by core_supervisor, core_process, rpc_scope, windows_core_transport) |
| linux-desktop | linux_production_entry | 76 | linux_headless (existing headless frontend) |
| linux-headless | linux_production_entry | 65 | as linux-desktop minus the 11 modules importing PySide6 at module level |

Never shipped on any platform: cli, `__main__`, package_entry, windows/linux
package entries, probes, scenarios, fixtures, q04 runner/loop/fixture,
q05_packaged, bip39_reconcile, windows_read_gui, windows_wallet_read,
windows_wsp_regtest. Static tests pin module-level closure and the exact
reviewed set of lazy (function-level) edges to excluded modules per platform;
each lazy edge is a developer/acceptance branch or another platform's
`sys.platform` branch and fails closed if reached.

Known follow-up (not done, needs qualified refactor): `windows_core_regtest_smoke`
mixes runtime helpers with a smoke function; split the helpers into a
runtime-named module in a change that is native-qualified on Windows.

## 2. Entries

- Windows: empty argv → stage pinned Core into a new private DACL directory
  (`windows_core_stage._stage_original_core`, AST-identical move) → existing
  managed onboarding. `--check-bundle` stages and verifies only.
- Linux: empty argv → existing desktop flow (manifest SHA-256 + provisioned
  root witness dialogs); `--check-bundle`; or
  `wallet --manifest-sha256 HEX --anchor-socket ABS --confirm-experimental-developer-regtest [--recover-backup ABS]`
  → existing `linux_headless.run` with bundled Core/WSP, no probe, no report.
- Every other argv (DEVELOPER_ARGV, incl. `--ci-*`, q04, `--core-dir`,
  acceptance flags, abbreviations, relative paths) returns 64 before resources.
  Environment variables are never read by the entries.

## 3. Builders and CI

- `python -I scripts/build_windows_bundle.py --production` →
  `windows-production-output/` (`PRODUCTION_BUILD_RECEIPT.json`,
  `PRODUCTION_MODULE_INVENTORY.json`, `PRODUCTION_DISPATCH_NEGATIVES.json`,
  `WAM-Privacy-Wallet-REGTEST-windows-x64-production-<sha>.zip`, LF sums).
- `python -I scripts/build_linux_wallet.py --core-dir … --production [--desktop]` →
  `linux-production-output/` (same receipts, `…-production-<sha>.tar.gz`).
- Default (no flag) builders are the unchanged qualification builds and keep
  their frozen E2E; their outputs never qualify production bytes.
- Workflows: production step runs after the qualification build in the same
  job (`windows-x64-credential-anchor.yml`, `linux-experimental-regtest.yml`)
  and uploads a separate artifact. macOS: `verify_macos_ci_outputs.py` binds
  production and qualification-only receipts to one commit.

## 4. Exact-HEAD CI requirements (owner-authorized dispatch only)

1. Push only after the full local macOS frozen qualification of that HEAD.
2. Windows x64 (windows-2022): qualification build PASS, then production build
   PASS (audit 76 PYZ modules + entry, DEVELOPER_ARGV all 64, `--check-bundle` 0).
3. Linux x86_64 (ubuntu-24.04, official v0.1.13 Linux Core, approved manifest
   `4052c4a7…`): headless and desktop qualification PASS, then production PASS.
4. macOS ARM64 (macos-15): split build + `verify_macos_ci_outputs.py` PASS.
5. Still missing after (2)–(4): normal-entry production E2E on each OS
   (Windows interactive Qt; Linux headless scripted session through the
   production binary; Linux desktop with provisioned witness), Authenticode /
   Developer ID, clean-device, V19 two machines, G6/G7.
