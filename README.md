# WAM Privacy Wallet — Real REGTEST candidates

Owner-acceptance audit and proposed UX fix: [results, defects and requalification](docs/OWNER_ACCEPTANCE_AUDIT.md). The qualified RC1 baseline remains unchanged.

Experimental native Qt wallet using official signed WAM Core v0.1.11,
pinned WSP-1 BIP352 and actual SQLite. Receive, Balance, History, review-gated
Prepare / Sign / Broadcast, confirmed change, encrypted backup, Lock / Unlock,
same-Mac recovery, Keychain anti-rollback, background sync and macOS Auto /
Light / Dark are implemented. **Disposable REGTEST only: no personal keys,
real funds, mainnet or production qualification.**

PRs [#6](https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/6)
(packaging), [#7](https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/7)
(encrypted recovery), [#8](https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/8)
(native payments) and [#9](https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/9)
(cross-session recovery and stale-writer protection) are merged.

## WAM Fusion REGTEST RC1 — 16 October 2026

Qualified code `144d87700b87a241467172adfad3692b41e1d273` has same-source macOS ARM64, Windows x64 and experimental Linux x86_64 packages. **READY FOR OWNER REGTEST TESTING**; human acceptance remains PENDING_OPERATOR. Start with [downloads, exact native CI and checksums](docs/RELEASE_CANDIDATE_QUALIFICATION.md), [owner test guide](docs/OWNER_REGTEST_ACCEPTANCE.md) and [DEV review draft](docs/DEV_WAM_REVIEW_HANDOFF.md).

This stacked integration preserves the existing engineering candidates. These are **Draft engineering units**, not merged V1/Final releases.
The older [Linux qualification checkpoint](docs/LINUX_QUALIFICATION.md) is historical; the RC1 report above supersedes its artifact list.
macOS retains official signed Core/Keychain; Windows retains official signed
Core/Credential Manager. Linux rejects the published executable-stack release
and uses an explicitly approved, exact upstream source build plus an independent
administratively provisioned root witness. It is not an official signed Linux
Core release. The original WAM coin artwork is shared unchanged.

Linux now reuses the same WalletSession and Fusion Qt screens, approvals,
reservations, native WSP signer and scanner. Source and frozen no-Qt headless / xcb
desktop gates are separate. Start with [headless](docs/LINUX_HEADLESS.md),
[Qt](docs/LINUX_QT.md), [packaging](docs/LINUX_PACKAGING.md) and
[root witness policy](docs/LINUX_ROOT_WITNESS_POLICY.md).
Portable/cross-OS backup migration remains unimplemented; platform-bound backups
and independent anchor checks must never be bypassed to simulate portability.

## Download and launch the actual application

Use the four actual [RC1 artifact links](docs/RELEASE_CANDIDATE_QUALIFICATION.md#published-downloads-and-checksums). The macOS artifact is `WAM-Fusion-REGTEST-RC1-macos-arm64-144d87700b87a241467172adfad3692b41e1d273`.
It contains `.dmg`, `.app.zip`, `SHA256SUMS.json` and native Qt previews.
Check the artifact provenance and checksums, then open the app from Finder.
The original owner-supplied black-and-gold WAM image is used for Finder/Dock
and Qt branding; its unchanged bytes and derived ICNS are pinned in
[assets](assets/README.md).

The app starts an isolated real REGTEST daemon with zero peers, establishes
its genuine BIP352 baseline, then offers **fresh random test keys** or recovery
of the **latest anchored encrypted backup on this Mac**. Enter a test-only
passphrase of at least 12 characters. Every payment requires exact review,
a separate Sign approval and a separate Broadcast action. Settings can mine
one test block to confirm it. The Security page provides encrypted backup,
Lock, Unlock and recovery. Keep the latest backup after each state change;
older anchored snapshots are rejected. Closing stops Core and removes the
private disposable chain/runtime. Save a current backup before closing if
same-Mac recovery is needed; recovery creates a new receive epoch on a fresh
chain while preserving original keys and irreversible reservations.

The app has an **ad-hoc outer signature and is not Developer ID notarized**.
Gatekeeper may require Finder right-click → Open on a downloaded preview.
Signed upstream Core members remain byte-for-byte unchanged. A release
signature authenticates those binaries; it does not prove loader integrity,
same-user malware resistance or production wallet custody.

## Source and reproducible build procedure

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[gui]' 'pyinstaller==6.22.3'
git clone https://github.com/Urriki1502/wam-silent-payments wsp-upstream
git -C wsp-upstream checkout ac55f13423620252bdbf848c7e8a280c3b84721e
python -m pip install -e ./wsp-upstream
python -m wam_regtest.release --platform macos-arm64 --destination core
python -m unittest discover -s tests -v
bash scripts/build_macos_bundle.sh
```

GnuPG (`brew install gnupg`) is required for intake from the fixed official
HTTPS endpoint. The verifier pins signing fingerprint
`4BD4A8D3AFD43F5CBCB500E23798462FE00ADBA4`, signed archive and both independent
executable hashes:

| Official v0.1.11 ARM64 member | SHA-256 |
| --- | --- |
| `wamd` | `7298de701e467eb28b4806cbcbe35edb393861b4b97117017fee4c1b194e3068` |
| `wam-cli` | `81a031ebf9b3060b19061b29756d43bcd09b32ad778348b8c3d8321397076e82` |

Builds authenticate Core and the pinned scanner, preserve original Core bytes
after PyInstaller, run the **final frozen executable** through complete real
Core / WSP / SQLite / Qt / payment / recovery gates, then create and verify
the DMG. Checksums record each output, source commit, Core and original logo.
This is a reproducible procedure, **not a claim of byte-identical builds**;
dependency versions, signatures, ZIP and DMG metadata can differ.

To launch the operational GUI from source:

```bash
wam-regtest wallet --core-dir core --wsp-source-root wsp-upstream \
  --confirm-disposable-regtest --confirm-public-fixture-payment
```

`smoke`, `demo` and `gui` retain the original read-only public-fixture baseline.
Public fixture keys are globally known and must never receive actual funds.
They are separate from the operational wallet's fresh random test keys.

## Qualification and remaining limits

The canonical-vector and macOS workflows cover 28 BIP352 vector suites and
native Apple Silicon real-Core source/frozen acceptance. Windows and Linux
qualification use their platform-specific native jobs. These include real reorg depths
1, 12 and 100, stale-writer rejection, native OS lease contention across vault
directories and recovery on a new Core chain. No mock RPC can replace these
gates. Negative unit contracts are additional tests, not real E2E evidence.

Offscreen CI does not prove macOS appearance or hands-on Finder behavior.
The supplemental frozen `--ci-real-core-wallet-cocoa` gate requires Cocoa and
native Light/Dark/Auto events on a Mac. Automated local checks must be reported
separately from human operator testing.

[Wallet scope](docs/WALLET-REGTEST.md), [security reuse and limits](docs/SECURITY-REUSE.md)
and [acceptance rules](docs/ACCEPTANCE.md) describe exact boundaries. Keychain
loss/replacement and ambiguous ciphertext/anchor updates fail closed; there
is no Cross-Mac recovery. Unlocked SQLite contains private plaintext state,
memory clearing is best effort, old signed/uncertain reservations stay locked
and recovery rotation is capped at 16 epochs. These are developer-preview
limitations, not production guarantees.

## Q01 clean-checkout build procedure

Read root `AGENTS.md` and the single case ledger
[`tests/acceptance/issue45.json`](tests/acceptance/issue45.json) first. Q01 is the
only active acceptance target; a successful build does not close its operator,
independent review or owner-authorized postmerge gates.

Use a new checkout, a new **external** venv path and the immutable WSP checkout.
Windows checkouts must preserve literal Git bytes, including upstream's binary
fuzz corpus: use `git -c core.autocrlf=false clone ...` for both repositories.
The native workflows configure this on their disposable checkout steps.

```bash
git clone https://github.com/Urriki1502/wam-silent-payments wsp-upstream
git -C wsp-upstream checkout --detach ac55f13423620252bdbf848c7e8a280c3b84721e
python -I scripts/q01_environment.py --profile gui \
  --environment /absolute/new/external/q01-env --receipt q01-install.json
```

The declared bootstrap interpreter is CPython **3.12.10 on macOS/Windows** and
**3.12.15 on Linux**; setup-python's current manifest supplies these native
architectures (3.12.15 is unavailable there on macOS/Windows). Subsequent build
and test commands must use that new venv's `bin/python` or `Scripts/python.exe`.
CI exports its path only after the installer step. `--profile headless` has no
Qt; Linux desktop uses the separate GUI profile. Wheel versions and hashes live
in `requirements/q01-*.lock`, install reports record actual download hashes,
and editable backend resolution cannot fetch additional undeclared dependencies.
The existing source/frozen WSP import guards remain mandatory.

Required OS prerequisites remain explicit: Git and native CPython; GPG plus
Apple command-line build/signing/disk-image tools on macOS; native Windows NTFS
and Credential Manager; and the existing workflow's Ubuntu 24.04 libraries,
Xvfb/xcb for desktop, and independently administered root witness for Linux.
Linux uses the pinned reviewed developer Core artifact, **not** an official
signed Linux release. Never provision a privileged witness on an owner host as
part of this installer. OS runner images/system libraries are separately
recorded prerequisites; wheel locks do not make the entire host hermetic.

Run existing platform native and final frozen builders only after the fresh
installation. They retain pinned Core/WSP checks and real-Core wallet gates.
`q01_core_negatives.py` tests modified disposable copies of **each** genuine
Core binary and a missing CLI; `q01_dependency_negatives.py` uses real bare
interpreters with missing WSP/crypto. These are SOURCE refusal evidence, not
Core E2E substitutes. No test modifies the original pair or opens owner data.
Builders additionally refuse dirty/staged/hidden executable source and verify
tracked source remains unchanged before packaging publication. A planned second
clean build must compare actual payloads; timestamps/signatures/container bytes
may differ and no bit-identical reproducibility is currently claimed.

## Sources

- [Official Core v0.1.11](https://github.com/wamcoin-core-dev/wam-coin/releases/tag/v0.1.11)
- [Pinned WSP-1](https://github.com/Urriki1502/wam-silent-payments/tree/ac55f13423620252bdbf848c7e8a280c3b84721e)
- [Legacy wallet reference](https://github.com/Urriki1502/wam-privacy-wallet) (read-only audit; no bulk architecture import)
