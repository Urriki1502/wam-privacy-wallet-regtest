# WAM-Fusion-REGTEST-RC1 — owner testing

Experimental disposable REGTEST only. No mainnet, personal seeds/keys, real funds
or production wallet. Technical automation results and human usability signoff
are separate. The proposed UX fix completed50 local real-Core owner checks and
native/frozen qualification; see the audit below. Only the physical/manual items
in its final section still need an operator. The exercises here are reproducible
reference instructions, not a requirement to manually repeat all automated gates.

Baseline RC1 code: `144d87700b87a241467172adfad3692b41e1d273`.
Proposed owner-UX fix code: `427d3b0789d0b7e2da1f506c8dde860b5c6b4575`, Draft PR38.
[Owner audit, qualification, new downloads/checksums](OWNER_ACCEPTANCE_AUDIT.md).
The proposed code remains unmerged. Use the actual candidate manifest/source/run;
never mix its receipts with baseline artifacts. Original baseline downloads:
[RC1 qualification](RELEASE_CANDIDATE_QUALIFICATION.md).

## Download, provenance and checksums

Use only actual published Actions links in the owner audit/RC1 qualification or
the integration PR. Choose the four RC1 artifacts whose FULL source SHA matches:
macos-arm64, windows-x64, linux-x86_64-desktop and linux-x86_64-headless.
GitHub login may be required. Artifacts have14-day retention; the report records
expiry. Rebuild from the exact source/pins using the existing workflows if expired.

After downloading the Actions ZIP, extract it into a NEW owned testing folder.
Mac/Linux payloads are in `package-output` / `linux-package-output`; Windows
payloads are at the artifact root. Read RELEASE_CANDIDATE_MANIFEST.json:

- candidate_id=WAM-Fusion-REGTEST-RC1, network=regtest, mainnet_allowed=false;
- source_head_sha=checkout_sha=the exact qualified integration code commit;
- the expected platform, independent Core pair and pinned WSP revision;
- workflow run URL, build versions and hashes. A self-contained manifest alone
  is not an authenticated release or a substitute for its successful workflow.

Verify ALL SHA256SUMS.txt entries before launching. On macOS:

```sh
shasum -a 256 -c SHA256SUMS.txt
hdiutil verify WAM-Privacy-Wallet-REGTEST-macOS-ARM64.dmg
```

On Linux: `sha256sum -c SHA256SUMS.txt`. On Windows PowerShell:

```powershell
Get-Content SHA256SUMS.txt | ForEach-Object {
  $pair = $_ -split '  ', 2
  if ($pair.Length -ne 2 -or [IO.Path]::GetFileName($pair[1]) -ne $pair[1]) { throw 'Invalid checksum entry' }
  $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $pair[1]).Hash.ToLowerInvariant()
  if ($actual -ne $pair[0]) { throw ('Checksum mismatch: ' + $pair[1]) }
}
```

Stop on any mismatch. Never disable antivirus, Gatekeeper or a custody/Core
check to make an unverified binary launch. Inspect original WAM coin branding.

## Platform launch and privileged setup boundary

**macOS ARM64:** the DMG/app ZIP contains `WAM Privacy Wallet REGTEST.app`.
Open the verified DMG and launch the app via Finder, or extract `.app.zip` with
macOS Archive Utility/ditto preserving bundle links. The outer app is ad-hoc
signed and not Apple Developer ID notarized. Original signed Core stays intact.
If macOS requires operator approval, review the verified candidate and use the
normal OS approval flow; do not strip security attributes or change OS policy.

**Windows x64:** extract the inner `WAM-Privacy-Wallet-REGTEST-windows-x64-<SHA>.zip`
and launch `WAM-Privacy-Wallet-REGTEST/WAM-Privacy-Wallet-REGTEST.exe`.
The application is not Authenticode-signed. Stop and report unexplained OS/AV
refusal; do not disable security protections. Use an ordinary test account on
NTFS. Native Credential Manager/owner-DACL/reparse checks remain mandatory.

**Linux desktop:** extract the inner `wam-regtest-desktop-linux-x86_64-<SHA>.tar.gz`.
Qualified OS is Ubuntu24.04 x86_64 with exact manifest-pinned Core system
libraries, binutils, libevent/libsqlite3, xcb/EGL and installed fonts. A different
library closure/distribution must refuse; do not substitute a new receipt/hash.
The source-built Core is reviewed developer Core, NOT an official signed release.

