# WAM Fusion — stable task names and pre-V1 network gate

> Governance naming catalog · 2026-11-02 · owner-requested · NOT a release approval.

## Permanent identifiers and readable feature names

IDs **must not be renumbered**. GitHub issues, acceptance case IDs, tests/acceptance/issue45.json, committed receipts and historical links already reference them. Use these canonical display names in future reports, documentation, PR descriptions, and release notes. Preserve literal legacy symbols and file paths until a separately tested, import-compatible migration exists.

| Stable ID | Canonical display name | Responsibility / product feature |
| --- | --- | --- |
| Q01 | Reproducible Build & Release Provenance | Clean installation, pinned dependencies, build closure, packaging/provenance |
| Q02 | Authenticated WAM Core & Chain Identity | Real Core, signed binaries, correct genesis, credentials and fail-closed chain verification |
| Q03 | Managed RPC & Credential Lifecycle | Serialized authenticated local RPC, reusable reads, cookie/credentials, Windows lifecycle |
| Q04 | Node/Miner Coexistence & Safe Reconnection | External Core observation, mining coexistence, busy backoff, recovery without adoption |
| Q05 | Owned Core Persistence & Native Wallet Custody | CoreSupervisor, encrypted vault, native anchor, checkpoint, crash/reopen and no replay |
| Q06 | BIP39 12-Word Wallet & BIP352 Silent Payments | Mnemonic, native-sealed seed, receive, Prepare/Sign/Broadcast, same-chain reconciliation |
| Q07 | BIP39 24-Word Wallet | Preserve this existing Issue #45 obligation; no reassignment to network P2P |

**Source-module naming convention for all new code:** names express an owned technical function, not a phase or CI gate (e.g., shared_regtest_profile.py, p2p_peer_policy.py, chain_attestation.py, regtest_block_coordinator.py). Existing qXX_ technical-probe modules and acceptance case IDs stay intact until migration can preserve imports, Python frozen hooks, tests and historical evidence. Do not mass-rename custody or wallet modules as a mechanical patch.

## Separate mandatory pre-V1 feature gate

**V1-NET — Shared REGTEST P2P & Cross-Platform Transactions** is an additional pre-V1 integration gate and NOT Q07. Implement it in exactly **one focused Draft feature PR**, normally based on main after an owner-authorized Q06 engineering integration. Do not layer a second wallet/seed/signer/transaction engine, fork consensus, or retrofit active Q06 owner profiles. V1-NET is currently SPECIFIED / NOT IMPLEMENTED / NO ACCEPTANCE.

Its objective is one authenticated REGTEST blockchain shared between macOS ARM64, Windows 11 x64 and Linux x86_64, initially two owner-operated devices then up to ten permitted peers. Each device has a separate native-custody BIP39 wallet; local loopback RPC and transaction approval are unchanged. Only the P2P transport uses a permitted private LAN/VPN. A dedicated authorized coordinator makes confirmation blocks. Mandatory fail-closed checks cover peer allowlist, canonical bootstrap block hash, chain ancestry/tip, reorg across anchored checkpoint, disconnection, broadcast uncertainty, reboot and irreversible reservations.

**One-PR rule:** integrate P2P networking, chain verification, scanner/recovery transitions, coordinator, UI network mode, negative tests and cross-platform native/frozen E2E in that single Draft PR as reviewed commits. Any unfinished portion stays PENDING; do not merge partial networking under a false success claim. The feature PR itself needs explicit owner authorization to merge. Preserve isolated Q06 zero-peers mode as regression baseline. This is a scope/roadmap amendment proposal, not authorization to bypass the existing single-active-Q Q-GATE or move Q07.

## Q06 audit and evidence

The authoritative case-level PASS/PENDING/BLOCKED and links remain in tests/acceptance/issue45.json; supporting per-case evidence interpretation is in [Q06 final engineering audit](Q06_FINAL_ENGINEERING_AUDIT.md). A CI green status and artifact receipt do not constitute physical operator acceptance, independent security approval, or production/mainnet permission.

No automatic merge, no production qualification, no exchange of live funds.
