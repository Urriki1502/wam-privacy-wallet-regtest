# V19 — two physical computers (readiness, not a PASS)

Status: **BLOCKED / NOT EXECUTED**. No second physical computer is present in this workspace. One Mac running two Cores, or a VM on the same Mac, is local engineering evidence only and **must not** be labelled V19 PASS.

Reuse existing qualified V1-NET. Do not add a new P2P protocol. Do not use the owner's isolated Desktop wallet (`wam-fusion-core-e905e0d22db25873`) for Shared-mode tests.

Canonical operator steps remain in [V1_NET_TWO_COMPUTER_ACCEPTANCE.md](V1_NET_TWO_COMPUTER_ACCEPTANCE.md). Local V1–V18 frozen evidence: [V1_NET_LOCAL_ENGINEERING_20261104.md](V1_NET_LOCAL_ENGINEERING_20261104.md). Product defaults live in `src/wam_regtest/shared_regtest.py`.

## Network identity (must match on both machines)

| Item | Required value |
| --- | --- |
| Transport | Core-to-Core TCP P2P only |
| Wallet RPC | Fusion → local Core only (`127.0.0.1`) |
| P2P port | 29555 |
| RPC port | 29554 (loopback) |
| Magic | `0x57414d52` (`WAMR`) |
| Genesis | `b88f3d262f285e38e184f50bf3eea1c8e615486ae67d3d9eaf0976fbd6d3d30d` |
| Peer discovery | `-addnode=<peer-host>:29555` via Fusion Shared REGTEST fields |
| Miner | exactly one designated coordinator |
| Maturity | 100-block coinbase; locked premine unspent |
| Fee | existing Core fallback fee |

Supported pairs: macOS+macOS, macOS+Linux, macOS+Windows. Windows is not mandatory. Each OS needs its own qualified Fusion+Core package; a macOS ARM64 DMG does not qualify Windows or Linux.

## Node A / Node B (new disposable Shared profiles only)

1. Install the **same** qualified candidate independently on each computer. Never copy seeds, chain dirs, cookies, journals or RPC credentials.
2. Welcome → **Shared REGTEST · manual Core P2P** → **Create a new wallet** in a new parent folder on that machine.
3. Fill immutable fields: peer LAN/VPN IP, local bind IP, RPC 29554, P2P 29555, peer P2P 29555. Check coordinator **only on A**.
4. Allow TCP 29555 between the two hosts. Do not expose RPC 29554.
5. Complete BIP39 backup on each wallet. **Verify peer and chain on both before mining.**
6. Connect peers **before** mining. Record genesis, magic, `getpeerinfo`, height and tip.
7. Only A mines/funds using existing Advanced test-funding. Wait for B to match tip.
8. Enable sending separately on each wallet. B Receive → BIP352 code. A sends **3 WAM**, fee **0.00010000**, explicit Sign then Broadcast.
9. Record TXID in B mempool, then A mines **one** confirmation block. Both Histories must show that TXID.
10. Disconnect/reconnect A P2P; quit/reopen the **same** profiles; lock/unlock. Do not retry uncertain broadcasts.

## OS-specific builds (only if that OS is the second computer)

- **macOS ARM64:** existing qualified V1 DMG `build/qualified-v1-29448e5/` (executable SHA256 `a86046ada47f9df6a57df4d93dcc7671281f3aa058624c8f7f66de9d59ed2535`) or a later owner-authorized frozen candidate. Rebuild only if that OS has no current qualified package.
- **Linux x86_64 / Windows 11 x64:** use the corresponding signed/frozen platform package after its own native qualification. Do not ship the macOS bundle.
- Firewall: permit inbound/outbound TCP 29555 on the chosen LAN/VPN interface only.

## Evidence that V19 still needs

Record on **both** physical hosts: operator, computer identity, OS, source SHA, Core/WSP digests, package hashes, peer handshake, common tips, payment TXID, confirmation block, both GUI histories, disconnect/reconnect, same-profile restart. Preserve FAIL history.

**Missing hardware:** a second distinct physical computer. Until it exists and this procedure actually runs, V19 remains BLOCKED / NOT EXECUTED.

Q06 `accepted=false`. G6/G7 unchanged. No mainnet.
