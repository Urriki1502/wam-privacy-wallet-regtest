# Engineer 2 checkpoint — macOS real-Core owned-session CI (not Q-GATE)

Branch `cursor/q05-history-pagination-9c81` HEAD `fa6d48a31fe56208dbc278901493ce718c0619b2`.
Codex Draft #138 remains `9b0361c6211f500ef78d0ace171c1bb6a5a10329`.
Canonical ledger: 37 Q05 PENDING, `accepted=false`. No second PR, no merge.

## This milestone

- Job `q05-owned-session` in `.github/workflows/real-core-regtest.yml`:
  official signed macOS ARM64 Core + `scripts/probe_q05_owned_session.py`
  empty START→RESTORE and funded BIP352/sign/broadcast.
- Probe records original Popen ownership, lock-without-Core-stop, restore.
- History rejects heights past the verified tip and non-positive confirmations.
- GUI close ignores in-flight sign/broadcast; in-process CLI stops Core on exit.

## Tests actually run (Linux agent)

- `test_q05*.py`: 114 PASS (SOURCE only)
- Linux probe: `Q05_OWNED_SESSION_PROBE_SCOPE_DENIED` (expected)
- REAL CORE / NATIVE macOS: NOT EXECUTED here

## CI

- Owner Linux supervisor run https://github.com/Urriki1502/wam-privacy-wallet-regtest/actions/runs/40786655493
  PASS on `d87a251` — **not** genuine Core E2E.
- Cloud Agent `gh workflow run real-core-regtest.yml`: HTTP 403 (no `actions:write`).

Owner dispatch:

```bash
gh workflow run real-core-regtest.yml \
  --repo Urriki1502/wam-privacy-wallet-regtest \
  --ref cursor/q05-history-pagination-9c81
```

Inspect job **Q05 owned-session genuine signed Core START→RESTORE** on SHA `fa6d48a`.
Do not attribute run 40786655493 to this SHA or to Core E2E.

## Next

Owner-dispatched macOS real-Core job, then repair from its receipts.
Do not mark canonical Q05 PASS from this checkpoint.
