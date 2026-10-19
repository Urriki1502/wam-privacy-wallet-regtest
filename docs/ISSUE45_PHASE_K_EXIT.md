# Issue #45 — Phase K engineering closure and outstanding acceptance

**Network:** WAM REGTEST only. Never use real wallet keys, miner datadir, mainnet, signer authority for a restored wallet, unattended broadcast, cross-OS anchor copying or automatic residue cleanup.

**Integration:** K-09 Draft PR #90 is the base of K-10 Draft PR #91. Preserve PR ancestry. No automatic merge.

## Evidence categories

Report SOURCE_PASS, CORE_E2E_PASS, FROZEN_PASS, PHYSICAL_ACCEPTED and UPSTREAM_REVIEWED independently, with exact HEAD, signed/developer Core artifact hash, pinned WSP source and actual platform. Green CI is not a substitute for a missing test scenario. SKIP is not PASS.

| Scope | Implementation evidence | Outstanding P0 qualification |
| --- | --- | --- |
| K-01–K-03 | BIP39/WSP derivation, encrypted custody, original-wallet signed REGTEST workflow | Final source/frozen/physical grid |
| K-04–K-06 | Isolated Core-native SQLite restore and descriptor/account isolation, BDB refusal | Six actual cross-OS Core SQLite handoffs and final clean-OS GUI |
| K-07–K-08 | Native Keychain/Credential/root-witness anti-rollback and separate portable recovery contracts | Actual owner-approved native anchor commissioning on the new machine |
| K-09 | Crash-residue forensic ledger, native encrypted stage inspection, owner-approved read-only Core risk inspection | Safe irreversible reservation handling, mempool/reorg proof, physical crash/recovery |
| K-10 | Deterministic WSP identity, encrypted backup parity, clean-host preflight, authentic isolated Core SQLite source-to-target smoke integrated into native CI | Six cross-machine transfers, frozen clean-OS wallet recovery, complete history/reservations and actual signed semantics per OS |

## Genuine Core-native SQLite tests

K-10's same-OS smoke creates a fresh disposable Core-native REGTEST SQLite backup containing only disposable test keys; stops the source Core; starts a separate isolated Core; invokes Core's restorewallet; compares public descriptor identity; checks source/target bytes unchanged; and refuses all Fusion signer/broadcast authority. Never publish the private backup as a CI artifact.

- macOS ARM64: signed official Core on the real-core-regtest CI lane.
- Windows x64: signed official Core on the native operational CI lane.
- Linux x86_64: reviewed developer-built Core in the existing root-witness-controlled native Qt/headless CI fixture; NEVER call this an officially signed Linux build.

Successful smoke attests only the executed same-OS Core SQLite restore. Mocked unit tests, frozen/physical portability, actual signed payments and the six cross-OS directions have separate evidence requirements.

## Six cross-OS source and target cases

| Source | macOS ARM64 | Windows x64 | Linux x86_64 |
| --- | --- | --- | --- |
| macOS ARM64 | Same-OS native smoke | PENDING | PENDING |
| Windows x64 | PENDING | Same-OS native smoke | PENDING |
| Linux x86_64 | PENDING | PENDING | Same-OS native smoke |

Each cross-machine qualification requires trusted source/target SHA, frozen artifact SHA-256 where applicable, exact Core binary provenance, REGTEST chain, unchanged private offline backup digest, Core restorewallet response, same public descriptors, and owner/OS-native custody evidence. Never publish a mnemonic, seed, Core wallet backup, private descriptor, RPC cookie or anchor material.

## Recovery and signing boundary

The original independently owned REGTEST wallet has its own manual authenticated GUI Send / Sign flow. That is NOT a right to unlock a transplanted or crash-ambiguous wallet. A restored wallet must remain LOCKED until K-09 signed/uncertain reservation risk and mempool/reorg uncertainty are safely resolved, a fresh legitimate destination OS anchor is commissioned, original scanner history is reconciled and frozen GUI clean-machine continuity is verified. No hidden unlock, cleanup, signer replay or override.

## Development handoff

K-10 engineering may be considered code-complete only after the current native Core smoke results PASS on exact HEAD. Mandatory P0 missing physical/recovery tests remain PENDING and are NOT waived. Starting Phase F in a separate sequential PR does not mean Phase K P0 passed. Do not add Phase F scope inside PR #91.
