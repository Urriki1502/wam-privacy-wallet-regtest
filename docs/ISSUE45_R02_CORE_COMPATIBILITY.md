# R-02 — Versioned Core compatibility: fail-closed first native gate

Issue #45 / R-02 [P0], one Draft PR stacked on exact green R-01 PR #102
commit `42d9baebe81999a92ad210094f72a668431d0869`.

## Implemented in this slice

- Immutable exact `COMPATIBLE_RPC_V011 = (111, "/WAM:0.1.11/", 70016)`
  factored into `r02_compatibility.py`; the real authenticated
  `ManagedReadRpc` Core `getnetworkinfo` response now uses this shared
  exact predicate. v0.1.12/unexpected Core protocol/subversion fails closed
  before ordinary RPC reads continue.
- Conservative **public-only** classification for v0.1.11/v0.1.12 and
  macOS ARM64/Windows x64/Linux x64. Only the already reviewed exact
  official v0.1.11 binary member digests from `release.py` and
  `windows_release_preflight.py` may match this source contract.
- Even exact signed v0.1.11 component hashes are **NOT** final R-02
  compatibility/activation approval. The classification outcome never permits
  binary activation, signing/broadcast or mainnet operations.
- v0.1.12 is explicitly **PENDING REQUALIFICATION**, not a supported runtime.
  Valid signature alone, a matching manifest, and matching release notes do
  NOT grant WAM Fusion runtime access.
- The independently reviewed Linux *developer-built* Core is categorically
  separate from official signed Linux release. This public preflight does not
  grant an official Linux approval via a developer receipt.
- Offline unit tests challenge malformed versions, wrong platform, swapped
  macOS/Windows members, forged signing claims, mainnet identity and changed
  protocol identities. Synthetic public tests do not substitute for Core E2E.

## Native evidence necessary

This PR's Mac, Windows and Linux genuine-Core CI must separately exercise the
actual authenticated WAM Core `getnetworkinfo` with the pinned v0.1.11 RPC
profile; exact HEAD and native/frozen receipts apply. The existing native
wallet E2E and WSP regression jobs remain in force. Do not inherit #102 PASS.

## Remaining R-02 P0: **PENDING / not in this PR**

1. Independently verified upstream R-01 release signature/key distribution and
   exact platform archive/member bytes for any new version, including v0.1.12.
2. Full per-platform **version + exact executable SHA-256 + OS + network +
   separate functional approval** for Core RPC, signer, WSP scanner, BIP39,
   SQLite descriptor import, mempool/tx, recovery, custody, network policy
   and frozen GUI. A signed release cannot create this approval.
3. Real signed/frozen native three-OS REGTEST runs with separate provenance
   and versioned receipts; negative wrong-version, wrong-digest, old-replay
   and interrupted update. DEV/security/operator review is independent.
4. Safe approved profile-switch/migration design with operator consent, never
   automatically changing a running supervisor's profile, owner datadir or
   attached solo miner.

A short `R02_V011_PUBLIC_MEMBER_PINS_MATCH_ONLY` result is **not**
`R02_FULL_P0_PASS`. No external/node attachments, wallet signing, Core
install/upgrade, mainnet, auto-merge or upstream consensus modifications.
