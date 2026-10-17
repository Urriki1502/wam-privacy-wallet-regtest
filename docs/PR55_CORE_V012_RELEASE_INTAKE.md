# Issue #45 R-01/R-02 — WAM Core v0.1.12 release intake (PR #55)

**Scope:** Signed release **intake only**, offline, read-only. New module and V1 unit contracts; no Core executable is launched, replaced, staged in a wallet datadir, or approved for Fusion operations. Existing v0.1.11 runtime pins and Core Update Manager deferred P1 are unchanged. Work is a **sibling branch to Codex PR #54**, based on #53, with no merge.

## Evidence and truth status

| Gate | Status |
| --- | --- |
| Official GitHub v0.1.12 release identified, marked pre-release, with leading MANDATORY consensus warning | OBSERVED (source metadata only) |
| Hard-pinned signing key, detached SHA256SUMS.asc -> SHA256SUMS -> archive check, platform/shape/rollback guards | CODED + UNIT TESTED |
| Real official v0.1.12 signature/manifest/archive bytes independently verified | PENDING — no claim from API metadata or mocked tests |
| Exact native WAM v0.1.12 process SHA, verified provenance and RPC compatibility profile | PENDING |
| Actual REGTEST v0.1.12 native/frozen E2E, BIP94 behavior, 3 OS and DEV physical review | PENDING |
| Issue #45 integrated V1 R-01/R-02 PASS | PENDING |

The code reuses the **existing** isolated GPG primary fingerprint and detached-signature verifier from wam_regtest.release (hard-pinned 4BD4 A8D3 AFD4 3F5C BCB5 00E2 3798 462F E00A DBA4). It enforces exact parsed installed/minimum versions, authenticates the archive against the **signed** manifest, examines archive member paths and sizes without extraction, and reports installation_authorized=false and wallet_signing_authorized=false even after success. An unexpected key, missing/invalid signature, bad digest, unsafe ZIP/tar path, missing node or CLI, or old version yields a redacted refusal. This is **not** a user-facing updater.

The release body's first nonempty MANDATORY: line is **not** itself covered by the detached OpenPGP checksum signature; the CLI treats its urgency as **UNVERIFIED advisory** rather than proof of consensus or permission to install. Missing data is **UNKNOWN**, never “up-to-date”.

## Run offline preflight on an isolated disposable host

Download the four required files from WAM's official v0.1.12 release. Independently verify the identity of the official public key. Use **absolute** local paths:

~~~sh
python -m wam_regtest.core_release_preflight \
  --platform macos-arm64 \
  --archive /absolute/wam-coin-v0.1.12-arm64-apple-darwin.tar.gz \
  --signing-key /absolute/SIGNING-KEY.asc \
  --sums /absolute/SHA256SUMS \
  --signature /absolute/SHA256SUMS.asc \
  --installed v0.1.11 --minimum v0.1.11
~~~

Use --platform windows-x64 + matching official .zip, or linux-x64 + matching official .tar.gz. Success reports SIGNED_CORE_V012_INTAKE_ONLY_COMPATIBILITY_PENDING. Do not interpret positive unit mocks as cryptographic PASS. Existing test_v1*.py CI suites (Linux/Windows) and Mac full tests cover the new negative/shape contract without any new workflow.

**Next separate engineering gate:** Verify genuine signed downloaded archives and actual independently approved v0.1.12 executable pair; add a distinct, opt-in Core compatibility profile only after complete native REGTEST E2E on all three OS, including version/network/genesis, BIP94 REGTEST, independent treasury/halving and 99/100/101 coinbase maturity, WSP/BIP352, actual Send/Sign/Broadcast and uncertain reservation locks, reorg, backups, recovery and frozen packaging. Keep v0.1.11 qualified pins intact until that acceptance is demonstrated.
