# Local Q01–Q06 stabilization — 4 November 2026

Owner approved Phase 0 and local repair/build/commits, followed by a separately reviewable V1-NET local branch after genuine local Q05/Q06 tests. This is not owner physical acceptance, independent signoff, merge permission or a change to the canonical acceptance ledger.

## Qualified local result

Runtime/build source: `aaf2de2a13471f955c367561e64276e5353180c5` on `feature/issue45-q06-bip39-12word-20261031`. Live main remains `35553f674851282c6e107e02ba02ef2a7ac5ce64`; remote [Draft #140](https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/140) remains unmerged at `414bebb07ac4705274a0b82617d8e72441b77cbe`. No push, remote PR, merge or CI dispatch was performed.

| Evidence layer | Actual result |
|---|---|
| Source suite | 594 tests discovered; **561 PASS / 33 platform skips / zero failures or errors** in `build/local-evidence-20261104/final-source-suite3.log` |
| Source Q06 contracts | 103 PASS before the final provenance-key correction; supplemental shared-worker Q05 9 PASS and real Qt pending/approval 4 PASS |
| Native macOS Core/GUI | `native-gui-core3.json`: actual Core/Keychain/BIP39 backup, 3 WAM explicit sign/broadcast/confirmation, three normal GUI Lock/Unlock cycles, wrong password refused, retained signed evidence, same-chain recovery and original-owner reopen; qualified runtime source `312c2e1` before probe-only restart/provenance additions |
| Final frozen macOS | Official builder completed all existing Core, Q02, Cocoa, Q04, Q05 lifecycle/security/signed/uncertain recovery and negative cases; normal Q06 GUI send/backup/repeated unlock plus **new Core-process restart of the original profile** PASS |
| Windows/Linux current-source native/frozen | NOT EXECUTED locally; no cross-OS PASS inferred. Existing historical evidence retains its own SHA/trust |
| Owner G6 / independent G7 | Owner's reported macOS failure remains open pending physical retest; Windows/Linux operators and independent signoff remain BLOCKED |

The immutable local distribution snapshot is `build/qualified-q06-aaf2de2/package-output/`. Current source-native, frozen and manifest records are distinct; none is a physical operator receipt.

Final DMG SHA256: `d482f8c2562a7f4c2162d58595ad808357b74ad7c0555419c08df23f4f227f43`.

Frozen executable SHA256: `e53f278da1117725d9f908d32b2d9c44ec69b7ca5f3991ddb25d66f4220b69fa`.

All **54 manifest members** were independently rehashed with zero mismatches. Core hashes remain `7298de701e467eb28b4806cbcbe35edb393861b4b97117017fee4c1b194e3068` / `81a031ebf9b3060b19061b29756d43bcd09b32ad778348b8c3d8321397076e82`; WSP remains `ac55f13423620252bdbf848c7e8a280c3b84721e`. The app remains ad-hoc signed/unnotarized. Local toolchain is under `build/local-toolchain`; setuptools 84.0.0, wheel 0.45.1 and Pillow 12.0.0 now match the existing hash locks. Shared system packages remain an explicit build-environment assumption; no new supply-chain/host-integrity guarantee is claimed.

## Real frozen transaction

From `q06-frozen-spend-evidence.json`:

- Amount 300000000 atoms; fee 10000; change 4449980000; one selected input.
- TXID `a299591a4108d6ecc475926fd988c89dd27e702bcf5aba208bdba19a915895a6`.
- Confirmed height 103; block `9be51639c1db47a6280c3cfd4777da2b99adbe31b54621547c3a3f9dbdb24856`.
- Normal backup verification, delayed GUI approval, repeated Unlock, encrypted signed-PSBT retention and same-profile Core restart are true. Both physical_accepted and independent_reviewed are false.

This transaction belongs to a newly created disposable test profile. The owner's earlier transaction/profile was not opened, rebroadcast, replaced, reset or modified; its historical network outcome remains unverified.

## Confirmed causes and changes

**Send ordering:** the pre-fix real Qt regression received only `prepare` after modal approval, with no `sign`. `_on_ready(prepare)` opened a nested modal loop before assigning the next command; worker.finished could drain that slot first. `Bip39TrialWindow` now buffers the result until thread completion and completes approval delivery before draining the single next command. `ControlWorker` keeps the original Future past its UI wait deadline, emits a pending notice once, and never resubmits. Actual backend timeouts remain failures. RPC, trust, custody and write-retry limits were not relaxed.

**State/availability:** confirmed balance was never equivalent to eligible funds: WSP excludes reserved/mempool-spent inputs and retains privacy-cluster selection. Backend snapshots now carry the existing review/signed/pending-confirmation state; unrelated GUI errors no longer erase signed readiness. A stale or irreversible reservation remains unavailable. The historical owner's WALLET_INPUT_FUNDS_UNAVAILABLE is consistent with this rule, but the precise original outpoint/state was not inspected and is not declared resolved by guessing.

**PSBT evidence:** Q06 reuses the existing transaction engine and native anchored reservations. It additionally publishes create-only AES-GCM/scrypt evidence in the original owned profile for signed, attempted/uncertain and matching broadcast outcomes. It retains signed PSBT bytes, exact intent and expected txid across locking/restart. These supplemental files never authorize replay or reservation release and do not migrate existing vault/KDF formats. Failure faults the session and preserves custody. Native storage/encryption tests verify password authentication and refusal to overwrite; frozen real-Core tests decrypt and compare the three records without logging their contents.

**Unlock:** seed authentication alone had been followed by a scratch snapshot that correctly refused the existing protected checkpoint. The backend now remembers a clean in-session prior spending authorization and restores it only through the existing original-owner/native checkpoint reconciliation path. New-process reopen still requires explicit activation. `_lock_q06` erases its separate password buffer in finally even when the spend-session close fails; ambiguous runtime/session data is retained. Wrong-password and repeated same-profile tests passed. No GUI force-enable or foreign Core adoption was added.

**UX:** stateful painted two-position Lock/Unlock switch; existing Light/Automatic/Dark retained; Fusion consent/password/confirmation dialogs replace the principal raw activation/funding/confirmation prompts; sidebar copy and footer wrapping fit the small window; backup step indicator, scrollable verification page and duplicate heading corrected; successful recovery closes clear field contents. Layout snapshots are supplemental visual evidence, not owner design signoff. `locked-switch-*.png` explicitly has no Core; `package-output/q06-ui-review` records real verified frozen-window views.

## Retained failures and limitations

All raw logs and run identities remain under `build/local-evidence-20261104`. Original owner-tested artifact/receipt bytes are under `build/retained-artifacts/owner-tested-8df4895`; its DMG still hashes to `b2e52eef06bf2c088797b629dd0fc453df0c9ec58c16caef5abaeec967df18c7`. Failed b070c56 frozen app/receipts are retained separately. The first frozen attempt failed before Create because the new probe consumed source_head_sha instead of the existing reader's candidate_source_sha; the final build replayed the entire required builder successfully.

The first native exploratory run caught an introduced str-versus-bytes error in signed-evidence encryption. Its inherited TemporaryDirectory cleanup also removed that disposable failed profile. This was not an owner wallet, but it was an evidence-retention defect: the updated probe and outer frozen builder now retain test profiles, signed/unknown data and failure metadata. A second native attempt hit a driver wait deadline: stack samples showed QTest.qWait/GIL starvation of the real owner thread. The driver now sleeps while releasing the GIL; it did not relax the timeout. Both failures remain FAIL in run history, not silently relabelled PASS.

The failed source processes may retain original test Core children/owner threads. Authenticated control recovery for the retained second profile returned MANAGED_CLIENT_REPLY_DENIED; the removed first profile no longer supplies a verifiable control capability. **No PID adoption, force kill, lock deletion or guessed Core stop was attempted.** Cleanup of those old disposable processes is BLOCKED on recovery through their proven original owner or a separately reviewed owner process action. Current successful native/frozen runs verified their own clean shutdown; no owner wallet/miner was touched.

Fresh empty-chain mnemonic identity is not funded-history recovery from another disconnected chain. Cross-OS current proof, owner clean-device/physical retest, genuinely independent review and exact-main integration remain open. Q06 accepted=false, canonical ledger blob `0e93a2b213d7dab6d0f5bc9c26997c68493aed8a` remains unchanged. Historical Q06 ledger counts remain 15 PASS / 4 PENDING / 5 BLOCKED; they are not updated by quoting this local suite.

## Gate and next-step boundary

Local scope inventory/internal review/source/native-Mac/frozen-Mac and exact artifact evidence passed their recorded scenarios. G2/G3 cross-OS closure is incomplete; G6 physical FAIL/open and G7 independent/integration BLOCKED. **Formal ENGINEERING HANDOFF NO; FULL Q ACCEPTED NO.** No q_gate transition was attempted.

The owner separately authorized local V1-NET work after these local engineering tests, independent of Q06 acceptance. Continue in one separate local branch from this qualified baseline; do not rename Q07, alter isolated profile defaults, update acceptance flags, push, open remote PRs or merge. V19 remains unexecuted until two actual computers are tested.

KEEP: original Core/RPC/custody/checkpoint/Signer/PSBT architecture. SIMPLIFY: one worker result/Future and backend-derived payment presentation. REMOVE: no historical feature, wallet, journal or workspace was removed; only faulty newly introduced probe assumptions were corrected.
