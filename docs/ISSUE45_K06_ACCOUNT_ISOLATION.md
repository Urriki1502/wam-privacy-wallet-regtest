# Issue #45 — K-06: Native Core versus WSP/BIP352 account isolation

**One Draft PR, only K-06.** Stacked directly on green #86 K-05. Mainnet and real user keys are out of scope.

## Actual account models

| Ownership category | Trusted original | Keys & scanner | Balance/history | Signing |
|---|---|---|---|---|
| Native Core descriptor (mining/legacy) | Core's `getwalletinfo` + `listdescriptors false` in attested REGTEST | Owned by Core wallet, **not WSP**; no key material exposed via this registry | Core UTXO observations only (coinbase maturity/treasury policies stay with mining model) | No Core signer delegated to Fusion WSP |
| Original legacy WSP 32-byte keyring | Native anchored, encrypted `Keyring` | WSP `ScanAccount` + explicit native WSP signer `spend_secret` | WSP scanner SQLite and native WSP wallet, never merged with Core balances | Only after original anchor, real owned-Core and exact-intent approvals |
| Full 64-byte BIP39 WSP | Native anchored `Bip39DurableKeyring` with K-02 versioned REGTEST derivation profile | WSP `ScanAccount` and spend secret from 64-byte BIP39 seed | Separately owned WSP scanner SQLite | Same exact-intent WSP Signer; **not** a Core `.dat` key provider |

**No conversion inference:** A WAM Core SQLite `.dat` is a Core-native descriptor wallet and cannot be recreated from a Fusion mnemonic merely because both use REGTEST or display similar addresses. A BIP39 mnemonic is not the legacy 32-byte WSP seed. No balance aggregation, auto-sweep, shared seed, fallback signer or cross-authority API.

## K-06 code changes

- New `account_isolation.py` immutable `CoreAccount`, `WspAccount` and `AccountRegistry`; read-only and key-free. Core identity comes from public `listdescriptors(false)` only; refused malformed, wrong-chain, wrong-format, BDB/private-descriptor and duplicate/partially overlapping Core wallet descriptor sets even if named differently.
- Registry allows **multiple Core wallet aliases** with disjoint public descriptor sets and multiple WSP account epochs/wallets, while refusing duplicate WSP scan/spend account identities, duplicate epochs for one wallet, mismatched per-wallet legacy/BIP39 profiles, and attempted Core ↔ WSP authority crossover. WSP registry routes only READ/SCAN, **never SIGN/BROADCAST**. Native sender permissions must separately flow through existing vault/anchor lease and exact transaction approval state machine.
- On WSP wallet creation, fail before first native anchor publication when native scan/spend, scanner account mapping or profile is malformed. On **every managed spending session reopen and snapshot**, recheck real native `Keyring` or `Bip39DurableKeyring` derived spend public key against the stored scanner account and native vault ID. Original managed read-only snapshot enforces the same account binding. The existing Q05 mock contract fixture remains explicitly mocked; independently tested K-06 native account checks are required on real pinned WSP in CI.
- Real Core K-04 backup `→` REGTEST quarantine restore is extended ONLY with K-06 public account-identity checks: original and restored descriptor sets MUST match, while attempting to register them as two separate owners must be denied. Mac ARM64, Windows x64 and Linux native/root-witness verify these extra facts on actual Core binaries. No persistent miner/owner Core datadir or WSP account is imported, changed or loaded.

## Remaining qualification and deferred scope

- Registry is **ephemeral read-only** and regenerated from trusted observations; it does NOT replace the Core wallet registry, native vault anchor, single-writer lease or the K-08 clean-device recovery contract. No second on-disk registry, duplicate secret cache, extra RPC permission or wallet import flow introduced.
- Multi-account registration and duplicate/overlap are tested with native WSP keyrings and public Core descriptors, but **loading multiple real Core mining/legacy wallets into the same managed Core** remains intentionally disallowed until its separately signed ownership/provenance and registry lifecycle are qualified.
- Physical clean-OS, live-wallet duplicate/reconciliation, encrypted native Core accounts and Codex/DEV review are still PENDING. Existing T05/K03 multi-OS Core/WSP GUI E2E and all 28 canonical BIP352 vectors remain mandatory; no job SKIP counts as acceptance.

No auto-merge, mainnet, owner's miner, live funds, or K-07 platform-custody changes.
