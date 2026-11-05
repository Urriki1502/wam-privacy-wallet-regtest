# Developer native Windows / Linux build handoff

Use **one** source revision on every OS:

```
3ab3e527cb90930631c4265f12923981452bf21e
```

WSP pin: `ac55f13423620252bdbf848c7e8a280c3b84721e`

Do not mix this SHA with older frozen DMGs or expired RC1 Actions ZIPs. Do not overwrite
historical `package-output/` trees. Write new trees:

```
release-candidates/3ab3e52/windows-x64/
release-candidates/3ab3e52/linux-x86_64-desktop/
release-candidates/3ab3e52/linux-x86_64-headless/
```

Reuse the **existing** builders and entries. Do not add a second Windows or Linux backend. Exact RC1 vs V2.2 file matrix: `docs/PLATFORM_REUSE_GAP_MATRIX.md`.

No GitHub push, merge, new CI workflow, or mainnet.

## Windows 11 x64 (required host)

1. Clean checkout of `3ab3e527cb90930631c4265f12923981452bf21e` on native AMD64 Windows (not WSL).
2. Python 3.12 x64. Install GUI freeze deps from `requirements/q01-gui.lock` (PySide6 6.12.0, PyInstaller 6.22.3, Pillow 12.0.0). No ambient `PYTHONPATH` / Git OpenSSL on PATH.
3. Official signed Core v0.1.11 ZIP (preflight pins):
   - archive SHA256 `ece622fa7ec3072c4e8b0d32e2c3749397d66260f2b0cf22b3636346873d15c5`
   - `wamd.exe` `31717319535c5b784b2bed3b4d3c9a727f5c062e9534b4d27c59d2ffd04e95a1`
   - `wam-cli.exe` `538a6d1b918b698ce76a949dda982fdda6776e33ba057efaac59b1af59e59d21`
4. Run `python -I scripts/build_windows_bundle.py` (refuses non-Win32).
5. Move `windows-package-output/` to `release-candidates/3ab3e52/windows-x64/` before any later build.
6. Launch the frozen `.exe` on that same machine with a **new disposable** REGTEST profile. Never open `wam-fusion-core-e905e0d22db25873`.
7. Fill `JOINT_ACCEPTANCE_CHECKLIST.md` Windows rows with job logs, SHA256, and GUI evidence. Leave FAIL history.

Until that host runs, Windows is **BLOCKED / NOT EXECUTED**.

## Linux Ubuntu 24.04 x86_64 (required host)

1. Same git SHA. Linux developer Core is **not** official signed Core.
2. Independently reviewed **developer** Core dir + manifest SHA256
   `e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806`
   with `wamd` `ccc9f0f1d299a1e98a49ff83859aa03e994e83e6ea4b7cd60c327eb1e0e8e4d6`
   and `wam-cli` `ada9dabd56d0859b9d64c0b20a05c33cb039b2573f75088443b45c35d5379652`.
   Official v0.1.11 Linux archive (GPG) is
   `bd010ed615ab8063d5c12aa61236311ece7e9d19896d9541dacba1888dd9987a`
   (`wam-coin-v0.1.11-x86_64-linux-gnu.tar.gz`). **Do not treat that archive as
   this builder’s Core.** Keep `official_signed_core_release=false`.
   ELF `PT_GNU_STACK` must be RW (`flags=6`). RWE remains rejected.
3. Provision the root witness separately (`docs/LINUX_ROOT_WITNESS_POLICY.md`). The app never sudo-installs it.
4. Headless (no Qt in the venv; `requirements/q01-headless.lock`):  
   `python -I scripts/build_linux_wallet.py --core-dir <verified-core>`
5. Desktop (xcb/EGL/fonts present; `requirements/q01-gui.lock`):  
   `python -I scripts/build_linux_wallet.py --core-dir <verified-core> --desktop`
6. Relocate outputs out of `linux-package-output/` immediately.
7. Record `official_signed_core_release=false` on every Linux receipt.

Until that host runs, Linux is **BLOCKED / NOT EXECUTED**.

## macOS ARM64 (this workspace)

Recipe: `PATH` must provide a `python` 3.12 binary (`/opt/homebrew/opt/python@3.12/libexec/bin`). Working tree must be clean.

`scripts/build_macos_bundle.sh` on `3ab3e52` reached Q06 spend and **failed closed**. No `.dmg` was published. Partial evidence is under `release-candidates/3ab3e52/macos-arm64/evidence/`. See `docs/RELEASE_CANDIDATE_V22_MANIFEST.md`.

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
