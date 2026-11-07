# Developer independent rebuild and test guide

Build and test this candidate without Cursor, Codex, or any other AI agent. Ordinary Git, Python, and the platform toolchain are sufficient.

This guide is documentation added after the freeze. The qualified packages remain the artifacts of source `56ea36186bf5a3410c75dda63b885f084de83610`. Do not relabel them if you commit this guide or any later edit.

`docs/DEVELOPER_NATIVE_BUILD_HANDOFF.md` describes an older SHA (`17adf5c`) and the older Linux manifest `e77a5745`. Use this guide for `56ea3618`.

## 1. Source

- Repository: `https://github.com/Urriki1502/wam-privacy-wallet-regtest`
- Branch: `feature/v1-net-shared-regtest-20261104`
- Fusion SHA: `56ea36186bf5a3410c75dda63b885f084de83610`
- WSP pin: `ac55f13423620252bdbf848c7e8a280c3b84721e` (checkout under `wsp-upstream/`)

```
git fetch origin feature/v1-net-shared-regtest-20261104
git checkout 56ea36186bf5a3410c75dda63b885f084de83610
git rev-parse HEAD
git -C wsp-upstream rev-parse HEAD
```

Do not open the owner Desktop wallet `wam-fusion-core-e905e0d22db25873`. Use a new disposable REGTEST directory.

## 2. Packages already built from this SHA

| Platform | SHA256 |
| --- | --- |
| macOS `.app.zip` | `357ef77900c0ac6bb9cc6fc5298a71654c27140f27cbd8ed52c8749bdb4d3df9` |
| macOS `.dmg` | `a77337b612fe9c9b2d9f5725ca7cf86c029172cfc869fa1b04c31503570e2d2c` |
| Windows ZIP | `2d5f5fffca095b87ea303f89c047b3047f5cff38c73f068d984f858c2f33929e` |
| Linux desktop tar.gz | `90450022266f14b39c86e65ee7a690b583c6acc01f24431c4915a67e79139b30` |
| Linux headless tar.gz | `387726039b3dddeb76f190da470156f684846e72492e8e297dd9e8d815b07023` |

Local copies: `~/Documents/WAM-RC-sidecars/rc-56ea3618/`. GitHub runs: Windows credential `41987376659` and the four companion Windows workflows listed in `docs/INDEPENDENT_RC_AUDIT_56ea3618.md`; Linux `41987397743`.

These archives are not claimed to be bit-for-bit reproducible until you rebuild them yourself and compare.

## 3. Core provenance

macOS ARM64 official v0.1.11, publisher fingerprint `4BD4A8D3AFD43F5CBCB500E23798462FE00ADBA4`:

- `wamd` `7298de701e467eb28b4806cbcbe35edb393861b4b97117017fee4c1b194e3068`
- `wam-cli` `81a031ebf9b3060b19061b29756d43bcd09b32ad778348b8c3d8321397076e82`
- The Fusion `.app` is ad-hoc signed only. It is not notarized.

Windows x64 official v0.1.11 PE:

- archive `wam-coin-v0.1.11-x86_64-w64-mingw32.zip` `ece622fa7ec3072c4e8b0d32e2c3749397d66260f2b0cf22b3636346873d15c5`
- `wamd.exe` `31717319535c5b784b2bed3b4d3c9a727f5c062e9534b4d27c59d2ffd04e95a1`
- `wam-cli.exe` `538a6d1b918b698ce76a949dda982fdda6776e33ba057efaac59b1af59e59d21`
- The Fusion EXE is not Authenticode signed.

Linux x86_64 is a reviewed developer build, not the official Linux tarball:

- `wamd` `ccc9f0f1d299a1e98a49ff83859aa03e994e83e6ea4b7cd60c327eb1e0e8e4d6`
- `wam-cli` `ada9dabd56d0859b9d64c0b20a05c33cb039b2573f75088443b45c35d5379652`
- manifest `1e8d6cbd3039fb7f80d26118c6e7c10c8defa654460072b6a3471d7f41cece4d`
- `PT_GNU_STACK` RW
- `official_signed_core_release=false`
- Core git `82a1487fd86f7021b1b9fc1524d267fca126f7d4` from `wamcoin-Project/wam-coin`

## 4. Rebuild commands

Python 3.12. Install from `requirements/q01-gui.lock` for GUI packages (PySide6 6.12.0, PyInstaller 6.22.3). Headless Linux uses `requirements/q01-headless.lock` and must not require Qt. Unset `PYTHONPATH` and run `python -I` so an editable checkout cannot be silently replaced.

macOS ARM64, from a clean checkout that already contains the verified `core/wamd`, `core/wam-cli`, and `core/receipt.json`:

```
python -I -c 'import wam_regtest,pathlib; assert pathlib.Path(wam_regtest.__file__).resolve()==pathlib.Path("src/wam_regtest/__init__.py").resolve()'
bash scripts/build_macos_bundle.sh
```

Windows 11 x64 (the script refuses any other OS):

```
python -I scripts/build_windows_bundle.py
```

Ubuntu 24.04 x86_64: use the existing Linux builder invoked by `.github/workflows/linux-experimental-regtest.yml` (`scripts/build_linux_wallet.py` for desktop and headless). Point it at the reviewed developer Core and manifest `1e8d6cbd…`. Do not substitute the official Linux tarball and do not set `official_signed_core_release` to true.

Write outputs to a new directory. Do not overwrite `package-output/` from an older SHA.

## 5. Install

- macOS: open the DMG and copy the app out. Gatekeeper will warn because the app is ad-hoc signed.
- Windows: unzip and run `WAM-Privacy-Wallet-REGTEST.exe` from that directory.
- Linux desktop: extract the tar and run the bundled executable inside `wam-regtest-desktop/`.
- Linux headless: extract and use the headless executable. It has no Qt UI.

## 6. Independent REGTEST procedure

On a disposable profile only:

1. Create a 12-word BIP39 wallet and write the receive code down in the test notes.
2. Restore that wallet into a second profile and compare the receive code.
3. Fund it from the bundled REGTEST Core. Confirm the receive scanner shows the coin.
4. Prepare, Sign, and Broadcast as two separate approvals. Cancel must stay the default on the approval dialog.
5. Mine one block with the bundled Core and confirm height, history, and balance agree.
6. Lock, unlock, and reopen the same profile.
7. On Windows, repeat the frozen wallet at 100%, 125%, and 150% DPI.
8. Shut the wallet down and confirm the Core process exits.

## 7. V19

V19 is two physical computers on one REGTEST. It was not executed. Do not mark it PASS from a single machine. The local V1–V18 evidence does not substitute for it. Procedure outline: `docs/V1_NET_TWO_COMPUTER_ACCEPTANCE.md`.

## 8. Known limitations

- Q06 `accepted=false`. G6 and G7 remain BLOCKED.
- No mainnet and no production custody claim.
- Qt/PySide6 license files are not in the current archives (audit M1).
- Linux desktop includes extra Qt modules (audit L1).
- Rebuilds are not yet shown to be bit-for-bit identical.

## 9. Blank human acceptance

| Role | Name | Date | Verdict | Notes |
| --- | --- | --- | --- | --- |
| Owner |  |  |  |  |
| WAM Core Developer |  |  |  |  |
| Independent reviewer |  |  |  |  |

Leave these blank until that person writes them.
