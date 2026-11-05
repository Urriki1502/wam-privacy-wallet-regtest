# Developer native Windows / Linux build handoff

Build **this functional source** on every OS. Do not substitute a later docs commit.

```
17adf5c5cbb1213ea5abd95a2ecdd9464b0874a2
```

WSP pin: `ac55f13423620252bdbf848c7e8a280c3b84721e`

This SHA includes the shared V1-NET Sign dialog / Qt teardown repair
(`PaymentApproval` ApplicationModal; two-window approval click; no
`QApplication.shutdown()` abort when original owners are retained).
Test those surfaces on Windows and Linux. Do not add a second backend.

Do not mix this SHA with `3ab3e52`, `0771759`, `00303de`, or expired RC1
Actions ZIPs. Do not overwrite historical `package-output/` or
`release-candidates/3ab3e52/`. Write new trees:

```
release-candidates/17adf5c/windows-x64/
release-candidates/17adf5c/linux-x86_64-desktop/
release-candidates/17adf5c/linux-x86_64-headless/
```

Reuse the **existing** builders and entries. Exact reuse matrix:
`docs/PLATFORM_REUSE_GAP_MATRIX.md`.

No GitHub push, merge, new CI workflow, or mainnet unless the owner
authorizes that separately.

Human Owner / Developer / Independent cells in
`JOINT_ACCEPTANCE_CHECKLIST.md` stay blank until those humans write them.

## Windows 11 x64 (required host)

1. Clean checkout of `17adf5c5cbb1213ea5abd95a2ecdd9464b0874a2` on native
   AMD64 Windows 11 (not WSL, not this macOS workspace).
2. Python 3.12 x64. Install GUI freeze deps from `requirements/q01-gui.lock`
   (PySide6 6.12.0, PyInstaller 6.22.3, Pillow 12.0.0). No ambient
   `PYTHONPATH` / Git / Chocolatey OpenSSL on PATH.
3. Official signed Core v0.1.11 ZIP (preflight pins; GPG `VALIDSIG`
   fingerprint `4BD4A8D3AFD43F5CBCB500E23798462FE00ADBA4`):
   - archive `wam-coin-v0.1.11-x86_64-w64-mingw32.zip`
     SHA256 `ece622fa7ec3072c4e8b0d32e2c3749397d66260f2b0cf22b3636346873d15c5`
   - `wamd.exe` `31717319535c5b784b2bed3b4d3c9a727f5c062e9534b4d27c59d2ffd04e95a1`
   - `wam-cli.exe` `538a6d1b918b698ce76a949dda982fdda6776e33ba057efaac59b1af59e59d21`
4. `python -I scripts/build_windows_bundle.py`  
   Entry: `src/wam_regtest/windows_package_entry.py`  
   The builder refuses non-Win32. It already runs Q05 frozen, Q06 frozen
   (`--ci-q06-owned-spend`), and `--ci-real-core-wallet`.
5. Move `windows-package-output/` to
   `release-candidates/17adf5c/windows-x64/` before any later build.
6. Launch the frozen `.exe` on that same machine with a **new disposable**
   REGTEST profile. Never open `wam-fusion-core-e905e0d22db25873`.
7. Exercise and keep receipts for: Q06 create/restore, Q06 spend, BIP352
   receive, Send / Sign / Broadcast, Core confirm, History / Balance,
   V2.2 Overview, ApplicationModal `PaymentApproval` (default Cancel),
   Qt worker lifetime, Lock / Unlock, Q04 / Q05, clean owned shutdown.
8. Record **unsigned** (no Authenticode) unless a real certificate is used.
   Ad-hoc macOS signing is not Windows signing.

Until that host runs, Windows is **BLOCKED / NOT EXECUTED**.

## Linux Ubuntu 24.04 x86_64 (required host)

1. Same git SHA. Linux Fusion Core is **reviewed developer ELF**, not
   official signed Core. Never relabel it as publisher-signed.
2. Independently reviewed **developer** Core dir + manifest SHA256
   `e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806`
   with `wamd` `ccc9f0f1d299a1e98a49ff83859aa03e994e83e6ea4b7cd60c327eb1e0e8e4d6`
   and `wam-cli` `ada9dabd56d0859b9d64c0b20a05c33cb039b2573f75088443b45c35d5379652`.
   Official v0.1.11 Linux archive (GPG) is
   `bd010ed615ab8063d5c12aa61236311ece7e9d19896d9541dacba1888dd9987a`
   (`wam-coin-v0.1.11-x86_64-linux-gnu.tar.gz`). **Do not use that archive
   as this builder’s Core.** Keep `official_signed_core_release=false`.
   ELF `PT_GNU_STACK` must be RW (`flags=6`). RWE is denied.
3. Provision the root witness separately (`docs/LINUX_ROOT_WITNESS_POLICY.md`).
   The app never sudo-installs it.
4. Headless (no Qt in the venv; `requirements/q01-headless.lock`):  
   `python -I scripts/build_linux_wallet.py --core-dir <verified-core>`
5. Desktop (xcb/EGL/fonts present; `requirements/q01-gui.lock`):  
   `python -I scripts/build_linux_wallet.py --core-dir <verified-core> --desktop`
6. Entry for both: `src/wam_regtest/linux_package_entry.py`.
7. Relocate `linux-package-output/` to the matching
   `release-candidates/17adf5c/linux-x86_64-*` tree immediately.
8. Desktop must exercise the same PaymentApproval / worker-lifetime path
   as macOS `17adf5c`. Headless does not run Qt Sign dialogs; do not claim
   GUI PASS from the headless tarball.
9. Exclude scratch, caches, credentials, and private wallet data from
   archives. The existing builder already stages only Core, WSP source,
   branding, and provenance JSON.

Until that host runs, Linux is **BLOCKED / NOT EXECUTED**.

## macOS ARM64 (already executed on this workspace)

`scripts/build_macos_bundle.sh` at `17adf5c` produced unnotarized ad-hoc
`.app.zip` / `.dmg` under `package-output/`. See
`ENGINEERING_HANDOFF.md` and `docs/RELEASE_CANDIDATE_V22_MANIFEST.md`.
Do not rebuild Windows or Linux from those Mach-O bytes.

## Operator run (all OS, disposable profile only)

- Never open the owner Desktop datadir `wam-fusion-core-e905e0d22db25873`.
- Isolated Q06: RPC `127.0.0.1:29554`, zero-peer. Shared P2P `29555` only
  after explicit Shared mode. V19 needs two physical computers.
- Backup / recovery / lock stay on Security. Network page for peers.
- Reduced Motion and Automatic / Light / Dark remain QSettings only.

## Deliverables the Developer must return

| File | Meaning |
| --- | --- |
| Frozen tree + SHA256SUMS | Exact bytes |
| `RELEASE_CANDIDATE_MANIFEST.json` | Written by existing builders **after** frozen E2E |
| Q04 / Q05 / Q06 frozen evidence JSON | From the existing qualify scripts |
| Screenshot / log set | Startup, Core identity, create/backup/lock, Receive, Send, theme, shutdown |
| Unsigned vs signed statement | Windows/Linux unsigned; Linux Core developer-built |
| PaymentApproval / worker note | ApplicationModal Sign/Broadcast; no SIGABRT on retained owners |

V19 remains **BLOCKED / NOT EXECUTED** until two real machines.
Q06 `accepted=false`. G6/G7 **BLOCKED**.
