# Proposed Q05/Q06 repair sequence — awaiting owner approval

2026-11-04; baseline `8df48952eb4c3c6f2f1db86d31c58125fb2a7e7e`. This document authorizes no implementation. The current session ends after Phase 0. Keep current artifacts and original profiles untouched. All proposed implementation stays in the canonical workspace, on the existing focused Q06 branch unless owner-approved regression scope requires a focused prior-Q fix. No push, merge, dispatch, source-history rewrite or production work.

## Phase 1 proposal

### 1. Establish exact transaction facts and a qualified test baseline

Files for inspection: `wallet_session.py`, `bip39_spend_session.py`, `bip39_native_checkpoint.py`, `bip39_scanner_checkpoint.py`, `managed_wallet_checkpoint.py`, `q05_package_provenance.py`, existing qualification scripts/receipts. Do not start by preparing another payment on the owner profile. Confirm original profile/public txid/commitment from owner evidence; inspect only authenticated read-only chain/mempool/UTXO/history/reservation facts if separately within approved scope. Never load/decrypt original user keys merely to diagnose availability; do not rebroadcast, replace, release or clean anything.

Hypothesis: selected input remains irreversibly reserved or draft after GUI loses stage. First document the actual state and its confidence. If exact identity/ownership is not provable, stop only that original-profile action and continue disposable regression work. Obtain raw named before/after unit logs where possible; otherwise establish a new explicit baseline in the pinned qualified toolchain. Preserve existing 25 errors as unresolved until classified individually. Do not run system Python 3.9 against a >=3.11 project and call it qualification.

Regression requirement: meaningful existing reservation/uncertain tests plus duplicate-prepare, process restart, wrong profile/chain and unavailable-input taxonomy. Real-Core: funded disposable same-chain profile, known exact outpoint/token and independent mempool/history observation. Packaged scenario: show confirmed vs available/reserved values truthfully and recover inspection after restart. PASS: known state is described accurately; no original state mutation, lock release, duplicate signing or broadcast occurs.

### 2. Reproduce and repair normal GUI sign scheduling

Likely files: `bip39_fusion_gui.py`, `bip39_owner_gui.py`, `managed_gui.py` only if the shared worker bridge needs a minimal change; `tests/test_q06_bip39_fusion_gui.py` or existing backup/GUI suite. Current hypothesis TX-01: finished signal drains pending work during approval modal exec.

Add a failing real Qt event-order regression before the fix: open normal Fusion window, prepare, leave approval visible long enough for queued worker.finished, explicitly approve Sign, observe exactly one backend sign, then require a separate Broadcast approval. Also test Cancel, wrong commitment, double click, unrelated sync denial and close during dialog. Use deterministic event-loop synchronization instead of arbitrary sleeps.

Smallest coherent change: schedule approval only after worker lifecycle is complete, or explicitly guard the one pending operation through modal lifetime using the existing execution path. Do not add another transaction engine, background retry or phase wrapper. Signed/uncertain state remains backend authority; unrelated denial must not falsely return UI to a new spendable draft.

Real-Core: one funded disposable BIP39 profile, exact recipient/3 WAM/.0001 fee, authenticate current UTXO before sign and broadcast; observe local mempool and block. Packaged normal GUI: actual mouse/keyboard approval path with delayed operator response. PASS: one prepare→one sign→one explicit submit, matching commitment, correct change, real txid and confirmed debit/change, no auto-resubmit after interruption.

### 3. Make transaction/reconciliation status authoritative

Likely files: `wallet_session.py`, `bip39_spend_session.py`, `bip39_owner_backend.py`, `wallet_executor.py`, `gui_errors.py`, `bip39_owner_gui.py`, `bip39_fusion_gui.py`; existing q05/q06 transaction and checkpoint tests. First inventory whether an existing encrypted structure can carry the minimum exact intent/state/txid references. Reservation-only checkpoint must not be described as persistent signed PSBT recovery. A format/KDF migration is outside current authority; return for a bounded design decision if existing compatible fields cannot safely represent required facts.

Intended change: preserve conservative backend state, expose only fixed redacted/public stage information and consistent immutable snapshots; distinguish unavailable because reserved/uncertain from insufficient eligible funds. Map Q06 errors to fixed public reasons without leaking paths, phrases or arbitrary exception text. Preserve a signed/unknown state after unrelated UI errors. Known RPC rejection must never be used to clear an already uncertain reservation without an independently justified policy.

Regression tests: draft cancellation only; sign-cut; uncertain reply; mempool accepted without reply; confirmed lookup; missing txid not failure; conflicting outpoint; restart; corrupt/stale native checkpoint; no signed downgrade; no foreign profile. Real-Core: deterministic disposable fault injection around exact durable boundaries, inspect counts/fingerprints before/after. Packaged: close/reopen after successful submit and uncertain reply; display retained reservation and safe inspection. PASS: no duplicate transaction, no lost reservation, no false success, exact current history/tip/identity and retained FAIL evidence.

### 4. Restore usable same-profile Lock→Unlock

Files: `bip39_owner_backend.py` (`_lock_q06`, `_reopen_q06`, execute unlock, `_scan_q06`, `_activate_q06`), `bip39_spend_session.py`, GUI callbacks and existing Q06 backend/GUI tests. Reuse `open_owned_spend_session` checkpoint reconciliation; do not bypass it with scratch scans. Seed authentication alone must not publish fully ready/custody-verified UI. Preserve explicit signer activation consent; either restore a previously valid authorization within its documented lifetime or ask the existing explicit confirmation after Unlock. Do not silently grant a new spending capability.

