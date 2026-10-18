# Issue #45 — T-09 cross-platform direct-RPC evidence gate

**One T-09 PR.** A mandatory exact-code native/frozen acceptance contract for existing genuine WAM Core v0.1.11 and pinned WSP-1 REGTEST. No new transport, network route, Core process or mock acceptance.

## Mandatory evidence from running Core

The t09_direct_rpc_evidence section is constructed inside the actual smoke_real_core operation after native WAM Core and WSP execute. Missing or invented prerequisite receipts refuse before PASS. It verifies exact WAM RPC version (111, /WAM:0.1.11/, 70016), owned process and established loopback socket before HTTP credentials, 8 repeated authenticated HTTP reads, chain-height/best-tip parity, stable Core/CLI identity, wrong-process pre-auth zero-byte refusal, genuine-Core invalid Basic-auth refusal, writes denied on read-only transport, real WSP BIP352 receive and SQLite scanner without per-read CLI.

When the full wallet or native Linux headless/Qt runner is qualified, require real 503 queue-saturation, three bounded idempotent read attempts, true recovery without daemon restart and idle socket reopen without replay. macOS/Windows full wallet also requires real lost-broadcast-reply reservation retention, native Sign/Broadcast approval and CLI-free operational snapshots.

## All operating systems, native AND final frozen

- macOS ARM64: original signed Core, native Qt/source and executed final app/DMG.
- Windows x64: signed Core, native GUI and executed packaged EXE.
- Linux x86_64: separately qualified developer Core/root witness, native Qt/headless and executed frozen desktop/headless.

The actual source/frozen operators and builders now reject absent or incompatible T-09 receipts. The receipt retains platform, measured height, frozen_entrypoint, mainnet_allowed=false, synthetic_rpc=false, physical_accepted=false and dev_reviewed=false. Unit-derived test fixtures never qualify as a genuine Core E2E.

## T-09 limitations explicitly PENDING

- **Cookie:** the supported managed REGTEST profile uses its strict owner-private wam.conf and not Core cookie authentication. A live invalid-cookie test or general cookie-based foreign-Core attach is NOT qualified; do not weaken T-06 or adopt an unrelated node.
- **Wrong chain/genesis, malformed/oversize JSON, timeout:** fail-closed offline/parser/negative tests exist and remain required, but do NOT count them as genuine foreign-chain Core runtime evidence. Mainnet is never contacted.
- **Solo-miner coexistence:** current real RPC saturation comes from 32 genuine Core long polls on disposable REGTEST, not an owner's active miner. Long-duration simultaneous external miner/wallet acceptance remains separate.
- **Physical Windows console flashing**, real Windows10/11 UI, macOS Finder, Linux desktop, Codex/DEV review and physical acceptance remain PENDING. Existing CREATE_NO_WINDOW is only a tested mitigation.

Per-core real test success does NOT mean that all Issue #45 P0, Q01–Q20, human, physical or independent-review gates are complete. Missing, SKIP, or changed-head evidence must not be promoted. No real funds, mainnet, auto retry of uncertain writes, default config mutation, upstream change or automatic merge.