# Native disposable REGTEST wallet

The native app now exposes Receive, Balance, History, Send, Security and Settings.
Use fresh experimental test keys only; never import personal or production keys.
Official signed WAM Core v0.1.11 is started in a private disposable chain with
zero peers. Closing the developer session deletes that chain.

The Finder app asks for a passphrase before creating fresh test keys. Its
key/checkpoint snapshots are AES-GCM/scrypt encrypted and anchored to a separate
macOS Keychain generation/digest. The passphrase is held only while unlocked,
never sent in RPC, printed or persisted. Clearing interpreter/native copies is
best effort. See SECURITY-REUSE.md for threat boundaries and backup limitations.

## Payment flow

1. Enter a `wamrtsp1` REGTEST recipient, decimal amount (up to 8 places), and fee.
2. Prepare selects confirmed UTXOs without merging privacy clusters, reserves
   them, constructs PSBTv2 using pinned WSP and persists the encrypted reservation.
3. Verify exact recipient, amount, fee and change in the native review. Approve
   signing explicitly. The signer recomputes destinations/change and verifies
   BIP352 proof/metadata and SIGHASH_ALL; the reviewed commitment and live inputs
   must still match. Signed reservations are anchored before exposing success.
4. Broadcast is a separate action. The coordinator reattests isolated REGTEST,
   checks live UTXOs and persists uncertain reservations BEFORE submitting to
   actual Core. Core testmempoolaccept/signature validation must succeed.
5. Settings → Mine 1 REGTEST block confirms the transaction. Background WSP sync
   updates actual SQLite Receive/Balance/History. No synthetic success fallback.

Only an unsigned draft can be cancelled. Signed/uncertain/broadcast input locks
are never automatically released, including on reorg, RPC timeout or recovery.
A crash may leave conservative reservations requiring deliberate investigation;
the app does not guess that a transaction failed or automatically retry it.

## Security and Settings

Lock clears the view, closes seed/scanner and removes the disposable plaintext
SQLite runtime. Unlock/recovery authenticates the latest Keychain-anchored
snapshot and scans actual Core before enabling balances or spending. Save latest
backup creates a new private folder with a 0600 ciphertext file; it never replaces
an existing backup. Keep a new backup after state changes; older generations are
rejected while a newer anchor exists. Recovery is available both within the active session and on a new app session
on the same Mac. Choose **Recover latest backup on this Mac** at startup. The
existing Keychain anchor must match the backup. The fresh chain is rescanned;
a new testing epoch is funded while prior signed/uncertain reservations remain
locked. Save a new latest backup after recovery. Cross-Mac anchor migration is
not allowed. The pinned keyring supports at most 16 testing epochs and fails
closed at its rotation limit.

Settings retains manual sync, a 30-second background worker, explicit REGTEST
mining and macOS light/dark Auto appearance with Light/Dark override. There is no
mainnet switch or real-key import. Developer .app/.dmg is ad-hoc signed and
unnotarized; production key custody and process-loader binding remain unqualified.

## Acceptance

Both source and final frozen executable must perform actual native Qt Prepare,
Sign and Broadcast to real Core; mempool acceptance; confirmation at block 105;
100,000 atoms received by an independent WSP scanner; verified sender change;
real send-block invalidate/reconsider with irreversible locks retained; and native
Qt backup/lock/wrong-password rejection/recovery, then a second actual Core
session proving the same keys recover against the retained Keychain anchor. All 28 BIP352 vector suites and
all security contracts remain mandatory. Mock unit contracts are not real E2E.

Local Cocoa appearance qualification runs the final package with
`QT_QPA_PLATFORM=cocoa` and `--ci-real-core-wallet-cocoa`. This additionally
verifies real macOS Qt color-scheme change events in Auto mode while repeating
the actual Core wallet/security/recovery flows. It does not replace the mandatory
headless source/frozen gates. No system appearance preference is changed.