The Linux artifact is the operator kit: archive, manifests, genuine native
receipt, this guide and `root-witness-review-only.py`. On the approved Ubuntu24.04
host, an administrator must separately review any missing dependency installation.
The exact CI package set is libevent-dev, libsqlite3-dev, binutils; desktop also
uses libegl1, libxcb-cursor0, libxkbcommon-x11-0, libxcb-icccm4, libxcb-image0,
libxcb-keysyms1, libxcb-render-util0, libxcb-xinerama0, libxcb-xkb1, libxcb-shape0,
libdbus-1-3 and fonts-noto-core. Xvfb/xauth are CI display infrastructure, not a
physical desktop requirement. Never change pinned runtime hashes to fit a host.

Linux needs a separately reviewed/provisioned root witness. The app NEVER runs
sudo, installs or starts it. **STOP before privileged setup** until the actual
host administrator approves the exact helper/source checksum, non-root wallet
UID and a fresh state location. These are operator instructions, not operations
performed automatically by the application or this engineering session:

```sh
# ADMIN ONLY, after explicit approval; substitute the actual ordinary UID.
sudo install -d -o root -g root -m 755 /usr/local/libexec
sudo install -o root -g root -m 755 root-witness-review-only.py /usr/local/libexec/wam-regtest-witness.py
sudo /usr/bin/python3 -I /usr/local/libexec/wam-regtest-witness.py \
  --state-root /var/lib/wam-regtest-witness-exp --uid 1000 --provision
```

Keep the service alive in that administrator terminal. Restart the SAME root
state/UID without `--provision`. Preserve its independent records for recovery;
never reset/delete/re-provision to accept an old backup. Root/whole-store rollback
and power-loss are not qualified. Use a path with the documented protected
root-owned ancestors, no ACL/symlink substitution. Client and server verify UIDs.

As the ordinary UID, launch `./wam-regtest-desktop/wam-regtest-desktop`.
Enter independent manifest SHA
`e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806`
and `/var/lib/wam-regtest-witness-exp/anchor.sock`; approve disposable REGTEST.
No authorized physical Linux host is available in the engineering session:
**PHYSICAL_LINUX_ACCEPTANCE=PENDING_OPERATOR**. Ubuntu CI is genuine native E2E,
not physical desktop acceptance.

## Genuine GUI wallet exercise — all three desktop platforms

1. Choose Create fresh test keys. Set a NEW test-only passphrase of12+ characters.
   No personal wallet import. Initial startup mines real isolated blocks and
   creates genuine on-chain BIP352 fixture payments; displayed balance/history
   come from Core+WSP SQLite, not invented activity.
2. Verify Overview, Receive, History, Send, Security and Settings. Receive shows
   a genuine `wamrtsp1...` silent-payment code/QR from fresh disposable keys.
   Copy it. In Settings verify Core identity and local-network diagnostics:
   chain=regtest, peers=0, no remote/proxy/fallback. Background sync is30s.
3. To test an actual payment without another personal wallet, the following is
   the globally-known PUBLIC REGTEST fixture recipient (scan scalar1/spend pub2)
   already used by pinned WSP/Core acceptance. It is not secret and must NEVER
   receive actual money:

   ```text
   wamrtsp1qqfumuen7l8wthtz45p3ftn58pvrs9xlumvkuu2xet8egzkcklqtesqkxq3legs0d04knq32qd62uqlxct3mcujuvau7202avpxu4cuy7u5nktq4e
   ```

   Prepare0.00100000 WAM with fee0.00010000 WAM. Inspect FULL recipient, amount,
   fee, change and input count. Cancel the native Sign dialog first: no signature
   or submission. Prepare/review remains. Sign needs a separate explicit approval;
   Signed state retains irreversible reservations and unsigned Cancel is disabled.
4. Cancel the Broadcast dialog once: no network submission. Approve Broadcast
   separately. Record public txid; click Mine one REGTEST block, then Sync.
   Verify confirmed change and a new confirmed history row. Expected sender
   balance is previous balance minus100000 atoms minus10000 fee atoms.
   The public recipient is on the SAME test node; a separate app's fresh chain
   cannot observe it. CI independently verifies actual recipient100000 atoms.
   No scripted/generic transaction log is a substitute for these live results.
