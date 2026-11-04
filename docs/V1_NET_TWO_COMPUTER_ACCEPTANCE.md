# V1-NET two-computer physical acceptance procedure

Status: NOT EXECUTED on two physical computers. This procedure creates no PASS receipt by itself. Use only new disposable Shared REGTEST profiles. Keep Q06 accepted=false; owner G6 and independent G7 remain separate.

## Record before starting

Record operator/date/time, two distinct computer identifiers and OS/architecture, exact source commit, DMG/ZIP/executable hashes, bundled Core digests and WSP pin from the candidate manifest. Copy only the public package to the second computer; never copy seed containers, chain directories, RPC configuration/cookies, keychain files or journals. Both machines run their own Fusion and original Core process.

Use the same qualified candidate on both supported hosts. A previous isolated-Q06 DMG cannot qualify Shared mode. A macOS ARM64 package is not Windows/Linux qualification. Revalidate actual binaries and ports; never signal or adopt an unrelated process occupying a port.

## Configure explicitly in the normal GUI

1. Start Fusion A and B. On Welcome, check **Shared REGTEST · manual Core P2P**. Choose **Create a new wallet**. Select separate NEW parent folders on their respective computers. Record the resulting supervisor-root paths privately for reopen.
2. In manual peer configuration enter these immutable values; both local RPCs stay 127.0.0.1. Literal private LAN/VPN IPs are supported; DNS/public-IP discovery is not implemented.

| Field | Computer A | Computer B |
|---|---|---|
| Peer private/LAN/VPN IP | B's interface IP | A's interface IP |
| This computer's P2P interface IP | A's interface IP | B's interface IP |
| Local RPC port | 29554 | 29554 |
| Local P2P port | 29555 | 29555 |
| Peer P2P port | 29555 | 29555 |
| Sole mining coordinator consent | checked | unchecked |

3. Permit Core-to-Core TCP 29555 between the two interfaces as needed. Do not forward/expose RPC 29554. Fusion talks only to its local Core, never the other Fusion or remote wallet RPC.
4. Create each independent BIP39 wallet and complete its real three-word backup challenge. Keep recovery material/passwords out of evidence/screenshots. Verify **Settings → Shared REGTEST → Verify peer and chain** on both computers BEFORE funding/mining.
5. Record required genesis `b88f3d262f285e38e184f50bf3eea1c8e615486ae67d3d9eaf0976fbd6d3d30d`, magic bytes `57414d52` (WAMR), peer handshake version/subversion, peer endpoints, height and best-block hash. Both must report the same genesis and a completed manual Core peer connection. No alternate genesis/network or consensus changes are allowed.

## Fund and transfer once

6. Only A may mine. For this NEW zero-height test chain, expand **Settings → Advanced controls → Show developer controls** on A and explicitly approve its existing test-funding action. It uses the existing Core mining/fallback-fee policy and matured funding fixture. Never attempt to spend immature coinbase or locked genesis premine. If the chain is not fresh, stop this funding step and inspect existing evidence; do not reset either chain.
7. Refresh/verify B until height and best hash match A. Record funding TXID/height and spendable balance. B's funding/mining actions must remain disabled; an attempted backend participant mining action must be refused in engineering evidence.
8. Enable sending on each wallet only through the existing native-custody/checkpoint confirmation. On B choose **Receive**, record its complete REGTEST BIP352 receiving code and compare it on both screens before signing.
9. On A prepare exactly 3 WAM to B, fee 0.00010000 WAM. Review recipient, amount, fee, change and selected input count. Explicitly approve **Sign**, then separately approve **Broadcast**. Record the returned public transaction ID. No automatic retry if an outcome is unknown; preserve the original signed PSBT/reservation and stop that payment action for read-only reconciliation.
10. Before confirmation, record the exact TXID in B's local Core mempool where supported. Then only A explicitly approves one confirming block through the existing pending-transaction confirmation control. Refresh both chains/wallets. Record identical tips, confirmation block/height, B's 3 WAM credit, A's debit/fee/change and both GUI History entries for the same TXID.

