# RELEASE_BUILD_MANIFEST

Candidate: `WAM-Fusion-REGTEST-b844dd3-RC-HARDENING`  
Shared functional source: `b844dd371d4ac5dc3d0469eb899d6709e8ac407f`

## Toolchain observed on the prep host (macOS 27.0.1 arm64) — not a Win/Linux claim

| Tool | Version |
| --- | --- |
| Python | 3.12.15 |
| PySide6 / shiboken6 / Addons / Essentials | 6.12.0 |
| PyInstaller | 6.22.3 |
| coincurve | 21.0.0 |
| cryptography | 50.0.0 |
| Pillow | **MISSING on this Mac** (Windows ICO step needs Pillow **on the Windows builder**) |

## Platform rows

| Platform | Builder | Output dir (do not overwrite `package-output/`) | Status | Artifact SHA256 |
| --- | --- | --- | --- | --- |
| macos-arm64 | `scripts/build_macos_bundle.sh` | `release-candidates/b844dd3/macos-arm64/` | **NOT EXECUTED** | — |
| windows-x64 | `python -I scripts/build_windows_bundle.py` | `release-candidates/b844dd3/windows-x64/` | **BLOCKED / NOT EXECUTED** | — |
| linux-x86_64 desktop | `python -I scripts/build_linux_wallet.py --core-dir <reviewed> --desktop` | `release-candidates/b844dd3/linux-x86_64/` | **BLOCKED / NOT EXECUTED** | — |
| linux-x86_64 headless | same without `--desktop` | same tree, distinct tarball name | **BLOCKED / NOT EXECUTED** | — |

Nondeterminism (when builds exist): PyInstaller timestamps, ad-hoc `codesign`, collected .pyc, local absolute paths in generated `.spec`. Do not claim byte-identical rebuilds until two independent native rebuilds match.

## Tests this session

| Test | Platform | Identity | Result |
| --- | --- | --- | --- |
| GPG SHA256SUMS | macOS prep host | key `4BD4A8D3…` | PASS (VALIDSIG) |
| Official Mac `wamd -version` | local `core/` | v0.1.11 | PASS |
| Disposable REGTEST genesis | local official Mac Core | genesis `b88f3d26…` | PASS |
| Source Fusion unittests | previously on V2.2 | 34 tests | PASS (not ledger) |
| Frozen app / Win / Linux / V19 | — | — | NOT EXECUTED / BLOCKED |
