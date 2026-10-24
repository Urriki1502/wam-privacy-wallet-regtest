# Platform qualification checkpoint — 15 October 2026

> Historical 15 October checkpoint. Current integrated RC1 source, downloads and acceptance: [release qualification](RELEASE_CANDIDATE_QUALIFICATION.md). Resume using [release handoff](CODEX_RELEASE_QUALIFICATION_HANDOFF.md); do not re-dispatch the old one-shot scheduler.
Code candidate: `be294c19dba02b5d8016cf76520b40975ee20c96` (Draft PR34).
Main remains `50e1ea94df61b8400cbab3bffe0fbdd285c6b419`; no stack merges.
Documentation commits after this code do not retroactively qualify new runtime.

| Platform / gate | Actual evidence | Disposition |
| --- | --- | --- |
| Linux x86_64 source custody/root witness | native-contracts, actual root service/UID/CAS/flock/crash tests in [38733851062](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38733851062) PASS | Developer REGTEST candidate |
| Linux no-Qt source wallet | actual CLI/Core/WSP/sign/broadcast/change, reorg1/12/100, uncertain locks, stale sign/broadcast, two fresh-chain recoveries in same run PASS | Source acceptance only |
| Linux native Qt source | same run native xcb/Xvfb workers, separate approvals/default Cancel, confirmed payment, lock/backup/recovery/fresh-Core native window PASS | Six Fusion screens; OS Auto/human signoff pending |
| Linux FINAL headless executable | same run frozen-wallet(headless) PASS | No Qt/shiboken, actual bundled Core/WSP E2E |
| Linux FINAL desktop executable | same run frozen-wallet(desktop) PASS | Actual bundled Qt/xcb/Core/WSP E2E |
| macOS ARM64 source + FINAL app/DMG | [38733851084](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38733851084) PASS | Official Core/Keychain/security gates retained; human Finder/appearance review pending |
| Canonical BIP352 vectors | [38733851085](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38733851085) PASS | Pinned WSP, 28 canonical suites |
| Windows x64 exact-code regression | [38734182038](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38734182038) PASS | Credential/private custody, real Qt wallet, frozen exe and125%/150% DPI gates PASS |
| Repeated Linux developer Core rebuild | same Linux run developer-core PASS; all six jobs PASS | Rebuild proof does not replace independently approved Core used by wallet gates |
| Portable/cross-OS backup migration | No implementation/acceptance | HOLD; [foundation](PORTABLE_BACKUP_FOUNDATION.md) is design only |

## Exact public Linux artifacts

Successful final executables were published only after their native acceptance.
Each artifact includes the tarball, `LINUX_PACKAGE_MANIFEST.json`, `SHA256SUMS.txt`,
real E2E receipt and public root-helper source/policy for administrator review.

- [Headless artifact11970254824](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38733851062/artifacts/11970254824)
- [Desktop artifact11970854820](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38733851062/artifacts/11970854820)
- [Source Qt evidence/screenshots11971044723](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38733851062/artifacts/11971044723)
- [Source headless evidence11971498887](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38733851062/artifacts/11971498887)

GitHub artifact ZIP digests (metadata, separate from inner tarball checksums):
headless `30c970fb74439c3bc83df754f498583cce49f46ec2fb81c58ea398ae704f1c8c`;
desktop `a7511e2eab671a052ba5fd28c80f0abf43baedd9c68b540d598cc1a046802479`.
Both downloaded tarballs were independently read on the Mac without extraction
or ELF execution. All top-level checksums, every regular member and safe internal
link, original brand,33 WSP source members, reviewed root helper, frozen receipt,
independent Core hashes and bootloader/Core stack RW matched. Headless has180
regular members/no links/no Qt; desktop441 regular members/25 internal links.

| Inner tarball | SHA256 |
| --- | --- |
| Headless | `387c3d8ad3716b31a8f3892f67b8ec3444376a8649e72d134b8a6d60bf14fd8b` |
| Desktop | `66847f30e2175de5a5404532ae87b5239ef12b5a35725fd13312f76e7ffe9bf3` |

Both manifests distinguish source PR HEADbe294c1 from actual merge checkout
`b6824f9990d04db1553465ac32964ade8e0e22f5`. Dependencies: PyInstaller6.22.3,
coincurve21.0.0, cryptography50.0.0; desktop additionally PySide6 6.12.0/qrcode8.2. Native Linux execution here is impossible:
the engineering host is macOS ARM64. Runner PASS and offline artifact inspection
must remain distinct from hands-on Linux desktop acceptance.

