# Post-DEV review remediation

Functional ancestor: `56ea36186bf5a3410c75dda63b885f084de83610`.
That pin's Windows, Linux, and local macOS packages stay in place.
This branch does not rewrite them and does not merge.

Q06 `accepted=false`. G6 and G7 remain blocked. V19 was not executed.
No mainnet and no GitHub Release.

## Findings

| Finding | Class | What changed |
| --- | --- | --- |
| Windows `SHA256SUMS.txt` CRLF makes `sha256sum -c` fail | FIXED in source | `write_portable_sha256sums` writes bytes and rejects CR. Windows CI must still show the new package. |
| Qt/PySide6 license files absent from packages | MITIGATED | GUI packages stage the installed wheel `METADATA` plus the unmodified GNU LGPL-3.0, GPL-3.0, and GPL-2.0 texts. The 6.12.0 wheel ships no license file. This is not a completed legal opinion. |
| Extra Linux Qt QML, Quick, PDF, Virtual Keyboard | MITIGATED | Desktop build deletes those libraries only when no kept ELF lists them as `NEEDED`. `libQt6Test` stays because frozen Q06 spend imports `PySide6.QtTest`. `libXcursor` and `libxcb-cursor` stay; they are X11, not Cursor the IDE. |
| `--ci-*` modes and the Core downloader inside the frozen app | ACCEPTED_LIMITATION | Frozen qualification calls those modes on the packaged binary. `core.py` imports hash constants from `release.py`, the same module as the downloader. Removing either would drop the current frozen gates or the provenance constants. |
| Ubuntu 22.04 / glibc 2.35 cannot start the package | ACCEPTED_LIMITATION | See `docs/LINUX_GLIBC_BASELINE.md`. Minimum remains glibc >= 2.38, Ubuntu 24.04. |
| Official Linux Core v0.1.13 has GNU_STACK RW | NOT_VERIFIED as a replacement | Signature and static ELF are recorded in `docs/LINUX_CORE_V0_1_13_REVIEW.md`. The developer Core pin is unchanged. |

## Root causes

`Path.write_text` without a binary write translates `\n` to `\r\n` on Windows. `sha256sum` then treats the carriage return as part of the filename.

PyInstaller collected Qt, Shiboken, coincurve, and cryptography. coincurve and cryptography wheels contain license files. PySide6 6.12.0 `dist-info` contains `METADATA` with `License: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only` and no license body. The archives therefore had no Qt license text.

PyInstaller's Qt hook copies the shared libraries shipped in the wheel, including modules the Widgets UI does not import.

## Files

- `src/wam_regtest/release_candidate.py`
- `src/wam_regtest/distribution_notices.py`
- `src/wam_regtest/qt_bundle_prune.py`
- `scripts/build_windows_bundle.py`
- `scripts/build_linux_wallet.py`
- `scripts/build_macos_bundle.sh`
- `tests/test_windows_portable_sha256sums.py`
- `tests/test_fusion_distribution_notices.py`
- `third_party/gnu/`
- `.github/workflows/macos-arm64-frozen-rc.yml`
- `docs/LINUX_GLIBC_BASELINE.md`
- `docs/LINUX_CORE_V0_1_13_REVIEW.md`

Wallet custody, BIP39, PSBT, and Core verification checks were not weakened.

## Legal limit that remains

The package now carries the publisher metadata and the GNU texts named by that metadata. It does not add a lawyer's sign-off, a Qt trademark review, or a hosted copy of the Qt for Python 6.12.0 source tree. Some Qt modules are GPL-only; the prune step is how unused QML, Quick, PDF, and Virtual Keyboard libraries leave the Linux desktop bundle when nothing links them. A recipient who needs the full LGPL source offer should use the public 6.12.0 sources at `https://pyside.org` and `https://download.qt.io`.

## Qualification

Artifact checksums from `56ea3618` and macOS workflow commit `22613ad` are not reused. New package hashes are the ones printed by the Actions run of this remediation commit, after the downloaded files are hashed again.
