# Q05 integrated managed GUI lifecycle — dedicated acceptance unit

Baseline Draft121 `f77548de8fb14d2ad4ae007aa5fc46929681c27a`. Preserve
Draft114 and its original raw failure. No change to A06-A/B/C qualification or
recovery policy, Core/WSP pins, supervisor, custody, vault or wallet semantics.
No automatic merge. REGTEST disposable funds only.

## Exact gap and executable evidence

The earlier `managed_gui_probe` intentionally opens no wallet. Its real three
GUI processes cannot qualify original WSP wallet continuity. The packaged
ordinary launch remains the disposable RC1 workflow. This unit adds an explicit
acceptance-only child route to the actual final native Qt executable, using the
existing `ManagedCoreWindow` and `ManagedOperationalWalletWindow` implementations.
It is not a new production entry or authority to adopt an external Core.

`managed_lifecycle_probe` provisions an isolated real supervisor, official pinned
v0.1.11 pair (reviewed developer pair on Linux), BIP39 native vault, original
receive identity, confirmed scanner history, genuine signed reservation and a
transaction accepted by Core whose reply is intentionally lost. It then launches
separate real GUI processes. No Core, RPC, WSP, vault, scanner or GUI result is
mocked. Qt supplies explicit consent/password through actual modal widgets.
Mac uses a new disposable native Keychain, Windows its native Credential Manager,
Linux its already provisioned independent root witness. No owner anchor is read.

Scenarios: wrong password, declined unlock, original read and spending view,
clean close/reopen, actual locked GUI kill/reopen, owned Core kill while a locked
GUI is running, its existing30s background authenticated fail-closed status
cycle, missing recovery consent, explicit exact-target reindex, original GUI
wallet reopen, genuine supervisor supervisor and concurrent-wallet GUI lock contention, actual attached GUI with
no lifecycle controls and read-only stop refusal. An unsupported-version COPY
of public profile metadata is denied in the real GUI before RPC; the original
Core/profile remain untouched. Core loss during an unlocked spending GUI also
disables spending via background sync; that still-live owner can close normally,
then explicitly restart the owned Core and authenticate the original wallet. Datadir identity, genesis/profile, native anchor/ciphertext, receive,
balance/history and irreversible signed/uncertain reservations are compared.
No re-mining or rebroadcast restores the chain or mempool.

Finally kill the actual GUI while the original spending session is unlocked.
Reopen through actual consent/password widgets. Existing plaintext runtime
causes the original vault restore to refuse. This is a **functional FAIL** to
complete the lifecycle, alongside a **correct safety refusal**. Never treat the
refusal as a recovered wallet. Preserve the original runtime, ciphertext,
anchors, scanner/reservations and private failed fixture; no alternate runtime,
auto-delete, replacement wallet, anchor reset or recovery-policy relaxation.
A separately reviewed explicit residue-resolution operation is still required.

## Evidence and strict gate

The probe runs inside the existing native/final frozen wallet invocations on
Mac/Windows and Linux desktop. Linux headless remains a separate non-GUI gate.
Each frozen child executes the actual same binary, with no external Python
fallback; hashes and actual Qt readiness are bound into the public receipt.
Frozen explicit reindex uses the actual existing frozen operator entry. Public
screenshots show disposable post-authentication windows only, never mnemonics
or password dialogs. Private crash data and native anchors are not artifacts.

The existing platform aggregate first rederives unchanged A06-A/B/C evidence,
then independently adjudicates Q05 native and all desktop frozen/DPI reports.
Missing/stale/corrupt/SKIP/PENDING/FAIL cannot count as PASS. Diagnostic collection
may finish successfully while **Q05 and the release aggregate remain FAIL**.
This preserves other test/artifact collection and never weakens an existing gate.
Source policy tests are supplemental only. Exact-head CI/artifacts and the Draft
body are authoritative for current results; local precommit runs are not final
frozen or cross-platform qualification.

A genuine differently versioned running binary is never launched/approved by
this pinned acceptance; unsupported selected profile rejection is the narrower
negative test. Safe authorized crash-residue resolution, broader interruption windows and
physical/independent DEV/security review remain explicitly unqualified. The
prior1001-block RPC TimeoutError evidence is preserved. Full Q05/V1 remain HOLD.