The independently approved Core manifest remains
`e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806`.
Its exact binary pair is `wamd`
`ccc9f0f1d299a1e98a49ff83859aa03e994e83e6ea4b7cd60c327eb1e0e8e4d6`
and `wam-cli`
`ada9dabd56d0859b9d64c0b20a05c33cb039b2573f75088443b45c35d5379652`.
Source revisions and ELF/system-library policy are in
[developer Core policy](LINUX_DEVELOPER_CORE_POLICY.md). Published Linux v0.1.11
with executable GNU_STACK remains rejected. Developer source build is explicitly
not an official signed release. Upstream WAM source was not modified.

## macOS and Windows artifact provenance

- [macOS app/DMG artifact11970334729](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38733851084/artifacts/11970334729): GitHub ZIP digest `6cd91204c591f19241bf323179bc5ce5fbb4f7c27fd4d1c955d0e7b3ba2d2085`, named with actual PR merge checkoutb6824f9.
- [Windows operational exe artifact11974571837](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38734182038/artifacts/11974571837): ZIP digest `aee2bbfee304f542da4f0385b814178f4c4ae5e33c9f94aba5c432b5941e2156`, exact dispatch HEADbe294c1.

Native runner gates execute their final packaged applications and preserve the
independently pinned signed original `wamd`/`wam-cli` pairs. App packaging is
experimental/ad-hoc or unsigned; no Developer ID notarization/Authenticode or
production claim. Both current artifacts were independently downloaded/inspected on the Mac.
Windows: all341 bundle files, PE32+ AMD64 application/Core identity, independent
Core hashes, original PNG and33 WSP files verified. Windows Git checkout stores
those source files as CRLF: every byte equals the pinned LF corpus with only
reversible LF→CRLF conversion; raw checksums also match its own manifest.
No runtime/CI gate or source implementation was changed for this distinction.
Windows cannot be executed locally on this ARM64 Mac.

macOS: app ZIP/DMG checksums,111 safe internal links, both independently pinned
ARM64 Core members, original PNG/ICNS and33 exact WSP source files verified.
`hdiutil verify` reports the downloaded DMG VALID. The newly downloaded FINAL
app also PASSed automated Cocoa real-Core E2E on this actual ARM64 MacBook:
native payment/change, reorgs, OS lease/checkpoint failures, uncertain broadcast,
backup/lock/recovery/fresh-Core reopen, and Qt Auto/Light/Dark event handling.
This is local automated MacBook evidence; human Finder and OS-setting interaction
are still pending. Local receipt/log/screenshots are saved in project
`outputs/cross-platform-qualified-be294c1/macbook-cocoa/`.

| Additional downloaded artifact | Inner file SHA256 |
| --- | --- |
| Windows operational ZIP | `49fb8e3d120f5aaed67f059b1d01dc9581d448dc42a6332a5798b3cdf2d885d7` |
| macOS app ZIP | `459a1f638e81a30a089f951ed5573365f873d5b68dbd55d856288c70bb030621` |
| macOS DMG | `ddcd42610a45d7c26f9ee45a746a08041e7a93da0c92863237fd686e45e95880` |

## Remaining qualification boundaries

Linux Xvfb reports no qualifying native color-scheme events (`qt_auto_events_verified=false`).
Manual Light/Dark and Auto selection/capture passed; GNOME/KDE appearance events,
desktop launch/close and operator visual acceptance remain pending; see the
[manual operator procedure](LINUX_OPERATOR_ACCEPTANCE.md). macOS and
Windows runner evidence likewise cannot substitute human device signoff.
Original supplied PNG remains hash-pinned across platforms; no generated image.

No Final/release/production classification. No mainnet, real funds, personal
keys, cross-Mac migration or PayJoin execution. Existing authenticated backups
remain platform/anchor-bound. WSP pin and native cryptography are unchanged.

Plaintext SQLite while unlocked, best-effort secret-memory clearing, the
16-epoch recovery limit, 10000-generation Linux witness journal limit, witness
loss/replacement/whole-store rollback, root compromise, real power-loss durability
and hardened executable-to-loader binding remain explicit limitations. Process
kill/lease/CAS and simulated filesystem-fault tests cover their stated paths;
they are not whole-host crash/power-loss proof. Ambiguous snapshot/anchor writes
fail closed and may require operator investigation; no automatic reset, overwrite,
old-reservation release or broadcast retry was added.
