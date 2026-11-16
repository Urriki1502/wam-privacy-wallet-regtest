# Independent RC audit — `56ea3618`

Verdict: **AUDIT_PASS_WITH_DISCLOSED_LIMITATIONS**

This is a pre-developer engineering audit of the frozen release candidate. It is not Owner acceptance, not Developer acceptance, and not Q06 `accepted=true`. No finding was closed by editing wallet, BIP39, BIP352, PSBT, custody, consensus, or V1-NET code. No package was regenerated. No external scanning service received wallet files.

Auditor role: local source and archive inspection on 2026-11-05. Automated scanners were not treated as proof of zero vulnerabilities.

## Scope

- Git HEAD and isolated macOS checkout: `56ea36186bf5a3410c75dda63b885f084de83610` on `feature/v1-net-shared-regtest-20261104`
- WSP: `ac55f13423620252bdbf848c7e8a280c3b84721e`
- Packages under `~/Documents/WAM-RC-sidecars/rc-56ea3618/`
- Windows workflows `41987376659`, `41987381106`, `41987385091`, `41987389218`, `41987393180` (all success)
- Linux workflow `41987397743` (9 jobs success)
- macOS local freeze log exit 0, V19 left BLOCKED

## Critical and high

None identified in this inspection.

## Medium

**M1. Qt / PySide6 license texts are not in the shipped archives.**

- Component: Linux desktop tar, and the same packaging pattern on the GUI bundles. Member search found coincurve and cryptography license files only.
- Evidence: archive name scan, `docs/RC_PACKAGE_CONTENT_VERIFICATION.md`.
- Impact: redistribution of Qt under the LGPL needs the corresponding notices available to the recipient. This does not by itself show a wallet-key flaw.
- Correction: add the upstream Qt/PySide6 license files at the packaging boundary, then rebuild and requalify the affected platforms. Not done in this audit, so the `56ea3618` checksums stay valid.
- Status: open, disclosed.

## Low

**L1. Linux desktop carries extra Qt modules.** QML, Quick, Pdf, VirtualKeyboard, and Qt6Test are in the desktop tar. The Fusion UI path is Widgets. Leaving them keeps the qualified bytes unchanged. Removing them needs a new Linux package and a new qualification.

**L2. Qualification argv is compiled into the frozen entrypoints.** `--ci-real-core-wallet`, `--ci-q06-bip39-spend`, and the other documented CI modes call local REGTEST probes. A normal launch does not pass those arguments. They are not a network backdoor.

**L3. Official Core HTTPS fetch code is present in the collected `wam_regtest` modules.** `release.py` downloads only the pinned `https://wamcoin.org` v0.1.11 objects when a build or staging script calls it. Default GUI launch does not.

## Informational

- No Cursor, Codex, or LLM client is required at runtime. Those names exist in engineering docs only.
- `libXcursor` / `libxcb-cursor` are X11 libraries.
- RPC clients use `127.0.0.1`. V1-NET P2P defaults to localhost and can be bound to another interface only when the operator asks for a shared REGTEST. V19 on two physical computers was not executed.
- No `shell=True` in `src/`.
- Archive scans found no OpenSSH private keys, `xprv`, `rpcpassword=` literals, or `/Users/dinhdang` paths.
- macOS app signature is ad-hoc and not notarized. Windows application Authenticode is false. Linux `official_signed_release` is false. Do not describe those binaries as publisher-signed.
- Bit-for-bit reproducibility was not established. A second machine was not asked to rebuild these exact archives during this audit.

## Binary integrity

| Platform | Core identity | Signed? |
| --- | --- | --- |
| macOS ARM64 | `wamd` `7298de701e467eb28b4806cbcbe35edb393861b4b97117017fee4c1b194e3068`, `wam-cli` `81a031ebf9b3060b19061b29756d43bcd09b32ad778348b8c3d8321397076e82` | Core archive receipt says signed v0.1.11. The Fusion app is ad-hoc. |
| Windows x64 | `wamd.exe` `31717319535c5b784b2bed3b4d3c9a727f5c062e9534b4d27c59d2ffd04e95a1`, `wam-cli.exe` `538a6d1b918b698ce76a949dda982fdda6776e33ba057efaac59b1af59e59d21` | Official Core PE is the pinned release. The Fusion EXE is not Authenticode signed. |
| Linux x86_64 | `wamd` `ccc9f0f1d299a1e98a49ff83859aa03e994e83e6ea4b7cd60c327eb1e0e8e4d6`, `wam-cli` `ada9dabd56d0859b9d64c0b20a05c33cb039b2573f75088443b45c35d5379652`, GNU_STACK RW, manifest `1e8d6cbd3039fb7f80d26118c6e7c10c8defa654460072b6a3471d7f41cece4d` | `official_signed_core_release=false`. Reviewed developer ELF. |

WAM Core source pin inside the Linux manifest: `82a1487fd86f7021b1b9fc1524d267fca126f7d4`. Bitcoin `32efe850438ef22e2de39e562af557872a402c31`. RandomX `102f8acf90a7649ada410de5499a7ec62e49e1da`.

## Historical evidence

The six successful GitHub runs and the macOS freeze log are for this SHA only. Earlier failures remain failures, including Windows `41976211783` and `41979595312` (`WALLET_REAL_CORE_CONFIRM_DENIED` at 125% on older commits) and Linux runs that failed before the `1e8d6cbd` manifest pin. CI success is not physical Owner or Developer acceptance.

Windows frozen DPI evidence at this SHA: ratio 1.0 (height 105, real Core snapshot), 1.25, and 1.5, with `native_qwindows_real_frozen_e2e=true` for the scaled runs.

## Corrections made

Documentation only: this report, the dependency matrix, the package verification note, and `docs/DEVELOPER_INDEPENDENT_REBUILD_GUIDE.md`. Executable source and package checksums were not changed. Packages do not need regeneration for this audit to be read. Regeneration is required only if a later change adds Qt license files or drops extra Qt modules.

## Still for the human reviewer

- G6 physical external observation: BLOCKED
- G7 independent architecture and security sign-off: BLOCKED
- V19 two physical computers: BLOCKED / not executed
- Q06 `accepted=false`
- No mainnet, no merge, no GitHub Release
- Blank Owner / Developer / Independent checklist in the rebuild guide
