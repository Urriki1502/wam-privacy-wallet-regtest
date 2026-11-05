# Complete feature parity matrix — Fusion V2.2

Mac frozen package pin: `17adf5c5cbb1213ea5abd95a2ecdd9464b0874a2`  
Review / Win-Linux probe SHA: `65a804ae1621546dae7948450912da526f346bdb`  
WSP: `ac55f13423620252bdbf848c7e8a280c3b84721e`  
Recorded: 2026-11-05T04:40:00Z on macOS 27.0.1 arm64.

Vocabulary: `IMPLEMENTED_AND_TESTED` | `IMPLEMENTED_NOT_NATIVE_TESTED` | `PARTIAL` | `MISSING` | `NOT_APPLICABLE` | `BLOCKED`.

This is **not** native Windows/Linux PASS, Q06 acceptance, G6/G7, V19, or a human verdict.

Shared desktop path (all three GUI ports):

`managed_onboarding.launch` → BIP39 create/open/restore → `launch_bip39_trial` → `Bip39FusionWindow`  
(`src/wam_regtest/managed_onboarding.py`, `bip39_owner_gui.py`, `bip39_fusion_gui.py`).

Legacy Q05 remains a separate welcome route (`managed_gui.ManagedWalletWindow`). It is not the V2.2 BIP39 desktop.

Linux headless excludes Qt (`build_linux_wallet.py` `--exclude-module PySide6`). GUI rows are `NOT_APPLICABLE`.

## Feature matrix

| # | Feature | macOS ARM64 Desktop | Windows 11 x64 Desktop | Ubuntu 24.04 x86_64 Desktop | Linux Headless | Code | Tests |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Onboarding / welcome | IMPLEMENTED_AND_TESTED (frozen welcome + cocoa) | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | NOT_APPLICABLE | `managed_onboarding.welcome_dialog` | `tests/test_q06_bip39_welcome.py`; Win/Linux `q06_platform_probe.assert_unified_welcome_qt` |
| 2 | BIP39 12-word create | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED (no GUI) | `Bip39ReadOnlyBackend` + Fusion start | macOS `--ci-q06-bip39-*`; Win/Linux `--ci-q06-owned-spend` |
| 3 | Seed backup ack | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | NOT_APPLICABLE | `Bip39BackupPage` in Fusion | `ui_layout_probe`, Q06 readonly |
| 4 | Wallet restore | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | welcome `restore` + `open(..., restore)` | Q06 same-chain / fresh restore |
| 5 | Recovery verification | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | `recovery_verify` | Q06 rescan stages |
| 6 | Lock / Unlock | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | Fusion custody switch + backend lock | cocoa wallet; platform LOCK_REOPEN |
| 7 | Confirmed balance | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | `FusionOverview.balance_value` | Q06 snapshots |
| 8 | Balance history chart | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | NOT_APPLICABLE | `BalanceHistoryChart` | `test_fusion_v2_widgets`, `desktop_probe` |
| 9 | Overview V2.2 layout | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | NOT_APPLICABLE | `fusion_ui.FusionOverview` | `test_fusion_v21_layout`, `test_cross_platform_fusion_parity` |
| 10 | Recent transactions | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | NOT_APPLICABLE | Overview + History page | Fusion binding in probes |
| 11 | BIP352 Receive | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | `ReceivePage` / scanner | Q06 fund + receive |
| 12 | QR + copy | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | NOT_APPLICABLE (qrcode excluded) | `PaymentQR`, copy buttons | Fusion receive page tests |
| 13 | Prepare | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | `_prepare_send` / `prepare` | Q06 spend + platform PREPARE |
| 14 | Review | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | NOT_APPLICABLE | `review_summary` + `PaymentApproval` | spend probe; platform PaymentApproval inspect |
| 15 | Explicit Sign | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | NOT_APPLICABLE (executor sign only) | `PaymentApproval` sign, default Cancel, ApplicationModal | `test_fusion_v2_widgets`, `test_cross_platform_fusion_parity` |
| 16 | Explicit Broadcast | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | NOT_APPLICABLE | `PaymentApproval` broadcast | macOS spend GUI click |
| 17 | Transaction Result | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | NOT_APPLICABLE | `describe_broadcast_result` | `test_fusion_design` |
| 18 | Confirm + History | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | confirm + History page | Q06 confirm |
| 19 | Fee / change copy | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | NOT_APPLICABLE | PaymentApproval card | widget tests |
| 20 | Core identity | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | `verified_core_paths` + adapters | platform TRUST |
| 21 | Core lifecycle | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | `CoreSupervisor` + quit/join | CLEAN_SHUTDOWN |
| 22 | Network status | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | NOT_APPLICABLE | `NetworkPage` | Fusion window |
| 23 | Shared REGTEST config | IMPLEMENTED_AND_TESTED (same-host V1-NET) | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | NOT_APPLICABLE | welcome checkbox + `shared_regtest_gui` | `test_shared_regtest`; Cocoa lab not ported |
| 24 | Auto / Light / Dark | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | NOT_APPLICABLE | `ThemeSlider` + `colorSchemeChanged` | cocoa auto appearance |
| 25 | Reduced Motion | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | NOT_APPLICABLE | `fusion_motion` | `ui_layout_probe` |
| 26 | Qt page transitions | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | NOT_APPLICABLE | `TransitionHost` | layout / fusion motion tests |
| 27 | Status check/spinner/warn/error | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | NOT_APPLICABLE | `fusion_status.classify` | `test_fusion_design` |
| 28 | Responsive sizing | IMPLEMENTED_AND_TESTED (900/1260 frozen; 1024/1280/1440 source) | IMPLEMENTED_NOT_NATIVE_TESTED; 125%/150% DPI **BLOCKED** | IMPLEMENTED_NOT_NATIVE_TESTED; xcb **BLOCKED** | NOT_APPLICABLE | `ResponsiveRow`, window resize | `test_cross_platform_fusion_parity` |
| 29 | Encrypted custody | IMPLEMENTED_AND_TESTED (Keychain) | IMPLEMENTED_NOT_NATIVE_TESTED (Credential Manager / NTFS) | IMPLEMENTED_NOT_NATIVE_TESTED (witness + protected storage) | IMPLEMENTED_NOT_NATIVE_TESTED | `q05_platforms` adapters | Q05 frozen scripts (native host) |
| 30 | Error / denial codes | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | `gui_errors`, Q06_* on entries | `test_platform_reuse_contracts` |
| 31 | Safe shutdown / reopen | IMPLEMENTED_AND_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | IMPLEMENTED_NOT_NATIVE_TESTED | executor quit/join; Fusion `_poll` stop | Q06 CLEAN_SHUTDOWN |

