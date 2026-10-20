# F-07 — WAM legacy Base58Check / Bech32-prefix parser parity

**Issue #45 / Phase F / F-07 [P0]**. REGTEST-only wallet safety and
public-source evidence. Exact-version Core mainnet runtime remains **PENDING**.

## Why the prefix trap exists in source

WAM Core v0.1.11 is assembled over Bitcoin Core **v28.1**. The
unmodified upstream `src/key_io.cpp` Git blob
`6cece47e410397e318d54643d0e459a44f756691` contains an
explicit case-insensitive, prefix-length comparison:

`is_bech32 = (ToLower(str.substr(0, params.Bech32HRP().size())) == params.Bech32HRP());`

Before it chooses the Base58Check decoding branch, it checks
`!is_bech32`. WAM's tagged `src/wam/chainparams.cpp` Git blob
`6e7eebfec5483f99ed13849a9b22cd502781364f` sets:

- **Mainnet:** P2PKH byte `73` ('W'), P2SH byte `135` ('w'),
  Bech32 HRP `wam`.
- **Testnet:** P2PKH `65`, P2SH `128`, HRP `twam`.
- **REGTEST:** P2PKH `65`, P2SH `128`, HRP `wamrt`.

A Base58Check address can begin with case-insensitive `wam` even
though its checksum and version bytes are correct. The source
predicate then routes it to the Bech32 decoder; this is not the
same as actually getting a `validateaddress` response from the
released mainnet binary.

## Public-only fixed vectors

These are deterministic SHA256-derived PUBLIC hash160 fixtures,
**not** generated from a private key, real user wallet or seed.

| Network | Address | Type | Source predicate |
| --- | --- | --- | --- |
| Mainnet | `WamAskWnsuS1LBhLhgGQSo9HACyE4aHLER` | P2PKH / version 73 | Bech32 branch prefix collision |
| Mainnet | `waMSB1joxWLA9nFTHpNT9HHKpavsLW7WXG` | P2SH / version 135 | Bech32 branch prefix collision |
| REGTEST | `TBDeDSETJdmttTFUwFVL8Qpw4SV87XAYEj` | P2PKH / version 65 | No HRP collision |
| REGTEST | `tjtGH5pUR8i7GweABGcPgFzic8Fv8mYLvq` | P2SH / version 128 | No HRP collision |

Independent Python Base58Check calculation confirms each checksum,
payload length, correct version and expected standard scriptPubKey.
That is **offline validity**, not permission for a production send.

## Actual Core acceptance scope

The pre-existing isolated native mining acceptance creates its
OWN disposable WAM Core v0.1.11 REGTEST instance; no mainnet
datadir or wallet exists. F-07 invokes the real read-only
`validateaddress` RPC on both REGTEST public fixtures and checks
exact Core-reported scripts against the offline result.

The two valid mainnet Base58Check collision fixtures are also
passed to the same **REGTEST** `validateaddress` as negative
wrong-network fixtures. If Core refuses them, that is **network
separation evidence only**; it does not reproduce the actual
mainnet prefix bug at runtime.

Real native Linux, macOS ARM64 and Windows x64 CI must assert
`f07_genuine_regtest_p2pkh_p2sh_validateaddress_parity=true`,
`f07_mainnet_collision_public_fixture_network_refusal_regtest=true`,
and `f07_native_mainnet_parser_runtime_qualified=false`.

## Send UI and custody safety

The current Fusion REGTEST Send workflow accepts only a verified
`wamrtsp1...` BIP352 recipient. Before querying Core or touching
custody, `WalletSession.prepare` recognizes checksum-valid
mainnet Base58 legacy inputs and refuses them with separate
redacted GUI messages for (a) potential `wam` HRP collision and
(b) other wrong-network legacy input. It never attempts to send
to a legacy mainnet address from a REGTEST wallet.

**An imported Core descriptor/key remains unchanged** even if the
node cannot parse its corresponding public address. We never
delete/rotate/import/remap keys, change ownership flags, or show
phantom spendable funds. There is no new Core legacy-send
workflow and no automatic fix.

## Qualification boundaries

- Unit contracts may demonstrate public checksum/collision and
  refusal, but are **not** Core E2E.
- Native REGTEST parity is accepted only with actual Core RPC
  return shape and script check on all three OS.
- Real mainnet `validateaddress` rejection, exact offending parser
  bug root cause on the released binary, any upstream fix, and
  DEV WAM acknowledgement are **PENDING**. Do not use this PR
  to launch or query a mainnet node, and do not announce upstream
  a runtime defect without a reproducible native observation.
- Future authorized DEV testing must use an isolated,
  non-treasury, no-key host and preserve all imported descriptors
  while demonstrating the original Core's parsing discrepancy.
- No consensus code, new key material, mainnet network access,
  imported user wallet, node shutdown or merge is authorized.

**Evidence limit:** do not mark F-07 complete until exact PR
HEAD CI is green, and keep mainnet runtime test explicitly pending.
