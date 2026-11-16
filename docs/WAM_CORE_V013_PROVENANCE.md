# WAM Core v0.1.13 provenance — 2026-11-05

Supply-chain verification PASS; runtime integration and final packages PENDING.
Downloaded afresh over HTTPS from `https://wamcoin.org/downloads/v0.1.13/`
into owner0700 `/tmp/wam-v013-intake.AlRCA7`. No retained wallet was opened.

Tag object `69943383378dfe563703a80ede894c23fbc12359` dereferences to
`b3fb899ddb1ceab7e9b3b12ccd034ad1b4be8186` (live git ls-remote).
Full signer `4BD4A8D3AFD43F5CBCB500E23798462FE00ADBA4` matches the fetched
[official security page](https://wamcoin.org/security/) and the previously
pinned release key in release.py / UPSTREAM_CORE_V0.1.11_VERIFICATION.md.
Isolated GnuPG verification returned exit 0, GOODSIG and full VALIDSIG,
no revoked/expired/bad signature status. Key expiration is 2031-09-03;
TRUST_UNDEFINED indicates no ownertrust, not cryptographic failure.
Key SHA256 `842d9419593efc8fe0a5f45feaeab86710c03b27b3e2416a2dc9205fe506ee63`.

Signed SHA256SUMS: 963 bytes,
`fab37640d6860fd28cadd547ca4e3312f60ec1441df4574029ff2cf6536c3907`.
Detached signature: 833 bytes,
`2014ce6a2fceb446448219ed16e1b923f457582cbeaf05bb57f62258ca9c1a73`.
Only the three selected Core entries were checked; absent miner/Qt archives
were not falsely checked. All selected digests and sizes match the live
[GitHub Release metadata](https://github.com/wamcoin-Project/wam-coin/releases/tag/v0.1.13).

| Platform | Archive bytes | Archive SHA256 | wamd SHA256 | CLI SHA256 |
|---|---:|---|---|---|
| macos-arm64 | 11133091 | `2e6d4cb34e4e1ca800db82591295ede775e5ba1769fec737db70ebaa38ab5894` | `fe04a61f17eb8047f1d2a537ebcb61b45cbde14c491bc332d2a2ab7ee18237ba` | `2b19fdac692cbed5810b6fa9663ac89f25ab8f346da84c5fd13bf2b8535e3e19` |
| windows-x64 | 16333094 | `db6bcb58e909a72a69ab7bb74a95ab3837298c12fd847dc83fdb37fca10732b4` | `5fbeb6e07a83b337209edf0efbe342201bc3bf2e0c113dea8fdf7bf0e07d49e3` | `a6171ed6cddfeea58b9a6a8b722f2c07c0d332f0f1a7263f52193e4ef9f6f326` |
| linux-x86_64 | 13163409 | `1adb703f9c881f1ce20ee1d085c7d0d07395b61751faa02a532f947bb97d594a` | `a3e3bf810e74824e3739fd4cbd1a45037cae997056b8c978c4dc1a61d674f0c7` | `d99fc90e3aa4233979056d9981a388360e5d7ff77090d00b9bc37191a2425300` |

Each archive was inspected before extracting only the intended two binaries:
unique bounded entries, exact root `wam-coin-v0.1.13`, no traversal, absolute
paths, links or special files. Full public entry inventory and signature bytes
are retained in [evidence/core-v013](evidence/core-v013/verified-members.json).

`file` observed ELF64 x86_64, PE32+ AMD64 and Mach-O64 ARM64 respectively.
macOS `otool -L` shows only `/usr/lib/libSystem.B.dylib` and
`/usr/lib/libc++.1.dylib` for both members. Linux stack, loader and dependency
closure plus native version/RPC observations must be recorded by Ubuntu24.04
before activation; Windows loader/native execution remains PENDING.
Upstream signature covers archive bytes, separate from Fusion outer ad-hoc
codesign, Authenticode, notarization or physical acceptance.

Q06 accepted=false; G6/G7 BLOCKED; V19 NOT EXECUTED/BLOCKED. No merge,
release, mainnet or owner-profile conversion is authorized by this receipt.

Native Linux intake [run 42060782393](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/42060782393)
at source `4098f21aae9e00650eca4cad91227fc00302b90f` PASS: observed numeric
113, `/WAM:0.1.13/`, protocol70016, zero peers, exact genesis and 101 blocks;
original Popen stopped. Downloaded receipt retained as
`evidence/core-v013/linux-native-intake-4098f21.json`.
Both ELF stacks RW; no RPATH/RUNPATH or missing dependency. The exact
Ubuntu24.04 root-owned loader/libc/libm/libgcc/libstdc++ closure was reviewed
and separately pinned in linux_official_core.py. Manifest
`4052c4a75dee853f5a27c2fb1869aee841a075ed8d6187b90a9d1c06a88cf3c2`
is deterministic from those reviewed identities; archive/member trust is
independently fixed in official_core_v013.py, never learned from that manifest.
This intake is not Q04/Q05/Q06 or frozen wallet qualification.
