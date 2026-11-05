# Windows x64 — install and run (after a native frozen build)

This host **did not** build or run a Windows package. Follow this only on native
Windows 11 AMD64 after `scripts/build_windows_bundle.py` succeeds on
`b844dd371d4ac5dc3d0469eb899d6709e8ac407f`.

## Layout

```
WAM-Privacy-Wallet-REGTEST.exe    windowed Fusion
_internal/ …                      Qt/Python
core/wamd.exe, wam-cli.exe        official v0.1.11 bytes
wsp-source/                       pinned WSP
```

Launch the `.exe`. Create a **new** disposable REGTEST profile. Do not import
or open any macOS Desktop chain. RPC stays on `127.0.0.1:29554`.

Shutdown: use the in-app Stop/Quit so the owned Core child exits. Do not kill
unrelated `wamd.exe` processes.

Icon: owner PNG converted to ICO at build time (`assets` branding). No substitute art.

If the build is unsigned, say so in every receipt.
