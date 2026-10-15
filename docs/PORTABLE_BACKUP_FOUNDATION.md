# Portable backup foundation — design only, execution HOLD

Native vault envelopes remain v1/macOS-Keychain, v2/Windows-Credential-Manager
and v3/Linux-root-witness. Their authenticated platform/anchor fields are part
of the custody boundary. Renaming files or removing those fields is not a
migration. This branch implements no portable export/import command and claims
no cross-OS/cross-host recovery acceptance.

A future opt-in migration must preserve the pinned WSP key backup and checkpoint
cryptography; introduce no replacement key derivation/signing scheme. An export
must be made under the source wallet's independent anchor lease from its exact
latest authenticated generation, with explicit reauthentication and consent.
It must preserve all original accounts, epoch/birthday metadata and every
signed/broadcast/uncertain reservation. Export must not release inputs or erase
source state merely because a file was written.

An authenticated, versioned migration profile must identify the source trust
policy, REGTEST genesis, source wallet identity/generation/checkpoint digest,
WSP pin, carried reservations and migration intent. Destination verification
must not infer freshness solely from passphrase possession or a self-contained
file. Provisioning a new anchor must not bless a stale source backup. Source
witness loss/replacement and independent whole-store rollback therefore remain
explicit blockers until a reviewed transfer/freshness protocol exists.

The destination must validate its own native private-storage/anchor policy,
attest the real isolated Core chain, restore through WSP, rescan, and keep old
irreversible reservations. A source/destination conflict or ambiguous crash
must deny spending, never automatically reset generations or discard locks.
The existing 16-epoch ceiling must be handled explicitly before migration can
be labeled operational; no silent rollover is authorized.

Required acceptance is actual source and destination OS processes with their
native anchors, encrypted export authenticity/tamper/wrong-password checks,
stale/concurrent writer rejection, crash points before/after publication and
anchor transfer, preserved keys/reservations, real reorgs and independently
approved real signing/broadcast. Synthetic RPC or a fake cross-platform anchor
cannot qualify it. Cross-Mac, real funds and mainnet remain outside current
execution scope. Design review and platform-specific evidence are required
before any implementation changes native envelope acceptance.
