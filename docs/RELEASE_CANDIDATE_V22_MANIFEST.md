# Release candidate inventory — Fusion UI V2.2

Candidate id: `WAM-Fusion-REGTEST-V22-RC-PREP`  
Source (all platforms): `b844dd371d4ac5dc3d0469eb899d6709e8ac407f`  
WSP: `ac55f13423620252bdbf848c7e8a280c3b84721e`  
Network: REGTEST only. Mainnet denied.  
Prepared UTC: 2026-11-05T02:15:00Z on macOS 27.0.1 arm64.

This file is a **preparation manifest**. `native_final_executable_e2e_pass` is false
for every row that was not executed on that OS from this SHA.

| Platform | Builder | Core provenance | Artifact | SHA256 | Signature | Tests from this SHA | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| macos-arm64 | `scripts/build_macos_bundle.sh` | official signed v0.1.11 Mach-O `wamd` `7298de701e467eb28b4806cbcbe35edb393861b4b97117017fee4c1b194e3068` / `wam-cli` `81a031ebf9b3060b19061b29756d43bcd09b32ad778348b8c3d8321397076e82` | fresh `.app`/`.dmg` | not produced | ad-hoc app, **not notarized**; do not call it signed release | source Qt: `test_fusion_v21_layout`, `test_fusion_design`, `test_q06_bip39_fusion_gui`, `test_ui_text_layout` (34 OK) | Frozen RC **NOT EXECUTED** |
| windows-x64 | `scripts/build_windows_bundle.py` | official signed v0.1.11 PE (see `windows_release_preflight.BINARY_SHA256`) | onedir + `.exe` | not produced | **unsigned** PyInstaller tree | none on this host | **BLOCKED** (no Win64 runner) |
| linux-x86_64-desktop | `scripts/build_linux_wallet.py --desktop` | reviewed developer ELF, not official signed | `wam-regtest-desktop-*.tar.gz` | not produced | **unsigned**; Core not publisher-signed | none on this host | **BLOCKED** (no Linux x86_64 runner) |
| linux-x86_64-headless | `scripts/build_linux_wallet.py` | same developer ELF | `wam-regtest-headless-*.tar.gz` | not produced | **unsigned**; Core not publisher-signed | none on this host | **BLOCKED** |

Local toolchain (Mac prep host only, not a Windows/Linux claim):

- Python 3.12.15
- PySide6 6.12.0
- PyInstaller 6.22.3

Existing `package-output/` files belong to **earlier** checkouts. Do not reuse their SHA256 as V2.2 proof.

Dependencies expected in a full native build (from `release_candidate.write_candidate_manifest`): PyInstaller, pyinstaller-hooks-contrib, setuptools, packaging, altgraph, PySide6 (+ Essentials/Addons/shiboken6/qrcode on GUI), Pillow, coincurve, cryptography, cffi, pycryptodome.
