# Q05 internal security checkpoint — 28 October 2026

Scope: runtime source `7c03988f9ee382dbde47474cccc4fb7ded6ad8ac` in Draft
PR #138. This is the implementing engineer's review, not independent DEV/G7
sign-off, formal verification or production qualification. Mainnet is denied.

## Authority and custody boundaries

Only the actual original Core Popen in its creating supervisor grants mutation
authority. The registered Q03 scope must contain that identical object. No
recorded PID, caller-supplied root, HTTP listener or control token independently
creates Core ownership. Explicit authenticated IPC commands are finite control
operations; there is no generic Core RPC, signing or wallet-secret endpoint.
Q03 HTTP reads, signed CLI writes and external read-only attachment stay intact.

Protected profile/token/config and native root lease bind the controller to its
isolated REGTEST datadir. New launch verifies exact signed/developer-policy Core
digests AND native executable custody before Popen; postlaunch binding still
checks original process image and socket ownership before credentials are sent.
This is not a hardened fd-to-loader guarantee against concurrent OS/same-user
compromise. A foreign or uncertain process is never terminated as cleanup.

## Findings corrected in this PR

| Finding | Correction | Evidence and limits |
|---|---|---|
| Lifetime replay set eventually denies all clients | Fresh connection-bound CSPRNG challenge, TTL, atomic single consumption and bounded live pending state | 5,000 requests, capacity recovery, expiry, wrong HMAC, cross-connection, restart and concurrent duplicate regression tests. Probabilistic 128-bit freshness, not a persisted monotonic counter. |
| Listener can appear before RPC warmup completes | Existing scoped signed CLI readiness before unchanged Q03 HTTP opens | Retained RPC_HTTP_DENIED FAIL diagnostic; later real signed Core lifecycle PASS. Authentication/identity failures are not retried as warmup. |
| Construction-time intake can become stale before launch | Fresh verified binary digests plus native metadata/custody before Popen | Pre-spawn drift/unsafe-custody tests and signed native lifecycle `native-custody-7eea2f7.json`. |
| Faulted original child had no safe explicit stop | Original real Popen plus fresh protected profile/native/chain attestation and signed CLI stop, positive wait | No termination fallback; missing original object refuses. Legacy runtimes without this endpoint remain untouched. |
| Earlier launch can reuse the current numeric PID | Dead recovery requires RUNNING in the CURRENT STARTING-delimited lifecycle, same journal owner, identical original registered Popen and positive exit | PID-reuse counterexample regression; actual retained-Popen Core crash/recovery `native-core-crash-7c03988.json` PASS. No cross-process PID adoption. |
| Transport-unreachable was treated as genuine busy | Propagate transport failures, only genuine busy/warmup signals get bounded retry | Q04 failure diagnostics retained; never count a timeout as a 503. |

## Journal failure model and remaining gaps

Intent is create-only, fsynced and HMAC chained before launch/stop/recovery.
Sequence, transition, profile and datadir identity are checked on reentry.
Truncated, missing-middle, malformed, forged or legacy-missing journal state
refuses without cleanup. Dirty reentry never starts a replacement automatically.

The profile token is local owner custody, not an independent antirollback
witness. Deleting a valid suffix or restoring an entire older same-user/OS
snapshot cannot be proved absent from this journal alone. No wallet rollback
claim is made. The 100,000 lifecycle-event cap reserves stop/fault capacity and
fails before spawn; reviewed compaction remains future work. Status requests do
not consume events. Journal errors do not justify overwriting files or anchors.

A supervisor-process crash loses its original Popen object. Reopening that
dirty profile safely refuses, even if the old Core is alive. A new controller
must not manufacture a Popen facade, register an observed PID, route stop through
external attachment or turn journal HMAC into wallet-spending permission.
Positive live-Core recovery needs a separately reviewed ownership architecture;
the current Core-crash probe does not qualify supervisor-crash reattachment.

The serial control server bounds unauthenticated frames/hello lifetime and
authenticates replies, but loopback availability against a local connection
flood is not guaranteed. Python key-erasure limitations and same-user/OS
compromise remain outside the claimed boundary. HMAC is not encryption; do not
put wallet passwords/seeds/checkpoints into this control protocol.

## Next integration boundary

Current `WalletSession.create` is a disposable funding fixture requiring height
102/103. It is unsuitable for normal managed onboarding. The smallest next unit
is a create-once wallet adapter inside the verified original owner process:

1. Require explicit wallet-creation consent, pinned WSP, live owned Core and
   original datadir/profile. Refuse existing vault/runtime/sidecars before keys.
2. Preserve pinned 32-byte `Keyring()` and existing native `CheckpointVault`;
   no BIP39/account/KDF/AEAD import from historical stacked dependencies.
3. Scan real current chain without fixture funding, save generation 1 to the
   existing envelope under native anchor lease; return no seed/secret over IPC.
4. Keep one owner/thread for SQLite and native anchor lease. Never claim another
   process's Core scope or nest an anchor lease through another object/thread.
5. Design authenticated encrypted locator/publication and explicit reopen as a
   separate unit. Existing encrypted envelopes/anchors stay authoritative;
   missing anchors, partial publication and existing runtimes remain refusals.
