# Release provenance

| Field | Value |
| --- | --- |
| Fusion functional source | `b844dd371d4ac5dc3d0469eb899d6709e8ac407f` |
| Docs/prep commits on top | `603a1981ac6b4da83c27e9d8a705cab130f6e12e` and later markdown-only commits |
| WSP | `ac55f13423620252bdbf848c7e8a280c3b84721e` |
| Network | REGTEST only |
| Official Core tag | v0.1.11 (wamcoin.org downloads; GitHub release **UNVERIFIED**/404) |
| Publisher fingerprint | `4BD4A8D3AFD43F5CBCB500E23798462FE00ADBA4` |
| macOS Core members | official signed, hashes in `core/receipt.json` |
| Windows Core archive | official signed ZIP `ece622fa…` |
| Linux Fusion Core | **developer-built unsigned** pins in `scripts/build_linux_wallet.py` |
| Official Linux archive | GPG-listed `bd010ed6…`; **not** the Fusion Linux builder input |
| App signatures | none produced this session; macOS historical builds are **ad-hoc**, not Developer ID/notarized |
| AI/agent assistance | used for documentation and verification commands; **not** a human Owner/Developer/G7 signature |
| Mainnet | denied |

Independent rebuild: check out `b844dd3`, follow `docs/DEVELOPER_NATIVE_BUILD_HANDOFF.md`, compare SHA256. Bit-for-bit PyInstaller identity is **not** claimed (timestamps, ad-hoc codesign, Mach-O rebuild of collected Python).
