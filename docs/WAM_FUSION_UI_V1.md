# WAM Fusion Signature — macOS ARM64 + Windows x64

**Branch:** `feature/wam-fusion-ui-cross-platform-20261014`. This is a Qt
presentation-only iteration, stacked on Windows operational PR #26. It must
not replace the real Core/WSP source gate or claim a production release.

## Design contract

- One PySide6 widget tree on both native platforms. Design tokens and reusable
  components live in `src/wam_regtest/fusion_ui.py`.
- Palette modes: **Signature Dark** (obsidian / graphite / WAM gold
  `#F1C55A`) and **Signature Light** (pearl / carbon / dark WAM gold
  `#795507`). **Auto** uses Qt's real macOS/Windows operating-system
  color-scheme hints when available. The original fail-closed
  `resolve_theme` fallback remains for unspecified system appearance.
- Dashboard replaces the old Balance-only page, without changing the
  original operational Send=3 / Security=4 / Settings=5 navigation indexes.
  Existing `balance_text`, `utxo_text`, `history_table`, review and
  signer controls retain their original identities for native E2E gates.
- Shared visual components include gradient balance hero, status cards,
  verified transaction bars, recent transactions, navigation icon geometry,
  action buttons, rounded input cards, table headers, and focus/disabled
  states. Other tabs retain existing content with the new global theme.
- The first screen is Overview. Receive, Send, History, Security and Settings
  remain functional on the same original Qt widget/session stack.

## Data truth / safety

- The only financial data source is a **validated real Core/WSP
  `WalletReadSnapshot`**; no hardcoded balances, account history, fiat FX,
  security ratings, connected peer counts or synthetic RPC fallback.
- The activity visualization shows **confirmed on-chain credit/debit sums by
  verified block**, NOT an invented balance-history chart. It explicitly
  labels gold = received and blue = sent; missing history draws an empty state.
- Node/scanner/status badges read the verified snapshot only. Lock/RPC failure
  clears hero balance, chart and recent-activity rows; uncertain reservations
  and reviewer approvals remain governed solely by WalletSession.
- PayJoin still **validation-only**; BIP352 × PayJoin execution belongs to V2.
- UI changes never call `Signer`, `Vault`, wallet RPC, or WAM Core directly;
  action buttons only navigate to the existing approved operational controls.
- No change to OS owner-only storage, Keychain/Credential Manager, WSP source
  pin or bundled official WAM Core hashes.

## Release qualification and limitations

- Required: native macOS exact-head real-Core/source + packaged .app/.dmg,
  Windows exact-head genuine-Core source + packaged .exe, and independent
  vectors/security contracts PASS. Zero E2E mocks or disabled review controls.
- Before handing to DEV: visually inspect dark/light/auto on a macOS device
  and Windows 10/11 x64; verify readable WAM amounts, no truncated warnings,
  keyboard/focus access, HiDPI chart, locked-state clearing, actual transaction
  receipts and no invented security/fiat labels. CI alone does not certify
  visual accessibility or human operator experience.
- Preserve PR #18–#26 as Draft and merge dependencies bottom-up only after
  independent acceptance; this theme branch is an overlay, not a release.
