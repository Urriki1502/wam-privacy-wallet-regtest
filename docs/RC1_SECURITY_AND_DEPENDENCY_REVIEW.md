# RC1 dependency and security review — 15 October 2026

Review baseline main50e1ea94df61b8400cbab3bffe0fbdd285c6b419; latest complete
stack1129645c250401b222e9c8ce49905c12359c9b24. All19 live PRs17–35 were read
for head/base, commits, file diff lists, mergeability, exact-head CI and reviews.
All were structurally mergeable with successful head checks at audit. GraphQL
review-thread inspection found zero unresolved threads across all19 PRs; no
formal external/DEV approval is implied. Historical
PR titles/numbers in older prompts differ; the actual table below is authoritative.

The integration worktree starts from PR35, which already includes Windows,
Fusion and Linux. A no-content-change merge of PR33 joins the two original xcb
fix commits already present as cherry-picks. No duplicate implementation or
replayed stack merges; no force push/rebase. `git diff HEAD^ HEAD` was empty for
that ancestry merge. Every actual PR18–35 head is now an ancestor. PR17 edits
only the old CODEX_HANDOFF and describes the older macOS-only handoff; it is
excluded from the candidate, left open and superseded by release-specific docs.
No main or legacy-repository modification. Main merge remains owner decision.

| PR | Actual scope/title | Exact audited head | Actual base branch | Candidate relation |
| --- | --- | --- | --- | --- |
|#17|docs(v1): update official REGTEST handoff and operator acceptance gate|`33f51a7b86c72472c50a3263aa19cbbf35476709`|main|excluded stale documentation|
|#18|feat(windows): offline Win64 WAM Core ZIP preflight (Phase 0)|`debc0b73037802e4ec543ed84b5c39ee44afbb06`|main|included ancestor|
|#19|feat(win64): run genuine signed WAM Core 101-block REGTEST lifecycle|`613dff314c71f3facc7d4dca2d11272734f7fc83`|feature/windows-x64-core-offline-preflight-20261014|included ancestor|
|#20|feat(win64): source-pinned WSP-1 real Core BIP352 receive E2E|`2404bb0063eb5c0e624cf741524d101f5dbc11d9`|feature/windows-x64-real-core-regtest-smoke-20261014|included ancestor|
|#21|feat(win64): actual WAM Core/WSP -> native Qt Receive Balance History E2E|`6ea3fc6a97f9672e00bd2b709fbe68e1322c14f2`|feature/windows-x64-wsp-real-receive-regtest-20261014|included ancestor|
|#22|security(win64): native Credential Manager checkpoint anchor and global mutation lease|`9d07c69a48b2c4ec69b6a4eaa15b2bf4cdd8542f`|feature/windows-x64-real-qt-readonly-e2e-20261014|included ancestor|
|#23|Windows V1: native private NTFS ciphertext custody gate|`65c56e0523f6a0d78d80e67401a0eb6d4b0f887d`|feature/windows-x64-native-credential-anchor-20261014|included ancestor|
|#24|Windows V1: native encrypted vault and real-Core recovery qualification|`b021eada48a31729fd3326adbd346581e463ef41`|feature/windows-secure-custody-v1|included ancestor|
|#25|Windows V1: real Core operational wallet and native Qt payment gates|`6116fe55378e76b2743eae3b7ed061691b63c20f`|feature/windows-anchored-vault-v1|included ancestor|
|#26|Windows V1: source-gated frozen operational exe and qualification checkpoint|`972c0e2cf3858bd504d65dad8494b03d6cf0cc90`|feature/windows-operational-wallet-v1|included ancestor|
|#27|feat(ui): WAM Fusion Signature shared macOS/Windows Qt dashboard + Auto theme|`2725f8440bb4db7ed9ef6d9a3cefae6f95c3a4b2`|feature/windows-frozen-operational-wallet-v1|included ancestor|
|#28|WAM Fusion 2.0: premium six-screen native wallet redesign|`a869a36a76ae3f3d9e0e39b4eea2135f01649c37`|feature/wam-fusion-ui-cross-platform-20261014|included ancestor|
|#29|Linux-02: pinned experimental Core build and strict ELF trust boundary|`576082d227ccd9eb139686ded431c69c07399237`|feature/wam-fusion-ui-v2-20261015|included ancestor|
|#30|Linux-03: private ciphertext custody and OS wallet leases, anchor fail-closed|`240881bfe457c9e0fdafc5440cf3036c1d754196`|feature/linux-regtest-integration-20261015|included ancestor|
|#31|Linux-03: independent root witness and authenticated monotonic checkpoint leases|`7335633e380ebaa4035b7897e425886b1a29384d`|feature/linux-private-custody-20261015|included ancestor|
|#32|Linux-04: shared root-anchored headless wallet and genuine Core acceptance|`a63c3716a453c9e26c2ace815ff37b7783d43366`|feature/linux-root-anchor-witness-20261015|included ancestor|
|#33|Linux: native Fusion Qt over approved Core and root witness|`9aa8607cc512c419c6800ccd2fd858ef7b31944f`|feature/linux-headless-wallet-20261015|included ancestor|
|#34|Linux: frozen headless and Fusion desktop real-wallet candidates|`be294c19dba02b5d8016cf76520b40975ee20c96`|feature/linux-fusion-qt-20261015|included ancestor|
|#35|Docs: native platform qualification, artifact checksums and resumable Linux checkpoint|`1129645c250401b222e9c8ce49905c12359c9b24`|feature/linux-frozen-wallets-20261015|included ancestor|

