# RC1 owner acceptance and UX audit — 16 October 2026

Only Urriki1502/wam-privacy-wallet-regtest; disposable REGTEST, genuine official
Core v0.1.11 ARM64, pinned native WSP. Qualified RC1 code remains
144d87700b87a241467172adfad3692b41e1d273 (PR36), unchanged. Its docs branch/main,
original wallet data and the owner's running app/Core were not modified.
Proposed fixes live only on audit/rc1-owner-acceptance-20261016, based on PR37.
No automatic merge or release. No personal keys, real funds or mainnet.

## Verdict and confirmed findings

Completed RC1 baseline: **46 PASS / 4 FAIL out of50** (43 original +6 keyboard/password-dialog checks
+1 actual fresh-GUI startup group). All50 PASS on the proposed
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

Additional regression PASS locally:132 application contract tests:99 PASS and33 SKIPPED
(platform skips are not proof of Windows/Linux execution), unchanged independent wallet auditor,
actual Cocoa native Keychain/signing leases/stale-before-sign/stale-before-RPC,
reorg1/12/100, killed-process leases, interrupted publication, wrong/absent anchor,
new-chain recovery, lost actual broadcast reply and irreversible reservations.
[NATIVE_COCOA_REGRESSION.json](evidence/owner-audit/NATIVE_COCOA_REGRESSION.json).
Its cross-session payment-stale fields are false on Mac because that old helper
only exercises them on Windows; false is not PASS. This audit separately reused
the same competing-writer logic on a fresh Mac Core session and explicitly named
native test Keychain: stale before actual native signer entry and before real
broadcast both refused; positive native signature control passed; no mempool
submission and signed reservations retained. This additional source regression
is outside the50 UX checks and outside the unchanged frozen receipt schema:
[Mac stale-payment proof](evidence/owner-audit/qualification/MAC_STALE_PAYMENT_RECEIPT.json).
The two earlier driver attempts failed only harness path resolution/read-only
observation after the intentionally faulted session; neither is counted PASS.
Final run uses an independent verified observer RPC without clearing the fault.

Additional actual-Core/Cocoa cases: masked passphrase acceptance and Cancel,
Sign Escape and Enter/default-Cancel, Broadcast Escape and Enter/default-Cancel
all PASS on both preserved RC1 and proposed code. Anchor/reservation states and
actual mempool were unchanged on each keyboard cancellation. Actual font family
Helvetica Neue, Qt cocoa. Receipts: [baseline keyboard/dialog](evidence/owner-audit/BASELINE_KEYBOARD_PASSWORD_DIALOG.json),
[proposed keyboard/dialog](evidence/owner-audit/FIXED_KEYBOARD_PASSWORD_DIALOG.json).

One additional real startup group PASS on both versions: actual Fresh selector,
masked password acceptance, fresh keys, live Core/WSP/SQLite snapshot at height103,
and clean window close. To protect the owner's Keychain, this source-only startup
fixture routes the native anchor factory to an explicitly named temporary test
Keychain; it still uses the real native factory, Core and crypto. This is not
Finder/Gatekeeper/default-owner-Keychain acceptance. Receipts:
[baseline startup](evidence/owner-audit/BASELINE_GUI_STARTUP.json),
[proposed startup](evidence/owner-audit/FIXED_GUI_STARTUP.json).
All50 individual verdicts: [comparison](evidence/owner-audit/OWNER_ACCEPTANCE_COMPARISON.json).

| Additional check | Original RC1 | Proposed fix, local Cocoa |
| --- | --- | --- |
| Masked passphrase accepted | PASS | PASS |
| Passphrase Cancel performs no operation | PASS | PASS |
| Sign Escape | PASS | PASS |
| Sign Enter/default-Cancel | PASS | PASS |
| Broadcast Escape | PASS | PASS |
| Broadcast Enter/default-Cancel | PASS | PASS |
| Fresh GUI selector/password/live snapshot/close | PASS | PASS |

## Native/frozen requalification

Proposed CODE SHA `427d3b0789d0b7e2da1f506c8dde860b5c6b4575`, [Draft PR38](https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/38).
Eight new workflow_dispatch runs completed **SUCCESS at this exact source SHA**;
each checkout is the same code SHA, not a synthetic pull-request merge commit.
The proposed code branch stays immutable while final evidence is published on a
separate documentation branch. No qualified baseline was advanced or merged.

| Gate | Exact-source CI evidence | Result |
| --- | --- | --- |
| Canonical WSP vectors | [38843576037](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38843576037) | PASS |
| macOS source + frozen app/DMG | [38843580133](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38843580133) | PASS |
| Windows credential/private storage + operational source/frozen + DPI | [38843585494](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38843585494) | PASS |
| Linux contracts + source Qt/CLI + both frozen + repeated developer Core build | [38843589482](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38843589482) | PASS, developer-Core scope |
| Windows official Core/PE/WSP preflight | [38843594122](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38843594122) | PASS |
| Windows genuine Core/101 blocks | [38843598553](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38843598553) | PASS |
| Windows BIP352/SQLite/restart | [38843604563](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38843604563) | PASS |
| Windows native read GUI | [38843609070](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38843609070) | PASS |

[NATIVE_CI_EVIDENCE.json](evidence/owner-audit/qualification/NATIVE_CI_EVIDENCE.json)
records exact jobs and conclusions. PR38 also has9 successful jobs and1 conditional
Linux developer-core SKIPPED; that skip is not counted as PASS. The independent
workflow_dispatch Linux developer-core job116789081626 actually passed. No new
workflow or reduced security assertion was introduced.

