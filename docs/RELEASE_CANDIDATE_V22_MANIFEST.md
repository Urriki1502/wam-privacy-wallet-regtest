# Release candidate inventory — Fusion UI V2.2

Candidate id: `WAM-Fusion-REGTEST-V22`  
Functional source (all platforms): **`17adf5c5cbb1213ea5abd95a2ecdd9464b0874a2`**  
Previous UI pin (not this RC): `b844dd371d4ac5dc3d0469eb899d6709e8ac407f`  
WSP: `ac55f13423620252bdbf848c7e8a280c3b84721e`  
Network: REGTEST only. Mainnet denied.  
Recorded UTC: 2026-11-05T04:22:00Z on macOS 27.0.1 arm64.

Human Owner/Developer cells remain blank. Q06 `accepted=false`. G6/G7 unchanged. V19 BLOCKED.

Expired RC1 Actions artifacts at `144d877` are **not** this candidate.

## Packages actually produced

| Platform | Builder | Core identity | Package | SHA256 | Signing | Tests from this SHA | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| macos-arm64 | `scripts/build_macos_bundle.sh` (full) | official signed v0.1.11 Mach-O wamd `7298de701e467eb28b4806cbcbe35edb393861b4b97117017fee4c1b194e3068` / wam-cli `81a031ebf9b3060b19061b29756d43bcd09b32ad778348b8c3d8321397076e82` | `package-output/WAM-Privacy-Wallet-REGTEST-macOS-ARM64.app.zip` / `.dmg` | zip `47a3489c3f2ad7f5523429a36294ddfb3aede50c189d05b6b02499cd1237e589` · dmg `dea3b4be67e9f62057a172ef0e53d9544ccdbb547ab39ae1975f6422d4292a6d` | ad-hoc, not notarized | Q04/Q05/Q06 readonly+spend, V1-NET V1–V18 local | **local frozen PASS**; not full release |
| windows-x64 | `scripts/build_windows_bundle.py` | official PE pins in `windows_release_preflight.BINARY_SHA256` | not produced | n/a | unsigned when built | none on this host | **BLOCKED / NOT EXECUTED** |
| linux-x86_64-desktop | `scripts/build_linux_wallet.py --desktop` | developer ELF, GNU_STACK RW, `official_signed_core_release=false` | not produced | n/a | unsigned; Core not publisher-signed | none on this host | **BLOCKED / NOT EXECUTED** |
| linux-x86_64-headless | `scripts/build_linux_wallet.py` | same developer ELF | not produced | n/a | unsigned | none on this host | **BLOCKED / NOT EXECUTED** |

## macOS frozen results (`17adf5c`, this host)

Evidence: `package-output/` and `~/Documents/WAM-RC-sidecars/freeze-17adf5c/build.log`. Owner Desktop profile was not opened.

| Case | Result |
| --- | --- |
| Bundle `--check-bundle` | PASS |
| Offscreen real Core BIP352 + Qt | PASS |
| Cocoa real Core wallet, Auto/Light/Dark, backup, lock, send/sign/broadcast, recover | PASS |
| Q04 external miner (frozen) | PASS |
| Q06 BIP39 readonly | PASS |
| Q06 BIP39 spend | PASS `Q06_NATIVE_BIP39_SEND_CONFIRM_REOPEN_PASS` |
| Frozen V1-NET same-host | PASS V1–V18 / V19 BLOCKED |
| `.dmg` / `.app.zip` | produced, unnotarized ad-hoc |

## Toolchain (this Mac only)

Python 3.12.15 · PySide6 6.12.0 · PyInstaller 6.22.3 · locks in `requirements/q01-gui.lock` and `requirements/q01-headless.lock`. Pillow 12.0.0 is required **on Windows** for ICO conversion.

## Known limitations

- Windows 11 x64 and Ubuntu 24.04 x86_64 hosts were not available. Builders refused on Darwin ARM64.
- Linux Fusion Core remains reviewed developer ELF (`PT_GNU_STACK` RW). Do not substitute official `wam-coin-v0.1.11-x86_64-linux-gnu.tar.gz`.
- V19 remains two physical computers.
- macOS package is not Apple Developer ID signed or notarized.
