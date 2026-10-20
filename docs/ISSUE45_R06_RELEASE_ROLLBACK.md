# WAM Fusion — R-06 Release / Update / Rollback Operator Policy

**Issue #45 / R-06 [P0] — READ BEFORE USING ANY CANDIDATE BINARY.**

This is the portable *operator procedure and stopping rule*, shipped with all
WAM Fusion **REGTEST-only** packages. It does not authorize updating WAM Core,
moving an existing live wallet, mainnet use, signing or unattended recovery.
The code in `r06_release_transition.py` reads PUBLIC manifests and performs
a conservative transition classification; it **never acts** on a wallet.

## 1. Freeze and authenticate the proposed release — before execution

1. Confirm this is a disposable REGTEST environment, with no existing
   personal funds, production keys, external miners or mainnet/testnet peers.
   Record exact candidate source SHA, native OS/architecture, Core version,
   `wamd`/CLI SHA-256, independent Core provenance, WSP pin, native custody
   schema, bundle archive SHA-256, complete dependency list and workflow IDs.
2. Obtain successful **exact-source** independent macOS ARM64, Windows x64
   and Linux x86_64 **source + real Core/WSP E2E + final frozen entrypoint**
   receipts as applicable. Mark missing/SKIP as PENDING, changed bytes as
   STALE, and failures as FAIL. An old green workflow is not evidence
   for new code. The source checkout must be the exact qualified commit,
   not a PR synthetic merge SHA substituted for the approved build.
3. Authenticate official WAM Core publisher signature and exact archive/core
   members independently; Linux reviewed developer-built Core remains
   **distinct from an official signed Linux binary**. Treat v0.1.12 and any
   nonapproved version as PENDING (R-02); a valid signature alone cannot
   authorize a Core version switch. Confirm R-04 SHA256SUMS/manifest and R-05
   public privacy report. No unknown code, unsigned manifests or unexpected
   dependencies may be assumed safe.
4. macOS final app/DMG is ad-hoc and unnotarized without publisher
   authorization; Windows EXE has no Authenticode publisher signature;
   Linux executable has separately reviewed developer Core and requires
   native library/witness qualification. Keep these missing signing and
   operator gates explicitly PENDING. Never bypass Gatekeeper/AV or lower
   filesystem custody to make an unknown build run.
5. Independent owner, DEV and security review remains separate, and
   `PHYSICAL_ACCEPTED` and `DEV_REVIEWED` are not inferred from CI.

## 2. Safeguard live state — no silent migration

- Distinguish **three different assets**: (a) encrypted WSP/Fusion key
  material and reservations, (b) WAM Core-native descriptor SQLite `.dat`
  wallet and public descriptors, and (c) Fusion scanner history, native
  Keychain/Credential Manager/root-witness anti-rollback checkpoint and
  current supervisor/chain identity. None can be substituted for another.
- Stop and obtain explicit consent **before** any app replacement, profile
  change, wallet unlock, daemon restart, database migration or transfer.
  Snapshot/record the current chain, source SHA, both Core member hashes,
  account public identity, wallet maturity and outstanding signed/uncertain
  reservations in non-secret evidence, preserving every original identifier.
- With authorized disposable test credentials, use only an already-reviewed
  native encrypted backup workflow. Confirm successful latest generation and
  independent original anchor. Never put a backup/seed/.dat/cookie/private
  runtime file in CI artifacts, PR comments, chat, Git or public manifests.
- Neither source-code upgrade nor valid backup proves destination native
  custody freshness. **Never copy or reset** macOS Keychain, Windows
  Credential Manager, Linux root witness, wallet generation, anti-rollback
  record or `supervisor.profile` to fit a new release. Do not erase old
  signed/uncertain reservations, silently release coins, automatically retry
  a potentially broadcast transaction or create a fresh wallet to conceal
  restoration problems. A broken/uncertain state must remain **refused**.

## 3. Release upgrade and Core version transitions

- **Same platform, exact pinned Core/WSP:** evaluate both PUBLIC candidate
  manifests with `review_transition`; matching signatures/hashes are still
  not runtime authorization. Compare the dependency inventory and the exact
  new package artifact and independently verify its CI. Preserve old,
  authenticated artifacts and state untouched. A separate user-approved
  disposable clean profile is safer than in-place replacement; require actual
  GUI/Core/WSP reopen/recovery acceptance before modifying a live profile.
