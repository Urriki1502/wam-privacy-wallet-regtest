# WAM Fusion REGTEST RC1 resume checkpoint — 16 October 2026

Only application repo: Urriki1502/wam-privacy-wallet-regtest. Never change legacy
wallet or upstream Core. Dedicated worktree: work/release-qualification.

Qualified CODE SHA: 144d87700b87a241467172adfad3692b41e1d273.
Code branch: integration/wam-fusion-regtest-v1-qualification, Draft PR36,
https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/36
Base: docs/linux-qualification-checkpoint-20261015 (#35).
Main unchanged: 50e1ea94df61b8400cbab3bffe0fbdd285c6b419.
Current delivery branch: docs/wam-fusion-regtest-rc1-evidence, a DOCS-ONLY child
of CODE SHA. Read actual git HEAD/status and live PRs on resume; its later docs
commit is NOT another qualified runtime. Do not rebuild merely to include the
aggregate report inside artifacts: all four qualified packages share CODE SHA.

## Completed RQ units

- RQ01–02 PASS: reviewed actual19 PRs17–35, files/ancestry/checks/review threads;
  zero unresolved threads at audit. All18–35 are candidate ancestors; #33
  ancestry-only merge has no content delta. Stale #17 excluded and left open.
  No shared history rewrite, predecessor close/merge or main merge.
- Focused three-platform security review retained custody/Core/WSP/scanner/
  rollback/lease/reservation/signing gates. No replacement crypto/new features.
- RQ03–05 PASS at EXACT CODE SHA: all eight native workflow_dispatch runs and
  four frozen payload gates. The five additional PR workflows/11 PR jobs also
  PASS, but synthetic merge artifacts are not owner downloads.
- First candidate0cdb111 failed an extra old Windows Qt gate because it omitted
  qrcode.144d877 installs the existing .[gui] extra; tests unchanged. All gates
  and packages were rerun at144d877. No old PASS reused for the successor.
- RQ06 automated actual-MacBook downloaded-app Cocoa PASS on Mac14,9/macOS27.0.1;
  DMG VALID, strict ad-hoc signature PASS, Core hashes unchanged, exit0 and owned
  app/Core processes absent. Human Finder/OS settings remain PENDING_OPERATOR.
  Owner explicitly has no authorized physical Linux machine: PENDING_OPERATOR.
  No SSH probing or privileged host provisioning performed. Windows10/11 human
  acceptance and Linux GNOME/KDE Auto remain separate pending operator tasks.
- RQ07 PASS: four published same-CODE RC1 artifacts downloaded; public manifests/
  every Windows+Linux member/Core/WSP33files/branding/ELF stack/PE/links verified;
  common manifest/source=checkout and headless no-Qt verified independently.
- RQ08–09 prepared: owner guide, full qualification matrix, public receipts,
  exact checksum/download/expiry report and DEV technical review draft. DEV
  package NOT sent. Disposition READY FOR OWNER REGTEST TESTING, not FINAL or
  production. No main merge or official final release is authorized.

## Exact-source CI and artifacts

All event workflow_dispatch, head144d87700b87a241467172adfad3692b41e1d273:

| Gate | Run | Result |
| --- | --- | --- |
| canonical28vectors |38747142053|PASS|
| macOS source + app/DMG |38747153198|PASS|
| Windows credential/storage/source + frozen + DPI125/150 |38747163508|PASS|
| Linux root/contracts/source/xcb/CLI/Core rebuild + both frozen |38747174307|PASS|
| Windows Core/WSP preflight |38747184018|PASS|
| Windows real101block Core |38747193574|PASS|
| Windows real BIP352/SQLite/restart |38747202781|PASS|
| Windows real read-only Qt |38747211715|PASS|

Published actual downloads, inner/outer SHA256, full build tools and UTC expiry:
RELEASE_CANDIDATE_QUALIFICATION.md and docs/evidence/rc1/*.json.
Artifact IDs: Mac11980032023, Windows11980747014,
Linux desktop11979187025, Linux headless11980206630.
All expire29October2026 (~14:00–14:19UTC); do not assume retained forever.
Rebuild at exact CODE SHA with the eight existing workflows if needed. An
expired immutable Linux Core dependency requires independent reprovisioning/
requalification, never accepting a self-learned new Core hash or RWE fallback.

Immutable pins: WSPac55f13423620252bdbf848c7e8a280c3b84721e;
Linux approved manifest e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806;
Core artifact run38697805476/name linux-developer-core-576082d227ccd9eb139686ded431c69c07399237.
Original Mac/Windows official node+CLI hashes remain in report and runtime.
Native backup profiles remain v1/Keychain, v2/Credential, v3/root witness.

## Next executable step / guardrails

Collect owner feedback using OWNER_REGTEST_ACCEPTANCE.md; physical Linux is
blocked on an explicitly authorized host and separate root-witness admin approval.
Do not ask again for a machine while the answer remains no. Do not mark manual
acceptance PASS without observations. DEV_WAM_REVIEWED=false until actual review;
DEV_WAM_REVIEW_HANDOFF.md is prepared only, do not send automatically.
If a concrete runtime defect is reported, make a small fix on a new candidate
branch and rerun same-source native/frozen qualification. Preserve uncertain/
signed locks and every security gate; no personal funds/keys/mainnet.

Before any engineering, inspect active threads/processes and acquire the common
Git engineering lease with scripts/engineering_lease.py --hold. Refuse exit73
or concurrent engineering. The delivery session used lease99094/PID35965; its
lifetime is recorded in the separate log, not permission to bypass a fresh lease.
Other worktrees/uncommitted owner files remain untouched. Session files/logs:
outputs/release-qualification-rc1/EXECUTION_LOG.txt, native-ci/, downloads/ and
verification harnesses (public receipts only; no vault or RPC credentials copied).

Existing linux-regtest-single-continuation one-shot remains PAUSED. Do not
restart/update it, create recurring retries/charges, use reset credits or assume
limits reset. Last actual usage query ordinaryUsageAllowed=true; future failure
must be recorded as observed, with this checkpoint pushed before stopping.
Residual production-hardening gaps are explicit in the report; portable backup
and BIP352×PayJoin execution remain design-only/V2 HOLD.
