# Issue #45 — K-08 Portable recovery: provenance and clean-device owner preflight

**One K-08 Draft PR stacked on K-07 #88. REGTEST-only. No silent successful restoration claims.**

## Four distinct authorities

| Operator-held material | What it can reconstruct | What it CANNOT reconstruct |
|---|---|---|
| 12/24-word BIP39 + exact optional passphrase + K-02 account index | K-02 profile: BIP352 scan/spend private keys and receive codes deterministically on a clean device, subject to authentic source and profile verification | Native Core descriptor keys from a separate Core `.dat`, legacy 32-byte WSP wallet keys, wallet reservation ledger, historical labels/notes, native OS anchor or full prior confirmed transaction history |
| Verified Core SQLite descriptor `.dat` | **Core-owned** legacy/mining account only through explicit supported WAM Core restore/quarantine; K-04 read-only inspection in GUI, no active wallet importer | Fusion BIP39/WSP account, Fusion encrypted checkpoint, OS anchor |
| Fusion native-encrypted `.enc` state | Existing WSP keys/history/reservations **only with original vault password + valid native OS anchor/lease and matching Core identity** | Portable unanchored profile on a different OS, another person's Core `.dat`, user seed phrase |
| macOS Keychain / Windows Credential Manager / Linux root witness | Current local anti-rollback continuity for original wallet and generation | Portable seed, keys, cross-device authority; **copying anchor is forbidden** |

## Implementation and strict scope

`portable_recovery.py` provides a typed four-mode plan with non-secret, explicit caveats and an actual 64-byte-seed BIP39 cryptographic preflight using the pinned original WSP source and the exact K-02 REGTEST derivation contract. A trusted prior **public metadata receipt** (full payment code and account identity, K-02 profile, account index, genesis) is required to prove the same historical WSP account; wrong optional passphrase, mnemonic, account index, role, profile or chain must reject. No secret/mnemonic/payment code/path is returned or logged. Mnemonic and optional passphrase are processed in local memory only and erased best-effort on keyring close.

**Current positive evidence**: only `K08_BIP39_ORIGINAL_PUBLIC_IDENTITY_VERIFIED_LOCKED`; all signer/broadcast/balance/history/native anchor/old state restored flags stay **FALSE**. A cryptographic public match is **not** operator-native ownership authentication. The preflight never creates a wallet, deletes an old vault, restores Core `.dat`, loads a legacy WSP seed, copies an OS anchor, scans through Core, unlocks/sends, or claims the original state is recovered.

`require_safe_bootstrap_prerequisites` rejects an existing encrypted vault or SQLite runtime/WAL/journal/crash residue in the target profile, unknown devices, unverified Core, missing owner-native authentication and missing historical reservation/reorg reconciliation. A positive result is **REVIEWED ONLY, wallet_created=False, signer_allowed=False**, not permission to spend. These are operator-input contracts, not cryptographic proof that a clean OS or native Keychain has actually been provisioned.

## Remaining mandatory P0 gates before K-08 is accepted

1. Explicit clean-device native OS custody bootstrap and credential/keychain/root-witness enrollment in a genuinely new profile, without copying old OS anchor. Native `create_managed_wallet` already independently rejects ambiguous pre-existing vaults; any new recovery-specific use must additionally bind the exact prior trusted public identity and never auto-adopt old profile files.
2. Safe WSP scan from a verified REGTEST Core, independent chain tip and replay/reorg validation; reconstruct confirmed coins from chain and distinguish that from restored history and reservation ledger. A mnemonic **alone** cannot tell whether a previous signed/broadcast/uncertain transaction exists on another wallet/host. Restrict signing until those reservations are reconciled.
3. Native Core `.dat` import remains the separate K-04 quarantine/DEV-vetted pathway; Fusion `.enc` portable restoration must not bypass OS anchor anti-rollback. K-09 owns crash/orphan checkpoint rescue after exact ledger proof. BDB Core migration remains the **last deferred backlog** in #45, never a hand-written converter.
4. Three-OS synthetic clean-device receipt/seed/grid test: same derivation and WSP payment code, actual native Core transactions, same-account and wrong-account denial, backup-loss/corruption, disk-full and clean-OS portability, frozen app and independent human/DEV/Codex review.

**Do not call K-08 full restore PASS** merely because these preflight contracts or K-02 vectors pass. Real funds/mainnet, live owner's old wallet `.dat`, hidden Core access and automatic signer adoption are not allowed.
