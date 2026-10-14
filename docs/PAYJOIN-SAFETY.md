# PayJoin Safety — canonical PSBTv2, validation-only

Status: **experimental REGTEST-only sender-side validation foundation**, not PayJoin (BIP78/BIP77) wire support. No new signer, Core RPC write method, broadcast capability or GUI action is added.

## Source and scope

Conservatively adapted from [wam-privacy Phase 4](https://github.com/Urriki1502/wam-privacy/blob/main/docs/PAYJOIN-SAFETY.md). Unlike the old transaction-shape prototype, `wam_regtest.payjoin_safety` parses **real immutable PSBTv2 bytes** using exact pinned `wam_sp.psbt.PSBT.decode` from WSP commit `ac55f13423620252bdbf848c7e8a280c3b84721e`. Input/UTXO claims are independently compared against scanner-owned outpoints and the existing attested WAM Core REGTEST `gettxout` read RPC.

### Strict policy

- The original is a **locally created unsigned PSBTv2**, not a remote annotation.
- All original sender inputs are retained in order, sequence/UTXO/script/metadata unchanged; no sender signatures.
- One to four genuinely additional, non-wallet-owned P2TR inputs are required. Each added input must carry a single finalized BIP340 Schnorr witness with **SIGHASH_ALL**, verified against the **new complete transaction**. No exposed keypaths, incomplete signatures or unknown extra input fields.
- Version, locktime, output amount/script, output metadata and global map must remain exactly unchanged. No output substitution, fee contribution from change, receiver batching or extra destinations.
- UTXO amounts/scripts of **every** input are independently verified via attested local Core RPC; chain tip checked before and after; absolute fee must not decrease or exceed 0.01 WAM.
- Only coarse redacted PASS flags returned. No transaction bytes, outpoints, amounts, addresses, keys or signature material are published as receipts.

### Mandatory BIP352 limitation

**PSBTv2 parseability does not imply safe BIP352 PayJoin.** The BIP352 sender proof and payment output depend on the full set of input public keys/outpoints. Adding a receiver-owned input invalidates the original derivation if the payment output and proof stay fixed.

Therefore any original or proposed PSBT with WSP BIP352 sender/recipient metadata is rejected using `PJ_BIP352_REDERIVATION_UNQUALIFIED`. Future BIP352 PayJoin would need a separately reviewed input-set-rederivation, receiver binding proof and signing authorization extension. **Do not delete this guard to obtain a positive PayJoin E2E.**

### Evidence distinction

- **Offline unit contracts:** generic native PSBTv2 encoding/parsing, real BIP340 Schnorr signature verification, hostile output/script/amount/keypath/UTXO/fee changes, attestation scope, no new authority. Offline fake RPC exists only inside unit tests.
- **Real WAM Core E2E:** the native disposable wallet builds an actual WSP BIP352 PSBTv2 from genuine Core-confirmed coins; its PayJoin inspection fails closed **before** the separately approved signing path. Existing real Core Send/Sign/Broadcast/recovery E2E must still PASS unchanged.
- Positive generic PSBTv2 acceptance is **not** proof of a complete PayJoin protocol or a successfully broadcast PayJoin payment.

No mainnet, third-party network endpoints, private key exporting, or real user funds.
