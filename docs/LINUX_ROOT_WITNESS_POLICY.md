# Experimental independent Linux root witness — review candidate

Problem: owner-controlled encrypted files cannot establish independent
monotonic freshness without Keychain/Credential Manager. This optional witness
separates authority by OS UID instead. It is not a cipher, keyring, signer,
hosted scanner or TPM. The explicit Linux runtime now connects it to the shared
vault/session; source wallet acceptance remains mandatory before qualification.

Administrative provisioning must install the reviewed standalone Python
service root-owned and non-writable by group/others, then explicitly provision
a new root-owned0755 endpoint directory. Its records and locks are root0700;
files are root0600 single-link, no ACL, no-follow. Existing state cannot be
re-provisioned; restart validates identity and configured non-root UID. Missing
identity/records/unsafe metadata refuse. The wallet never invokes sudo or
auto-installs/starts a service. Native tests install/stop/remove only their exact
disposable helper and random state directory on ephemeral Ubuntu CI.

The pathname socket is protected by root-owned non-writable ancestors and a
root0755 parent; socket0600 belongs to the authorized wallet UID. Both sides
verify Linux SO_PEERCRED. Server requires configured UID; client requires UID0.
Only bounded messages for lease/read/advance/ping/release are accepted. There
is no reset/delete, key material, arbitrary file path, command execution,
signature or network submission API. Public wallet ID/generation/digest only.

An OS wallet-ID flock remains in the root server for the entire client lease.
Exact-object/thread nesting is allowed; another object/process contends even
across vault directories. Release acknowledgement follows actual unlock.
Client validates a live lease after its body; service loss raises and must fault
the future coordinator before success/signature exposure. A killed client or
server releases OS locks. Server instance flock prevents competing listeners.

Advance compares the exact prior generation/digest, requires next generation,
writes/fsyncs a stage, create-only links the immutable journal member, removes
the stage, fsyncs directory and verifies readback before success. Journals must
be contiguous and are capped at10000 generations. Root metadata/missing
members/partial records deny. Ambiguous publication never silently overwrites.

Boundary: protects wallet-user directory rollback while the independent root
witness remains intact. Root compromise, rollback/loss of the entire witness
store/OS, hardware power loss, guaranteed erasure, availability against the
authorized UID, and hardened executable-to-process binding are unqualified.
Loss/replacement must not authorize old-backup import or automatic reset.
Future Linux vault envelopes must bind this policy and require the witness;
absence must keep spending disabled. Cross-OS migration remains separate.

Required native tests: actual root peer and UID custody, monotonic CAS/stale
writer denial, ordinary-user inability to write witness records, exact-object
lease reentry/contention, server crash/lost-lease detection and restart
persistence, missing endpoint and uninstalled service refusal. No mock witness
is accepted as qualification. Full real-Core wallet gates remain additional.

Reference for peer-credential semantics:
https://man7.org/linux/man-pages/man7/unix.7.html (SO_PEERCRED, pathname sockets).