| Platform | Source/native regression | Final packaged E2E | Independent downloaded inspection | Physical/human |
| --- | --- | --- | --- | --- |
| macOS ARM64 | PASS, native Cocoa/Keychain | PASS, runner + this MacBook | PASS, Core/WSP/brand/ZIP, DMG VALID, ad-hoc signature | PENDING_OPERATOR |
| Windows x64 | PASS, QWindows/Credential Manager | PASS, native runner, DPI125%/150% | PASS, 341 members/PE/Core/WSP/brand | PENDING_OPERATOR |
| Linux x86_64 desktop | PASS, xcb/root witness | PASS, Ubuntu/Xvfb runner | PASS, members/ELF RW stack/Core/WSP/helper | PENDING_OPERATOR; OS Auto unknown |
| Linux x86_64 headless | PASS, real CLI/root witness | PASS, Ubuntu native runner | PASS, members/ELF RW stack/Core/WSP/helper/no Qt | PENDING_OPERATOR hardware |

The freshly downloaded proposed Mac app was executed on Mac14,9, macOS27.0.1,
ARM64, Qt Cocoa, 16October2026 04:46:49–04:47:46UTC. Exit0; all5 packaged
Core/BIP352/Qt/send/security/recovery/reorg/appearance suite markers present.
Downloaded DMG passed hdiutil verify, app passed strict deep ad-hoc codesign
verification, official Core hashes stayed unchanged after execution, and no audit
app/bundled-Core process survived. This is actual automated MacBook binary testing,
not a runner-only claim, Finder consent or human signoff. See
[local receipt](evidence/owner-audit/qualification/LOCAL_MACBOOK_COCOA_RECEIPT.json).
Windows/Linux execution was performed by their native runners; downloaded Windows
and Linux code is not executed on this Mac. The native frozen GUI probes exercise
7 real input-refusal feedback cases and submitted→confirmed state transitions;
50-case source owner acceptance is a separate suite, not50 packaged tests.

Linux uses the explicitly reviewed developer-source v0.1.11 build. The official
Linux binary's executable-stack policy remains rejected; no official signed Linux
qualification is claimed. Repeated source build success does not automatically
replace the independently approved Core hashes in packages. macOS/Windows retain
their independently pinned official signed upstream bytes. WSP stays at
ac55f13423620252bdbf848c7e8a280c3b84721e; all33 packaged Python source files and
the original WAM artwork were checked (Windows permits only exact reversible Git
LF→CRLF checkout conversion). Upstream Core was not modified.

**Disposition:** original RC1 has3 confirmed UX defects; proposed427d3b0 is
technically qualified by native/frozen REGTEST gates for controlled disposable
review, with all four downloaded packages independently inspected. Keep
Draft PR38 unmerged for owner review. No Final/production/mainnet release or
cross-platform recovery qualification. Remaining physical checks are listed below.

## Downloads and exact payload SHA-256

All packages below were built from427d3b0 and independently downloaded/inspected.
Actions artifacts expire30October2026; these are expiring engineering artifacts,
not a durable Final release. Full payload/Core hashes, sizes, Actions-reported
outer archive digests and expiry timestamps:
[PUBLISHED_ARTIFACTS.json](evidence/owner-audit/qualification/PUBLISHED_ARTIFACTS.json).
The outer Actions digest is GitHub-reported; local inspection independently
recomputes the inner payload/member/public-output hashes.

| Package | Download | Payload SHA-256 |
| --- | --- | --- |
| macos-arm64 DMG | [artifact12022821744](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38843580133/artifacts/12022821744) | `ac0b4ce5a580ce6af5e99be6e20e252617e413d03d1d3312a302aa4608f8eec9` |
| macos-arm64 app ZIP | [artifact12022821744](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38843580133/artifacts/12022821744) | `72ae4590bb01c8674122c4b1d82db8913d0ed03ba1f916682a5f66fba7697704` |
| windows-x64 | [artifact12023245350](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38843585494/artifacts/12023245350) | `8520719ee1a2fa1b3e0df6b54a8154af10779dd40a8313239b8b844100d4eef3` |
| linux-x86_64-desktop | [artifact12022432490](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38843589482/artifacts/12022432490) | `dd57ddf9fd69429bf678415573641c4f2521dd046bc35d903ceab9dbb171604b` |
| linux-x86_64-headless | [artifact12022796655](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38843589482/artifacts/12022796655) | `75eafb5ae656bff36c32d3b314ab1b7125989bae76892e1a825e634fa2a722a9` |

[Common manifest/toolchain verification](evidence/owner-audit/qualification/COMMON_MANIFEST_VERIFICATION.json),
[Mac/Windows member verification](evidence/owner-audit/qualification/MAC_WINDOWS_ARTIFACT_VERIFICATION.json),
[Linux member verification](evidence/owner-audit/qualification/DOWNLOADED_ARTIFACT_VERIFICATION.json).
Build Python3.12.10 on macOS/Windows and3.12.15 on Linux; PyInstaller6.22.3,
Qt/PySide6 6.12.0 where present. Headless package has no Qt dependency. Manifests
contain exact dependencies/build OS; same-source provenance is verified, but no
bit-for-bit reproducible-build claim is made. Windows native receipts preserve
field-specific results: older unused read-GUI fields can be false while
wallet_send_e2e_pass, wallet_live_core and security_live_core record the exercised
operational modes. Linux OS Auto remains unknown/PENDING, never relabeled PASS.

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
