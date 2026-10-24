# Linux operator acceptance — still required

Native runner E2E is complete for the exact code/artifacts in
[qualification](LINUX_QUALIFICATION.md). This procedure is manual acceptance on
a disposable Ubuntu24.04 x86_64 desktop, not a previously executed PASS. Never
use a personal wallet, key, mainnet node or actual funds. Linux distribution
relocation, desktop appearance and privileged provisioning require an operator.

1. Download the exact artifact, verify its published tarball SHA256 and all
   `SHA256SUMS.txt` entries, then inspect `LINUX_PACKAGE_MANIFEST.json` and its
   source/checkout identities. Extract into an owned directory with no writable
   or symlink ancestors. Preserve executable bits. Do not repair an unknown
   package or disable Core/system-library checks to make it start.
2. The administrator must review `root-witness-review-only.py` against the
   corresponding source commit and published checksum. The wallet must run as
   an ordinary user; the witness is a separate root process. An independently
   provisioned witness is a prerequisite, never an app-installed component.
   The following are illustrative administrator commands, **not commands the
   wallet executes**. Replace the UID with the intended non-root wallet UID,
   choose a new unused state root, and keep its records for recovery:

   ```sh
   sudo install -d -o root -g root -m 755 /usr/local/libexec
   sudo install -o root -g root -m 755 root-witness-review-only.py /usr/local/libexec/wam-regtest-witness.py
   sudo /usr/bin/python3 -I /usr/local/libexec/wam-regtest-witness.py \
     --state-root /var/lib/wam-regtest-witness-exp --uid 1000 --provision
   ```

   Keep that foreground service alive in the administrator terminal. Restart
   the SAME identity/state with the same command **without `--provision`**.
   There is no automatic re-provision/reset after loss, corruption or replacement.
   Do not delete the state root as a troubleshooting shortcut. The directory,
   script and all ancestors must meet the documented root-owned/no-ACL/no-follow
   policy; failure is a refusal, not permission to weaken the policy.
3. As the ordinary wallet UID, start `wam-regtest-desktop` from its extracted
   onedir folder with no arguments. Enter the independently approved Core
   manifest SHA256 from qualification and the absolute socket path
   `/var/lib/wam-regtest-witness-exp/anchor.sock`; explicitly approve the
   disposable isolated chain. No request to install root code should appear.
4. Create fresh test keys with a test-only passphrase. Check original WAM icon,
   all six screens, receive code/QR, actual confirmed balance/history and Core
   identity. In Settings verify local network privacy/zero peers and no remote,
   proxy or clearnet fallback. No field should display a cached verified balance
   after a failed live scan.
5. Prepare a payment to a separate disposable REGTEST receive code. Compare the
   full recipient, exact WAM amount, fee, change and input count. Cancel the
   native approval once: it must not sign or submit. Approve Sign separately;
   check Signed state and that unsigned cancellation is unavailable. Cancel
   Broadcast once, then approve it separately. Mine one test block and verify
   sender change and confirmed history. Recipient credit needs a recipient
   scanner attached to the SAME isolated node, as in native acceptance; another
   application's fresh independent chain cannot observe this payment. No automatic broadcast retry is acceptable.
6. Save the latest encrypted backup into a new private folder. Lock: balance,
   history and payment details must clear. Wrong passphrase must refuse and
   retain locks. Unlock/recover using the correct test passphrase. After any
   new anchored state, take a new backup; older generations intentionally fail.
7. Close normally and confirm the owned daemon exits and disposable chain/runtime
   are removed. Reopen with the latest backup and SAME live root witness. Confirm
   original accounts and irreversible reservations, fresh receive epoch and a
   freshly scanned real chain. This is same-host recovery, not portable migration.
8. Test desktop launching/closing and GNOME/KDE OS Light/Dark/Auto settings.
   Explicit manual Light/Dark is distinct from OS appearance events. If Qt does
   not expose native events, record Auto as unqualified/unsupported; do not
   force a PASS with synthetic hints. Review compact/large layouts, scrolling,
   keyboard focus, default Cancel and readable full approval details.
9. Record OS/version, artifact SHA, source and checkout SHAs, Qt platform/DPI,
   manual results and unresolved defects in an operator receipt. Abrupt fatal
   app/host loss, whole-witness rollback and power-loss durability remain separate
   unqualified scenarios; normal shutdown and CI process/lease tests do not prove
   them. Any further crash test must affect only identified owned test processes
   and preserve backups/witness records.

The headless tarball needs no Qt/display/keyring; use its executable from a
private interactive terminal with explicit manifest/socket/REGTEST consent,
then `--recover-backup` for latest same-host startup recovery. See
[headless guide](LINUX_HEADLESS.md). Missing root witness or incorrect approved
library closure must fail before funding, signing or broadcast.
