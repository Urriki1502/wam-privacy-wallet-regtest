# Official Linux Core v0.1.13, read-only

Inspected 2026-11-05. The qualified developer Core was not replaced.
macOS and Windows remain on official v0.1.11.

Signed sums: `https://wamcoin.org/downloads/v0.1.13/SHA256SUMS`
GPG `VALIDSIG` key `4BD4A8D3AFD43F5CBCB500E23798462FE00ADBA4`
(`WAM Coin (release signing)`). The key is not in a local trust
web; the check is the same fingerprint already pinned for v0.1.11.
`TRUST_UNDEFINED` is that missing ownertrust, not a bad signature.

Linux archive `wam-coin-v0.1.13-x86_64-linux-gnu.tar.gz`
`1adb703f9c881f1ce20ee1d085c7d0d07395b61751faa02a532f947bb97d594a`
matches the signed sums.

| Member | SHA256 | ELF |
| --- | --- | --- |
| `wamd` | `a3e3bf810e74824e3739fd4cbd1a45037cae997056b8c978c4dc1a61d674f0c7` | ELF64 x86_64, `PT_GNU_STACK` RW, interpreter `/lib64/ld-linux-x86-64.so.2`, highest glibc symbol `GLIBC_2.34` |
| `wam-cli` | `d99fc90e3aa4233979056d9981a388360e5d7ff77090d00b9bc37191a2425300` | ELF64 x86_64, `PT_GNU_STACK` RW, same interpreter, highest glibc symbol `GLIBC_2.34` |

DEV WAM's report that v0.1.11 official Linux `wamd` is GNU_STACK RWE
and v0.1.13 is RW matches this static inspection of v0.1.13.
The binaries were not executed. REGTEST port, magic, and WSP
integration were not run. Strings for `regtest` and `testnet` exist
in the binaries; that is not a network-identity proof.

Migration stays blocked until a separate Linux job verifies these
hashes, runs the existing Core, BIP352, and wallet gates, and
publishes a new package. This document is not that qualification.
`official_signed_core_release` stays false for the current developer
Core pin `ccc9f0f1…` / manifest `1e8d6cbd…`.
