# Owned disposable Core startup — T03/T08 component

Stacks on Draft54; independently developed Draft55–59 are unchanged. v0.1.11
node AND CLI pins, network/profile, native custody, WSP and signing gates remain.
No v0.1.12 activation, external-node attachment, persistent profile or Core Update
Manager. Never merge automatically.

The prior startup polled RPC through CLI before native endpoint ownership was
proven. Free-port selection also released each socket independently and failed
on any collision. The shared disposable startup helper now:

- Reserves two distinct loopback ports together until config creation completes.
- Creates a new private empty datadir/config/credentials per attempt, maximum3
 attempts under a shared deadline; no existing datadir or endpoint accepted.
- Proves owned pinned image and kernel server socket BEFORE sending any auth.
 The raw readiness TCP connection sends zero bytes. The subsequent authenticated
 connection independently repeats the existing native ownership gate.
- Retries a startup only after actual owned Core EXIT and its private log's
 explicit bind-failure category; no wallet exists yet. No auth/RPC stop goes to
 a competing listener. Other failures, unknown network/version/config or auth
 errors fail closed. No automatic retry after the lifecycle is handed to wallet.
- Handles exact positively refused Core warmup(-28) in startup only, max30 bounded
 backoff reads under deadline. Ordinary runtime closes/hides on warmup; its read
 retry policy remains positive503-only. Never retries an uncertain request or
 any write/sign/broadcast.
- Reaps only its own Popen process on every exit, including failed attempts;
 temporary data only. POSIX SIGTERM permits normal Core shutdown; Windows uses
 process termination. This is NOT persistent/production shutdown qualification.

Genuine fault injection occupies actual TCP ports rather than returning mock
RPC values. It proves one collision then successful second Core, three-attempt
exhaustion, zero auth bytes received by the competing listener, all6 Core
processes reaped and disposable directories removed, and no restart after a
post-start operation error. Native/frozen gates require this component, with no
new workflow/job. Unit malformed/timeout tests remain supplementary.

Local preliminary actual Core proof PASS and172 units139PASS/33platformSKIP.
An initial source unit attempt without network permission failed socket.bind;
reran with authorized native loopback access, no test skipped. Initial real probe
caught Core warmup HTTP500; fixed by parsing only exact structured error-28,
never exposing its message. Exact-commit source/frozen and cross-platform CI are
required before promoting the component, and all integrated P0/Q gates remain
pending. Follow docs/ISSUE45_CONTINUATION.md and separate session resume log.
