# Phase 0 full local audit — WAM Fusion REGTEST

Date: 2026-11-04. Audited source: `8df48952eb4c3c6f2f1db86d31c58125fb2a7e7e`. This is a static source, metadata and existing-evidence audit. No new functional PASS is claimed. Phase 0 is complete as a bounded read-only audit; unknown runtime/physical facts remain explicitly unresolved. Implementation remains stopped for owner approval.

Evidence vocabulary: **VERIFIED** means directly inspected bytes, source, Git object or metadata; **REPORTED BUT NOT VERIFIED** means a receipt/operator/agent claim not replayed here; **INFERRED** means a source-supported causal hypothesis; **MISSING EVIDENCE** means the necessary proof was not located; **BLOCKED** means a named actor/action is required. Existing receipt existence and contents can be VERIFIED while its execution claim remains un-replayed.

## Principal findings

1. **VERIFIED:** Canonical root is a real clean Git checkout at the reported HEAD. DMG hash matches exactly. ZIP source stamp, Core members and executable match local receipts/dist. Source is identifiable, but this is a shallow checkout and five local commits are absent from live Draft #140. No remote run exists for this local HEAD in the queried Actions API. See [manifest](WORKSPACE_MANIFEST.md).
2. **INFERRED P0:** Normal Q06 Send has an event-ordering gap. `Bip39FusionWindow._on_ready('prepare')` opens a modal dialog before it assigns the next `sign` command; `Bip39TrialWindow._finished` may consume the pending slot during the nested Qt event loop. A successful backend preparation can therefore leave GUI approval ahead of backend signing. This is not yet a runtime reproduction.
3. **VERIFIED source mismatch / INFERRED owner cause:** `_reopen_q06` authenticates seed/acknowledgement but does not restore the anchored spend session. The unlock UI queues `snapshot`; `_scan_q06` refuses a pre-existing protected scanner checkpoint without active spend reconciliation. This explains a plausible seed-open / custody-not-verified split. It does not prove wrong password, identity mismatch, or Core failure on the owner's machine.
4. **VERIFIED coverage gap:** Frozen Q06 probe uses direct executor prepare/sign/broadcast and lock→`open(...,'reopen',...)`→`activate`. It does not execute the owner's normal GUI approval/worker path or normal `unlock` route. Unit Unlock coverage uses a stub and directly calls `_on_ready`. Earlier PASS is compatible with the observed defects.
5. **REPORTED BUT NOT VERIFIED:** Full source suite “Ran 508, errors=25, skipped=33” is not 508 PASS. Raw named before/after unit logs were not located in the inspected locations, so equality of 25 error causes and harmlessness are unproven. Local final build logs and frozen receipts exist; these establish narrower recorded scenarios.

## Governing contract and current remote state

