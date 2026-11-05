# Cross-platform compatibility gap register

Pinned source for this candidate: **`b844dd371d4ac5dc3d0469eb899d6709e8ac407f`**
(`feature/v1-net-shared-regtest-20261104`, Fusion UI V2.2).

This register is an engineering inventory. It is **not** a PASS, signature, or
waiver. Do not run a macOS bundle on Windows or Linux.

| ID | Area | Finding | Severity | Status |
| --- | --- | --- | --- | --- |
| G-01 | Frozen launch | `package_entry.py` requires Darwin ARM64 frozen `_MEIPASS`. `windows_package_entry.py` requires Win32 AMD64 frozen. `linux_package_entry.py` requires Linux x86_64 frozen. Cross-OS launch fails closed. | Expected | By design |
| G-02 | Core identity | macOS uses official signed v0.1.11 Mach-O (`wamd` `7298de70…`, `wam-cli` `81a031eb…`). Windows uses official signed PE (`wamd.exe` `31717319…`, `wam-cli.exe` `538a6d1b…`). Linux uses **reviewed developer ELF**, not official signed Core (`wamd` `ccc9f0f1…`, `wam-cli` `ada9dabd…`, manifest `e77a5745…`). | High (trust) | Documented; do not equate Linux with signed Mac/Win |
| G-03 | Custody FS | macOS: Keychain + `flock` + 0700 private dirs. Windows: DPAPI/CNG + `LockFileEx`. Linux: independent root witness socket + POSIX private dirs. | High | Platform modules already exist; must be proven on native OS |
| G-04 | WSP pin | All platforms pin WSP `ac55f13423620252bdbf848c7e8a280c3b84721e`. Windows scanner locking is not POSIX `fcntl`. | High | Native Win64 WSP must be re-proven; Mac PASS is not Win PASS |
| G-05 | Qt plugins | macOS Cocoa, Windows `QT_QPA_PLATFORM=windows`, Linux desktop xcb/EGL/fonts. Headless Linux **must not** ship PySide6. | Medium | Native GUI required per OS |
| G-06 | Datadir | Per-profile private directories; never `~/Library` owner Desktop chain. Shared REGTEST RPC `127.0.0.1:29554`, P2P `29555`. | High | Keep; do not weaken RPC bind |
| G-07 | Process lifecycle | Windows `CREATE_NO_WINDOW` + cwd next to PE. POSIX no-follow + chmod 0700 on Core members. PyInstaller on macOS re-signs Mach-O and **must restore** original Core bytes. | High | Existing builders restore hashes |
| G-08 | Packaging outputs | `package-output/` (macOS), `windows-package-output/`, `linux-package-output/` overwrite in-place. Prior artifacts in `package-output/` are **not** this SHA. | High | Use a dated output dir; never overwrite qualified DMGs |
| G-09 | Signing | macOS app is ad-hoc, not notarized. Windows/Linux frozen trees are **unsigned**. Linux Core is developer-built. | High | Never present unsigned as signed |
| G-10 | Linux portability | Ubuntu 24.04 x86_64 only. `relocatable_across_linux_distributions_qualified=false`. | High | Do not ship as generic AppImage/deb |
| G-11 | UI V2.2 | Overview/theme/motion proven in source Qt on this Mac only. Frozen Win/Linux GUI of V2.2 is untested. | Medium | Native GUI evidence required |
| G-12 | Second host | V19 needs two physical computers. | Blocker | V19 BLOCKED / NOT EXECUTED |
| G-13 | Human gates | G6 physical solo-miner observation and G7 independent architecture/security sign-off remain human. | Blocker | Unchanged; agents must not self-approve |
| G-14 | Official Linux vs Fusion Linux | GPG-valid official gnu tarball `bd010ed6…` is **not** `build_linux_wallet.py` input (developer ELF `ccc9f0f1…`). Official ELF members UNVERIFIED this session. | High | Never label Linux Fusion Core as official signed v0.1.11 |
| G-15 | `[regtest]` config | Official v0.1.11 ignores `rpcbind`/`port`/`connect` outside `[regtest]`. | High | Fusion `write_config` must keep the section |
| G-16 | GitHub Releases | `github.com/wamcoin-core-dev/wam-coin` tag `v0.1.11` 404 from this environment | Medium | Use wamcoin.org + GPG, not GitHub badge |
| G-17 | Pillow | Missing on this Mac; Windows ICO conversion needs Pillow on the Windows host | Medium | Windows builder dependency |
| G-18 | RC1 artifacts | GitHub runs 38747153198 / 38747163508 / 38747174307 remain `success` at `144d877`, but Actions artifacts `total_count=0` (expired ~2026-10-29). | High | Historical PASS only; cannot re-download packages |
| G-19 | Git ancestry | This clone has **no merge-base** between RC1 `144d877` and pin `b844dd3`. Reuse is the surviving `scripts/build_*` and `*_package_entry.py` files. | High | Do not claim V2.2 contains RC1 as ancestor |
| G-20 | V1-NET frozen | `--ci-v1-net-shared-regtest` is Cocoa/`package_entry.py` only. Win/Linux reuse interactive shared-mode, not that probe. | Medium | Do not copy the Cocoa lab onto PE/ELF |
| G-21 | GNU_STACK | Developer ELF must be `PT_GNU_STACK` RW (`flags=6`). Official published Linux RWE remains rejected and is not the Fusion builder input. | High | Never relabel developer Core as official signed |

## Hardcoded / OS-specific (intentional)

- Official Core asset names: `wam-coin-v0.1.11-arm64-apple-darwin.tar.gz`, `wam-coin-v0.1.11-x86_64-w64-mingw32.zip`.
- Isolated REGTEST `listen=0`; Shared mode uses explicit `-addnode` only.
- Branding: `assets/wam-coin-logo.png`, `assets/wam-wallet.icns`; Windows ICO is derived from the owner PNG at build time.

## What this Mac can and cannot do

Can: source Qt tests, inspect recipes, pin SHA, write checklists.

Cannot: produce a Windows PE tree, produce Linux ELF Core, execute those packages, or complete V19.
