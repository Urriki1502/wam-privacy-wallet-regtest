# Issue40 — experimental V1 foundation

Production is a product objective, not an achieved security qualification.
RC1 SHA144d877 remains immutable; this new stack builds on owner-audit docs995ff12.
No mainnet/public network, original mining datadir or owner's backup is accessed.

## Inspection, 16 October 2026

Live main50e1ea94; open Drafts18–39 inspected, latest code427d3b0/docs995ff12.
No BIP39/native Core import/persistent online implementation exists in that stack.
wam-security c9b1ce872c2b0b65276883d4e210b6a2f7c96467 already tests native
backupwallet/restorewallet and wallet state; reuse Core operations, not key parsing.
wam-privacy db3d2dcaa540f1129d540101813b761167d33174 supplies fail-closed privacy
policies, not seed derivation. WSP default HEADdcf1aecc00a64bfad3151fa202c3e07d47d83e69
has unchanged tree relative to pinned ac55f13423620252bdbf848c7e8a280c3b84721e;
pin stays fixed. Its native hd.ExtendedPrivate accepts16–64bytes; Keyring/backup
accept only32bytes. WAM current main64b4cb01a202399d7e11a89b40e8de72131639bc;
latest published release remains prereleasev0.1.11. No v0.1.12 adoption.
Core release source src/wam/chainparams.cpp confirms REGTEST genesisb88f3d26…,
wamrt HRP and test extended-key versions. WAM is a pinned Bitcoin Core28.1 overlay.

## Version and account boundaries (implemented contracts)

- RC1 WSP keys/backup algorithm/version never reinterpreted as mnemonic wallets.
- New profile fusion-bip39-bip32-bip352-regtest-v1: English BIP39 128/256bit entropy,
  12/24words, NFKD, PBKDF2-HMAC-SHA512/2048 to64bytes, ALL64bytes to native WSP
  BIP32 master. Spend m/352'/1'/account'/0'/0; scan m/352'/1'/account'/1'/0.
  Coin1 is the standard test-network namespace, bound to the exact WAM REGTEST
  genesis and wamrtsp code. Retain the existing16-account/epoch limit.
- WAM Core SQLite descriptor account is a separate model. Require actual native
  getwalletinfo.format=sqlite/descriptors=true and independent live chain+genesis;
  a SQLite header or .dat suffix cannot attest wallet type, ownership or network.
- Core getbalances.mine.trusted can include unconfirmed change. Never label it
  confirmed/spendable without separate UTXO/locks/height evidence. Expose native
  trusted, untrusted_pending and immature separately; unpaid pool earnings absent.

## Required security design before integration

Mnemonic generation uses the verified Trezor reference library, no alternate ECC,
BIP32, BIP352 scanner, signature or PSBT implementation. Optional BIP39 passphrase
is distinct from the application unlock password; a different BIP39 passphrase
produces another valid wallet and cannot be diagnosed from checksum alone.
No mnemonic logging/clipboard/telemetry/screenshots or plaintext persistence.
Python/native temporary memory cannot be guaranteed wiped. New profile backup
must have an explicit discriminator and preserve OS anchor/lease/crash ordering;
old WSP-only restore functions must never silently accept new profile ciphertext.

Core import MUST use backupwallet/restorewallet/loadwallet on a protected COPY,
never custom SQLite/key/descriptor parsing or source mutation. Account public
observations never contain private descriptors. First engine accepts only
explicitly generated disposable REGTEST fixtures, not an arbitrary owner file.
A native database may not carry a trustworthy recoverable network discriminator;
loading into a REGTEST node alone does not prove original network. General import
remains closed until source provenance/network compatibility is evidenced.
Windows reparse/owner-DACL, POSIX ACL/ancestor/link checks, duplicate identity,
Core-native lock contention and crash cleanup are mandatory before GUI exposure.
Real Mac fixture confirms restorewallet permits simultaneously loaded clones of
the same keys. The new contract rejects exact public descriptor-set duplicates
independently of local wallet names/next indices; this is not a persistent global
identity registry or a proof against partially overlapping descriptor sets.
No database/key material may be uploaded in CI artifacts, including fixture DBs.
Cross-OS .dat interchange therefore needs a separately authorized private test
transport; public receipt JSON alone cannot demonstrate interchange.

Persistence must retain one chain and durable identity across restart, unlike RC1
fresh-chain recovery/epoch rotation. Preserve signed/uncertain reservations,
anchored encrypted state and same-wallet lease; do not rebuild old locks from chain
alone. Core-private traditional keys stay Core-owned and are not converted to BIP39.
Online sync follows separately verified REGTEST/local-node policy first. No remote
endpoint or peers are enabled by this foundation. Mainnet requires explicit owner
authorization, DEV review, external review and signed/notarized platform releases.

## DEV WAM decisions (not invented parameters)

