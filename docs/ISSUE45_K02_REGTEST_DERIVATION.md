# Issue #45 — K-02: Immutable REGTEST BIP39 → BIP32 → BIP352 derivation profile

## Qualified scope

This is one K-02 Draft PR. The existing K-01 BIP39 12/24-word engine yields the FULL 64-byte PBKDF2 seed. K-02 freezes the *experimental REGTEST* derivation identity that existing PR #43 used and makes it an explicitly testable, versioned, fail-closed public contract. This **does not** convert a legacy WSP 32-byte seed to BIP39, does not create a durable vault or authorize mainnet.

| Parameter | Exact K-02 value |
|---|---|
| Schema | `wam-fusion-regtest-bip352-derivation/v1` |
| Profile | `fusion-bip39-bip32-bip352-regtest-v1` |
| Purpose | 352' |
| REGTEST/testnet coin type | 1' |
| Account | Hardened 0' through 15' only |
| Spend branch | `m/352'/1'/account'/0'/0` |
| Scan branch | `m/352'/1'/account'/1'/0` |
| Chain/genesis | `regtest`, pinned WAM REGTEST genesis |
| Accounts | One public WSP BIP352 receive code per index |
| Legacy WSP Keyring | **INCOMPATIBLE**, no silent interpretation |
| Mainnet/production | **NOT APPROVED** |

The exact record also contains `version=1`, `account_limit_exclusive=16`, account index, spend and scan roles, the network genesis, no-mainnet, no-production and no-legacy-conversion policy. A canonical JSON SHA-256 fingerprint makes profile drift visible to future K-03 encrypted wallet metadata and recovery contracts. This fingerprint is NOT a signature, permission token or custody authentication; an attacker can forge JSON and recompute hashes. Any actual wallet profile must be anchored under independent native custody and checked against keys derived from the authenticated seed.

## Changes

- Centralize REGTEST purpose/coin/account limit/roles in `v1_contracts.py`. The native BIP39 wallet *uses this same contract* for WSP `silent_key(...)`, rather than passing a separately hardcoded coin type that could diverge from the displayed path.
- Add `derivation_profile_receipt()` and exact `require_derivation_profile_receipt()` with strict account-index type checks and whole-record equality. Wrong profile, legacy WSP, mainnet type, path/role substitution or even unknown extra fields fail closed.
- `Bip39RegtestKeys.public_metadata(account)` now includes this non-secret derivation receipt, and `require_public_metadata()` verifies seed-derived receive code, account ID, exact path, network and fingerprint before a future K-03 restore accepts an identity. No phrase, seed, private key, RPC password or encrypted wallet data is serialized by these public methods.
- New public-data unit tests across all 16 account index paths, fixed golden profile SHA-256 fingerprints at indexes 0/1/15, negative tamper tests, real 64-byte BIP39 seed-derived WSP scan key checks and deterministic account-specific receive code restore using the pinned native WSP implementation. Existing 16 Trezor BIP39 and 28 WSP canonical BIP352 vectors remain mandatory.

## Mainnet is *not* implied by coin type

`coin_type=1` here is reserved strictly for WAM **REGTEST** compatibility. It is **not** a claim that WAM mainnet uses SLIP-44 index 1, Bitcoin's mainnet coin type 0, or any other guessed number. Future mainnet derivation, address prefix, network rules and cross-device recovery require written upstream WAM DEV confirmation, a NEW explicit profile/version, independent fixed vectors and security qualification. Never silently reinterpret a REGTEST backup under a changed or newly approved mainnet profile.

## K-03 and subsequent work still pending

K-02 does **not** persist a BIP39 seed, import it into the original managed WSP signer, authorize Send/Sign/Broadcast, bind OS-native anti-rollback, do a clean-device restore or convert an existing 32-byte seed. K-03 must implement that durable seed-to-signer link without dropping the existing fail-closed wallet identity/lease/reservation chain. K-08 defines portable recovery and native anchor continuity. No physical/production/reviewer acceptance is asserted by unit suite results.
