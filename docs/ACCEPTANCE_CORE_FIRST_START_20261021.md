# A-05 — first authenticated Start after an owned Core crash

Affected baseline: PR112 `2cd3889bfac17102a4e1a7da6420d83d0855e8c0`.
Classification: verified medium lifecycle/reliability defect, P0 T05/Q05
acceptance blocker. No demonstrated unauthorized signature or funds loss.

## Reproduction and cause

Start the independently pinned official WAM Core v0.1.11 in a disposable
REGTEST supervisor, mine101 public-fixture blocks, cleanly stop/reopen to
establish a durable tip, then kill and wait for that exact owned child.
Without refreshing status, submit one correctly authenticated Start frame.

Before the fix, `CoreSupervisor.handle` checks only `self.process is None`.
The exited Popen remains assigned, so Start does nothing. Its subsequent
`status()` finally observes the exit and clears it, returning
`recovery-needed`, no owned process and no height. This reproduces with real
Core, genuine HMAC authorization and no wallet keys or mocked RPC. The
public baseline receipt records the no-op; it does not establish chain loss.
The previous T05 regression refreshed status before restarting and missed
this request-order failure.

## Minimal correction

After unchanged authentication/replay checks, a Start request polls an
assigned child. Only a positively established exit invokes existing status
cleanup before the existing start decision. A live or unverified live child
is neither discarded, adopted, terminated nor duplicated. Core hashes,
ownership/endpoint checks, protected profile, custody, scanner, signer and
irreversible reservations are unchanged. No automatic payment retries or
new control authority are introduced.

## Verification

- Five supplemental lifecycle contracts cover exited child, live child,
  bad authentication, replay and live image-verification failure. The old
  implementation fails the relevant restart contracts; the corrected
  implementation passes all five.
- Existing native T05 real-Core regression now sends the authenticated
  Start frame directly after confirmed child exit, without a status refresh,
  and checks height/tip continuity. This runs within existing platform jobs;
  handler invocation is not claimed as an independent TCP transport test.
- An independent actual Core probe changes from `recovery-needed`/no new
  process to first-request `ready`,101blocks and the same tip after the fix.
- A separate funded Cocoa audit exercises actual supervisor TCP control,
  WSP signed reservations and subsequent native reopen. Its evidence is
  reported separately; a source contract is never real-Core/frozen PASS.

Required release evidence remains exact-head native3OS/frozen regressions
and artifact verification. Complete V1 frozen entry, clean-host recovery,
physical acceptance and independent DEV/security review remain separate
pending gates. REGTEST/disposable only; no upstream Core edits, owner data,
anchor resets, reservation release or automatic merge.
