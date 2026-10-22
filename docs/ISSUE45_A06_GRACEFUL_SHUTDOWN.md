# A06/Q05 graceful shutdown qualification

This unit qualifies the clean path separately from original PR114's unchanged
abrupt-crash failure. It does not change Core, runtime versions, supervisor
recovery, signing, custody, scanner or reservation behavior.

`shutdown_probe.prove_graceful_shutdown` creates an isolated owned profile,
a disposable Core descriptor wallet and 101 genuine blocks. It records the
exact tip and native datadir/profile identity and checks a funded Core wallet's
original address label/ownership and balances after restart.

* All native platforms: direct authenticated `stop` RPC; require child exit0.
* POSIX: an independent fresh profile receives genuine `SIGTERM`; require exit0.
* Restart: original101 height/tip and wallet state must match, without reindex,
  post-restart mining, wallet replacement or deletion to repair the chain.

The stop proof does not call the supervisor cleanup fallback. Cleanup may use
the existing owned-process shutdown only after the test assertions; it never
counts as proof of successful RPC/SIGTERM. Uncertain children retain private
data. Wallet CLI reads are a test-only witness and do not broaden application
transport allowlists. No keys, addresses or private paths enter receipts.

The component runs in the existing genuine source/native and final frozen
acceptance entries (macOS app/dmg, Windows exe, Linux desktop/headless).
Failures propagate; skipped/missing results are not PASS. No new workflow.
Original independent A06 crash diagnostic and mandatory release aggregates
remain FAIL. Graceful qualification cannot qualify abrupt recovery, native
Fusion checkpoint continuity, full Q05/V1 or physical acceptance.

Local macOS exact pinned v0.1.11 binary pair independently passes both methods.
Three-OS/frozen results require exact-head CI and downloaded artifact review.
The owner's DEV report about v0.1.12 flushing/reindex is separate evidence;
it does not qualify v0.1.11 recovery or authorize a runtime upgrade.
