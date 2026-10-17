# Issue #45 — PR #59 — Real v0.1.12 Core + WSP BIP352 receive, isolated Linux

**Scope: component-level REGTEST evidence only.** This follows PR #58's actual
owned authenticated v0.1.12 HTTP reads. PR #59 runs a **second independent**
real official signed Linux Core instance with a disposable datadir and
a pinned upstream WSP-1 engine at `ac55f13423620252bdbf848c7e8a280c3b84721e`.

## Genuine evidence gate

- CI runner: isolated Ubuntu 24.04 x64, checked-out exact PR HEAD;
  independently pinned actual WSP source checkout (verified commit).
- Download and verify original WAM Core v0.1.12 GPG signature and signed
  SHA256SUMS -> Linux tarball, extract exactly two checked ELF binaries,
  record SHA256 for both. Never use operator's wallet/datadir or mining node.
- Start private zero-peer REGTEST, validate genesis and exact WAM
  `(112, '/WAM:0.1.12/', 70016)` version.
- Mine **101 blocks to public, globally known scalar-31 test address**;
  scanner uses only publicly known ScanAccount fixture (not a spend key).
- Pinned WSP constructs and signs a **public-fixture-only** Bitcoin-like
  input -> WAM BIP352 silent payment; genuine WAM Core `sendrawtransaction`
  verifies consensus and next block confirms payment at height 102.
- WSP Scanner must detect exactly one owned silent output, credit the
  exact amount, persist SQLite history, and restart without double-credit.
- WSP adapter restricts `Scanner.call` to four read-only methods. Writes
  are exclusively the isolated test fixture's `generatetoaddress(1)`
  and explicitly bounded `sendrawtransaction(raw)`; never expose these
  methods to actual wallet sessions, GUI or RPC transport.
- Preserve artifact with exact git source SHA, signed archive + ELF hashes,
  pinned WSP commit and confirmation/SQLite evidence; fail CI on any
  missing, contradictory or unverified observation.

## Release hold — NOT an integrated approval

PR #59 does **not** activate Core v0.1.12 for WAM Fusion. Existing wallet
`ManagedReadRpc` still rejects v0.1.12, and old v0.1.11 pins are unchanged.
Full WalletSession/WSP operational send and signer with v0.1.12, Linux
frozen GUI, macOS/Windows signed v0.1.12, reorg/double-spend/custody
recovery, full BIP94, OS installer and physical DEV acceptance remain
**PENDING**. PR #59 should remain Draft even if its Linux component CI is PASS.

Mainnet, live keys, any owner datadir, Core Update Manager and automatic
merges are explicitly out of scope.
