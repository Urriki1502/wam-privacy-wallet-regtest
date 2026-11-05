# Platform reuse / gap matrix — RC1 vs Fusion V2.2

Previous UI pin: **`b844dd371d4ac5dc3d0469eb899d6709e8ac407f`**. Functional source after the Q06 frozen deny-token classification is the commit that lands this matrix with `windows_package_entry.py` / `linux_package_entry.py` (see `ENGINEERING_HANDOFF.md`).
Historical qualified RC1 source: **`144d87700b87a241467172adfad3692b41e1d273`**
This document is engineering inventory. It is **not** V2.2 native PASS, a human
sign-off, or a waiver of Q06 / G6 / G7 / V19.

## Verified identities (2026-11-05)

| Item | Result |
| --- | --- |
| GitHub Windows run [38747163508](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38747163508) | `conclusion=success`, `head_sha=144d877…`, completed 2026-10-15 |
| GitHub Linux run [38747174307](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38747174307) | `conclusion=success`, same SHA |
| GitHub macOS run [38747153198](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38747153198) | `conclusion=success`, same SHA |
| Actions artifacts on those three runs | **`total_count=0`**. Documented expiry was 2026-10-29 UTC. **Not downloadable.** |
| Local `git merge-base` of RC1 SHA and `b844dd3` | **none** in this clone. RC1 is a fetched commit, not an ancestor of the V2.2 pin. Reuse is **module/file**, not linear ancestry. |
| RC1 inner payload hashes | still recorded in `docs/evidence/rc1/` and `docs/RELEASE_CANDIDATE_QUALIFICATION.md` |

Do not treat those 2026-10-15 PASS jobs as V2.2 GUI / Q06 / V1-NET qualification.

## Existing ports (reuse; do not duplicate)

| Surface | Path | RC1 | V2.2 pin | Action |
| --- | --- | --- | --- | --- |
| Windows frozen builder | `scripts/build_windows_bundle.py` | present | same file; provenance + Q05/Q06 frozen qualify added | **REUSE** |
| Linux frozen builder | `scripts/build_linux_wallet.py` | present | same; `--desktop` vs headless; Q05/Q06 qualify | **REUSE** |
| Linux developer Core | `scripts/build_linux_developer_core.sh` + `linux_developer_core.py` | present | GNU_STACK RW (`PT_GNU_STACK` flags `6`) still mandatory | **REUSE** |
| macOS frozen builder | `scripts/build_macos_bundle.sh` | present | scoped `--ui-layout-focused` / `--v1-net-focused`; Q04–Q06 + V1-NET probe | **REUSE** |
| Windows entry | `windows_package_entry.py` | real Core + Qt | + Q04/Q05/Q06 + `managed_onboarding.launch` | **REUSE / adapted** |
| Linux entry | `linux_package_entry.py` | developer Core + witness | + Q04/Q05/Q06 + `managed_onboarding.launch` | **REUSE / adapted** |
| macOS entry | `package_entry.py` | splash + `smoke_real_core` | welcome + Q04–Q06 + `--ci-v1-net-shared-regtest` | **REUSE / adapted** |
| GUI | `fusion_ui.py`, later `bip39_fusion_gui.py`, `fusion_motion.py`, `fusion_status.py` | Fusion pages at RC1 | V2.2 Overview/motion in the **same** package, collected by `--collect-submodules wam_regtest` | **ADAPT shared GUI**, not a new OS backend |
| Q05 adapters | `q05_platforms.py` | n/a at RC1 | Darwin / Windows / Linux adapters | **REUSE** |
| Q06 Win/Linux frozen | `q06_platform_probe.py` | n/a | existing Win/Linux probe | **REUSE** |
| V1-NET same-host lab | `shared_network_probe.py` | n/a | **Cocoa-only**; V19 forced `BLOCKED` | Do **not** copy onto Win/Linux |
| Interactive shared P2P | `managed_onboarding` checkbox → `shared_regtest_gui` | n/a | **all desktop ports** | **REUSE** |

No new `build_windows_*` / `build_linux_*` / `*_package_entry.py` files were added.

## Exact four-platform matrix

| Concern | macOS ARM64 | Windows x64 | Linux x86_64 Desktop | Linux x86_64 Headless |
| --- | --- | --- | --- | --- |
| Builder | `build_macos_bundle.sh` | `build_windows_bundle.py` (Win32 only) | `build_linux_wallet.py --desktop` | `build_linux_wallet.py` (no Qt) |
| Frozen entry | `package_entry.py` | `windows_package_entry.py` | `linux_package_entry.py` | same entry; Qt excluded at freeze |
| Core trust | official signed Mach-O v0.1.11 `7298de70…` / `81a031eb…` | official signed PE `31717319…` / `538a6d1b…` (`windows_release_preflight.BINARY_SHA256`) | reviewed developer ELF `ccc9f0f1…` / `ada9dabd…`, manifest `e77a5745…` | same developer ELF |
| Official Linux gnu tarball `bd010ed6…` | n/a | n/a | **not** builder input | **not** builder input |
| GNU_STACK | n/a | n/a | must be RW; RWE (`flags=7`) denied | same |
| `official_signed` | True | True | **False** | **False** |
| V2.2 GUI | `Bip39FusionWindow` via `managed_onboarding` | same | same (xcb) | no GUI |
| Q06 frozen flag | `--ci-q06-bip39-readonly` / `--ci-q06-bip39-spend` | `--ci-q06-owned-spend` | `--ci-q06-owned-spend` | `--ci-q06-owned-spend --headless` |
| Same-host V1-NET frozen | `--ci-v1-net-shared-regtest` (cocoa) | **not ported** (interactive shared checkbox only) | **not ported** | n/a |
| RC1 native CI | PASS 38747153198 at 144d877 | PASS 38747163508 at 144d877 | PASS 38747174307 at 144d877 | PASS same Linux run |
| V2.2 native/frozen | source Qt on this Mac only; fresh DMG **NOT EXECUTED** | **BLOCKED / NOT EXECUTED** | **BLOCKED / NOT EXECUTED** | **BLOCKED / NOT EXECUTED** |

## What can be reused without rewriting

1. Entire Windows PE intake, ACL staging, Schannel TLS check, and PyInstaller onedir recipe.
2. Entire Linux ELF verify / root-witness / headless-vs-desktop split.
3. macOS codesign-restore-Core-bytes recipe.
4. WSP pin `ac55f13423620252bdbf848c7e8a280c3b84721e`.
5. Q04/Q05/Q06 frozen dispatch already present on the three entries.
6. Fusion V2.2 widgets: one Python package, frozen automatically.

## Necessary compatibility (this session)

- Classify frozen Q06 failures as `Q06_*` on **existing** Windows/Linux entries (previously collapsed to unclassified).
- Record artifact expiry and the missing git merge-base so RC1 is not misread as current qualification.

## Must not be claimed from this Mac

Windows native PASS, Linux native PASS, official Linux ELF substitution, V19, G6, G7, Q06 `accepted=true`.
