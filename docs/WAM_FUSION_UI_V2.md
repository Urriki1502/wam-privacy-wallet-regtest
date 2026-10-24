# WAM Fusion 2.0 — visual review candidate

UI-only branch `feature/wam-fusion-ui-v2-20261015`, stacked on PR27 head
2725f8440bb4db7ed9ef6d9a3cefae6f95c3a4b2. Main and Windows dependencies
remain unchanged/unmerged. This is not Final or a human visual approval.

All six screens use one native Qt tree and shared palette/spacing/type/icon
components. The original supplied WAM PNG remains unchanged. No proprietary
font is bundled; available system families are selected at runtime.

- Overview: watermark hero, real balance/UTXOs/tip, three status cards,
  confirmed gross credit/debit chart with WAM axes, block hover details and
  recent-transaction navigation. Never a reconstructed balance/price chart.
- Receive: checksum/public-key validated genuine REGTEST BIP352 code, pure
  qrcode8.2 encoder matrix, square black/white modules and four-module quiet
  zone. Exact full-value copy and selectable wrap-anywhere plaintext.
- History: direction, actual credits/debits, confirmations, block, transaction
  search/filter, exact-ID detail/copy. No external metadata or explorer lookup.
- Send: four-step presentation, amount/fee form and exact native review;
  default-Cancel Sign and Broadcast dialogs. These are additional UI consent,
  not signer authorization or automatic approval. Existing WalletSession
  commitment, anchor, lease, reservations and uncertainty gates are untouched.
- Security: encrypted runtime, native anchor, lock/unlock, backup/recovery and
  separately authenticated local disclosure. No fabricated security score.
- Settings: native Auto/Light/Dark, verified Core hash, actual privacy/sync
  controls, test mining and honest experimental build/platform information.

Lock/fault clearing covers balance, QR, code, chart/hover, transaction table,
selected details, disclosure, identity tooltip and faulted payment form/review.
Immutable buffers and unlocked SQLite retain the existing explicit limitations.

## Verification

Presentation unit fixtures are not real-Core acceptance. New tests verify
contrast, exact copies, QR refusal/clear, history filtering/clear, selectable
plaintext, default-deny dialogs and absence of signer/RPC authority in the
presentation modules. Native real-Core probes inspect the redesigned visible
columns and full detail/copy values; no comparison of blockchain truth is removed.

The genuine WalletSession E2E operator drives actual modal approval buttons;
Cancel is tested before signing. There is no application test flag or auto-sign
path. Real source/frozen runs capture six Dark screens plus Light/Auto Overview,
1280x800 / 1440x900 / 1920x1080 and a compact viewport, and both approval dialogs.
All screenshots come from a real Core-funded test wallet, not illustration or
synthetic balances. `fusion-ui-review/*-visual-receipt.json` states the platform,
Qt backend, DPR, verified height and pending human visual review.
The receipt records requested and actual logical geometry separately. Cocoa
can constrain a large requested window to the MacBook display work area;
filenames describe the requested viewport, not proof of a larger display.
Review the actual geometry before accepting a viewport or scale claim.

The frozen Windows gate also reruns the genuine wallet at125%/150% via
QT_SCALE_FACTOR, verifies qwindows + actual DPR and publishes separate views.
Human Windows OS/display-setting and macOS/Windows visual signoff remain
separate from these automated source/frozen runs. Review exact-head artifact/checksum provenance
before qualification. Linux HOLD; PayJoin validation-only; no mainnet or funds.

Local MacBook native Cocoa E2E on6fdff6d passed real send/confirmation,
reorg1/12/100, encrypted recovery, fresh-Core reopen and Auto/Light/Dark.
This is automated native application testing, not human visual approval.
