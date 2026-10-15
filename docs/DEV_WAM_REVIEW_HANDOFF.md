# WAM Fusion REGTEST RC1 — technical review handoff

Prepared for collaborative DEV WAM review. NOT sent automatically; DEV_WAM_REVIEWED=false.
Experimental disposable REGTEST only, not mainnet/production/official final release.
Owner testing comes first. Use the exact source SHA and successful native run
links from RELEASE_CANDIDATE_QUALIFICATION.md / integration PR, and verify every
artifact's RELEASE_CANDIDATE_MANIFEST.json and SHA256SUMS.txt. An artifact may
contain this static guide before aggregate multi-platform qualification completes;
its own receipt alone is not a claim all platforms or humans accepted the RC.

## Compact architecture

One application repo: Urriki1502/wam-privacy-wallet-regtest. Legacy is read-only.
Shared WalletSession coordinates reviewed intents, immutable reservations,
checkpoint persistence and actual local Core RPC. Existing Fusion Qt uses the
same session via workers; Linux headless wraps it without importing Qt. There
is no parallel signer/scanner/cryptography stack or synthetic blockchain mode.

Native WSP source pin: ac55f13423620252bdbf848c7e8a280c3b84721e. Its native
secp256k1/PSBTv2, purpose/network-bound AES-GCM/scrypt key backup, scanner SQLite,
checkpoint validation, reorg undo, coin reservations and intent-verifying signer
are reused.28 canonical BIP352 suites remain mandatory; vectors alone are not E2E.

## Platform Core/custody boundaries

- macOS ARM64: official publisher-signed v0.1.11, independent wamd SHA
  7298de701e467eb28b4806cbcbe35edb393861b4b97117017fee4c1b194e3068
  and CLI81a031ebf9b3060b19061b29756d43bcd09b32ad778348b8c3d8321397076e82.
  Keychain holds public generation/digest; private descriptor/no-ACL ciphertext
  storage and per-wallet OS lease remain. App is ad-hoc, not Developer ID notarized.
- Windows x64: official signed v0.1.11; wamd.exe
  31717319535c5b784b2bed3b4d3c9a727f5c062e9534b4d27c59d2ffd04e95a1;
  CLI538a6d1b918b698ce76a949dda982fdda6776e33ba057efaac59b1af59e59d21.
  Credential Manager public checkpoint, protected owner-only NTFS/DACL,
  no reparse/hardlink traversal and global wallet mutation mutex. App unsigned
  Authenticode; native exe/DPI125%/150% gates do not prove human Windows10/11.
- Linux x86_64: reviewed developer build, NOT official signed release. WAM source
  82a1487fd86f7021b1b9fc1524d267fca126f7d4; Bitcoin
  32efe850438ef22e2de39e562af557872a402c31; RandomX
  102f8acf90a7649ada410de5499a7ec62e49e1da. Independent approved Core manifest
  e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806;
  wamd ccc9f0f1d299a1e98a49ff83859aa03e994e83e6ea4b7cd60c327eb1e0e8e4d6;
  CLIada9dabd56d0859b9d64c0b20a05c33cb039b2573f75088443b45c35d5379652.
  ELF stack RW, no W+X/RPATH/RUNPATH and exact root-owned loader/library closure;
  original published RWE Linux release rejected. Owner/ACL/no-follow storage
  plus separately administrator-approved root witness (UID/SO_PEERCRED/CAS/flock).
  No app sudo/service installation or software-only file-anchor fallback.

Original WAM PNG and native branding remain pinned. Build metadata records
actual installed tools/dependencies. Windows Git CRLF WSP checkouts are expected;
verify exact reversible CRLF versus pinned Git LF corpus, not arbitrary changes.
Core executable bytes are never re-signed/replaced to satisfy packaging.

## Transactions / backup / failure paths

Prepare→Review→Sign→Broadcast: separate explicit approval, Cancel default. Sign
anchors irreversible reservations BEFORE native crypto; Broadcast anchors
uncertain state BEFORE genuine Core RPC. Stale writer/chain/UTXO checks and OS
lease span sensitive work. Lost actual reply faults, never auto-retries or
releases locks. Reorgs preserve reservations. Final packaged bootloaders repeat
genuine Core/WSP/SQLite/native GUI or headless gates, including confirmed change.
Fault instrumentation delegates to actual native crypto/RPC; no fake blockchain
or mocked wallet counts as acceptance.

Native backups stay v1/Keychain, v2/Credential and v3/Linux-root-witness bound.
Wrong password, malformed/stale/replaced/missing anchor, unsafe file metadata,
incomplete restore and interrupted publication fail closed. Recovery rescans
real Core; old signed/uncertain locks remain. Same-host fresh-chain recovery
preserves original test accounts while creating a new test receive epoch.
Portable export is design-only, not required for RC1; do not remove bindings.
Future portability must address source freshness, offline guessing and KDF
cost on lower-end hardware before source/destination native acceptance.

## Reproduce / review evidence

Run all existing workflows by workflow_dispatch at the SAME exact candidate ref:
`bip352-vectors.yml`, `real-core-regtest.yml`,
`windows-x64-credential-anchor.yml`, `linux-experimental-regtest.yml`.
The last includes actual root service contracts, separate no-Qt CLI and native
xcb Qt source gates, reviewed Core build and both FINAL binary gates. Mac also
needs downloaded app Cocoa testing on actual ARM64 Mac and DMG validation.
Recipes: scripts/build_macos_bundle.sh, build_windows_bundle.py and
build_linux_wallet.py; only after their final executable E2E do they write the
RC manifest/public package. Preserve immutable Core artifact/pins; expiry or a
changed system-library closure requires independent requalification, no fallback.

All four RC1 artifacts use the common FULL source SHA in their names. Their
manifest records PR head and actual checkout separately; owner-ready builds
must be single_commit_build=true. Successful predecessor PR/synthetic merge
checks do not qualify a new integration SHA. Source and receipts/run URLs,
artifact checksums/expiry and residual findings are in the release report.
Owner launch/tests are self-contained in OWNER_REGTEST_ACCEPTANCE.md.

## Disposition / residual risks

No automatic main merge or official preview publication; owner decides. Physical
Linux is PENDING_OPERATOR (owner reports no authorized host). Native Ubuntu/xcb
is not a physical GNOME/KDE review; OS Auto may be unavailable. Human Finder/
Windows/desktop acceptance and DEV WAM review stay separate from automation.

Unqualified: plaintext unlocked SQLite; best-effort secret memory clearing;
16 receive epochs;10000 Linux witness generations; ambiguous orphan availability;
loss/replacement or rollback of both anchor stores; root/OS compromise; hardware
power loss; guaranteed erasure; hardened loader-to-process binding; generic Linux
distribution portability. BIP352×PayJoin transport/execution stays V2/HOLD.
No production keys, mainnet permission, real funds or exaggerated custody claim.
