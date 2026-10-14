# WAM Privacy Wallet — Real REGTEST (macOS ARM64 first)

**Fresh MIT repository. No historical mock-first PR chain. WAM Core v0.1.11 is the only node baseline.**

**Status:** foundation only — independently signed Core bootstrap and *real* REGTEST blockchain smoke. This is **not** a working WSP wallet or E2E Receive/Send yet. Nothing has been proven against a live node until the `real-core` CI job succeeds on this repo. No mainnet, real funds or personal keys.

## Actual first acceptance gate

1. Download the official signed WAM Core v0.1.11 macOS ARM64 release from `wamcoin.org`.
2. Verify detached `SHA256SUMS.asc` with pinned signing fingerprint `4BD4A8D3AFD43F5CBCB500E23798462FE00ADBA4` and SHA256 of the archive; check exact signed `wamd` member hash `7298de701e467eb28b4806cbcbe35edb393861b4b97117017fee4c1b194e3068`.
3. Start `wamd` from that release in a **fresh disposable** directory, isolated from the user's normal WAM installation and mainnet.
4. Use real `wam-cli` RPC to create a disposable wallet, mine 101 REGTEST blocks and read back the live tip/chain/blocks.
5. Stop daemon, remove all disposable state, write non-secret JSON evidence.

These actions are implemented in `wam_regtest.release` and `wam_regtest.core`. No HTTP mock or synthetic RPC is used by this acceptance path.

## Run on an Apple Silicon Mac

```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -e .
# Creates core/ containing verified copies of official wamd and wam-cli.
python -m wam_regtest.release --platform macos-arm64 --destination core
# Explicit approval; always uses temporary REGTEST datadir and fresh test credentials.
wam-regtest smoke --core-dir core --confirm-disposable-regtest
python -m unittest discover -s tests -v
```

`python -m wam_regtest.release` requires a locally trusted `gpg` executable (`brew install gnupg`), real HTTPS access to `wamcoin.org`, and a genuine signed release. It fails closed on download/signature/hash/architecture errors. The runner never fetches an arbitrary binary URL.

## Scope and clean milestones

- **M0 (implemented, awaiting CI):** signed binary intake + live Core REGTEST RPC + 101 blocks.
- **M1:** two isolated real nodes and synchronized RPC/P2P/index diagnostics.
- **M2:** transplant pinned WSP-1 scanner and actual 28/28 upstream BIP352 vectors; scan a genuine REGTEST transaction, persisted SQLite, Receive/Balance/History GUI.
- **M3:** explicitly reviewed REGTEST-only PSBT/sign/broadcast and recovery/reorg; no mainnet.
- **M4:** frozen Apple Silicon `.app`/`.dmg`, real Core regression and operator hands-on review.

**Testing convention:** unit tests may use local stubs for negative conditions but can *never* substitute for the mandatory real-node CI acceptance. Core launcher is experimental: signing the distribution does not independently prove the dynamic loader, same-user tamper resistance or a reproducible build. No release-ready claim until these gates and end-to-end WSP are reviewed.

## GitHub repository initialization

The active GitHub connector can edit existing repos but cannot create a new one. To create **the truly new GitHub repo with zero old commit history**, install `gh` and run:

```bash
brew install gh
# only if not already signed in:
gh auth login
bash scripts/create-github-repo.sh
```

The script uses the current GitHub identity, creates `wam-privacy-wallet-regtest` as a **public MIT** repository, initializes `main` and pushes this source. Do not run it in an existing unrelated repo.

## Sources

- Official Core: https://github.com/wamcoin-core-dev/wam-coin/releases/tag/v0.1.11
- WSP source pin: https://github.com/Urriki1502/wam-silent-payments/tree/ac55f13423620252bdbf848c7e8a280c3b84721e
- Legacy wallet (archive/reference only): https://github.com/Urriki1502/wam-privacy-wallet