## Exact Windows gaps

No user-facing Fusion page is **MISSING** in source. Remaining gaps are **native evidence**:

- Frozen PE + `--ci-q06-owned-spend` on Windows 11 x64 **BLOCKED / NOT EXECUTED**
- GUI Sign/Broadcast click path not exercised by the Win frozen probe (executor sign; dialog inspected only)
- 125% / 150% DPI **BLOCKED**
- Interactive Shared REGTEST + owned shutdown on Windows **BLOCKED**
- Cocoa `--ci-v1-net-shared-regtest` **NOT_APPLICABLE** (must not be copied)

## Exact Linux gaps

No applicable desktop Fusion page is **MISSING** in source.

- Desktop/headless tarballs **BLOCKED / NOT EXECUTED**
- Extra Linux launch prompts (manifest SHA + root witness) are **required security**, not a missing wallet page
- Headless: all Qt/QR/theme/motion rows **NOT_APPLICABLE**
- Official Linux Core tarball must not replace developer ELF
- `PT_GNU_STACK` RW still mandatory
- xcb + desktop appearance **BLOCKED**
- Cocoa V1-NET lab **NOT_APPLICABLE**

## Implemented parity corrections (this audit)

- `q06_platform_probe` now refuses a desktop Fusion window without the V2.2 chart / Send-Receive / Quick Actions removal, and inspects `PaymentApproval` (ApplicationModal, default Cancel) after prepare. No change to BIP39/BIP352/PSBT engines.
- `tests/test_cross_platform_fusion_parity.py` locks shared welcome → Fusion wiring and identity constants.

No second Windows/Linux backend.

## Mac frozen impact

macOS default GUI and `--ci-q06-bip39-spend` were not rewritten. Qualified `17adf5c` `.app.zip` / `.dmg` remain valid for that SHA. A later docs/test/probe SHA does **not** relabel those bytes.

## Native test plan (after Owner authorizes push)

Checkout **the exact review SHA** (not a mixed tree).

Windows 11 x64: `python -I scripts/build_windows_bundle.py` then existing `windows-x64-qualification.yml` / `windows-x64-credential-anchor.yml` jobs **for that SHA**. DPI 125/150 on the same PE. Do not run PE on macOS.

Ubuntu 24.04 x86_64: reviewed developer Core + `scripts/build_linux_wallet.py` and `--desktop`. Existing `linux-experimental-regtest.yml`. GNU_STACK RW. `official_signed_core_release=false`.

Do not trigger those workflows from this session.

V19 stays two physical computers.
