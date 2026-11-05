# Linux x86_64 — install and run (after a native frozen build)

Supported qualification target: **Ubuntu 24.04 x86_64**. Other distros are
unqualified. This Mac workspace **did not** produce or execute a Linux tarball.

After `scripts/build_linux_wallet.py` on SHA `b844dd371d4ac5dc3d0469eb899d6709e8ac407f`:

1. Extract the dated `wam-regtest-desktop-*.tar.gz` or headless archive.
2. Confirm `DEVELOPER_CORE_MANIFEST.json` SHA256
   `e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806`.
3. Provision the independent root witness first (`docs/LINUX_ROOT_WITNESS_POLICY.md`).
4. Desktop launch with no args prompts for that manifest SHA and socket, then
   disposable-chain consent (default No).
5. Do not pass `--core-dir` / `--wsp-source-root` into the frozen binary
   (bundle override is denied).
6. Record `official_signed_core_release=false` on every receipt.

RPC remains `127.0.0.1:29554`. Shared P2P is `29555` only after explicit Shared
mode. Never open the owner macOS Desktop wallet.
