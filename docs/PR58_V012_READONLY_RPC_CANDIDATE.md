# Issue #45 PR #58 — WAM Core v0.1.12 owned-HTTP candidate compatibility

This builds on PR #57's real, signed official Linux REGTEST Core and keeps
existing wallet runtime **v0.1.11-only**. No new Core may be installed or
enabled for a Fusion wallet from this work.

## Exact scope

- Versioned **test-only** candidate profile for Linux v0.1.12: signed archive,
  signing-key fingerprint, independently measured official `wamd` and
  `wam-cli` SHA-256, genesis, zero external peers and the exact measured
  `(112, '/WAM:0.1.12/', 70016)` network RPC version.
- Reuse existing protected Linux `wam.conf` reader and read-only RPC
  parameter/reply validators without changing their v0.1.11 global gate.
- For a disposable CI-owned Core process, create a loopback TCP socket,
  independently confirm that its server endpoint belongs to the **owned
  signed Core process** before sending any HTTP authentication bytes, then
  make exactly four bounded read-only calls:
  `getnetworkinfo`, `getblockchaininfo`, `getblockhash(0)`,
  `getblockcount`.
- Deliberately assert that existing `ManagedReadRpc` v0.1.11 response
  validation **DENIES** the v0.1.12 network profile. The separate candidate
  parser accepts only the independently measured exact triplet.
- Check request IDs, duplicates, wrong network, denial of writes, bounded
  public replies, pinned binary/process/config identity and zero external
  peers. No wallet selector, WSP signer, attached Core, auto upgrade or
  mainnet authority is introduced.
- Run Linux true Core integration with official signed v0.1.12 binary in
  the isolated PR #57 runner and attach **source SHA + artifact digest**.

## Hard release holds

A passing test documents only a **Linux test-only candidate RPC shape**.
A valid signature or compatible RPC API does **not** mean Fusion can run
v0.1.12. Existing WAM v0.1.11 Core loader, wallet RPC allowlists and pins
remain unchanged. macOS/Windows native v0.1.12, WSP/BIP352 receive/scan,
PSBTv2 Sign/Broadcast, persistent/attach Core lifecycle, reorg,
BIP94, frozen packages, DEV physical review, and full R-01/R-02 acceptance
are **PENDING**. No new integrated Issue #45 P0 can be marked PASS based on
the component artifact alone.

Draft PR; no automatic merge/force push/RC1/main modification.
