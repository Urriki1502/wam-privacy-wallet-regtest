# RC package content verification

Inspection date: 2026-11-05. Archives were listed and scanned. Windows and Linux binaries were not executed on this Mac. SHA256 values were recomputed and match `~/Documents/WAM-RC-sidecars/rc-56ea3618/THREE-PLATFORM-RC-INVENTORY.md` and each package's `SHA256SUMS`.

Source for every package manifest below: `56ea36186bf5a3410c75dda63b885f084de83610`.
WSP pin: `ac55f13423620252bdbf848c7e8a280c3b84721e`.

## Hashes

| Package | Members | SHA256 |
| --- | ---: | --- |
| macOS `.app.zip` | 621 | `357ef77900c0ac6bb9cc6fc5298a71654c27140f27cbd8ed52c8749bdb4d3df9` |
| macOS `.dmg` | same app, disk image | `a77337b612fe9c9b2d9f5725ca7cf86c029172cfc869fa1b04c31503570e2d2c` |
| Windows ZIP | 314 | `2d5f5fffca095b87ea303f89c047b3047f5cff38c73f068d984f858c2f33929e` |
| Linux desktop tar.gz | 582 | `90450022266f14b39c86e65ee7a690b583c6acc01f24431c4915a67e79139b30` |
| Linux headless tar.gz | 228 | `387726039b3dddeb76f190da470156f684846e72492e8e297dd9e8d815b07023` |

The DMG hash was verified. Member-level inspection used the `.app.zip`, which is the application the DMG installs. The older workspace DMG `dea3b4be…` was not overwritten.

## Allowlist

Required and observed: WAM Core, WSP source closure, Qt/PySide6 on GUI packages, BIP39 `mnemonic` wordlists, coincurve, cryptography, and their license files, Python runtime, and platform GUI libraries.

## Not found inside the application archives

- Cursor, Codex, OpenAI, or Anthropic strings
- `.git` metadata, `tests/`, `AGENTS.md`, `ENGINEERING_HANDOFF.md`
- Agent transcripts, prompt files, `.env`, OpenSSH private keys, `xprv`
- `rpcpassword=` literals, wallet-runtime SQLite files
- `/Users/dinhdang` build-machine paths in the raw archives

Reviewer files such as `DEV_WAM_REVIEW_HANDOFF.md` sit beside the ZIP inside the GitHub artifact directory. They are not members of the Windows ZIP.

## Extra content (not removed)

Linux desktop includes Qt6 QML, Quick, Pdf, VirtualKeyboard, and Qt6Test libraries (18 path hits). The Fusion UI is Qt Widgets. Those extra modules were not deleted, because removing them would create a new package identity and require a new Linux qualification. `libXcursor.so.1` stays; it is the X11 cursor library.

License files found in the archives are coincurve and cryptography only. A dedicated PySide6/Qt license file was not in the member list. See the audit report.

## Core members

macOS app contains one regular `wamd` and one `wam-cli`, hashes `7298de70…` and `81a031eb…`, matching the signed v0.1.11 ARM64 receipt. `codesign` reports an ad-hoc signature and no TeamIdentifier.

Windows ZIP contains `wamd.exe` and `wam-cli.exe`. Manifest pins `31717319…` and `538a6d1b…`. `authenticode_signed_application` is false.

Linux headless and desktop bundle `DEVELOPER_CORE_MANIFEST.json`: `official_signed_release` false, policy `EXPERIMENTAL_SOURCE_BUILD_REGTEST_ONLY`, `gnu_stack` RW, `wamd` `ccc9f0f1…`, `wam-cli` `ada9dabd…`, WAM source `82a1487fd86f7021b1b9fc1524d267fca126f7d4`. Loader library `libsqlite3.so.0.8.6` is `c9126b7c…`.
