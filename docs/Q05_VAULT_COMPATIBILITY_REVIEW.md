# Q05 Stage B vault compatibility review — 27 October 2026

Design review only, responding to the owner-listed DEV WAM concerns. No vault,
KDF, AEAD, storage, native anchor or envelope migration is implemented here.
Scope is the current main custody/vault contract plus pinned WSP commit
`ac55f13423620252bdbf848c7e8a280c3b84721e`, `src/wam_sp/keystore.py`.

| Concern | Current contract | Stage B decision / unresolved work |
|---|---|---|
| Versioned format | WSP magic `WAMSP02\x00`; outer encrypted payload has custody-specific version 1 macOS, 2 Windows, 3 Linux, strict field/type equality and REGTEST genesis/wallet/generation. | These are distinct encryption/payload/platform versions. Preserve existing reader/writer and pin. No speculative new fields in legacy envelopes. |
| Explicit KDF parameters | WSP `_key`: scrypt N=32768,r=8,p=1,32-byte output; 16-byte random salt, password bytes length 12–1024. Parameters are code/version implied, **not self-described in the header**. | Document exact legacy parameters. A future self-describing format needs a new authenticated version plus allowlisted algorithms and resource bounds before KDF; no silent parameter change under old magic. |
| AEAD extensibility | AES-256-GCM, 12-byte nonce, 16-byte tag. AAD binds magic, REGTEST genesis and purpose (vault uses `recovery`). Payload binds identity/generation inside encryption. | No current algorithm negotiation. New AEAD suite would require a separately reviewed format/version and explicit migration, downgrade refusal and legacy regression vectors. No crypto redesign in supervisor integration. |
| Authenticated chunks | Current envelope is one bounded AEAD message (max 32 MiB plaintext); no chunk sequence/final marker framing. | Whole-message tag refuses truncation; it is **not streaming chunk authentication or partial recovery**. Do not parse partial plaintext. If chunking is later justified, authenticate header, wallet/network/generation, index/count/length/final marker and a complete manifest, with nonce uniqueness; reject reorder/duplication/omission/truncation. Keep outside current Stage B unless separately approved. |
| Atomic publication | macOS `encrypted_storage.publish`: private create-only staging, full writes, fsync file, no-overwrite hard-link publication, unlink staging, fsync directory; native Win/Linux equivalents. Vault then advances native anchor under lease/CAS. | Publication and anchor advancement are not one cross-resource atomic transaction. Interrupted stages and publish-before-anchor orphans must remain visible/refused. Do not delete residue, reset anchors, overwrite generations or treat latest filename as authority. |
| Clean-device restore | `CheckpointVault.restore` requires native platform anchor and authenticated exact generation/digest; fresh runtime, keyring/scanner restore then real-chain resync. Missing anchor fails closed. | Copying ciphertext/OS anchor is not qualified clean-device bootstrap. Need explicit legitimate-owner bootstrap/recovery policy, account identity, source version and complete checkpoint reconciliation before activation, preserving signed/uncertain reservations. No silent rollback or fresh anchor based solely on a password. |

Legacy layout: 8-byte magic + 16-byte salt + 12-byte nonce + ciphertext/tag;
minimum 52 bytes. `unseal` authenticates the whole bounded envelope before JSON
parsing. Vault ciphertext digest must match the separately held native anchor.
Nested keys/checkpoint backups use their own purpose separation. Native custody
profile differences explicitly prevent assuming cross-platform file portability.

Before Stage B enables recovery, test each boundary: partial/truncated/bit-flipped
stage and published envelope; bad password/tag/purpose/genesis/version; resource
limit; fsync/publication error; crash before/after publish and anchor advance;
orphan/divergent generation; missing/stale/foreign native anchor; competing owner;
fresh runtime sidecars; signed/uncertain reservation persistence and no broadcast
replay. Test actual native storage on each OS and final packaged entry separately.
Existing failure/refusal tests are evidence of safe denial, not successful
interrupted-write or clean-device recovery. The independent review remains open.

Smallest compatible Stage B: keep the legacy vault envelope intact, add explicit
supervisor lifetime ownership and narrow scanner adapter, then design a durable
recovery journal and owner-authenticated bootstrap as separate tested units.
Do not import historical format/keyring/account migrations to satisfy imports.

Source references in this repository: `src/wam_regtest/vault.py` (`save`,
`_load_payload`, `restore`), `custody.py` (`envelope_profile`, `anchor`),
`encrypted_storage.py` (`publish`, `read`) and native Windows/Linux storage.
The pinned WSP keystore was read from the actual `ac55f134…` Git object, not an
unverified bundled copy. This review provides no production or mainnet approval.
