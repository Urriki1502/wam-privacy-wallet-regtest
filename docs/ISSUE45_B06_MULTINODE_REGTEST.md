# Issue #45 / B-06 — Two genuine WAM Core REGTEST nodes + WSP reorg lab

**Single Draft PR on green R-06 #107** — base commit
`922b66687ae940ead3d160bd85b5bbb201a68be6`.

## Implemented acceptance slice

`scripts/issue45_b06_multinode_regtest.py` launches **two independently
running official v0.1.11 WAM Core processes**, each backed by a freshly
created private disposable REGTEST directory, private RPC credentials
in owner-only `wam.conf`, unique loopback P2P/RPC ports and a separate
database. It reuses `verified_core_paths` signed-core binary validation,
the exact pinned WSP-1 source, and the ORIGINAL `wam_sp.scanner.Scanner`
with its actual SQLite undo journal; it does not implement a second
scanner or synthetic chain.

The lab makes a local-only P2P link using one-shot `addnode` and
`disconnectnode`; no DNS seeds/discovery/proxies or outward bind.
The production wallet's separate zero-peer `network_policy` is
**unchanged**. No user-provided datadir, attached node, personal wallet,
solo-miner environment, real keys or network peer is involved.

1. Verify each real Core is exactly REGTEST v0.1.11 with the true WAM
   genesis, matching RPC identity and 0 external peers.
2. Node A mines genuine 101 maturity blocks to a globally known PUBLIC
   disposable REGTEST address. Connect A/B and prove equal chain height/tip.
3. Start the pinned original WSP Scanner with public disposable scan key
   1 and spend public key 2. Scan the real chain into SQLite.
4. Isolate the two nodes; on A, mine an actual BIP352 P2TR payment into
   a block using the existing native WSP fixture. Sync Scanner and
   confirm a real wallet coin appeared. On B, mine two blocks on the
   competing fork, reconnect, and prove A switched chains. Original
   scanner must undo **exactly 1 block** and remove the orphaned payment.
5. Repeat isolated competing chain branch replacement for **12** and
   **100** blocks, syncing Scanner on the orphaned branch first and
   verifying the exact durable WSP rollback depth after reconnect.
6. Close/reopen the SAME SQLite scanner at each round and verify no
   data loss, false wallet balance, or duplicate replay.
7. Disconnect, stop and restart the independently owned B node, verify
   unchanged persisted tip, reconnect and resync once more.
8. Publish ONLY bounded nonsecret aggregate proof; both private
   Core datadirs and WSP SQLite are deleted when test scope ends.

The macOS native `real-core-regtest.yml` step executes this lab
against actual official signed Core *before* existing T05 and wallet
tests, with a strict 12-minute independent bound. Cross-platform
source/unit guards run in existing workflows.

## Security boundaries

This test intentionally permits loopback P2P only **inside the temporary
B06 lab**, unlike the default wallet. No arbitrary RPC, external peer,
mainnet, production/private account, or auto-merge. Reject any non-
`127.0.0.1` observed peer. Do not confuse the public source-unit tests
with real multi-node E2E. The `LabReader` is private test-only and does
not relax the production transport trust boundary or Core custody.

## Remaining B-06 P0

- Native two-node lab execution on exact Windows x64 and Linux x86_64
  Core builds, distinct runtime/provenance constraints and frozen GUI
  scanner/reconnect behavior.
- Nondeterministic peer timing/race and interrupted-node fault injection
  beyond the bounded run, plus operator/DEV independent review.
- Three-platform integrated candidate rerun and Issue #45 Q01–Q20
  evidence. PASS on a macOS native lab is **not** an integrated three-OS
  B06/Issue45 acceptance; `full_b06_p0_qualified=false`.

Do not mark B06 complete unless all required evidence is present and
reviewed. After native E2E, record exact code SHA, Core and WSP identity,
runner, chain, depth and external review status in the P0 registry.
