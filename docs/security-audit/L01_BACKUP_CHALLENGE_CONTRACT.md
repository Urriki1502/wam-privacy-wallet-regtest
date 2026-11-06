# L-01 backup acknowledgement challenge

The serialized `Bip39ReadOnlyBackend` owns one outstanding challenge per open
session. `backup_challenge` takes no arguments and returns a random 32-byte
opaque identifier as 64 lowercase hex characters, three distinct sorted
positions in 1..12 selected by `secrets.SystemRandom`, and a 120-second TTL.
The backend retains only identifier, positions, profile path, session epoch and
monotonic expiry in memory. Neither mnemonic nor answers enter this record.

`backup_verify(identifier, answers)` accepts exactly three bounded strings;
caller-selected positions and the old API are refused. Every submission consumes
the challenge before validation or native authentication. Identifier, profile,
epoch and expiry must match; expiry is checked again before writing the existing
authenticated acknowledgement. Wrong answers return false, other refusals use
fixed public error codes. Success, refusal or an uncertain acknowledgement write
cannot replay the identifier. A new request replaces the previous challenge.

Lock, defer, reopen, restart and verification cancellation invalidate it. The GUI
obtains a fresh challenge when entering verification and after a failed attempt;
it sends only the identifier and answers, never chooses positions, and never
automatically resubmits verification. Returning to the phrase page cancels the
challenge. The preexisting HMAC sidecar and seed/anchor formats are unchanged.

Source regressions cover short answers, caller positions, replay, expiry both
before and during native authentication, profile/epoch substitution, cancel,
lock/restart, write failure and concurrent executor submissions. The existing
genuine-Core same-chain qualification additionally exercises short answers,
caller positions, wrong-answer replay, cancellation, lock/reopen, exact-three
native acknowledgement and successful-submission replay inside final frozen
Mac/Windows/Linux executables. Its receipts contain only case names/booleans.

This acknowledgement is a UX check. Displaying words and answering three prompts
does not prove that an offline backup exists. It grants no independent signing,
broadcast, migration, release or mainnet authority. Other audit findings remain
outside this implementation.
