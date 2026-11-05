# Release content audit — runtime vs engineering record

Pin: `b844dd371d4ac5dc3d0469eb899d6709e8ac407f`  
Audit date: 2026-11-05. No frozen V2.2 tree was produced this session, so this is
the **allowlist for packaging boundaries**, plus inspection of existing recipes.

## Trust rule

Cleaning a bundle is not permission to rewrite git history, hide AI assistance,
fabricate reviews, or strip copyright/licenses. Engineering records stay in the
source tree. They must **not** be copied into the shipped application.

## Runtime allowlist (must be the only classes of files inside .app / onedir / tar)

| Class | Examples | Why |
| --- | --- | --- |
| Frozen Fusion entry | `package_entry.py` / `windows_package_entry.py` / `linux_package_entry.py` as collected bytecode | Launch |
| Wallet runtime | `wam_regtest` submodules actually imported | GUI + custody |
| WSP | pinned `wsp-source` + `wam_sp` / coincurve native | BIP352 |
| Official or labelled Core | `wamd`/`wam-cli`/`receipt.json` **or** Linux developer Core + `DEVELOPER_CORE_MANIFEST.json` | Node |
| Qt | PySide6 / shiboken / platform plugin for that OS | GUI |
| Branding | owner `wam-coin-logo.png`, icns/ico derived from it | Icon |
| Provenance JSON | `Q05_BUILD_SOURCE.json` | Reproducibility inside the app |
| Licenses shipped by Qt/Python wheels | as bundled by PyInstaller | Legal |

## Runtime denylist (exclude at packaging; keep in git)

| Class | Examples |
| --- | --- |
| Agent/session | `.cursor/`, agent transcripts, prompt scratch |
| Local evidence | `build/local-evidence-*`, GUI screenshots, fixture PNG |
| Engineering docs | `AGENTS.md`, `ENGINEERING_HANDOFF.md`, `JOINT_ACCEPTANCE_CHECKLIST.md` (reviewer copies travel **beside** the app, not inside it) |
| Tests | `tests/`, disposable wallets, `*.sqlite` fixtures |
| Secrets | `.env`, cookies, `wam.conf`, seeds, keychain-db, RPC user/pass |
| Build caches | `build/`, `dist/` leftovers, `bundle-input/` temp stages |
| Machine-absolute spec | committed `WAM Privacy Wallet REGTEST.spec` contains this Mac’s absolute paths — **build-time only**, regenerate; do not treat as a portable recipe |
| Unrelated docs dumps | `LEGACY_WORKSPACE_INVENTORY.md` etc. |

Existing builders already `--collect-submodules wam_regtest` (broad). Independent
reviewer should confirm the frozen TOC has no `tests`, no `.cursor`, no PNG
evidence, no datadir. Command after a real build:

```
python3 -c "from pathlib import Path
root=Path('dist')
bad=('.cursor','agent-transcripts','local-evidence','ENGINEERING_HANDOFF','.env','mnemonic')
print([p for p in root.rglob('*') if any(b.lower() in p.as_posix().lower() for b in bad)])"
```

## This session’s inventory

| Path | Included in git? | In runtime package? |
| --- | --- | --- |
| `src/wam_regtest/*` | yes | yes (frozen) |
| `scripts/build_*.py`, `build_macos_bundle.sh` | yes | no |
| `release-candidates/b844dd3/evidence/upstream-v0.1.11/SIGNING-KEY.asc` | yes (public key) | no |
| empty `macos-arm64/` `windows-x64/` `linux-x86_64/` | README only | no fake binaries |
| owner Desktop wallet | never opened | n/a |

## Verification evidence

No packaged TOC to hash: frozen apps **NOT EXECUTED**. Re-run the TOC scan on the
Developer’s native output before calling a package “clean.”
