# Release candidate inventory — Fusion UI V2.2

Candidate id: `WAM-Fusion-REGTEST-V22`  
Functional source (all platforms): **`3ab3e527cb90930631c4265f12923981452bf21e`**  
Previous UI pin (not this RC): `b844dd371d4ac5dc3d0469eb899d6709e8ac407f`  
WSP: `ac55f13423620252bdbf848c7e8a280c3b84721e`  
Network: REGTEST only. Mainnet denied.  
Recorded UTC: 2026-11-05T03:12:00Z on macOS 27.0.1 arm64.

Human Owner/Developer cells remain blank. Q06 `accepted=false`. G6/G7 unchanged. V19 BLOCKED.

Expired RC1 Actions artifacts at `144d877` are **not** this candidate.

## Packages actually produced

| Platform | Builder | Core identity | Package | SHA256 | Signing | Tests from this SHA | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| macos-arm64 | `scripts/build_macos_bundle.sh` (full) | official signed v0.1.11 Mach-O `wamd` `7298de701e467eb28b4806cbcbe35edb393861b4b97117017fee4c1b194e3068` / `wam-cli` `81a031ebf9b3060b19061b29756d43bcd09b32ad778348b8c3d8321397076e82` | **no `.dmg` / `.app.zip`** — builder stopped after Q06 spend FAIL | n/a | ad-hoc `.app` in `dist/` is not a published package; inner Mach-O `e6793d1bd0984319590f2e6585d389348a546de7389fcfdc9718c59c67cdfa58` | see macOS table below | **incomplete RC** |
| windows-x64 | `scripts/build_windows_bundle.py` | official PE pins in `windows_release_preflight.BINARY_SHA256` | not produced | n/a | unsigned when built | none on this host | **BLOCKED / NOT EXECUTED** |
| linux-x86_64-desktop | `scripts/build_linux_wallet.py --desktop` | developer ELF, GNU_STACK RW, `official_signed_core_release=false` | not produced | n/a | unsigned; Core not publisher-signed | none on this host | **BLOCKED / NOT EXECUTED** |
| linux-x86_64-headless | `scripts/build_linux_wallet.py` | same developer ELF | not produced | n/a | unsigned | none on this host | **BLOCKED / NOT EXECUTED** |

## macOS frozen results (`3ab3e52`, this host)

Evidence JSON: `release-candidates/3ab3e52/macos-arm64/evidence/`. Owner Desktop profile was not opened.

| Case | Result |
| --- | --- |
| Bundle `--check-bundle` | PASS |
| Offscreen real Core BIP352 + Qt (`--ci-real-core-gui`) | PASS |
| Cocoa real Core wallet, Auto/Light/Dark, backup, lock, send/sign/broadcast, recover | PASS (`MACOS_COCOA_PACKAGED_AUTO_LIGHT_DARK_REAL_CORE_WALLET_PASS`) |
| Q04 external miner (frozen) | PASS |
| Q06 BIP39 create/receive/fund/restore/shutdown (`--ci-q06-bip39-readonly`) | PASS |
| Q06 BIP39 spend/broadcast (`--ci-q06-bip39-spend`) | **FAIL** after `SIGNED_ANCHORED_PASS` (`MACOS_Q06_NATIVE_BIP39_SEND_CONFIRM_REOPEN_DENIED`) |
| Frozen Cocoa UI layout / Overview V2.2 (`--ci-ui-layout`, no Core) | PASS |
| `.dmg` / `.app.zip` | **NOT PRODUCED** |
| V19 two physical computers | **BLOCKED / NOT EXECUTED** |

## Toolchain (this Mac only)

Python 3.12.15 · PySide6 6.12.0 · PyInstaller 6.22.3 · pyinstaller-hooks-contrib 2026.9 · locks in `requirements/q01-gui.lock` and `requirements/q01-headless.lock`. Pillow 12.0.0 is required **on Windows** for ICO conversion; missing on this Mac.

## Known limitations

- Full macOS RC archives were not written because Q06 spend failed closed.
- Windows/Linux native execution was not available.
- Linux Fusion Core remains reviewed developer ELF (`PT_GNU_STACK` RW). Do not substitute official `wam-coin-v0.1.11-x86_64-linux-gnu.tar.gz`.
- Frozen V1-NET same-host lab was not reached. V19 remains two-machine.
