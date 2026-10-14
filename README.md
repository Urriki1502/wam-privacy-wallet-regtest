# WAM Privacy Wallet — Real REGTEST (macOS ARM64 first)

**Fresh MIT repository. No historical mock-first PR chain. WAM Core v0.1.11 is the only node baseline.**

**Status:** the official signed WAM Core v0.1.11 has passed native macOS ARM64 real REGTEST RPC; pinned WSP-1 detected an actual BIP352 payment at block 102, with SQLite/history/restart. The new Qt **read-only public-demo Receive/Balance/History** must still pass its exact-head live-Core GUI CI gate. This is NOT a user-key wallet, generalized signer or mainnet application.

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

## One-command live macOS REGTEST demo

After installing the exact pinned WSP upstream checkout and the signed Core release, run one command:

```bash
python -m pip install -e '.[gui]' -e /ABSOLUTE/PINNED/wam-silent-payments
wam-regtest demo --core-dir core \
  --wsp-source-root /ABSOLUTE/PINNED/wam-silent-payments \
  --confirm-disposable-regtest --confirm-public-fixture-payment
```

This starts official signed WAM Core v0.1.11 on a new private disposable REGTEST chain, mines 101 blocks to a **globally known test key**, broadcasts and mines a genuine BIP352 payment at block 102, opens the Qt wallet, and enables automatic background WSP/SQLite refresh. **Close the window to stop the daemon and erase the temporary test chain.** Nothing touches regular WAM data or mainnet. The published demo receive code is not safe for personal funds. A Core binary from an unverified local directory is refused. The desktop app is not yet a self-contained signed `.app/.dmg`.

## Native Qt wallet (experimental, public-demo account only)

Install `python -m pip install -e '.[gui]'` plus the exact pinned WSP upstream source. A separate **official, signed, already-running** WAM Core v0.1.11 REGTEST daemon must be available with an owner-private `0700` datadir and a WSP SQLite database. Run:

```bash
wam-regtest gui --core-dir core --datadir /ABSOLUTE/DISPOSABLE/REGTEST-DATADIR \
  --wsp-source-root /ABSOLUTE/PINNED/wam-silent-payments \
  --confirm-disposable-regtest
```

The GUI performs a live WSP scanner RPC round-trip in a background Qt thread every 30 seconds; it clears all balances/history when verification fails and never creates/signs/broadcasts transactions. It shows **public-fixture-only** BIP352 Receive, confirmed Balance and History. Appearance Auto uses the operating system's local clock (light 06:00–17:59, dark 18:00–05:59) and supports manual override. **Never send real WAM to its published demo receive code.**

The macOS real-Core CI drives the actual GUI against a signed running daemon, a mined BIP352 transaction and real WSP SQLite, then uploads a UI screenshot; no synthetic RPC is accepted.

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
