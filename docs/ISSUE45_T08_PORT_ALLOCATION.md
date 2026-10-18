# Issue #45 — T-08 Port Allocation Safety

**Implementation scope:** one numbered T-08 PR. The existing disposable
REGTEST startup already reserves two distinct loopback ports until private
configuration is written and permits at most three **positively classified,
pre-wallet, owned-daemon bind-collision retries** using fresh, disposable
datadirs and credentials. It never reconnects to or terminates a stranger.
The native Core process/socket must be authenticated before any HTTP
credentials are sent.

## Gap in persistent managed Core

Unlike the disposable starter, the persistent supervisor owns a **create-once
private datadir, protected `wam.conf`, and stable wallet chain/history**.
It cannot safely replace the configured RPC port on startup failure. Before
T-08, it launched `wamd` while that existing port might already be held
by an unrelated process, relying on later readiness failure.

T-08 now tests the previously authenticated private configured RPC port with
a native, exclusive **127.0.0.1 TCP bind** immediately before `Popen`.
If another process owns the port, it refuses **before process spawn** with
the fixed, redacted code `MANAGED_RPC_PORT_OCCUPIED`. It does not change
`wam.conf`, chain files, wallet, token, P2P policy, owner settings, or
binary pins. It does not send RPC bytes, signal a foreign process, or
adopt a PID. When that other process is gone, an operator-initiated retry
may start the original managed Core using **exactly the same** protected
config and datadir; the existing maximum of three consecutive start
failures remains effective.

After the reservation is released, there remains a small kernel scheduling
**release-then-daemon-bind handoff race** because WAM Core does not accept a
socket-activation file descriptor. A later bind collision does **not**
authorize changing a protected persistent profile. Any foreign responder
remains blocked by `OwnedCoreBinding.assert_socket` and the exact native
owned process/image attestation **before** HTTP/basic-auth bytes. This is
a bounded mitigation, not a claim that a competing untrusted OS process
cannot race the port handoff.

P2P stays `listen=0`, `connect=0`. No remote listener or mainnet peer
is permitted. An external REGTEST Core attached via T-06 is never started,
stopped or changed by this guard.

## Testing and limitations

- Unit negatives: existing RPC port held by unrelated listener -> no
  `Popen`, preserved state, fixed denial; invalid port types/ranges
  refuse before socket allocation; reservation releases cleanly.
- **Genuine Core E2E** on macOS and Windows, plus qualifying Linux Qt
  harness: hold the actual disposable persistent Core's chosen private
  RPC port with a competing listener; require pre-launch refusal with
  untouched protected config; close listener and successfully launch
  *the same verified Core, chain and config*. Continue the existing
  genuine WSP wallet / GUI / Sign / Broadcast and native/frozen gates.
- Older disposable startup queue/retry, wrong-endpoint preauth refusal,
  Core-socket ownership and WSP BIP352 vectors remain mandatory.
- Physical operator tests, independent reviewer, cross-host adversarial
  scheduling and prolonged contention remain separately PENDING.

No automatic multi-port reallocation of durable profiles, no config
rewrites, no replacement node, no deletion of wallet state and no
production/mainnet authorization.
