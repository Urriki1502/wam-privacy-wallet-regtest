# RC runtime dependency matrix

Frozen source: `56ea36186bf5a3410c75dda63b885f084de83610`
Entrypoints inspected: `src/wam_regtest/package_entry.py`, `windows_package_entry.py`, `linux_package_entry.py`.
This matrix does not change those packages. A filename containing "agent" or "cursor" was not treated as an AI dependency.

| Component | Classification | Evidence |
| --- | --- | --- |
| Cursor CLI / Cursor session | DOCUMENTATION_ONLY | Named in `AGENTS.md`, `ENGINEERING_HANDOFF.md`, and historical docs. Zero matches for `cursor.com` inside the four application archives. |
| Codex CLI | DOCUMENTATION_ONLY | Named only as the local engineering-transfer protocol. Not imported by the three package entrypoints. |
| OpenAI / other LLM APIs | UNUSED | Source search found no `api.openai`, `anthropic`, or inference client. Archive byte search count was 0 for `openai`, `api.openai`, `cursor.com`, and `anthropic`. |
| AI agent session manager | UNUSED | No runtime import or subprocess launches an agent orchestrator. `wallet_executor.py` "listener" is a localhost control socket. |
| `libXcursor` / `libxcb-cursor` | RUNTIME_REQUIRED | X11 cursor libraries inside the Linux desktop tar. They are not the Cursor IDE. |
| `mnemonic` wordlists | RUNTIME_REQUIRED | BIP39 wordlists shipped on macOS, Windows, and both Linux packages. Public wordlists, not a wallet seed. |
| PySide6 / Qt | RUNTIME_REQUIRED | Desktop and macOS GUI. Headless Linux package has no PySide6 members. |
| WSP `ac55f13423620252bdbf848c7e8a280c3b84721e` | RUNTIME_REQUIRED | `wsp-source/` is inside the macOS and Windows packages. Pin is recorded in the package manifests. |
| WAM Core binaries | RUNTIME_REQUIRED | Bundled `wamd` / `wam-cli` (`.exe` on Windows). Identities are in the audit report. |
| `https://wamcoin.org` downloader in `release.py` | BUILD_ONLY | `scripts/build_windows_bundle.py` and `q05_platforms.stage_windows_core` call `_download_exact` while staging official Core. Default `launch()` does not. The module is collected because PyInstaller collects `wam_regtest` submodules, so the code is present in the frozen binary. |
| `https://github.com/...` strings | DOCUMENTATION_ONLY | Used in `q_gate.py` and `release_candidate.py` as recorded URLs, not as a wallet network client. |
| JSON-RPC `http.client` | RUNTIME_REQUIRED | `json_rpc.py` connects only to `127.0.0.1`. |
| V1-NET P2P bind | RUNTIME_REQUIRED | Default bind is `127.0.0.1`. The operator can set another P2P interface for the two-computer test. RPC remains localhost. |
| `--ci-*` argv modes on the frozen entrypoints | TEST_ONLY | Present in the shipping entry modules. They run local REGTEST qualification. They are not started by a normal double-click. |
| Engineering lease / handoff | DOCUMENTATION_ONLY | Not imported by the package entrypoints and not present as files inside the application archives. |
| Test suite | TEST_ONLY | `tests/` was not a member of the four application archives. |

No application function requires Cursor, Codex, an LLM API, or an AI runtime.
