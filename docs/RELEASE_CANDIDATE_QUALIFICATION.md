# WAM-Fusion-REGTEST-RC1 — engineering qualification

16 October 2026 (Asia/Ho_Chi_Minh). **READY FOR OWNER REGTEST TESTING.**
Experimental disposable REGTEST only. No mainnet, production approval, official
Final release or DEV WAM endorsement. Nothing has been merged to main.

Qualified **CODE SHA: `144d87700b87a241467172adfad3692b41e1d273`**; candidate
`integration/wam-fusion-regtest-v1-qualification`, [Draft PR #36](https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/36),
stacked on #35. This documentation/evidence branch is a docs-only descendant of
that immutable code SHA. Its later documentation commit is NOT a newly qualified
runtime. All four distributed builds use source_head=checkout=CODE SHA, event
workflow_dispatch. PR synthetic merge builds are supplementary and are not the
downloads below. Main remains `50e1ea94df61b8400cbab3bffe0fbdd285c6b419`.

## Milestones and platform matrix

| Milestone | Result |
| --- | --- |
| CODE_INTEGRATED | PASS: all #18–35 heads are ancestors; #33 ancestry-only merge has no content delta; stale #17 excluded and left open |
| NATIVE_CI_QUALIFIED | PASS: eight new exact-CODE workflows, every included job succeeds |
| FROZEN_BINARY_QUALIFIED | PASS: macOS app/DMG, Windows exe and Linux desktop/headless, independently downloaded/inspected |
| PHYSICAL_OR_HUMAN_ACCEPTED | PENDING_OPERATOR; automated MacBook execution is separate |
| DEV_WAM_REVIEWED | PENDING; review package prepared, not sent |

| Platform | Source E2E | Frozen E2E | Custody | Core provenance | Human acceptance |
| --- | --- | --- | --- | --- | --- |
| macOS ARM64 | PASS [38747153198](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38747153198) | PASS same run + downloaded app Cocoa on actual MacBook; DMG VALID | Keychain + private ciphertext + native lease PASS | Official signed v0.1.11, independent node/CLI hashes | PENDING_OPERATOR Finder/OS settings; local automated Cocoa PASS |
| Windows x64 | PASS [38747163508](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38747163508) | PASS same run, native QWindows at 125% and 150% | Credential Manager + protected owner NTFS/DACL + global lease PASS | Official signed v0.1.11, independent node/CLI hashes | PENDING_OPERATOR Windows10/11 device; Server2022 runner is automated evidence |
| Linux desktop x86_64 | PASS [38747174307](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38747174307), native xcb/Xvfb | PASS same run, bundled real Core/WSP/Qt | Private UID/ACL storage + separate root witness PASS | Exact reviewed developer Core; ELF GNU_STACK RW, pinned library closure | PHYSICAL_LINUX_ACCEPTANCE=PENDING_OPERATOR; owner confirms no authorized host; GNOME/KDE Auto pending |
| Linux headless x86_64 | PASS same native Ubuntu run, actual CLI | PASS same run; no Qt/PySide/shiboken | Same independent root witness, no software-only fallback | Same approved developer Core, not an official signed release | PENDING_OPERATOR physical terminal; native CI PASS |

## Exact-source native runs

Every run below has head_sha `144d87700b87a241467172adfad3692b41e1d273` and event workflow_dispatch. Direct
job links/conclusions are retained in [NATIVE_CI_EVIDENCE.json](evidence/rc1/NATIVE_CI_EVIDENCE.json).

| Gate | Result | Run |
| --- | --- | --- |
| vectors | PASS | [38747142053](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38747142053) |
| macos | PASS | [38747153198](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38747153198) |
| windows | PASS | [38747163508](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38747163508) |
| linux | PASS | [38747174307](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38747174307) |
| windows_preflight | PASS | [38747184018](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38747184018) |
| windows_core | PASS | [38747193574](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38747193574) |
| windows_receive | PASS | [38747202781](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38747202781) |
| windows_read_qt | PASS | [38747211715](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38747211715) |

The supplemental five PR workflows also succeeded, including all 11 PR jobs;
those use GitHub's merge checkout and are not substituted for exact-source runs.
The old `macos-lite-dmg.yml` workflow repackages a fixed historical artifact;
it was excluded from current-source qualification, not disabled or weakened.

Real-Core acceptance includes WSP Scanner.sync/SQLite/restart, Receive/Balance/
History, native six-screen Fusion, separate review/Sign/Broadcast approvals with
Cancel default, mempool acceptance, recipient 100000 atoms and confirmed sender
change, lock/wrong-password/unlock/backup, new-chain same-key recovery,
irreversible and uncertain reservations, stale rejection before native sign/RPC,
background sync, and actual reorg depths 1/12/100. Linux headless covers the full
reorg/uncertainty suite; desktop independently covers real native Qt/session use.
Negative unit contracts supplement genuine Core E2E; they do not replace it.

Native OS failure contracts include lease contention across directories,
killed-process lease release, anchor loss/replacement, orphan publication,
failed restore cleanup, directory substitution, hardlink/ACL/reparse refusal,
Linux peer-UID/CAS/service crash/restart and no unprivileged anchor fallback.
These are process-crash/failure tests, not a hardware power-loss durability claim.

Commands recorded by the exact-source workflows:

- macOS: source unittest/security/native Core gates, `bash scripts/build_macos_bundle.sh`;
  downloaded binary `Contents/MacOS/WAM Privacy Wallet REGTEST --ci-real-core-wallet-cocoa`,
  `QT_QPA_PLATFORM=cocoa`; `hdiutil verify <downloaded.dmg>` and
  `codesign --verify --deep --strict --verbose=2 <downloaded.app>`.
- Windows: native `test_windows_*.py` without skips, pinned WSP vectors/locks/scanner,
  actual Core/vault/native QWindows probes; `python scripts/build_windows_bundle.py`
  repeats genuine frozen wallet at QT_SCALE_FACTOR=1.25 and 1.5.
- Linux: root/private-storage native contracts; `python scripts/linux_headless_acceptance.py
  --core-dir qualified-linux-core/linux-core`; the same with `--qt` under native
  xcb/Xvfb; `python scripts/build_linux_wallet.py --core-dir qualified-linux-core/linux-core`
  and desktop `--desktop` under xcb/Xvfb. Approved Core is downloaded from the
  independently pinned artifact; the repeated developer-core build is a separate check.

See each successful run's exact YAML/log for environment/setup and all arguments;
never apply Linux administrative CI provisioning automatically to an owner's host.

## Published downloads and checksums

All names are `WAM-Fusion-REGTEST-RC1-<platform>-144d87700b87a241467172adfad3692b41e1d273`.
These are actual Actions download URLs; GitHub login may be required. Retention
is 14 days. Expiry times below are UTC (add 7 hours for Vietnam).

| Package | Published artifact | Expires UTC |
| --- | --- | --- |
| macos | [Download 11980032023](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38747153198/artifacts/11980032023) | 2026-10-29T14:02:34Z |
| windows | [Download 11980747014](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38747163508/artifacts/11980747014) | 2026-10-29T14:19:11Z |
| linux-desktop | [Download 11979187025](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38747174307/artifacts/11979187025) | 2026-10-29T14:01:33Z |
| linux-headless | [Download 11980206630](https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/38747174307/artifacts/11980206630) | 2026-10-29T14:00:53Z |

Actions ZIP digests, common manifest digests and full actual tool versions are
in [PUBLISHED_ARTIFACTS.json](evidence/rc1/PUBLISHED_ARTIFACTS.json) and
[COMMON_MANIFEST_VERIFICATION.json](evidence/rc1/COMMON_MANIFEST_VERIFICATION.json).
After extracting the outer Actions ZIP, verify SHA256SUMS.txt and the exact inner
payload hash below; outer Actions ZIP and inner payload hashes differ.

| Inner payload | SHA256 |
| --- | --- |
| `WAM-Privacy-Wallet-REGTEST-macOS-ARM64.app.zip` | `f094e6c5c18687e67acea632fe50c70bc6f9a8332972818ffd4ac688abc2c296` |
| `WAM-Privacy-Wallet-REGTEST-macOS-ARM64.dmg` | `df06b152719a3c23cdf899d9416234660676835c96a8c2e9809d6a221137d50d` |
| `WAM-Privacy-Wallet-REGTEST-windows-x64-144d87700b87a241467172adfad3692b41e1d273.zip` | `426431c0d53d997cfff40cded5a13bbb3fc013e4b4ca0d96117c1063e2171b3c` |
| `wam-regtest-desktop-linux-x86_64-144d87700b87a241467172adfad3692b41e1d273.tar.gz` | `2aac43def1444d7dae753e924de7752c312e568d9143aafd5af31ffa5aae420f` |
| `wam-regtest-headless-linux-x86_64-144d87700b87a241467172adfad3692b41e1d273.tar.gz` | `d6944fc8b04e4b93be77fb3d64f73f91f68c64a5ad4cb2e187cba05ac5131ffd` |

Every package contains the common RELEASE_CANDIDATE_MANIFEST.json, platform
manifest, public receipt/checksums and owner/DEV guide. No existing wallet,
SQLite, backup, RPC config, credentials or Keychain was copied. Independent
inspection checked every Windows/Linux archive member against its manifest,
Core ELF/PE/Mach-O architecture and pins, 33 WSP Python files, original WAM PNG /
macOS ICNS, safe internal links, and the headless no-Qt closure. Windows WSP
members match the exact reversible Git LF→CRLF checkout, with no source changes.
The root-witness review helper matches the reviewed source. This inspection on
a Mac is not execution of Windows/Linux binaries; native execution is in the
linked genuine platform runners.

## Core/source identity and build environment

WSP pin: `ac55f13423620252bdbf848c7e8a280c3b84721e`; all 28 canonical suites retained.
Original WAM PNG: `1b189fb54969e6229a984f27ade4524bf4c327bb447d6da9fdbef3a8c2c30989`.
ICNS: `dc8c4de2aeac66e062ac530b2a462e639646e02b3cfe5a7ba6f8c4bd8f571fb7`.

| Platform | wamd SHA256 | wam-cli SHA256 |
| --- | --- | --- |
| macOS official ARM64 | `7298de701e467eb28b4806cbcbe35edb393861b4b97117017fee4c1b194e3068` | `81a031ebf9b3060b19061b29756d43bcd09b32ad778348b8c3d8321397076e82` |
| Windows official x64 | `31717319535c5b784b2bed3b4d3c9a727f5c062e9534b4d27c59d2ffd04e95a1` | `538a6d1b918b698ce76a949dda982fdda6776e33ba057efaac59b1af59e59d21` |
| Linux reviewed developer x64 | `ccc9f0f1d299a1e98a49ff83859aa03e994e83e6ea4b7cd60c327eb1e0e8e4d6` | `ada9dabd56d0859b9d64c0b20a05c33cb039b2573f75088443b45c35d5379652` |

Linux approved manifest `e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806`;
WAM source 82a1487fd86f7021b1b9fc1524d267fca126f7d4, Bitcoin 32efe850438ef22e2de39e562af557872a402c31,
RandomX 102f8acf90a7649ada410de5499a7ec62e49e1da. The original published Linux
RWE-stack binary remains rejected. No new build hash was auto-trusted and no
upstream WAM source was changed. Linux runtime packages retain the independently
approved Core from run38697805476/artifact linux-developer-core-576082d227ccd9eb139686ded431c69c07399237.

PyInstaller 6.22.3/hooks 2026.8; Qt/PySide6 6.12.0 and qrcode 8.2 where GUI is present;
coincurve 21.0.0, cryptography 50.0.0, pycryptodome 3.23.0, cffi 2.1.1. Python 3.12.10
on macOS 15.7.9 ARM64 and Windows Server 2022; Python 3.12.15 on Ubuntu 24.04/cloud
kernel 6.17.0-1022-azure/glibc 2.39. Windows icon build Pillow 12.0.0. Full dependency
inventories are linked above; headless has no Qt/PySide/shiboken. Reproducible
procedure is documented; byte-identical ZIP/DMG/signature output is not claimed.
Mac outer app is ad-hoc signed, not Apple Developer ID notarized; Windows app
has no Authenticode signature. Upstream official Core bytes remain unchanged.

## Actual MacBook and remaining operator work

The downloaded exact-CODE app was extracted with ditto and executed on actual
MacBook model Mac14,9, macOS-27.0.1-arm64-arm-64bit, Qt platform cocoa, starting
2026-10-15T23:33:20.175446+00:00. Exit 0 and all five packaged acceptance markers PASS;
DMG verification VALID, strict ad-hoc code signature PASS and both original Core
hashes unchanged after execution. Native Auto/Light/Dark events, real scanner,
payment/security/recovery/reorg gates and Qt cleanup completed. Only isolated
acceptance Keychains/test REGTEST were used; no personal keys/default Keychain
search-list changes. [Local receipt](evidence/rc1/LOCAL_MACBOOK_COCOA_RECEIPT.json).
This is automated actual-MacBook evidence, not a human Finder/OS-settings signoff.

Owner action: follow [OWNER_REGTEST_ACCEPTANCE.md](OWNER_REGTEST_ACCEPTANCE.md),
record observed results and use its feedback checklist. Windows human 10/11 and
macOS Finder/manual OS appearance remain PENDING_OPERATOR. The owner explicitly
reports no authorized physical Linux host. No SSH probing or privileged Linux
setup was attempted. Ubuntu native CI is not physical GNOME/KDE review; Linux
Auto OS events remain pending. The separately approved root witness is mandatory;
STOP before its administrative installation/provisioning until a host admin approves.

## Findings and release boundary

A real additional Windows Qt gate first failed on predecessor 0cdb111 because its
old install omitted qrcode. Commit 144d877 installs the existing declared .[gui]
extra; every real-Core assertion remains. All eight runs and four artifacts were
then rebuilt/requalified at 144d877. Earlier PASS/artifacts were not recycled.
No current mandatory native/frozen gate is failing. PR #36 remains Draft and all
predecessor Drafts/main remain unchanged. [Security/dependency review](RC1_SECURITY_AND_DEPENDENCY_REVIEW.md).

Residual production-hardening limitations: unlocked private SQLite is plaintext;
secret-memory clearing is best effort; native backups are bound to platform/
anchor; recovery epochs 16; Linux witness generations 10000; anchor loss or ambiguous
snapshot publication can deny availability; no rollback proof if both independent
stores/whole OS are replaced; no same-user/root-malware or power-loss guarantee;
process/loader binding, guaranteed erasure and arbitrary Linux distribution
portability are unqualified. Native v1/v2/v3 profiles remain authenticated; no
cross-Mac/cross-OS portable import claim. Future portable export must address
offline guessing/KDF hardware cost. BIP352×PayJoin execution remains V2/HOLD.

Disposition: owner REGTEST testing may begin with these disclosed operator gaps.
No main merge, official final release, mainnet or production approval; DEV handoff
is prepared but not sent. Next: collect actual owner receipts; review concrete
failures; retain exact source and Core/pin/lease/security gates for any fix, with
new exact-commit native/frozen qualification after runtime changes.

## Rebuild the same reviewed source

The candidate branch is deliberately pinned at CODE SHA. Check it before dispatch
and stop if it moved; never rebuild an unreviewed successor under this receipt.

```sh
gh api repos/Urriki1502/wam-privacy-wallet-regtest/branches/integration/wam-fusion-regtest-v1-qualification --jq .commit.sha
# Must equal 144d87700b87a241467172adfad3692b41e1d273.
for workflow in bip352-vectors.yml real-core-regtest.yml windows-x64-credential-anchor.yml linux-experimental-regtest.yml windows-x64-qualification.yml windows-x64-real-core-regtest.yml windows-x64-wsp-real-receive.yml windows-x64-qt-live-read.yml; do
  gh workflow run "$workflow" --repo Urriki1502/wam-privacy-wallet-regtest --ref integration/wam-fusion-regtest-v1-qualification || break
done
```

Check every new run and newly generated manifest/checksum; old digests do not
qualify new ZIP/DMG metadata. If the immutable Linux Core artifact has expired,
STOP for independent Core/library requalification. A newly built Core is never
automatically a replacement for the approved pair. Source build recipes and full
commands remain available at the CODE commit; OS dependency installation requires
the local administrator's separate review. No reset of witness/native anchors.
