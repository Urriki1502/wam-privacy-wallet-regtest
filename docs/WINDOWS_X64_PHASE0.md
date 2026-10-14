# Windows x64 port — Phase 0 (offline signed Core intake, NOT an app release)

**Target repository:** `Urriki1502/wam-privacy-wallet-regtest`.
**Base:** `main` at `50e1ea94df61b8400cbab3bffe0fbdd285c6b419`.
**macOS ARM64:** frozen V1 acceptance continues independently. **Linux:** HOLD.

## Grounded status

- Official WAM Core v0.1.11 has a published `wam-coin-v0.1.11-x86_64-w64-mingw32.zip` asset and signed SHA256SUMS; **no native Windows wallet build, node test or ZIP member fingerprint is accepted yet**.
- WSP-1 scanner still imports POSIX `fcntl` in the pinned baseline. The Windows native `LockFileEx` replacement is proposed in upstream WSP PR #9, which is OPEN as of this review. Never remove locking or silently substitute a thread-only lock.
- Existing V1 macOS Keychain, `security` CLI, private-directory ACLs, native `flock`, Mach-O bundle/provenance and notarization behavior are macOS-specific. Directly invoking the macOS wallet on Windows will fail closed.
- Python/Qt view models, BIP352 point derivation, PSBTv2 and some wallet policy may be reusable after explicit native dependency tests. Do not copy cryptography or create a second derivation engine.

## Implemented here (Stage W0)

`wam_regtest.windows_release_preflight` is a **non-executing** Windows release ZIP shape checker. It reuses the existing pinned GPG/SHA256SUMS verifier, refuses ZIP traversal and duplicate entries, checks for two `bin/*.exe` candidates and validates PE32+/AMD64 structural headers. It returns only coarse hash/identity evidence and **always** denies native execution, loader binding, signing, scanning, mainnet and wallet readiness. It does not extract any file and cannot authorize a runnable Windows bundle.

Once an official download is independently obtained, run locally with authentic input files:

```
python -m wam_regtest.windows_release_preflight \
  --archive /path/to/wam-coin-v0.1.11-x86_64-w64-mingw32.zip \
  --signing-key /path/to/SIGNING-KEY.asc \
  --sha256sums /path/to/SHA256SUMS \
  --signature /path/to/SHA256SUMS.asc
```

These paths are examples, not proof the official archive was inspected in this PR.

## Staged acceptance after W0

1. **W1:** authenticate the actual official Windows Core artifact on native Win64 CI, record archive/member hashes and expected PE architecture, actual dependencies and build provenance. Separate executable loader/OS process identity from archive hashes.
2. **W2:** upstream WSP scanner native Windows x64 import/lease, interprocess contention, SIGKILL-equivalent exit release, SQLite reorg and official 28-vector conformance — never reinterpret a Mac pass as Win64 pass.
3. **W3:** interface-based backend for secure file custody, `LockFileEx`, DPAPI/CNG or equivalent approved key/anti-rollback anchor; include upgrade/backup/crash threat model. Preserve signed/uncertain reservation locks; reject missing anchors.
4. **W4:** native Windows Core v0.1.11 isolated REGTEST RPC/101-block smoke, actual BIP352 transaction receive/scan, native Qt show/history, real PSBT sign/broadcast/reorg/recovery. Require explicit user consent and no imported real keys.
5. **W5:** frozen Windows x64 `.exe`/installer build, original WAM Core binary identity, independent security gate, fresh process packaged E2E and manual Windows GUI/Gatekeeper-equivalent review. Never promote to production based on synthetic fixture/packaging-only PASS.

## Non-negotiable boundaries

- No Windows execution of unsigned/unqualified binary, no mainnet or real funds.
- No change to macOS WSP/Core pins or macOS pipeline; any future shared interface must preserve exact macOS regression gates.
- No Linux execution; wait for qualified official ELF replacement/review.
- PayJoin remains validation-only in V1; BIP352×PayJoin integration is V2.
- A format-accepted ZIP fixture is **not** a verified official release. GPG validity and native on-host attestation are distinct gates.
