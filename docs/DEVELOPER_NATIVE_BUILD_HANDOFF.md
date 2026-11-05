# Developer native Windows / Linux build handoff

Use **one** source revision on every OS:

```
b844dd371d4ac5dc3d0469eb899d6709e8ac407f
```

WSP pin: `ac55f13423620252bdbf848c7e8a280c3b84721e`

Do not mix this SHA with older frozen DMGs. Do not overwrite
`package-output/WAM-Privacy-Wallet-REGTEST-macOS-ARM64.dmg` or other qualified
archives. Write new trees:

```
release-candidates/b844dd3/macos-arm64/
release-candidates/b844dd3/windows-x64/
release-candidates/b844dd3/linux-x86_64-desktop/
release-candidates/b844dd3/linux-x86_64-headless/
```

No GitHub push, merge, new CI workflow, or mainnet.

## Windows 11 x64 (required host)

1. Clean checkout of `b844dd371d4ac5dc3d0469eb899d6709e8ac407f` on native AMD64 Windows (not WSL).
2. Python 3.12 x64, declared `requirements`, no ambient `PYTHONPATH` / Git OpenSSL on PATH.
3. Official signed Core v0.1.11 ZIP (preflight pins):
   - archive SHA256 `ece622fa7ec3072c4e8b0d32e2c3749397d66260f2b0cf22b3636346873d15c5`
   - `wamd.exe` `31717319535c5b784b2bed3b4d3c9a727f5c062e9534b4d27c59d2ffd04e95a1`
   - `wam-cli.exe` `538a6d1b918b698ce76a949dda982fdda6776e33ba057efaac59b1af59e59d21`
4. Run `python -I scripts/build_windows_bundle.py` (refuses non-Win32).
5. Move `windows-package-output/` to `release-candidates/b844dd3/windows-x64/` before any later build.
6. Launch the frozen `.exe` on that same machine with a **new disposable** REGTEST profile.
7. Fill `JOINT_ACCEPTANCE_CHECKLIST.md` Windows rows with job logs, SHA256, and GUI evidence. Leave FAIL history.

Until that host runs, Windows is **BLOCKED / NOT EXECUTED**.

## Linux Ubuntu 24.04 x86_64 (required host)

1. Same git SHA. Linux developer Core is **not** official signed Core.
2. Independently reviewed Core dir + manifest SHA256
   `e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806`
   with `wamd` `ccc9f0f1d299a1e98a49ff83859aa03e994e83e6ea4b7cd60c327eb1e0e8e4d6`
   and `wam-cli` `ada9dabd56d0859b9d64c0b20a05c33cb039b2573f75088443b45c35d5379652`.
3. Provision the root witness separately (`docs/LINUX_ROOT_WITNESS_POLICY.md`). The app never sudo-installs it.
4. Headless (no Qt in the venv):  
   `python -I scripts/build_linux_wallet.py --core-dir <verified-core>`
5. Desktop (xcb/EGL/fonts present):  
   `python -I scripts/build_linux_wallet.py --core-dir <verified-core> --desktop`
6. Relocate outputs out of `linux-package-output/` immediately.
7. Record `official_signed_core_release=false` on every Linux receipt.

Until that host runs, Linux is **BLOCKED / NOT EXECUTED**.

## macOS ARM64 (this workspace)

Recipe: `scripts/build_macos_bundle.sh` then `scripts/create_verified_dmg.py`.
Local toolchain observed 2026-11-05: Python 3.12.15, PySide6 6.12.0, PyInstaller 6.22.3, Darwin arm64.
Official Core in `core/` matches `core/receipt.json`.
A **fresh** `.app`/`.dmg` from `b844dd3` was **not** built in this session so that
existing `package-output/` artifacts would not be overwritten.

## Operator run (all OS, disposable profile only)

- Never open the owner Desktop datadir `wam-fusion-core-e905e0d22db25873`.
- RPC localhost 29554 only. P2P 29555 only when Shared mode is explicit.
- Backup/recovery/lock stay on Security; Network page for peers.
- Reduced Motion and Automatic/Light/Dark remain QSettings presentation only.

## Deliverables the Developer must return

| File | Meaning |
| --- | --- |
| Frozen tree + SHA256SUMS | Exact bytes |
| `RELEASE_CANDIDATE_MANIFEST.json` | Written by existing builders **after** frozen E2E |
| Q05/Q06 frozen evidence JSON | From `qualify_q05_frozen.py` / `qualify_q06_frozen.py` |
| Screenshot/log set | Startup, Core identity, create/backup/lock, Receive, Send, theme, shutdown |
| Unsigned vs signed statement | Windows/Linux unsigned; Linux Core developer-built |
