# Issue #45 — K-01 native BIP39 creation and backup confirmation

## Scope and provenance

One K-01 Draft PR, stacked exactly on T-09. Reuses existing K/BIP39 engine in `bip39_wallet.py`: 12 words from 128-bit CSPRNG entropy or 24 from 256-bit CSPRNG entropy, checksum/English 2048-word-list SHA pin, BIP39 NFKD normalization, optional passphrase and 64-byte BIP39 seed. Public reference vectors in `tests/test_v1_bip39.py` verify 16 Trezor 12/24-word cases, BIP32 and WSP receive addresses on the experimental REGTEST profile.

The GUI now exposes a **separate** `BIP39 backup words (not wallet)` action in `ManagedCoreWindow`, available even when Core is offline. It requires an explicit acknowledgement, creates the local English BIP39 phrase, shows numbered words solely for an offline written backup, and hides them before requesting the user to type **all** words in the exact original order. Optional passphrase and confirmation are masked, with an explicit passphrase-loss warning. After exact phrase and passphrase confirmation, it exercises the local 64-byte PBKDF2 seed derivation (best-effort zeroizes the temporary bytearray), clears all widgets and reports **only** a non-secret confirmation status. Cancelling/failing also clears displayed words, confirmation and passphrase fields. No clipboard, export, file write, GUI screenshot, automated logging, Core RPC, signing, wallet mutation or background upload is part of this flow.

## Do not conflate new mnemonic with live Fusion wallet

This K-01 dialog **does not create, unlock, rotate, restore or provision an original Fusion WSP wallet**. The existing `Create legacy WSP wallet (NOT BIP39)` button still uses a legacy WSP keyring and native encrypted checkpoint. That wallet CANNOT be restored from the K-01 phrase. K-02 must finalize versioned BIP32/BIP352 derivation and account semantics; K-03 must bind a 64-byte BIP39 seed to OS-native custody, encrypted checkpoint and signing/recovery. The experimental PR #43 engine and current GUI wizard are not substitutes for those milestones. No old 32-byte seed is reinterpreted as mnemonic. No external Core, mainnet or real funds.

## Tests and remaining gates

- Existing engine tests: genuine CSPRNG 12/24 generation, checksum, wordlist pin, 16 standard reference vectors, NFKD passphrase equivalence, deterministic receive addresses.
- New Qt tests: explicit consent, 12/24 choice, phrase display then forced hide, complete backup re-entry, incorrect words/passphrase refusals, optional passphrase acknowledgement, post-verification secret field clearing, cancellation, redacted errors, non-persisting result. Main managed GUI action does not contact Core or create a legacy wallet.
- macOS/Windows/Linux native unit suites and existing genuine Core/WSP + final frozen GUI E2E must stay green on the new SHA. Unit GUI tests are not proof of human backup usability or OS screenshot protection.
- Physical operator view of mnemonic flow and QA on 3 operating systems, screen-reader/accessibility, external security review, secure memory zeroization and OS-level screenshot prevention are **not claimed**. Python immutable strings and Qt widgets can hold residual plaintext; a compromised OS or screenshot software is out of this workflow's protection.

All PR CI and independent reviewer gates remain separate. Do not auto-merge, auto-backup a phrase, display words in artifact logs/screenshots, or accidentally claim this phrase protects the current wallet.