# Linux Fusion Qt candidate

Use `wam-regtest linux-wallet` with the exact approved Core directory, independent
manifest SHA256, administratively provisioned root-witness endpoint and pinned
WSP source described in LINUX_HEADLESS.md, then add `--gui`.
No root service is installed by this application. Missing trust inputs refuse
before wallet creation or funding. The UI offers create/recover using the same
WalletSession and authenticated Linux-v3 backup profile.

The existing Fusion Overview, Receive, History, Send, Security and Settings
screens are reused. PaymentApproval still defaults to Cancel, with separate
Sign and Broadcast approvals over the exact prepared intent. Root lease,
checkpoint/reservations and native WSP signer are unchanged. Background scanning
uses the existing Qt worker every 30 seconds; balance/history clear on failures
or lock. Linux uses installed Noto/DejaVu/Liberation fonts, the owner's original
WAM coin image, and honest developer-Core provenance text.

Ubuntu x86_64 CI uses Qt xcb under Xvfb, genuine qualified developer Core and an
independent root-owned witness process. It drives native workers, rejects native
Cancel before signing and broadcast, confirms 100000 recipient atoms and sender
change, backs up, locks, denies a wrong password, recovers and reopens the same
original keys/reservations in another native window on a fresh Core chain.
The separate headless job installs no Qt and retains reorg1/12/100, stale writer,
lease-before-sign and uncertain-broadcast gates. Neither gate substitutes RPC,
blockchain or cryptography.

Screenshots include all six screens, approval dialogs, explicit light/dark/Auto
and several sizes. Xvfb appearance and captures are runner evidence, not human
Linux desktop signoff. Auto records whether the platform exposed Light/Dark
color-scheme events; Unknown is not claimed as OS appearance acceptance. Native
GNOME/KDE desktop launch/close, OS theme integration and human visual review
remain operator work. Frozen executables and portable migration remain separate
milestones. No Final, production, mainnet or real-funds qualification.