6. Preserve signed/uncertain reservations before enabling spending. Startup,
   sync or reconnect must never rebroadcast, reset reservations, rotate keys,
   regenerate a wallet or silently replace its datadir.

Only after the lifecycle and exact-checkpoint foundation is verified should
normal packaged GUI integration proceed. All three OS native/frozen, Windows
125% DPI, physical clean-device and independent review gates stay unresolved.

Supplemental existing-custody AST/crash-model audit at ef700da is retained in
`docs/evidence/q05/existing-custody-audit-ef700da.json`. It verifies unchanged
WalletSession/vault ordering and model mutation sensitivity; it does not audit
new supervisor runtime or constitute independent approval. Full compatibility
constraints are in `Q05_VAULT_COMPATIBILITY_REVIEW.md`.


## Narrow adapter implementation (a87772b)

The proposed create/reopen checkpoint unit now exists as owner-local direct API,
with no IPC command or packaged GUI integration. `supervisor.wallet` is a small
nonsecret create-only HMAC reference binding wallet ID to immutable profile/WSP;
the existing encrypted vault/native anchor remain the authoritative generation.
No KDF/AEAD/vault migration or BIP39 import is introduced. Native anchor lease
covers one-thread restore/sync/save. Successful operations anchor ciphertext,
close keyring/scanner and remove only their freshly created runtime; failure
retains residue and refuses later ambiguous state. A new source-only empty-wallet
native probe is pending; unit reference/custody refusals do not count as E2E PASS.


## Adapter native requalification (fca3115)

Source-only actual signed macOS Core + literal pinned WSP: empty creation,
wrong-password refusal with unchanged anchor/reference/ciphertext, explicit
public REGTEST fixture receipt, funded balance and one-row history fingerprint
across original-owner/Core reopen PASS. Native receipt is
`docs/evidence/q05/native-wallet-fca3115.json`. The probe explicitly signs a
PUBLIC funding fixture; it never signs/spends from the created wallet. This
replaces the earlier adapter-native-PENDING statement only within that narrow
scope. Signed/uncertain wallet reservations, checkpoint interruption, supervisor
process loss, clean-device recovery and normal packaged use remain unqualified.
History summary refuses a full 1000-row page pending proper pagination; it does
not silently claim a complete truncated history. All canonical Q05 cases remain
PENDING. A strict boolean reference guard also rejects authenticated integer 0
as a substitute for `mainnet_allowed=false`.


## Signed/uncertain native continuity (49f7fec / 3436ab7)

The owner-local adapter now returns nonsecret reservation count/state/fingerprint
and reserved/available balances. It does not release or mutate reservations.
Actual existing WalletSession signing at 49f7fec proves signed-state continuity
with zero wallet submissions. At 3436ab7, actual signed CLI/Core submission
returned the matching txid, then the probe discarded only the caller result;
explicit signed CLI observation confirms mempool acceptance. Uncertain state,
reserved balance and full reservation fingerprint survive resync and clean
Core/owner reopen; total wallet submissions remain one. Irreversible draft release
is refused. This is controlled result-loss injection, not physical power loss,
independent review or integrated packaged behavior.
The first uncertain probe failed because its observer used a disallowed scanner
method. That FAIL/profile are preserved; only probe observation was corrected.
No scanner HTTP/method expansion, replay retry or synthetic Core result was used.
Interrupted publication/runtime ownership reconciliation still needs explicit
design and adversarial/native evidence before any recovery policy is introduced.


## Native persistent directory identity (264faa2)

A real host restart changed st_dev from 16777233 to 16777230 for two unchanged
legacy directories (same inode). V1 metadata cannot safely infer the prior
volume and is not automatically rebound. Fresh v2 journal HMACs native stable
volume/file/birth identity. macOS uses fgetattrlist volume UUID and common
file-ID/creation attributes from one guarded FD; Linux uses fstatvfs fsid and
statx INO/BTIME from a guarded FD; Windows uses existing guarded handle native
volume/file/creation data. Unsupported identity fails, no path/st_dev fallback.
V1 remains readable/appendable only under its original exact binding/MAC and
mixed-schema chains refuse. This changes the separate supervisor journal for
fresh records, not a vault/encryption/KDF migration or process-adoption grant.
Source ABI references: Darwin SDK sys/attr.h ATTR_VOL_UUID/ATTR_CMN_FILEID/
ATTR_CMN_CRTIME; Linux v6.8 include/uapi/linux/stat.h (256-byte statx ABI,
INO/BTIME masks); existing Win32 INFO metadata wrapper. Native tests still need
all target OS. A real v2 reboot and full-OS snapshot rollback are not proven.


## Interrupted publication safety (a77a78e)

Real encrypted native publication/fsync is executed, then a typed controlled
fault is injected before anchor advancement. The probe requires the actual
fault context (other failures cannot PASS), unchanged native anchor/reference/
old ciphertext, preserved orphan and runtime, and refusal on the next open.
It runs after a genuinely signed/accepted-but-caller-uncertain disposable wallet
transaction; no extra submission occurs. This is a narrow safety-negative
PASS, not positive recovery, physical failure, independent review or Q05 case
promotion. Recovery must preserve the exact native-anchor authority and all
signed/uncertain reservations; an unknown runtime/orphan is never a cleanup cue.