## Read-only evidence collection

Use the bundled pinned `wam-cli` locally, with `-datadir` pointing to that machine's owned supervisor `chain` folder. Credentials remain in its protected local configuration; do not place them in command arguments or export/copy them. Commands below are observations, not wallet/broadcast recovery authority:

```text
wam-cli -datadir=<LOCAL_PROFILE>/chain getblockhash 0
wam-cli -datadir=<LOCAL_PROFILE>/chain getblockchaininfo
wam-cli -datadir=<LOCAL_PROFILE>/chain getbestblockhash
wam-cli -datadir=<LOCAL_PROFILE>/chain getpeerinfo
wam-cli -datadir=<LOCAL_PROFILE>/chain getrawmempool
wam-cli -datadir=<LOCAL_PROFILE>/chain getblock <CONFIRMING_BLOCK_HASH> 2
```

Collect only public metadata/transaction IDs and screenshots without secrets. Match RPC outputs to the GUI and exact source/artifact receipt. Core handshake is actual TCP P2P; local block-file magic validation is not a passive wire capture.

## Recovery and negative cases

11. With no new payment in progress, use **Disconnect Core P2P** on A. Verify zero ready peers, retained wallet/history and refusal of new network-dependent actions. Explicitly reconnect, verify peers and common tip, then refresh wallet state. Do not retry a prior uncertain broadcast.
12. Gracefully close each app through its owned quit path. Reopen the SAME supervisor roots with exact original Shared settings and each wallet's own password. Verify no new mnemonic/profile, the same receive code, history/TXID, balances and reservation counts. Repeat Lock → Unlock and a wrong-password refusal; correct authentication must restore only the previously authorized custody/checkpoint state.
13. Reorg engineering is performed on separate disposable acceptance profiles using existing Core mechanisms, never the owner's old wallet. The locally qualified 29448e5 candidate supports explicit recovery; no physical reorg receipt is implied. Record both wallets' tip/history/reservations, then on the designated A test Core only invalidate the current tip through its existing local RPC. Refresh A: custody must fail closed at the old native checkpoint. Only A generates two replacement blocks through existing Core mining RPC; B must validate the stronger branch and reach the identical new tip. Refresh B: it must also refuse to silently advance the old checkpoint.

14. On each wallet choose **Settings → Shared REGTEST → Reconcile retained shared-chain state**. Enter that wallet's original password and explicitly approve **Reconcile**. This requires the original owned Core/profile, native checkpoint authentication and strictly greater canonical work for a competing branch. It retains old checkpoint generations/runtime bytes and every irreversible reservation; no payment is retried. Sending must remain disabled immediately afterwards. Separately approve **Enable sending**, refresh verified History and record the original TXID exactly once, correct balances, unchanged reservation counts and the new common chain tip. Gracefully restart/reopen the same profiles and prove these values persist. A wrong password, weaker/equal competing branch, modified runtime, uncommitted native generation or changed owner must refuse safely. Never erase runtimes/locks, reanchor by hand, release signed reservations or reset chains to manufacture recovery.

If native Keychain authentication is refused, unlock the appropriate OS keychain through its normal owner-controlled mechanism; do not reset anchors or change protection settings. The engineering harness's public disposable-keychain authentication is not a production recovery shortcut.

## Case receipt

For V1–V19 record PASS / FAIL / BLOCKED / NOT EXECUTED with timestamp, both physical-host identities, source SHA, Core/WSP digests, final executable/DMG hashes, command/log/screenshot references, actual TXID and block evidence, and blocker actor/action. Preserve every failure. V18 needs the existing isolated REGTEST workflow on these exact V1 frozen bytes. V19 may be PASS only after this procedure has actually run across the two distinct computers; localhost tests and this document cannot satisfy it.

No push, merge, remote CI, production/mainnet, acceptance-ledger mutation or independent sign-off is performed by this procedure. The owner retains final acceptance authority.
