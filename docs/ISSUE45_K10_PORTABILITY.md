# Issue #45 — K-10 P0 Cross-OS / clean machine portability

**Scope:** REGTEST only; macOS ARM64, Windows x64, Linux x86_64.
One Draft PR stacked on #90, not approved for mainnet, merge or real funds.

## 1. Deterministic native pinned WSP/BIP39

`probe_original_bip39_identity` checks the previous trusted K-08 public
receipt, exact REGTEST BIP352 path and two independent K-02/K-03 native
derivation implementations. The probe returns only a canonical PUBLIC
metadata SHA-256; no mnemonic, seed, private key, full receive address,
wallet file or OS native credential is logged or returned.

Source/runner probe, one invocation per genuine native OS:

```console
python scripts/issue45_k10_public_portability_probe.py --disposable-public-fixture
```

The fixture mnemonic is PUBLIC and deterministic (0x35 repeated 32 bytes
of BIP39 entropy); never put real funds into its addresses. All three
public identity SHA-256 values should match. Receipt OS labels alone
are NOT proof of three actual native executions or physical devices.

Independent acceptance requires pinned exact HEAD, genuine signed Core/WSP
binary provenance, same account and receive identities, genuine signed
REGTEST payment on all three OSes and source/frozen parity. No simulated
positive may be upgraded to physical qualification.

## 2. Cross-host Core-native SQLite descriptor wallet

`inspect_original_core_sqlite` reuses K-04 native read-only owner/mode/
file-handle inspections. `compare_core_sqlite_bytes` compares source and
target-copy SHA-256 and exact byte count; equal bytes prove only equal
bytes, NOT descriptor identity, chain ownership, restoration or safety.

For complete Independent acceptance: use Core `backupwallet` to create a
disposable native SQLite backup separately on each OS; transfer only
the offline backup (not WAL, credentials, anchors or live miner data).
Restore using actual pinned disposable WAM Core on the other two
platforms (6 source→target permutations), attest REGTEST genesis,
`getwalletinfo`, `listdescriptors(false)`, same public descriptor identity
and unchanged backup digest. No BDB conversion or private descriptor
disclosure. Full operation is not certified by these Python contracts.

## 3. Clean-OS bootstrap and frozen GUI

K-10 `review_clean_host_target` performs an additional consent-bound,
**read-only** local namespace inspection to deny an existing wallet vault,
runtime SQLite/WAL/journal, symlinked or otherwise ambiguous chain path.
It returns only a locked preflight receipt and CANNOT create an anchor,
import a wallet, certify a fully clean OS or authorize a signer. These
tests use temporary local directories, not physical fresh installations.

K-08 already implements mnemonic-owner preflight and clean target
prerequisite guards. A correct seed is not an OS anchor, Core `.dat`,
Fusion `.enc`, reservation ledger or fully verified transaction history.
Do not copy an OS-specific native anti-rollback anchor between machines.
Do not silently generate a new signer, replay prior uncertain payments,
clear reservations, assume mempool non-observation proves safety, or
automatically unlock/sign/broadcast on GUI import. If K-09 crash recovery
is unresolved, leave the actual portable restore and signer LOCKED.

Independent qualification must validate clean-OS source/frozen Qt recovery
against genuine WAM Core on all three platforms, including restore
history, reorg, signed/uncertain states, native credential continuity
and cross-machine failure/refusal scenarios. Physical tests that cannot
run must remain PENDING, never PASS.

## 4. Current status

**IMPLEMENTED:** K10 public BIP39/WSP portability, strict OS receipt
comparison without fake attestation, Core SQLite byte continuity gates,
negative tests, and public-only native CLI probe.

**PENDING:** full cross-OS native signed-transaction behavior, physical
clean-OS transfer and Core SQLite restore matrix, genuine frozen GUI
recovery, K-09 reservation reconciliation, independent technical and upstream review.

No owner wallet.dat, personal keys, mainnet value or mining secrets
may be used in any test. Keep this PR DRAFT until independent P0 QA.