Read the live [Issue #45 specification](https://github.com/Urriki1502/wam-privacy-wallet-regtest/issues/45), [owner Q-GATE v2](https://github.com/Urriki1502/wam-privacy-wallet-regtest/issues/45#issuecomment-6379544993), root AGENTS, canonical ledger, README, acceptance/security/custody/recovery/build contracts and relevant source paths. The present directive confines work to Phase 0 and prohibits acceptance changes.

Permanent definitions are Q01 build provenance; Q02 authenticated Core/chain; Q03 RPC/credentials; Q04 coexistence/reconnection; Q05 owned persistent Core/custody; Q06 BIP39-12 and BIP352. “Q05 Send” in the owner incident describes shared transaction machinery; it does not rename Q05 or transfer Q06 cases. Q07 remains BIP39-24. T-01–T-09, K-01–K-10, relevant transaction/GUI/release requirements and §G must remain in repair scope. The architecture matrix includes the actual case IDs and their frozen ledger statuses.

Live GitHub GET results: main `35553f674851282c6e107e02ba02ef2a7ac5ce64`; PR #138 merged at `a0ec5799de3e59e93689c744672168b76bf571be`; PR #140 remains Draft, unmerged, remote head `414bebb07ac4705274a0b82617d8e72441b77cbe`. GitHub compare finds main is an ancestor of PR head with 166 commits ahead. Do not use this as authorization to merge a stacked history; narrow ancestry review is still required. Local-only eight-file diff includes backend/executor/UI and tests.

Exact main Actions [41174699996](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/41174699996) has one successful canonical-vector job; [41174700002](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/41174700002) has five successful macOS Core/Q05/Cocoa/Q04/frozen jobs. This is genuine main-ref evidence at `35553f6`, later than the Q05 merge, not a proof that Windows/Linux exact-main gaps are closed or that current Q06 source passed. The ledger's recorded missing-main qualification needs future reconciliation, not a Phase 0 edit.

Remote PR-head runs `41569725929`, `41569725908`, `41569725920`, `41569725907`, `41569725943` report success. They qualify their own SHA/scope only. Actions query for local `8df4895…` returned zero runs. No CI was dispatched.

## A–D. Workspace, source and artifact provenance

[WORKSPACE_MANIFEST.md](WORKSPACE_MANIFEST.md) contains exact branches, hashes and source/artifact linkage. Its generated inventory below covers all canonical top-level categories without dumping binaries/caches/secrets. [Legacy inventory](LEGACY_WORKSPACE_INVENTORY.md) identifies older repos and evidence separately. Canonical source bytes match all 405 HEAD blobs; pinned WSP's 33 Python files match literal Git objects. No source replacement/copy/clone is required or performed.

`scripts/build_macos_bundle.sh` performs source capture, pinned WSP closure, PyInstaller collect-submodules, original Core byte restoration, ad-hoc app signing, final frozen diagnostics, source verification and archive hashing. Existing build/PYZ TOCs name `wam_regtest.bip39_fusion_gui`. ZIP source stamp names current HEAD; ZIP app executable matches dist and Q05 frozen receipt. All 54 manifest-member hashes match. These checks establish consistent local artifacts; they do not prove a clean dependency supply chain or the DMG's interior independently.

Core receipt and code pins match actual bytes; receipt assertion of signed intake is not a fresh GPG verification. `RELEASE_CANDIDATE_MANIFEST.json` reports setuptools 84.2.1 while lockfile pins 84.0.0; resolve installation/build-isolation provenance before reproducibility claims. This does not itself prove a custody exploit. Generated `.spec` contains absolute build-stage paths and is historical output, not an alternate source authority.

## E–F. Actual architecture and evidence layers

Normal Finder: `package_entry.main`→`_check_bundle`→`managed_onboarding.launch`→BIP39 launch→`Bip39FusionWindow(Bip39TrialWindow)`→`ControlWorker`→single `WalletExecutor` owner thread→`Bip39ReadOnlyBackend`→`CoreSupervisor` plus native seed/checkpoint/spend session→shared `WalletSession`→pinned WSP Scanner/Wallet/Signer→attested local RPC. Legacy Q05 onboarding remains a separate, explicit route using `ManagedWalletWindow`/proxy and the 32-byte Keyring vault. It must not be silently interpreted as BIP39.

GUI owns presentation and requests; it cannot grant custody. Backend `_activate_q06` obtains `open_owned_spend_session`, validates a live native checkpoint and exact receive identity before exposing Send. Q06 checkpoints are independent seed/scanner namespaces with original-Core binding; Q05 encrypted checkpoint/ref/recovery machinery stays separate. `WalletSession.prepare/sign/broadcast` is shared rather than duplicated.

The [architecture matrix](Q01_Q06_ARCHITECTURE_MATRIX.md) maps every local application module to symbols/dependencies/tests/RPC literals and identifies normal runtime vs platform/probe paths. IMPLEMENTED, PACKAGED, UNIT TESTED, REAL-CORE TESTED, FROZEN-GUI TESTED and OWNER ACCEPTED are kept separate. Source presence/packaging is verified; historical run claims are scoped; owner acceptance is absent/failed.

## G. Owner Send incident

Owner report: ~47.4999 WAM confirmed, receive at height 102, payment 3 WAM, fee .0001, change 44.4998, one selected input, signature approval shown, Broadcast appeared unavailable, later Prepare and `WALLET_INPUT_FUNDS_UNAVAILABLE`. Arithmetic is internally consistent. No confirmed outgoing payment is established by these observations. Neither failure nor success of network submission can be inferred from the GUI alone.

`Wallet.propose` excludes every reserved and mempool-spent outpoint and selects within a privacy cluster; failure is `INSUFFICIENT_SINGLE_CLUSTER_FUNDS`, mapped only for `prepare` to the visible funds-unavailable code. Confirmed balance can therefore remain positive while spendable funds are zero. This is compatible with an earlier draft/signed/uncertain/broadcast reservation; it is not proof of insufficient total wallet value. A fresh Prepare after a lost GUI stage could produce this symptom.

`WalletSession.prepare` persists reservation before review; `sign` marks signed and saves before native signing; `broadcast` saves uncertain before `testmempoolaccept`/`sendrawtransaction`. Broadcast uncertainty faults the session and retains inputs. `_unchanged_inputs` verifies tip and exact Core `gettxout`. These are essential protections and must remain.

The modal ordering hypothesis is supported by `bip39_fusion_gui.py:534`, `bip39_owner_gui.py:334,729`, and `managed_gui.ControlWorker.run`: queued result and finished delivery can run inside `dialog.exec()`, before `_pending_action` is written. A real timed GUI regression is required before declaring this the incident root cause. `PaymentApproval` itself creates an enabled approval button with default Cancel; no explicit blanket disable was found in that constructor. Owner's disabled control may instead be the main Broadcast button or a busy/unsigned/faulted state. Do not force-enable it.

Persistent reservation states are `draft`, `signed`, `uncertain`, `broadcast`; AVAILABLE is derived from coins minus reservations/mempool spends. Confirmed history and mempool tables are separate. REJECTED and CONFLICTED are not a complete durable per-intent GUI state machine here; RPC rejection is folded into conservative broadcast uncertainty. Signed PSBT bytes live in session `_signed`; scanner checkpoint persists reservation state, not an automatically resumable signed-payment document. There is no proven durable exact-intent→signed bytes→txid lifecycle across this owner flow. Preserve all existing signed artifacts; absence of a file does not authorize releasing inputs.

Runtime confirmation still needed after approval: identify the exact original profile and reviewed PSBT/commitment/txid from existing private evidence; compare anchored reservation state, history, original Core mempool, raw transaction and spent outpoint observations. No Core RPC or original wallet database was opened here. No rebroadcast, replacement, cancel, reservation release, journal deletion or reset was attempted.

## H. Owner Lock/Unlock incident

`_lock_q06` closes an active spend session, then clears backend password buffer/public metadata/folder. `Q06OwnedSpendSession.lock` closes RPC/scanner/keys, verifies anchor/runtime guard and removes only its verified runtime on clean closure; uncertainty preserves runtime and clears session secrets in finally. However if session.lock raises, backend `_lock_q06` exits before clearing its separate `_secret` buffer. This is a source-supported cleanup gap requiring a failing fault-injection test; no memory inspection was performed.

`execute('unlock', password, False)`→`_reopen_q06` verifies original Core, unique seed folder, password/native seed anchor, authenticated backup ack and profile, then populates seed metadata with signer/broadcast false. It does not reopen scanner checkpoint/spend session. GUI `_on_ready('unlock')` marks ready and queues snapshot. `_scan_q06` denies a checkpoint namespace when no spend session exists. `ControlWorker` maps unknown Q06 exceptions to `WALLET_OPERATION_DENIED_STATE_RETAINED`. Overview stays unverified while Security derives “Seed open” from `_ready`. This is a coherent source-supported explanation for the owner's status split.

`_activate_q06` exists as an explicit separate approval action and can perform real checkpoint reconciliation. Its availability is not evidence of automatic usable Unlock. Correct restoration must retain the original authorization boundary; owner approval is needed for any change in when consent is requested. No wrong password, wrong profile, foreign Core or broken checkpoint is proven; those remain mandatory negative cases. The missing import was already fixed at `24447ff`; repeating that patch will not repair this remaining state-machine gap.

## I. GUI/UX

Functional P0: pending-action/modal ordering, unlock→checkpoint restoration, conflicting security labels, error handling that clears `_signed_ready` on any denial with an approval commitment, and stage indicators driven by local flags rather than complete backend transaction state.

Visual P1/P2: fixed 226px sidebar with long unwrapped note, shared footer/status space, backup headers and progress value 1 of 2 beneath Step 2, verification-card alignment, raw QMessageBox activation, separate Lock/Unlock buttons, and recovery-modal fidelity. Normal Fusion size is 1260×810, minimum 900×630. Existing 900×650/1280×800/1440×900/1920×1080 light/dark/auto screenshots are mainly legacy diagnostic UI and cannot establish normal Q06 responsiveness. A saved preview was inspected; it visibly represents the older Q05 Send layout, not the owner's complete Q06 flow. No fresh GUI was launched.

Recovery dialog has masked 12 inputs, 3 columns×4 rows, tab/backspace handlers, explicit paste, checksum gate and application-modal exec; backup page uses masked three-word cards and ResponsiveRow. These source facts do not establish approved-design fidelity. Successful recovery acceptance closes via `accept()` without explicitly clearing all field contents; reject/cancel/close paths do clear. Review lifetime and references before security claims. There is no guarantee of perfect CPython memory erasure. Owner-provided approved design reference is not present in this instruction; design signoff remains owner action.

## J. Tests and evidence audit

Static count: 588 `test_*` function definitions in top-level test files; this is not executed test count. Parametrization/import failures/skips change discovery totals. Q06 backup/Unlock tests use `_StubExecutor`, synthetic GUI result objects and direct callbacks; many crypto/checkpoint source tests use real WSP SQLite/encryption with mock Core/native anchors. These are useful contracts, not real-Core acceptance.

`q06_spend_probe.run` uses actual owned signed Core and native custody, direct executor transaction commands, one-block confirmation and same-chain mnemonic proof. It renders results into `Bip39FusionWindow`, but bypasses user preparation/sign modal scheduling; reopening is `open`+`activate`, not Unlock. `q06_owner_probe` is chiefly read-only seeded/funded receive/reopen/identity proof. Q05 executor scenarios cover their own legacy managed GUI, not automatically the changed Q06 route.

Local `package-output/q06-frozen-spend-evidence.json` records spend-confirmed, same-owner reserved reopen, same-chain seed-history recovery and readonly txid reconciliation true, fresh-mnemonic full-history recovery false. It lacks its own source SHA/time/final-executable hash, so bind it through the outer manifest/build log rather than treating it as independently complete provenance. `q05-frozen-evidence.json` supplies exact source/executable/Core pins, Cocoa and seven observations, timestamp 2026-11-04T03:24:47Z, physical false. Negative/signed/uncertain supplements name current HEAD too.

`/private/tmp/q06_build_FINAL20.log` ends in packaged/source-verify/DMG E2E PASS markers. Its stdout includes some source_sha values `24447ff…` while current output receipts name `8df4895…`; do not silently reconcile these as a uniform execution record. Inspect provenance/environment and command record in Phase 1. Earlier logs retain real failures: FINAL12 metadata missing coincurve, FINAL13 self-check denial, FINAL15 Q06 readonly denial, FINAL16/17/19 Q05 scope denial, FINAL9 evidence FileExistsError. Later success does not erase them. A generated appendix hashes these logs and records only safe status markers.

The 508/25/33 and baseline 497/25/33 claims occur in `package-output/Q06_OWNER_UX_ENGINEERING_HANDOFF_REPORT.md`; raw named unit logs were not found. Numerically 508−25−33 = 450 only if all errors/skips are counted single tests; no exact PASS count is certified without raw results. `wsp_import.py` actively rejects preimported/non-source/wrong-byte WSP; dependency/import order problems can prevent entire modules from running, including regression coverage. An environment error is a qualification failure, even if pre-existing. Do not weaken the guard. Earlier `docs/Q06_FINAL_ENGINEERING_AUDIT.md` claims other totals and explains 35 vs 33 skips by unittest “deduplication”; that explanation is unsupported by evidence inspected here and must not be relied upon.

## G0–G7 disposition for the current integrated candidate

Gate names differ slightly between older repo shorthand and owner v2. The table uses owner-v2 technical meanings and explicitly retains owner-labelled G6 physical/G7 independent/merge obligations. It is an audit assessment, not a ledger update.

| Gate | Current-candidate audit | Exact supporting evidence / missing actor |
|---|---|---|
| G0 scope inventory | PASS for this static Phase 0 inventory only; functional completion not certified | Canonical cases and architecture appendix; repair gaps remain |
| G1 source/security | FAIL for unresolved source-level restoration/cleanup gaps; causal runtime bugs still hypotheses | `bip39_owner_backend._reopen_q06/_lock_q06`, GUI paths; independent review still missing |
| G2 required-OS native | NOT EXECUTED in this audit; current three-OS proof incomplete | Historical 3368341 OS links in Q06 ledger; current local Mac receipts are narrower; Win/Linux exact-current missing |
| G3 frozen/package | FAIL for owner-visible normal-flow result; recorded automated frozen scenarios exist | Current DMG hash, local receipts; owner 2026-11-04 Send/Unlock FAIL; no new replay |
| G4 functional/fault | FAIL on reported physical path; automated scenarios do not cover it | Owner observations plus direct-executor probe code; integrated retest required |
| G5 provenance | BLOCKED for full qualification; verified local hash association is partial PASS evidence | Manifest 54/54, ZIP stamp; missing clean dependency/DMG-interior/full runtime linkage and cross-OS current proof |
| G6 physical | FAIL on macOS owner flow; Windows/Linux BLOCKED | Owner report 2026-11-04; owner retest and consenting Win/Linux operators required |
| G7 independent / authorized integration & postmerge | BLOCKED | No independent named signoff; #140 Draft unmerged; complete exact-main matrix absent |

No new tests were executed. Frozen ledger counts are quoted in the matrix and remain unchanged; old PASS values are not current failure-free qualification. `q_gate.validate` was not run or modified because no transition is attempted. Acceptance remains false.

## K–P. Risk, consolidation, repair and V1-NET

[Gap register](Q05_Q06_GAP_REGISTER.md) names risks and evidence confidence. [Legacy inventory](LEGACY_WORKSPACE_INVENTORY.md) proposes manifest-first future archival, with no deletion or movement. [Repair plan](Q05_Q06_REPAIR_PLAN.md) orders transaction integrity, checkpoint/reservation safety, Unlock/backend/UI correctness, then visual improvements. Historical builds, original profiles and all FAIL receipts must remain preserved.

V1-NET is BLOCKED until repaired Q06 result receives explicit owner authorization, after integrated real local acceptance and owner physical review in the owner's prescribed order. Current `network_policy._FIXED` enforces listen=0/connect=0 and local RPC; do not modify Q06 profiles to enable peers. Future two real nodes on one Mac precede multi-machine evidence; independent RPC/P2P ports, shared genesis/tip, transaction propagation, restart/reconnect, reorg/custody negatives and actual device proof remain required. No GUI-to-GUI network or consensus change is needed.

Required decision: owner reviews these six documents and approves a bounded Phase 1 repair scope. Runtime confirmation, source/test edits, builds and local commits remain future work. No source-selection conflict requiring a new workspace was found; incomplete ancestry and exact original owner transaction/profile identification remain blockers to stronger conclusions. No original seed/password/cookie/private descriptor/container payload was read or printed.


## Existing local build-log preservation index

These logs were not generated/replayed by this audit. Hashes preserve identity; volatile /private/tmp retention is not guaranteed. Only fixed public stage codes are shown. No raw exception values, passwords, seeds or RPC config are copied.

| Absolute log path | Bytes | SHA256 | Last safe status markers |
|---|---:|---|---|
| `/private/tmp/q06_build_FINAL10.log` | 25144 | c779674b0e1f9247acd870c72069548c9aba3dd03a5f1f43b49e5a4e00c1ccce | 427:BUILD_SOURCE_VERIFY_PASS; 428:BUILD_SOURCE_VERIFY_PASS; 429:MACOS_APP_STAGE=DMG_CREATE_START; 432:MACOS_APP_STAGE=DMG_VERIFIED; 433:MACOS_ARM64_REAL_CORE_BIP352_PACKAGED_APP_DMG_E2E_PASS |
| `/private/tmp/q06_build_FINAL11.log` | 205 | 7bf5f935f10486303fe3971dddcbf5929fd8a35ecc6927d6ebf5ec41c1656e8a | 1:BUILD_SOURCE_CAPTURE_PASS; 2:BUILD_SOURCE_CAPTURE_PASS; 4:MACOS_APP_STAGE=PYINSTALLER_START |
| `/private/tmp/q06_build_FINAL12.log` | 2770 | 7e3a471444cc567195a4c8e5b5e630790eb132d89fb2cc195f1ccdd31e926d7a | 1:BUILD_SOURCE_CAPTURE_PASS; 2:BUILD_SOURCE_CAPTURE_PASS; 4:MACOS_APP_STAGE=PYINSTALLER_START |
| `/private/tmp/q06_build_FINAL13.log` | 8909 | cb83e610261dcc4a1700bcd9ae8903e9897745b9f956b255bce1103ecf4950a3 | 108:MACOS_APP_STAGE=PYINSTALLER_COMPLETED; 109:MACOS_APP_STAGE=UNMODIFIED_SIGNED_CORE_SHA256_PASS; 111:MACOS_APP_STAGE=OUTER_APP_SIGNED_CORE_HASH_STILL_PASS; 113:MACOS_APP_STAGE=FROZEN_BUNDLE_SELF_CHECK_START; 115:MACOS_FROZEN_BUNDLE_CHECK_DENIED |
| `/private/tmp/q06_build_FINAL14.log` | 24963 | fb5407805eed1691685719e4afaa726c018d0b3fe8e87c6d09deaa1d9f8f6498 | 425:BUILD_SOURCE_VERIFY_PASS; 426:BUILD_SOURCE_VERIFY_PASS; 427:MACOS_APP_STAGE=DMG_CREATE_START; 430:MACOS_APP_STAGE=DMG_VERIFIED; 431:MACOS_ARM64_REAL_CORE_BIP352_PACKAGED_APP_DMG_E2E_PASS |
| `/private/tmp/q06_build_FINAL15.log` | 20007 | 8562db62d240c42b4ba59a75f1c455c1e00e42c167df76c4e64a4179792c6069 | 321:MACOS_Q06_OWNER_STAGE=GENUINE_CORE_FUNDED_SCAN_START; 322:MACOS_Q06_OWNER_STAGE=GENUINE_CORE_FUNDED_SCAN_PASS; 323:MACOS_Q06_OWNER_STAGE=ENCRYPTED_SEED_REOPEN_START; 324:MACOS_Q06_OWNER_STAGE=FAIL_CLOSED_EXPLICIT_OWNER_SHUTDOWN_ATTEMPT; 325:MACOS_Q06_NATIVE_BIP39_12_GUI_CORE_READONLY_DENIED |
| `/private/tmp/q06_build_FINAL16.log` | 22265 | c8036d50940c4d483869bcaa0b7e1dcf4f2ba783565827763979ef4c2ff1f2e0 | 365:MACOS_Q06_SPEND_STAGE=POST_REOPEN_TXID_INSPECTION_START; 366:MACOS_Q06_SPEND_STAGE=POST_REOPEN_TXID_INSPECTION_PASS; 367:MACOS_Q06_SPEND_STAGE=CLEAN_CORE_SHUTDOWN_PASS; 369:MACOS_Q06_NATIVE_BIP39_SEND_CONFIRM_REOPEN_PASS; 370:MACOS_APP_STAGE=FROZEN_Q06_BIP39_SPEND_PASS |
| `/private/tmp/q06_build_FINAL17.log` | 23067 | 19b3f438da200c1a76e0b386f922bcfe2b9c5ba512b330afef8fedf1ad5cdf30 | 365:MACOS_Q06_SPEND_STAGE=POST_REOPEN_TXID_INSPECTION_PASS; 366:MACOS_Q06_SPEND_STAGE=CLEAN_CORE_SHUTDOWN_PASS; 368:MACOS_Q06_NATIVE_BIP39_SEND_CONFIRM_REOPEN_PASS; 369:MACOS_APP_STAGE=FROZEN_Q06_BIP39_SPEND_PASS; 390:Q05_FINAL_FROZEN_MANAGED_GUI_LIFECYCLE_PASS |
| `/private/tmp/q06_build_FINAL18.log` | 25949 | 0092a160d144e6a59873f8ff34daafb3a5a04ca88d57b8a81592b6a4d0fe763a | 418:Q05_FINAL_FROZEN_NEGATIVE_MULTIPLE_ORPHANS_PASS; 420:Q05_FINAL_FROZEN_NEGATIVE_ANCHORED_HARDLINK_PASS; 422:Q05_FINAL_FROZEN_NEGATIVE_SYMLINK_PASS; 424:Q05_FINAL_FROZEN_NEGATIVE_PERMISSION_PASS; 425:MACOS_APP_STAGE=PACKAGED_REAL_CORE_GUI_PASS |
| `/private/tmp/q06_build_FINAL19.log` | 22266 | 219a9262fac801a0ad3851b89a798f281282a714309a6e72804cbc730a6e0e56 | 365:MACOS_Q06_SPEND_STAGE=POST_REOPEN_TXID_INSPECTION_START; 366:MACOS_Q06_SPEND_STAGE=POST_REOPEN_TXID_INSPECTION_PASS; 367:MACOS_Q06_SPEND_STAGE=CLEAN_CORE_SHUTDOWN_PASS; 369:MACOS_Q06_NATIVE_BIP39_SEND_CONFIRM_REOPEN_PASS; 370:MACOS_APP_STAGE=FROZEN_Q06_BIP39_SPEND_PASS |
| `/private/tmp/q06_build_FINAL20.log` | 25131 | afab9e438845e2738b46c5316369a64f8ebb02dc7e08763d61db46b7fe0dfdc6 | 427:BUILD_SOURCE_VERIFY_PASS; 428:BUILD_SOURCE_VERIFY_PASS; 429:MACOS_APP_STAGE=DMG_CREATE_START; 432:MACOS_APP_STAGE=DMG_VERIFIED; 433:MACOS_ARM64_REAL_CORE_BIP352_PACKAGED_APP_DMG_E2E_PASS |
| `/private/tmp/q06_build_FINAL8.log` | 23078 | 0f2430f63d61aa9bf29ee5e59e041422289dc065f8fd2b97bb9954a07b82ed69 | 365:MACOS_Q06_SPEND_STAGE=POST_REOPEN_TXID_INSPECTION_PASS; 366:MACOS_Q06_SPEND_STAGE=CLEAN_CORE_SHUTDOWN_PASS; 368:MACOS_Q06_NATIVE_BIP39_SEND_CONFIRM_REOPEN_PASS; 369:MACOS_APP_STAGE=FROZEN_Q06_BIP39_SPEND_PASS; 390:Q05_FINAL_FROZEN_MANAGED_GUI_LIFECYCLE_PASS |
| `/private/tmp/q06_build_FINAL9.log` | 25961 | 491b927427a39bdeff449e36fac3e8376309bc8b69b8655d4c9fbcbabb7cfafc | 418:Q05_FINAL_FROZEN_NEGATIVE_MULTIPLE_ORPHANS_PASS; 420:Q05_FINAL_FROZEN_NEGATIVE_ANCHORED_HARDLINK_PASS; 422:Q05_FINAL_FROZEN_NEGATIVE_SYMLINK_PASS; 424:Q05_FINAL_FROZEN_NEGATIVE_PERMISSION_PASS; 425:MACOS_APP_STAGE=PACKAGED_REAL_CORE_GUI_PASS |
| `/private/tmp/q06_build_final2.log` | 81 | 371c580b110a836569cd81e9a6d769d43922be9af4c4aa0ed82181b7eb494de4 | No whitelisted terminal marker |
| `/private/tmp/q06_build_final3.log` | 229 | 92c68b850130a33c91a14396c0259660a7e5be1e0d19572dbd79a042ca62e7a5 | No whitelisted terminal marker |
| `/private/tmp/q06_build_final4.log` | 229 | 92c68b850130a33c91a14396c0259660a7e5be1e0d19572dbd79a042ca62e7a5 | No whitelisted terminal marker |
| `/private/tmp/q06_build_final5.log` | 229 | 92c68b850130a33c91a14396c0259660a7e5be1e0d19572dbd79a042ca62e7a5 | No whitelisted terminal marker |
| `/private/tmp/q06_build_final6.log` | 25017 | 6e6ba97d6b075c874173427744a8f4703ebcc5fe0badc0c04a64cdc6d8a98a1a | 426:BUILD_SOURCE_VERIFY_PASS; 427:BUILD_SOURCE_VERIFY_PASS; 428:MACOS_APP_STAGE=DMG_CREATE_START; 431:MACOS_APP_STAGE=DMG_VERIFIED; 432:MACOS_ARM64_REAL_CORE_BIP352_PACKAGED_APP_DMG_E2E_PASS |
| `/private/tmp/q06_build_final7.log` | 22239 | aa09a31700bdf425320484fc99f91f2a5393003c37f9cb3e8c398aea12a54d73 | 364:MACOS_Q06_SPEND_STAGE=POST_REOPEN_TXID_INSPECTION_START; 365:MACOS_Q06_SPEND_STAGE=POST_REOPEN_TXID_INSPECTION_PASS; 366:MACOS_Q06_SPEND_STAGE=CLEAN_CORE_SHUTDOWN_PASS; 368:MACOS_Q06_NATIVE_BIP39_SEND_CONFIRM_REOPEN_PASS; 369:MACOS_APP_STAGE=FROZEN_Q06_BIP39_SPEND_PASS |

## Final Phase 0 boundary check

Verified 2026-11-04T06:56:55.940738+00:00: HEAD unchanged; no tracked diff; acceptance ledger matches its HEAD blob (`0e93a2b213d7dab6d0f5bc9c26997c68493aed8a`), SHA256 `c5e45753c64a9248b6f57312e5bd9eb8f62c2488167490103fa3cd172f42cee2`; exactly the six requested Markdown audit documents are new/untracked. No source/test/runtime qualification was executed. Engineering handoff NO; full Q06 accepted NO. Await owner Phase 1 approval.