- **Different Core revision, binary digest, WSP source, database version or
  OS:** **STOP**. Obtain a new independently reviewed compatibility matrix
  for all affected Core RPC, custody, signer, scanner, SQLite descriptor,
  backup, mempool/history and GUI flows. v0.1.12 is **not approved** merely
  because it exists or is signed. Migration must be real-Core native and
  separately reviewed, never an edit to JSON hashes or a blind file copy.
- **Core legacy BDB wallet:** not a Fusion native SQLite wallet. Official
  `migratewallet` RPC depends on linked Berkeley DB support. The verified
  upstream v0.1.12 Windows x64 and macOS ARM64 binaries support it; the
  verified Linux x86_64 binary does **not**. Any migration needs explicit
  separate plan, original backup, encrypted-wallet passphrase if applicable,
  increased RPC timeout if necessary, failure handling and full descriptor
  identity check. Do **not** improvise a BDB import or promise cross-OS
  migration. Core's timestamped `.legacy.bak` is not a Fusion witness or
  a proof of protected reservations.
- **Cross-platform move:** Core-native SQLite transfer and portable Fusion
  key backup are different workflows. A valid `.dat` restore doesn't bring
  a WSP seed, signed/uncertain reservations, native anchor or scanner.
  Complete six directed source→destination Core tests and actual
  native-encrypted Fusion custody transfer must be independently accepted.
  Current portable-backup foundation explicitly says execution HOLD.

## 4. Rollback and disaster recovery — deny unsafe shortcuts

If a new release fails, **stop initiating Sign/Broadcast**, preserve the
new program and original on-disk evidence unchanged, and document the
exact chain tip, pending/mempool state, process failure, artifact identities,
backup generation and whether a transaction might have reached Core.
No automatic rebroadcast and no reset of uncertain input reservations.

Rollback an **application executable only** after an authorized operator
independently verifies the earlier exact package, OS custody compatibility,
profile-version readability, Core and WSP versions and *existing newest
checkpoint*. Do not overwrite or roll back the data/Keychain/Credential/
root-witness state. Code rollback does not imply schema rollback is safe.
If the older build cannot open the newer state safely, stop and maintain
read-only/quarantine until a reviewed forward recovery is available.

If the device or native anchor was lost, an encrypted portable blob or
Core `.dat` alone does not provide Fusion spend authority. Reprovisioning
a root witness or creating a fresh anchor to accept stale data is forbidden.
Perform recovery in a new isolated REGTEST profile only with independently
approved source identity, genuine Core chain, key and reservation continuity
and native operator consent. Reject mismatching account, chain, descriptor,
source generation, reorg or recovery evidence.

## 5. Acceptance record and release decision

Keep immutable public receipts recording source/checkout SHA, OS, native Core
binary fingerprints, independently verified trust, WSP pin, dependency lock,
packaging hashes, test environment, current Core+GUI acceptance, reviewer
identity/authority (without secret data), timestamps and separate PASS/FAIL/
PENDING/STALE statuses. The candidate becomes **REGTEST V1 release candidate**
only after complete Issue #45 B/T/K/F/R integration, the required Q01–Q20
three-OS source/Core/frozen/physical evidence and explicit DEV/security review.
Neither historical RC1 evidence nor green Draft PRs alone close those gates.

### Scope and qualification

The R-06 pure source contract proves only that **public manifest changes are
classified and no automatic installer/rollback authority is returned**. It
cannot attest publisher authenticity, process integrity, operator identity,
fresh physical backups, actual database migration, reproducible build,
wallet continuity after update or correct remote transaction status.
**R-06 full P0 remains PENDING** until genuine native cross-version failure,
upgrade, partial-update, rollback, reorg/recovery and 3-platform operator tests
with separately verified receipts. Core Update Manager remains deferred P1.

For application launch/physical checks see `OWNER_REGTEST_ACCEPTANCE.md`;
for Core-native SQLite transfer see `ISSUE45_K10_PORTABILITY.md`;
for independent Linux root witness see `LINUX_OPERATOR_ACCEPTANCE.md`.
