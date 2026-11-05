# Linux x86_64 — install and run (after a native frozen build)

Supported qualification target: **Ubuntu 24.04 x86_64**. Other distros are
unqualified. This Mac workspace **did not** produce or execute a Linux tarball.

After `scripts/build_linux_wallet.py` on SHA

```
17adf5c5cbb1213ea5abd95a2ecdd9464b0874a2
```

1. Extract the dated `wam-regtest-desktop-*.tar.gz` or headless archive.
2. Confirm `DEVELOPER_CORE_MANIFEST.json` SHA256
   `e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806`.
3. Confirm bundled `wamd` / `wam-cli` match
   `ccc9f0f1d299a1e98a49ff83859aa03e994e83e6ea4b7cd60c327eb1e0e8e4d6` /
   `ada9dabd56d0859b9d64c0b20a05c33cb039b2573f75088443b45c35d5379652`.
4. Confirm `PT_GNU_STACK` is RW (`flags=6`), not RWE.
5. Provision the independent root witness first (`docs/LINUX_ROOT_WITNESS_POLICY.md`).
6. Desktop launch with no args prompts for that manifest SHA and socket, then
   disposable-chain consent (default No).
7. Do not pass `--core-dir` / `--wsp-source-root` into the frozen binary
   (bundle override is denied).
8. Record `official_signed_core_release=false` on every receipt. Do not call
   this official signed Linux Core.

RPC remains `127.0.0.1:29554`. Shared P2P is `29555` only after explicit Shared
mode. Never open the owner macOS Desktop wallet.