5. Save latest encrypted backup into a NEW private folder. Lock: confirmed
   balances/history/payment details clear; signing/broadcast disable. Attempt
   wrong-password Unlock and verify refusal with no plaintext/verified balance.
   Unlock correctly and rescan. Never expose passphrase/keys in feedback/logs.
6. Save a NEW latest backup after each anchored state change. Lock and Recover
   the latest backup. It must preserve test accounts and irreversible locks and
   obtain current state from real Core. Stale/modified/wrong-platform backups
   intentionally refuse; do not remove authenticated platform fields.
7. Close normally. Confirm the owned test daemon exits, owned temporary chain
   and plaintext runtime disappear, and unrelated user data were untouched.
   Reopen, choose Recover latest backup on this computer (same native anchor;
   same Linux witness), re-enter test passphrase and rescan a NEW isolated chain.
   Original accounts/irreversible reservations remain; a fresh receive epoch
   supports new test funding. Recovery is capped at16 epochs. It is not cross-OS
   portability, cross-Mac recovery or proof an old chain's funds were recovered.
8. Review native Light/Dark/Auto, window resize/scrolling, fonts, dialogs and
   keyboard focus/Cancel default. macOS automated Cocoa event tests differ from
   manually changing OS settings. Windows CI tests125%/150%; owner should test
   Windows10/11 hardware. Linux owner should test actual GNOME/KDE OS events.
   If native Auto events are unavailable, record PENDING/unsupported, not PASS.

Do not retry an uncertain broadcast automatically or release old signed locks.
A lost anchor or ambiguous publication is a refusal/diagnostic state, not an
instruction to reset custody. Unlocked SQLite is plaintext in a private runtime;
memory clearing is best effort. There is no production-custody claim.

## Linux headless — no Qt/display/keyring required

Extract the independent headless tarball. With the SAME approved Core libraries
and separately approved root witness, use a private interactive terminal:

```sh
./wam-regtest-headless/wam-regtest-headless \
  --manifest-sha256 e77a5745263b8fdbcffdb282af22800b6f7805f033c09f00738e997150a0f806 \
  --anchor-socket /var/lib/wam-regtest-witness-exp/anchor.sock \
  --confirm-experimental-developer-regtest
```

Enter a test-only passphrase via getpass; no secret argv/env or non-TTY fallback.
Commands: receive, balance, history, sync; `prepare RECIPIENT 0.00100000 0.00010000`;
`sign` requires typed `SIGN <exact commitment>`, then `broadcast` separately
requires `BROADCAST <same commitment>`; mine; backup NEW_PRIVATE_FOLDER; lock;
unlock; recover BACKUP_FOLDER; quit. Startup recovery uses
`--recover-backup /absolute/private-folder/wallet-backup.enc`. Bundled Core/WSP
paths cannot be overridden. Missing witness/incorrect pins refuse before funding.

## Owner feedback receipt — fill only what was actually observed

- Candidate ID / FULL source SHA / artifact SHA256:
- OS/version/architecture; physical device or runner/VM; Qt platform/DPI:
- Operator/date; Linux kernel/distro/desktop/session and witness approval:
- [ ] Download/checksum/Core identity verified
- [ ] Startup reliability / real Core / zero peers / Receive / Balance / History
- [ ] Navigation / fonts / resize / scrolling / appearance / native dialogs
- [ ] Prepare / exact review / Cancel / Sign / separate Broadcast / confirmation
- [ ] Startup/sync performance and responsive worker shutdown
- [ ] Backup destination/privacy / Lock / correct Unlock / incorrect refusal
- [ ] Latest same-host backup recovery / fresh chain / safe normal shutdown
- [ ] Error messages / REGTEST warnings / irreversible/uncertain-state clarity
- [ ] Linux desktop usability / Linux headless usability / physical OS Auto
- Actual PASS/FAIL/PENDING and reproducible defect steps:

Do not tick unseen checks. Share only redacted public receipts/screenshots;
never seed/private key, passphrase, RPC credentials, wallet database or backup.
DEV WAM review is a later collaborative technical step; nothing is sent automatically.