Fix backend secret invalidation under `finally` without removing uncertain scanner/runtime evidence or suppressing the fault. Keep original supervisor/Popen, profile/seed identity, backup HMAC/generation, native anchor and monotonic reservation checks. Publish one coherent backend result to all pages, then update permissions and stage labels together.

Regression tests: real checkpoint exists vs fresh readonly profile; verified/deferred/tampered ack; wrong password; wrong/duplicate seed profile; foreign Core; anchor loss; Core unavailable; session.lock close/guard/save failure; stale tip; signed/uncertain reservations. UI test must use execute unlock and actual worker completion, not just direct `_on_ready` with stub results.

Real-Core: funded profile→activate→lock→wrong-password fail→correct unlock→receive/history/available state intact→repeat several cycles→same-profile app restart. Include signed and unknown reservation variants without resubmission. Packaged: normal Finder launch, same original profile and UI controls; owner can use wallet after successful verification, and fault cases stay unavailable with accurate reason. PASS: same address/profile/chain/history/reservation fingerprint, no new datadir, no bypass, no contradictory seed/custody labels; wrong-password grants nothing.

### 5. Finish approved control and visual UX

Files: `bip39_fusion_gui.py`, `bip39_owner_gui.py`, `fusion_ui.py`, `fusion_pages.py`, `bip39_backup_page.py`, `bip39_locale.py`, existing Qt layout/keyboard tests. Add the requested stateful two-position Lock/Unlock switch only after step 4 is correct. It reflects backend locked/unlocked/busy/faulted state, handles cancelled password and failed authentication, and never optimistically enables wallet functions.

Replace raw activation prompt using existing Fusion confirmation components while retaining explicit scope. Wrap/size sidebar/footer and error panels, make backup heading/progress consistent, align three masked-word cards to owner reference and verify recovery-modal fidelity. Clear recovery fields on every completion route; best-effort memory limits remain honest. Avoid duplicating components or unrelated theme rewrites.

Regression: measure text fit/focus at 900×630, default 1260×810 and larger sizes, light/auto/dark, macOS scale, keyboard-only path, disabled-control explanation and Cancel/default focus. Real-Core: every visual security status driven by the real backend, no test-set flags. Packaged: owner compares normal Q06 UI with approved design; Windows 125/150% later requires actual target-host evidence. PASS: unclipped critical text, truthful progress/states, accessible switch/dialogs, no secret screenshot, owner layout approval retained separately from engineering tests.

### 6. Validate the smallest affected closure and commit locally

Sequence: focused source/negative tests→disposable local Core integration→normal native macOS GUI→one final frozen .app/.dmg qualification after functional fixes settle. Avoid full rebuilds after each layout tweak. Use existing probes as supplemental regression evidence, extend the normal-route scenarios rather than introducing wrappers that bypass user flow. Record exact source/tree, Core/WSP pins, OS/Qt/native trust, timestamps, final executable/DMG hashes, named cases and retained failures. Investigate old-source stdout and dependency manifest discrepancy before claiming exact build closure.

Small local commits should separate a reproduced functional defect and its regression from later UX. Do not commit generated owner-state data. Preserve all old artifacts; publish a new candidate only locally after approved build scope. Three-OS native/frozen requirements remain outstanding until actual hosts execute them; Mac success does not close Windows/Linux gates.

## Phase 2 — integrated real local acceptance, after Phase 1

Use isolated disposable profiles, original owned Core, true BIP39 backup challenge, funded BIP352 UTXO and exact sign/submit consent. Verify wrong-password fail-closed, repeated Lock/Unlock, same-profile restart, real mempool/block confirmation, full anchored history reconciliation, signed/unknown locks, no duplicate transaction, no new empty chain and exact package provenance. Exercise normal GUI entry on native macOS and final frozen app; diagnostic CLI-only success cannot stand in for this flow. Do not change acceptance flags automatically. Target-host/independent backlog remains explicit.

## Phase 3 — owner physical acceptance

Deliver locally verified DMG/hash and concise redacted steps. Owner personally retries the observed 3 WAM flow, backup/recovery UI and repeated Lock/Unlock. G6 stays failed/open until successful owner evidence; Windows/Linux operator gates remain separate. G7 requires a genuinely independent named source-specific review. Owner controls acceptance and any later merge authorization.

## Phase 4 — V1-NET, blocked

Only after explicit owner approval of Q06 completion result. Prepare one dedicated Draft proposal, preserving Q06 zero-peer profile and Q07 identity. First two actual Core processes on one Mac, independent datadirs and RPC/P2P ports, same genesis and validated bootstrap ancestry, real TCP peer handshake, block/hash-tip agreement, cross-node BIP352 transfer/mempool propagation, explicit signing/submit, confirmation and restart/reconnect. Preserve custody under disconnect/reorg/unknown-submit tests and prohibit chain reset/duplicate payment. Multi-device evidence follows; one-Mac success is not two-device acceptance. No consensus changes or GUI-to-GUI networking.

## Approval requested

Owner approval is required by the current master directive: “Source changes require owner approval after the audit” and “Then STOP for owner approval.” Proposed approval is for Phase 1 steps 1–6 within these boundaries, with original owner-wallet mutation/rebroadcast/release still prohibited. No implementation, local source commit, build, V1-NET or remote action has started.

