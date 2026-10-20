# R-01 — Offline signed WAM Core intake (first source subgate)

Refs #45 / Release Trust / R-01 [P0]. One Draft PR stacked on green
[F-10 #101](https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/101)
at `5b14535dc7a7420ab4d26c77ab3ae6eebd895a1d`.
**No merge, activation, auto-update, mainnet or external node access.**

## Exact implemented contract

`wam_regtest.r01_release_intake.verify_offline_core_intake` accepts
**operator-selected local public files**, never downloads or starts anything:

- Public `SIGNING-KEY.asc`, exact `SHA256SUMS`, detached `SHA256SUMS.asc`
  and exact platform archive for recognized v0.1.11/v0.1.12.
- All inputs are private snapshots from bounded regular source files;
  refuse symlinks, hardlinks, missing/empty/oversized or drifting sources.
- Reuse established `release._validate_signed_sums` GPG implementation:
  isolated temporary keyring, fingerprint pin
  `4BD4A8D3AFD43F5CBCB500E23798462FE00ADBA4`, and actual detached
  signature over the byte-exact `SHA256SUMS`. No keyserver/default keyring.
- Match expected **Core** archive exact name for macOS ARM64, Windows x64 or
  Linux x64 and compute SHA-256 over the snapshotted archive bytes.
- Return redacted and versioned-nature authentication result; explicitly
  mark independent key-distribution provenance, runtime compatibility,
  Core execution, sign/broadcast, installation and mainnet authorization
  as **false**. The result is **NOT** a Fusion executable approval manifest.

Recognition of v0.1.12 is **not** a Core support/activation allowlist.
The upstream v0.1.12 GitHub release was seen as **pre-release** on
2026-10-20. Its status may change; do not infer a future release's trust
from a historical GitHub API response. Detached GPG identity and exact
signed archive hash must be checked on the operator's actual input bytes.

## Tests and actual evidence

`tests/test_v1_r01_release_intake.py` uses synthetic public fixture bytes
with a stubbed signature result to verify the **input and output policy**,
failure/refusal taxonomy, archive digest matching and prohibition of
implicit activation. **A mocked signed digest is never native GPG PASS.**

The existing `release.py` and `windows_release_preflight.py` retain their
separate already-pinned v0.1.11 native release policies. This PR does not
replace or weaken their per-platform approved hash checks.

## Required remaining R-01 P0 qualification (PENDING)

1. Independently authenticate upstream signing public key and exact primary
   fingerprint through trusted DEV/release-process evidence, not a key
   fetched from the same compromised release page alone.
2. Run the actual public offline `SHA256SUMS.asc` + signed manifest +
   archive verifier for the published release on macOS, Windows and Linux,
   with exact source SHA, GPG version, input SHA-256 and redacted receipt.
3. Exercise an actual tampered manifest, wrong signer, signed-archive
   mismatch, unavailable/revoked key and rollback conditions via real GPG.
4. Isolate archive content/member extraction controls and verify platform
   executable provenance separately before any runnable staging.
5. R-02 compatibility matrix and explicit approval still must pass
   independently before using any new binary with a test wallet.

**CI success of this initial R-01 policy test is not overall R-01 P0
acceptance, new Core verification, and certainly not mainnet readiness.**
