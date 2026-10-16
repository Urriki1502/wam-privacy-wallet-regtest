# RC1 owner acceptance and UX audit — 16 October 2026

Only Urriki1502/wam-privacy-wallet-regtest; disposable REGTEST, genuine official
Core v0.1.11 ARM64, pinned native WSP. Qualified RC1 code remains
144d87700b87a241467172adfad3692b41e1d273 (PR36), unchanged. Its docs branch/main,
original wallet data and the owner's running app/Core were not modified.
Proposed fixes live only on audit/rc1-owner-acceptance-20261016, based on PR37.
No automatic merge or release. No personal keys, real funds or mainnet.

## Verdict and confirmed findings

Completed RC1 baseline: **39 PASS / 4 FAIL out of43**. All43 PASS on the proposed
fix using a fresh native Cocoa session with real Core. The four FAIL checks
represent three UX defects; they do not show a broken native signer or loss of funds.

1. P1 feedback: OperationWorker catches every exception and emits one generic
   code; prepare_payment also combines amount/fee errors. Invalid amount, fee,
   ordinary Core address, malformed/checksum address and insufficient available
   single-cluster funds therefore look identical. Reproduction: create a fresh
   disposable wallet, Sync, paste its Core mining address into Send (not a WSP
   silent-payment code), amount0.00100000/fee0.00010000, Prepare. Correct safety
   refusal, but the UI says generic DENIED without identifying the recipient.
2. P1 verification state: _operation_denied unconditionally calls _clear_balance,
   clearing Core/Receive/History and displaying Not verified even after a local
   parsing failure. Every one of14 genuine invalid-input cases reproduced this
   with unchanged anchor, reservations and real mempool; session remained healthy.
3. P2 pending UX: successful Broadcast shows a local receipt, but Sync overwrites
   the status with a generic verified scan before confirmation. Both a payment
   to another fresh account and a self-payment reproduce the missing pending cue.

The owner's existing RC1 process was observed running, but read-only Computer Use
AX access timed out even with its exact path. No owner window actions were taken.
Thus this audit confirms the reproducible failure classes in unchanged RC1 code;
it does not claim to know the owner's exact input, passphrase or live error cause.

## Small proposed fix and safety review

- gui_errors.py maps exact known exceptions to fixed public categories. Arbitrary
  exception text/str(), RPC replies, credentials, private paths and tracebacks
  never become UI messages/signals. Unknown errors use a constant refusal.
- Separate amount/fee errors; recipient instructions specify the full wamrtsp1
  REGTEST silent-payment code, not ordinary Core addresses. Fund refusal explains
  confirmed availability, privacy-cluster selection and retained reservations.
- Only known pre-mutation input/coin-selection refusals may retain an already
  verified snapshot, explicitly labeled Last verified. A fresh Sync reattests it.
  Locked/faulted/unknown, stale, custody and actual node failures still hide data;
  prepare/sign/broadcast still verify live Core/anchors/UTXOs independently.
- Track only the last local submitted txid in the UI. Sync says confirmation has
  not yet been observed; a genuine confirmed history row clears it. No invented
  mempool balance, automatic retry, anchor reset or reservation release. Lock and
  fault clear it. This is not persistent transaction tracking across restart.
- Existing actual source/frozen GUI probes now exercise7 invalid-input cases,
  unchanged reservation/anchor/mempool evidence, reattested Sync and submitted→
  confirmed feedback. Existing signing/crash/reorg/uncertainty gates remain intact.

Safe examples: “Recipient not accepted: use full REGTEST silent-payment code”;
“Fee must be0.00000001–0.01000000 WAM”; “Not enough available confirmed funds in
one privacy cluster”; “Broadcast result uncertain; do not retry automatically”.
Unlock/recovery messages intentionally group passphrase/snapshot/custody failures
where the lower layer does not distinguish them safely. They never claim that
resetting an anchor is a remedy.

## Completed automated matrix — actual Core, no mock E2E

PASS requires the recorded assertion; FAIL is preserved, not relabeled. The
baseline runtime/src/workflows/pyproject matched qualified RC1 before execution;
the audit driver is separate test code. See BASELINE_SCOPE.json. Initial harness
attempts corrected decoder pixel format and malformed-envelope framing; partial
attempts are not used as completed acceptance.

| Automated check | Original RC1 | Proposed fix, local Cocoa |
| --- | --- | --- |
| fresh_wallet_core_wsp_sqlite | PASS | PASS |
| receive_code_native_wsp | PASS | PASS |
| rendered_qr_independent_decode | PASS | PASS |
| six_screen_navigation | PASS | PASS |
| amount_empty_safe_refusal | PASS | PASS |
| amount_negative_safe_refusal | PASS | PASS |
| amount_comma_safe_refusal | PASS | PASS |
| amount_dust_safe_refusal | PASS | PASS |
| amount_precision_safe_refusal | PASS | PASS |
| fee_zero_safe_refusal | PASS | PASS |
| fee_negative_safe_refusal | PASS | PASS |
| fee_excess_safe_refusal | PASS | PASS |
| fee_precision_safe_refusal | PASS | PASS |
| recipient_empty_safe_refusal | PASS | PASS |
| recipient_garbage_safe_refusal | PASS | PASS |
| recipient_standard_core_safe_refusal | PASS | PASS |
| recipient_bad_checksum_safe_refusal | PASS | PASS |
| insufficient_funds_safe_refusal | PASS | PASS |
| specific_input_error_feedback | FAIL | PASS |
| validation_error_not_core_failure | FAIL | PASS |
| other_exact_review | PASS | PASS |
| other_sign_cancel | PASS | PASS |
| other_sign_approved | PASS | PASS |
| other_broadcast_cancel | PASS | PASS |
| other_real_pending | PASS | PASS |
| other_pending_gui_feedback | FAIL | PASS |
| other_confirmed_math | PASS | PASS |
| recipient_independent_scanner | PASS | PASS |
| self_exact_review | PASS | PASS |
| self_sign_cancel | PASS | PASS |
| self_sign_approved | PASS | PASS |
| self_broadcast_cancel | PASS | PASS |
| self_real_pending | PASS | PASS |
| self_pending_gui_feedback | FAIL | PASS |
| self_confirmed_math | PASS | PASS |
| native_background_sync_responsiveness | PASS | PASS |
| native_resize_theme_screenshots | PASS | PASS |
| lock_redaction | PASS | PASS |
| wrong_password_refusal | PASS | PASS |
| malformed_recovery_refusal | PASS | PASS |
| wrong_recovery_password_refusal | PASS | PASS |
| latest_backup_recovery | PASS | PASS |
| correct_unlock | PASS | PASS |