## Focused code review

- `release.py`, `windows_release_preflight.py`, `core.py`,
  `windows_core_transport.py`: publisher fingerprint/signature and separate
  original node/CLI SHA pins remain; Windows PE64/native transport and local
  config attestation deny remote/proxy/fallback routes. Core children retain
  sanitized environments. No mainnet launch route or receipt-derived hash trust.
- `linux_developer_core.py`, `linux_runtime.py`: approved manifest remains
  e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806,
  exact node/CLI pair and upstream revisions unchanged. Static ELF64/x86_64,
  stackRW, no W+X/RPATH/RUNPATH, independently pinned system loader/libraries,
  explicit consent and root peer before funding. Published RWE release rejected.
  Developer build is not an official signed release; loader-to-process binding
  and distribution relocation remain unqualified.
- `custody.py`, `vault.py`: v1/Keychain, v2/Credential Manager and v3/root-witness
  profiles remain authenticated and platform-bound. No portable-import bypass.
  Latest generation/digest checked under OS lease; create-only ciphertext fsync
  precedes anchor advance. Ambiguous orphan publication refuses/retry cannot
  overwrite. Restore requires fresh runtime and live rescan, cleans only owned
  newly created plaintext files after failure.
- `private_directory.py`, `encrypted_storage.py`: macOS owner/mode/no-follow
  descriptor walk, native absent-ACL requirement, regular single-link bounded
  envelope I/O and create-only publication remain intact. Keychain stores only
  public generation/digest; global wallet lease spans vault directories.
- `windows_private_storage.py`, `windows_checkpoint_anchor.py`: native SID/DACL,
  protected single-owner NTFS storage, pinned ancestor handles/reparse denial,
  single-link data and flush/create-only handle rename preserved. Credential
  records contain no secrets; same-wallet global mutex validates owner/DACL,
  rejects abandoned writers and cross-object/process contention.
- `linux_private_storage.py`, `linux_anchor_witness.py`: no-follow UID0700/0600,
  absent POSIX ACL, hardlink/FIFO/bounded-I/O checks, fsync create-only publication;
  independent root-owned journal with SO_PEERCRED both directions, per-wallet
  root-held flock, exact CAS, contiguous bounded records, no reset/delete/keys
  or arbitrary path API. Root listener has16 connection slots; missing/lost
  witness faults the shared coordinator. No app sudo/service installation.
- `wallet_session.py`: Sign and Broadcast retain exact-intent guard and OS lease
  through persistence/native crypto/RPC. Irreversible signed state is anchored
  BEFORE crypto; uncertain state BEFORE RPC. Lost replies do not auto-retry or
  release locks. Chain/UTXO/stale-state checks remain before sensitive calls.
- `operational_gui.py`, `fusion_pages.py`, `linux_headless.py`: same shared
  session; separate Sign/Broadcast approvals, Cancel default; locked/faulted data
  clear, worker teardown and background real sync remain. No alternate signer.
- Native probes/builders retain actual Core/WSP/scanner/SQLite acceptance in
  FINAL bootloaders. Fault instrumentation delegates to genuine Core/Signer;
  no synthetic RPC/blockchain replacement counts as acceptance. Negative unit
  fixtures remain supplementary. Source WSP pin and28 vectors unchanged.

No new runtime custody/signing defect was found requiring a gate relaxation.
Actual integration issues addressed: join original PR33 ancestry; consistent
RC1 platform artifact names and source/checkout/build/dependency manifests;
owner/operator guidance; Mac build tool pin aligned with qualified6.22.3.
No new wallet feature, cipher, KDF or migration implementation was introduced.
All existing native failure-path gates must pass on the NEW candidate commit;
predecessor success is baseline only.

## Residual findings / preview disposition

Owner accepts these only as disclosed disposable REGTEST preview limits:
plaintext unlocked SQLite, best-effort memory clearing,16 receive epochs,
10000 Linux witness generations, availability after ambiguous publication,
anchor/witness loss or replacement, rollback of both independent stores,
root/OS compromise, hardware power loss and hardened loader binding. Same-user
malware resistance and production custody are not claimed. Portable backup
stays design-only and is not required for this preview. Future portable exports
must disclose offline password-guessing and calibrate KDF on lower-end hardware.

Physical Linux host: owner explicitly answered none authorized; therefore
PHYSICAL_LINUX_ACCEPTANCE=PENDING_OPERATOR. Native Ubuntu CI and a runnable
operator package remain mandatory. Human Windows10/11 and Finder/OS-setting
signoff are also distinct from automated runner/local Cocoa testing.

Pre-qualification status: CODE_INTEGRATED; new exact-head native/frozen results
PENDING. READY FOR OWNER REGTEST TESTING requires actual successful run/artifact
receipts, not this review narrative. DEV WAM review has not been sent/completed.
