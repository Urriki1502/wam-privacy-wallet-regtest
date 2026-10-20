# Issue #45 / R-04 — Final package output integrity gate

**Task:** R-04 [P0], one Draft PR stacked on green R-03 PR #104
commit `50a11745df03242ccc1115c74d4fe3d885cd1d03`.
REGTEST only. Does not merge, change Core version, install certificates,
access a wallet or launch user/third-party miners.

## Existing qualified foundations reused — no builder rewrite

All three builders already use clean-clone provenance, pinned official
macOS/Windows Core v0.1.11 or separately reviewed Linux developer Core,
pinned WSP-1 source, native final executable real-Core tests, SHA manifests
and per-platform release candidate metadata. Linux emits independent
headless and desktop archives. None implies full byte-for-byte
cross-build reproducibility or independent physical/vendor release review.

## Implemented in this narrow slice

`src/wam_regtest/r04_package_audit.py` is a strictly read-only final
output inventory auditor. It now runs **after**
`write_candidate_manifest` in all three existing builder scripts,
before printing the packaging PASS stamp.

It checks:

- the final `RELEASE_CANDIDATE_MANIFEST.json` profile is correctly scoped
  to REGTEST, platform, source hash, pinned WSP hash, Core pair SHA-256;
- every regular output file, including nested Windows UI evidence files, is
  exactly enumerated in `files_sha256`; missing/extra paths fail closed;
- all actual file bytes match the declared SHA-256, without following
  symlinks/reparse points or accepting multi-link regular files;
- final platform `SHA256SUMS.txt` covers the exact public top-level file
  set, including the final candidate manifest; reject wrong hash, duplicate
  entry, unsafe name, unsorted entries or unexpected extra/missing output;
- no manifest may assert mainnet, production, official final release or
  independent DEV approval in this experimental scope.

`tests/test_v1_r04_package_audit.py` uses only public synthetic files
to exercise all hostile input, mutation and inventory cases. Such unit
fixtures are NOT genuine WAM Core or execution evidence. Existing native
macOS ARM64, Windows x64, Linux x86_64 desktop/headless frozen E2E jobs
must run their actual final package verifier at this PR's exact HEAD.

## Explicit guarantees NOT provided

An attacker who can replace the files AND their manifest can forge a
self-consistent inventory. This is not a GPG signature, toolchain
reproducibility proof, supply-chain vendor attestation, Linux distribution
portability, notarization, Windows Authenticode signature, genuine-Core
runtime test or physical/DEV acceptance.

R-04 full P0 remains PENDING for exact-code cross-OS import/restore,
independent clean-build comparison and trust provenance, validated
vendor signing/notarization where authorized, full frozen GUI review,
operator and DEV physical testing, and up-to-date complete three-OS
source/Core/frozen CI at one integration revision. Never relabel RC1
historical PASS as later integrated V1 PASS.