The other recipient is another fresh WSP Keyring and independent actual Scanner
on the SAME real Core chain. A separate app starts an unrelated disposable chain
and cannot observe that transfer; cross-instance networking/shared-node operation
is outside this preview. For external payment, sender balance decreases by amount
+fee; receiver scanner sees100000 atoms. Self-payment decreases total balance by
fee only. Pending balance remains confirmed-only, while real getrawmempool proves
submission. Actual before/after/history credit/debit atoms are in the receipts.

QR decoding uses independent zxing-cpp2.3.0 over actual rendered grayscale widget
pixels; the exact decoded code matches native WSP. This dependency is audit-only
in an isolated output folder, not added to application/packaging dependencies.

Additional regression PASS locally:132 application contracts (33 platform skips,
not proof of Windows/Linux execution), unchanged independent wallet auditor,
actual Cocoa native Keychain/signing leases/stale-before-sign/stale-before-RPC,
reorg1/12/100, killed-process leases, interrupted publication, wrong/absent anchor,
new-chain recovery, lost actual broadcast reply and irreversible reservations.
[NATIVE_COCOA_REGRESSION.json](evidence/owner-audit/NATIVE_COCOA_REGRESSION.json).

## Native/frozen requalification

New exact source commit and native CI/artifacts: **PENDING until dispatched and
observed**. Previous RC1 PASS does not qualify the changed GUI. Reuse the existing
eight workflows and their final executable gates; no new workflow or reduced
assertion is introduced. Do not install the proposed binary over the owner's
running RC1 or treat this source-only result as frozen acceptance.

## Evidence and reproduction

[Baseline43 checks](evidence/owner-audit/BASELINE_OWNER_ACCEPTANCE.json),
[fixed43 checks](evidence/owner-audit/FIXED_OWNER_ACCEPTANCE.json),
[baseline failure cases](evidence/owner-audit/BASELINE_INPUT_FAILURE_REPRODUCTION.json),
[fixed failure cases](evidence/owner-audit/FIXED_INPUT_FAILURE_REPRODUCTION.json).
Screenshots contain disposable fixture/public transaction data only:
[baseline recipient refusal](evidence/owner-audit/baseline-recipient_standard_core.png),
[fixed recipient guidance](evidence/owner-audit/fixed-recipient_standard_core.png),
[fixed unavailable funds](evidence/owner-audit/fixed-insufficient_funds.png),
[self-payment confirmed](evidence/owner-audit/fixed-self-confirmed.png).

Reproduce on authorized macOS ARM64 with the exact original Core/pinned WSP,
PySide6/qrcode and existing source test environment. Install zxing-cpp==2.3.0
only into <output-parent>/test-deps, then:

```sh
PYTHONPATH="$PWD/src" QT_QPA_PLATFORM=cocoa python scripts/owner_acceptance.py \
  --core /absolute/verified-core --wsp-source /absolute/pinned-wsp \
  --output /absolute/new-audit-output
```

The output folder must not already exist. Only isolated native test Keychains
are created/removed after cleanup; existing/default owner Keychain is untouched.
Nonzero exit for any FAIL. Fixtures never delete anchors to bypass a denial.

## Remaining physical/manual observations

PENDING_OPERATOR only where technical automation is not equivalent:

- Human comfort/legibility, focus/keyboard feel, perceived latency and OS dialogs
  on the owner's actual screen. Automated screenshots/font family/geometry/event
  timers cover technical rendering/responsiveness, not subjective usability.
- Physical camera QR scanning, Retina/external-monitor rendering and display
  scaling on actual hardware. Decoder roundtrip is automated PASS. Native Cocoa
  clamped requested1440x900/1920x1080 to1440x840/1920x840 on this display; those
  images are not claimed as full900/1080-height physical-screen acceptance.
- Finder/Gatekeeper/notarization/operator OS approval; genuine local binary startup
  and clean teardown can be automated, but consent/system-policy decisions stay
  with the operator. Do not disable security or replace existing wallet data.
- Real OS-wide appearance preference changes and GNOME/KDE/Windows10/11 hardware
  review. Qt Light/Dark/Auto event handling is covered by native probes; Linux
  Xvfb reports Unknown where appropriate. No authorized physical Linux host exists.
- The exact owner's currently open failure input remains unobserved because AX
  access timed out. All common input classes have been tested without requesting
  personal secrets or accessing that session's database/config/Keychain.

Native backups remain platform-bound; no cross-Mac/cross-OS recovery or portable
export claim. Plaintext unlocked SQLite, best-effort memory clearing,16 epochs,
anchor/OS compromise/power-loss and loader-binding limitations remain explicit.
DEV review is not sent; main/qualified RC1 branches remain unchanged.
