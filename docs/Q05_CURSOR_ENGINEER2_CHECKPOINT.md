# Engineer 2 checkpoint — owned-Core GUI attach (not Q-GATE)

Branch `cursor/q05-history-pagination-9c81` HEAD `f0448d69e164ad3f0e46c8b429fe335d0dc9c792`.
Codex Draft #138 remains isolated.
Canonical ledger unchanged: 37 Q05 PENDING, `accepted=false`.
No second PR, no merge, no mainnet.

`gh workflow run` on this token: HTTP 403 Resource not accessible by
integration (contents:read). No native/frozen CI on this SHA.

## Implemented (this milestone)

- `WalletSession.open_owned`: live session on original `CoreSupervisor`
  Popen. No fixture funding, no height 102/103 gate, no PID adoption.
  Dirty runtime/sidecars refuse without repair.
- `wam-regtest managed-gui`: in-process start + Qt. Window close locks
  the wallet only. Core shutdown only with explicit `--stop-core-on-app-exit`.
- History older/newer window (`skip_newest` / SQL `skip`) after full
  fingerprint. Receive stats use `COUNT(credit>0)`, not the GUI window.
- Fail-closed publication inspect unchanged (`automatic_recovery_allowed=False`).
- `scripts/probe_q05_owned_session.py`: in-process START→RESTORE harness for
  signed macOS Core. Linux agent: `Q05_OWNED_SESSION_PROBE_SCOPE_DENIED`.
- `gh workflow run` HTTP 403 Resource not accessible by integration.

## Tests actually run (Linux agent)

- `unittest discover -s tests -p 'test_q05*.py'`: 111 PASS (includes
  `test_q05_owned_session`)
- `test_history_pages`, `test_gui_error_privacy`, owned-open consent/runtime:
  PASS
- Qt `test_fusion_v2_widgets`: NOT EXECUTED (no PySide6)
- Genuine Core / macOS / Windows / frozen / physical: NOT EXECUTED
- `gh workflow run`: previously 403; re-attempt after push

## Next unblocked task

Dispatch existing Q05/linux/macos/windows workflows on this SHA if
Actions grants `workflow_dispatch`. If 403, continue source-level
recovery/reservation contracts. Do not fabricate native PASS.

Do not promote Q05 cases to canonical PASS from this checkpoint.
