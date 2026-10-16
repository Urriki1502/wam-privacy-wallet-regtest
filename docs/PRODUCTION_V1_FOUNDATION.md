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
