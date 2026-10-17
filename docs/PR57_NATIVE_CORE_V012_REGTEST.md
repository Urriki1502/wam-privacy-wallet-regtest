# Issue #45 PR #57 — Authentic WAM Core v0.1.12 Linux REGTEST native smoke

**Purpose:** Move from PR #56's verified *signed archive only* evidence to
**first genuine v0.1.12 native execution** in an isolated disposable GitHub
Actions Ubuntu runner. This is a **component qualification**, NOT approval
to install v0.1.12 in WAM Fusion or an assertion of integrated V1 completion.

## Reproducibility and trust

- Exact PR head asserted against `git rev-parse HEAD` before download/execution.
- Fetch public official release's `SIGNING-KEY.asc`, `SHA256SUMS`,
  `SHA256SUMS.asc` and Linux Core tarball over restricted HTTPS endpoints.
- Validate signed checksums against **independently pinned publisher**
  fingerprint `4BD4 A8D3 AFD4 3F5C BCB5 00E2 3798 462F E00A DBA4`.
- Validate full signed archive SHA-256, expected members and ELF x86_64 shape.
- Extract only `wamd` and `wam-cli` into a disposable owner-only directory,
  record their measured SHA-256; no archive blanket extraction.
- Start an isolated local-only node with generated credentials, fresh
  datadir, listen=0, connect=0, no peers, no external miner and no real funds.
- Mine 151 disposable REGTEST blocks, independently validate genesis and
  WAM v0.1.12 version RPC, block-1 / 149 / 150 / 151 subsidy split,
  independent treasury ownership, Core `getdevfeeinfo` and reward schedule.
- Verify Core wallet coinbase depth 99/100/101 before/after spend eligibility
  without sending to any user or production address.
- Shut down the owned node and delete test datadir even on failure.

## Evidence and mandatory limits

The workflow publishes `v012-linux-native-regtest.json` only after exact-head
native tests pass. The receipt distinguishes actual version/chain, signer,
binary SHA-256, verified coinbase/maturity from untested acceptance layers.
The expected `status=V012_SIGNED_LINUX_CORE_REGTEST_COMPONENT_PASS` is
**not** an integrated REGTEST Fusion PASS or approval of an activated Core.

Still PENDING: macOS/Windows v0.1.12 real native tests, binary loader/OS
custody attestation, WSP/BIP352, signed outgoing PSBTv2 and ambiguous
broadcast recovery against v0.1.12, long-height treasury sunset,
multi-node/reorg, full BIP94 behavior, frozen artifacts and DEV physical
acceptance. Historical v0.1.11 pins and runtime stay unchanged.

**Issue #45 progress reporting must separate code-component coverage from
the strict ALL-P0 release gate.** A green CI suite is not independent
physical or cross-platform approval.
