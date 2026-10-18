# Issue #45 — T-04 executable hash/exec boundary

One numbered requirement, one Draft PR. The pinned signed v0.1.11 Core/CLI
receipt and platform-native verifier remain the authoritative trust source;
the existing T-03 process image and owned socket proof is unchanged.

## Executed Core path

A fresh **owned** `subprocess.Popen` must match exactly the selected
`wamd`/`wamd.exe`, private `-datadir` and foreground `-daemon=0` arguments.
Before the post-launch `verified_core_paths()` call hashes/signature-checks
the Core and CLI bytes, the binder takes both files' OS metadata
(device/file identity, size, native attributes, owner, links and timestamps).
Immediately after verification it requires the same two paths, stable
metadata for both files and the expected native process image.

Every ordinary authenticated HTTP request continues to verify **live process
image and inexpensive file metadata**, but never hashes either executable
again. Replacement of the node *or CLI* during the hash-to-exec handoff
refuses the binding before credential-bearing RPC bytes may be emitted.
Unverified paths/processes remain fail-closed; no opportunistic binary
replacement or automatic recovery is permitted.

Tests include a same-path, same-size **different inode** CLI replacement
*while the verifier is invoked*, wrong daemon argv refusal before hash, and
the no-per-read-rehash guard. Those are **unit negatives**, not simulated
blockchain acceptance. The existing signed WAM Core native/frozen jobs
exercise the positive new binder against genuine REGTEST `wamd`.

## Explicit limitations

Metadata snapshots and process image path are **not** OS loader attestation,
module signing, protection against a compromised same-UID process, kernel
tampering, or a malicious operator able to alter the verification environment.
Same-UID attacks and TOCTOU remain bounded rather than eliminated. A complete
fd-to-loader guarantee would require independently qualified OS-specific
mechanisms; do not mark such guarantees as implemented or replace the
independent security-review gate. Official release-intake/publisher trust
belongs to R-01 and remains separate.

No mainnet, live funds, attached external Core, WSP signing change, native
anchor/lease downgrade, generic RPC forwarding or automatic merge.
