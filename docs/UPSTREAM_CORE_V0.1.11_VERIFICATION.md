# Official WAM Core v0.1.11 verification (2026-11-05)

Functional Fusion pin: `b844dd371d4ac5dc3d0469eb899d6709e8ac407f`  
Evidence dir: `release-candidates/b844dd3/evidence/upstream-v0.1.11/`  
This is **not** a GitHub “Verified” badge. GitHub Releases for
`wamcoin-core-dev/wam-coin` `v0.1.11` returned **HTTP 404** (API and HTML).
Authoritative download this session: **HTTPS `https://wamcoin.org`**.

## Signing key

| Item | Value |
| --- | --- |
| Published fingerprint | `4BD4 A8D3 AFD4 3F5C BCB5  00E2 3798 462F E00A DBA4` at https://wamcoin.org/security/ |
| Imported key fpr | `4BD4A8D3AFD43F5CBCB500E23798462FE00ADBA4` |
| Identity | `WAM Coin (release signing) <wam.coin.official@proton.me>` RSA-4096 |
| URLs fetched | `https://wamcoin.org/SIGNING-KEY.asc` (3179 bytes) |
| SHA256SUMS | `https://wamcoin.org/downloads/v0.1.11/SHA256SUMS` |
| SHA256SUMS.asc | `https://wamcoin.org/downloads/v0.1.11/SHA256SUMS.asc` |

Commands:

```
gpg --import SIGNING-KEY.asc
gpg --status-fd 1 --verify SHA256SUMS.asc SHA256SUMS
```

Result: `[GNUPG:] VALIDSIG 4BD4A8D3AFD43F5CBCB500E23798462FE00ADBA4`  
Signature time in status: `2026-09-27`.  
`TRUST_UNDEFINED` is expected (key not in a personal trust web).  
Do not treat that warning as a failed signature.

GitHub tag SHA / GitHub asset inventory: **UNVERIFIED** (repo/release 404 from this environment).

## Signed archive inventory (from GPG-valid SHA256SUMS)

| Artifact | SHA256 | Role vs Fusion |
| --- | --- | --- |
| `wam-coin-v0.1.11-arm64-apple-darwin.tar.gz` | `6e10ea10cc324e947c9d646ba8276412175edd0f168c0d95ca5228ccc37f5afb` | Official Mac Core archive (matches local `core/receipt.json`) |
| `wam-coin-v0.1.11-x86_64-w64-mingw32.zip` | `ece622fa7ec3072c4e8b0d32e2c3749397d66260f2b0cf22b3636346873d15c5` | Official Windows Core archive (matches `windows_release_preflight.ARCHIVE_SHA256`) |
| `wam-coin-v0.1.11-x86_64-linux-gnu.tar.gz` | `bd010ed615ab8063d5c12aa61236311ece7e9d19896d9541dacba1888dd9987a` | Official Linux **archive**. Not used by `build_linux_wallet.py` |
| `wam-qt-v0.1.11-*` (all three OS) | see SHA256SUMS | **Do not ship as WAM Fusion.** Reference GUI only |
| `wam-miner-v0.1.11-*` | see SHA256SUMS | Not Fusion |

`wam-qt` is excluded from Fusion packages by policy.

## Binary identity (members)

| Platform | Artifact | Version | Arch | Member SHA256 | Signing | Runtime libs | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| macOS | `core/wamd` | `WAM Coin version v0.1.11` | arm64 Mach-O | `7298de701e467eb28b4806cbcbe35edb393861b4b97117017fee4c1b194e3068` | via signed archive + local receipt | system libc/Cocoa; not inventoried ELF-style | **PASS** hash + `-version` |
| macOS | `core/wam-cli` | `WAM Coin RPC client version v0.1.11` | arm64 | `81a031ebf9b3060b19061b29756d43bcd09b32ad778348b8c3d8321397076e82` | same | same | **PASS** hash + `-version` |
| Windows | `wamd.exe` / `wam-cli.exe` | v0.1.11 (pin) | PE AMD64 | `31717319535c5b784b2bed3b4d3c9a727f5c062e9534b4d27c59d2ffd04e95a1` / `538a6d1b918b698ce76a949dda982fdda6776e33ba057efaac59b1af59e59d21` | archive SHA GPG-valid | MSVC/UCRT (native) | Archive **PASS**; PE members **not re-extracted this session**; native exec **BLOCKED** |
| Linux official | `wamd`/`wam-cli` inside gnu tarball | claimed v0.1.11 | ELF x86_64 | **UNVERIFIED** (tarball not downloaded/extracted here) | archive SHA GPG-valid `bd010ed6…` | glibc/libevent/libsqlite (typical) | Archive listed; **member hashes UNVERIFIED** |
| Linux Fusion | developer `wamd`/`wam-cli` | reviewed source-build | ELF x86_64 | `ccc9f0f1d299a1e98a49ff83859aa03e994e83e6ea4b7cd60c327eb1e0e8e4d6` / `ada9dabd56d0859b9d64c0b20a05c33cb039b2573f75088443b45c35d5379652` | **unsigned developer** | Ubuntu 24.04 loader set | **Not official signed Core** |

## REGTEST / V1-NET vs this official Mac binary

Disposable datadir (non-default ports 18444/18445, wiped after). Public RPC JSON retained.

| Check | Expected | Observed on official macOS `wamd` v0.1.11 | Result |
| --- | --- | --- | --- |
| `getblockchaininfo.chain` | regtest | `regtest` | PASS (this host) |
| Genesis / best at height 0 | `b88f3d262f285e38e184f50bf3eea1c8e615486ae67d3d9eaf0976fbd6d3d30d` | exact match | PASS (this host) |
| Help: P2P default regtest | 29555 | documented in `-help` | PASS (help text) |
| Help: RPC default regtest | 29554 | documented in `-help` | PASS (help text) |
| `-addnode` | present | present | PASS (help text) |
| `-rpcbind` | present; Fusion still forces `127.0.0.1` in `[regtest]` | present; **settings without `[regtest]` section are ignored** | PASS + config warning recorded |
| Message magic `57414d52` | Fusion `shared_regtest.MAGIC` | **not re-dumped from P2P this session** | PENDING wire capture |
| Windows/Linux official node behavior | same genesis/ports | **NOT EXECUTED** | BLOCKED |
| Developer Linux ELF vs official gnu tarball | must not be equated | different provenance; official members UNVERIFIED | **incompatible as “the same signed binary”** |

Fusion `write_config` must keep a `[regtest]` section. A top-level `rpcbind=` is ignored by this binary.

## Compatibility conclusion

- **macOS Fusion** is designed around **official signed v0.1.11** Mach-O. Local node matches genesis used by V1-NET.
- **Windows Fusion** is designed around **official signed v0.1.11** PE. Archive hash GPG-valid. Native Windows behavior **BLOCKED**.
- **Linux Fusion packaging does not consume the official gnu tarball.** It requires a separately labelled **developer-built unsigned** Core plus independent witness. Do **not** call that official v0.1.11.
- Official `wam-qt` is not a substitute for WAM Fusion.
