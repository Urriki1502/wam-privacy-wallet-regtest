# Dependency inventory (prep host only)

Generated 2026-11-05 with `importlib.metadata` on the Mac that wrote this file.
This is **not** a CycloneDX/SPDX SBOM of a frozen Windows or Linux tree, and it
is **not** a vulnerability-free certificate.

| Package | Version on prep host | Role |
| --- | --- | --- |
| PySide6 | 6.12.0 | Qt GUI (LGPL) |
| PySide6_Essentials | 6.12.0 | Qt |
| PySide6_Addons | 6.12.0 | Qt |
| shiboken6 | 6.12.0 | Qt binding |
| PyInstaller | 6.22.3 | freeze (build-time) |
| pyinstaller-hooks-contrib | 2026.9 | freeze |
| coincurve | 21.0.0 | WSP crypto |
| cryptography | 50.0.0 | TLS/crypto helpers |
| cffi | 2.1.1 | native FFI |
| pycryptodome | 3.23.0 | present in env |
| qrcode | 8.2 | receive QR |
| setuptools | 84.2.1 | build |
| packaging | 26.3 | build |
| altgraph | 0.17.5 | PyInstaller |
| Pillow | missing here | Windows ICO conversion **on Windows** |

No new telemetry libraries. Fusion RPC is localhost-only. The only outbound
HTTPS used in this session was `https://wamcoin.org` for `SIGNING-KEY.asc` and
`downloads/v0.1.11/SHA256SUMS{,.asc}`. GitHub `wamcoin-core-dev/wam-coin` was
queried and returned 404.

Scanner limitation: no CVE database was applied. “Listed here” ≠ “safe.”