SLIP44 registers WAM coin5718349; this is evidence, not approval of an entire
production BIP352 account/recovery/birthday/descriptor profile. DEV must confirm
production paths, address/descriptor compatibility and future migration semantics.
Mainnet profile rejected. Real-fund import, OS anchor portability, whole-system
rollback, power loss and physical acceptance remain unqualified.

Primary specifications: [BIP39](https://github.com/bitcoin/bips/blob/master/bip-0039.mediawiki),
[BIP32](https://github.com/bitcoin/bips/blob/master/bip-0032.mediawiki),
[BIP352](https://github.com/bitcoin/bips/blob/master/bip-0352.mediawiki),
[SLIP44](https://github.com/satoshilabs/slips/blob/master/slip-0044.md),
[Core v0.1.11](https://github.com/wamcoin-core-dev/wam-coin/tree/v0.1.11).

## PR-A local evidence

Four boundary contracts PASS. [Native macOS Core fixture PASS](evidence/production-v1/PR_A_CORE_FIXTURE.json);
Windows/Linux fixture and interchange remain
PENDING. Reproduce with the pinned source/native Core and GUI test environment:

```sh
PYTHONPATH=src python scripts/v1_core_fixture_probe.py \
  --core /absolute/verified-core --wsp-source /absolute/pinned-wsp \
  --output /absolute/new-public-receipt.json --confirm-disposable-regtest
```

The fixture generates its own Core wallet and .dat via backupwallet, mines only
its own REGTEST, restores through Core, checks owned receive address/amounts and
unchanged source bytes. No external .dat argument exists. Databases and private
Core replies are destroyed; receipts contain only categories/booleans/hashes of
the official Core binary, never descriptor text, mnemonic, key or database.

## PR-B implemented engine (not yet an operational persistent wallet)

`bip39_wallet.py` reuses Trezor python-mnemonic0.21 (tag commit
 d4b106cdec196202d44628026fcb8fedc8ea50c1). The exact English2048-word corpus is
SHA2562f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda;
runtime checks that canonical corpus. Reference generation uses secrets.token_bytes.
No second ECC/BIP32/BIP352/scanner/signature implementation was introduced.
All64PBKDF2 bytes go directly to the pinned native silent_key/ExtendedPrivate.

Implemented: opt-in disposable REGTEST generation12/24; strict English/checksum/
count/profile validation; NFKD phrase/passphrase handling; deterministic native
scan/spend derivation and public wamrtsp code; redacted secret-object repr;
closed-key refusal and best-effort clearing of the owned seed bytearray. CSPRNG
phrases/seed are never logged/persisted/copied to clipboard by this engine.
Immutable Python/library/native copies can remain; this is not memory forensics
protection. Caller-owned ScanAccount contains scan secrets and must not be logged.

Eight shared contracts PASS locally, including all16 supported public Trezor
English128/256bit vectors, exact64-byte seeds, published root xprv serialization,
explicit native BIP352 paths, same-code restore, NFKD, random generation roundtrip,
invalid words/checksum/18word/profile/consent, wrong types/Unicode and closed state.
These are standards/negative contracts, not mock Core E2E. Test data contains
ONLY globally published vectors, never generated application wallet phrases.
Failure assertions deliberately do not format phrases, seeds or xprv values.

The new real-Core receive probe creates24words in memory, restores independently,
receives an actual confirmed BIP352 payment, compares two independent native WSP
scanners, and reopens SQLite without reprocessing blocks. It never enables signing
or persists seed/DB/phrase in artifacts. Only the final completed matching-source
receipt counts. A preliminary driver missed the mandatory attest; another treated
Metrics as an integer. Both refused/faulted and are not counted as PASS.

Cross-platform vector checks are added to existing Windows/Linux native contract
jobs; macOS already discovers alltests. No new workflow/job or removed security
assertion. Windows/Linux new-engine execution remains PENDING until live CI proof;
source/runner evidence does not qualify a new GUI/frozen feature. The RC1 packaged
regression remains separate from new BIP39 operational acceptance.

Next: native onboarding state/phrase confirmation, then a separately versioned
custody bridge and durable wallet identity before GUI activation/signing. BIP39
keys alone do not restore irreversible reservations/anchors. Never mint a fresh
anchor to bypass pre-existing same-wallet state or reinterpret RC1 backups.

[Completed macOS BIP39/Core/WSP/SQLite receipt](evidence/production-v1/PR_B_BIP39_CORE.json):
24words ->64bytes -> native WSP -> real confirmed receive4749990000atoms at103;
original/restored scanners and SQLite restart agree. Engine source hash matches
the committed implementation. [Unchanged signer/security auditor](evidence/production-v1/PR_B_SECURITY_AUDIT.json) PASS.
All140 local contract tests:107PASS/33SKIPPED/0FAIL (native foreign-platform skips
are not acceptance). Windows/Linux native new-vector CI still pending at commit.
