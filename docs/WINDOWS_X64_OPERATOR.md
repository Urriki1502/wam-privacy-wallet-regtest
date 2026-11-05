# Windows x64 — install and run (after a native frozen build)

This host **did not** build or run a Windows package. Follow this only on
native Windows 11 AMD64 after `scripts/build_windows_bundle.py` succeeds on

```
17adf5c5cbb1213ea5abd95a2ecdd9464b0874a2
```

## Layout

```
WAM-Privacy-Wallet-REGTEST.exe    windowed Fusion
_internal/ …                      Qt/Python
core/wamd.exe, wam-cli.exe        official v0.1.11 PE pins
wsp-source/                       pinned WSP ac55f13423620252bdbf848c7e8a280c3b84721e
```

Launch the `.exe`. Create a **new** disposable REGTEST profile. Do not import
or open any macOS Desktop chain. Isolated RPC stays on `127.0.0.1:29554`.

Shutdown: use the in-app Stop/Quit so the owned Core child exits. Do not kill
unrelated `wamd.exe` processes.

Icon: owner PNG converted to ICO at build time (`assets` branding). No
substitute art.

If the build is unsigned, say so in every receipt. Do not call it Authenticode
or notarized.
