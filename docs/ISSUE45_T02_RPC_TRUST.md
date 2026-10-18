# Issue #45 T-02 — Owned REGTEST RPC and IPC trust boundary

Scope: **T-02 only**. The unchanged Core RPC connection remains authenticated to the
native supervisor-owned `wamd` process on `127.0.0.1` with strict chain,
genesis, protected private `wam.conf`, native process/socket attestation,
method/param/result allowlists, reply-size caps, timeout and redacted failures.
This is not a new Core attach, mainnet, wallet-import or spending workflow.

## Capability separation

The long-lived supervisor has three independently random, owner-private,
create-once 32-byte tokens:

| File | Purpose |
|---|---|
| `supervisor.token` | Supervisor status / explicitly consented start / stop |
| `supervisor.scan.token` | HMAC-authenticated read-only WSP scanner IPC |
| `supervisor.spend.token` | HMAC-authenticated restricted, separately approved payment IPC |

Each protocol retains its independent domain-separated HMAC, nonce/replay checks,
scope and response authentication. A token obtained through the normal scanner
client no longer authenticates the control or payment protocol. Neither
scanner nor GUI receives the Core HTTP password/port from this API, nor can a
scanner request switch to the spend method allowlist.

## Existing managed REGTEST profiles

On an **explicitly authorized** CoreSupervisor start, a fully authenticated
legacy profile with *both* new token files absent is upgraded through
native create-only private files, without replacing the original control key,
Core chain/datadir, encrypted wallet, key material, or native anti-rollback
anchor. Restart preserves all three files.

If exactly one new token exists, or either file is malformed, wrong-owner,
link-swapped, improperly permissioned or inaccessible, the supervisor
**refuses to start**. It neither repairs, overwrites, deletes, nor silently
falls back to the legacy common-token wire format. A partially interrupted
upgrade requires authorized inspection/recovery; never delete a vault to make
the gate pass.

## Explicit limits and remaining gates

Native file ACLs protect against *different* OS users, but do **not** isolate
mutually distrusting processes running under the **same** OS user account.
In particular, a compromised same-UID process able to read all owner-private
files is outside this change's security guarantee. Application-level GUI
Sign/Broadcast exact-intent and irreversible reservation protections remain
mandatory. This split does not claim independent privileged signer isolation,
external audit, anti-malware defense or arbitrary same-user IPC authority
separation. Real OS sandbox/separate-identity deployment and authorization
hardening remain review considerations.

T-02 Core-cookie external attach applies **only** to the separately gated
T-06 Connect Existing Core implementation; no attached Core or cookie support
is activated here. Per-platform native/frozen and real-Core qualification must
be recorded against exact code SHA. Passing source/unit tests alone is not
P0 acceptance.
