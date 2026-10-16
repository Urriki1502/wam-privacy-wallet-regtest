# Pinned source contract, not node E2E

`v0.1.11/wam/` contains unchanged upstream MIT-licensed public files from
wamcoin-core-dev/wam-coin tagv0.1.11. `check_wam_subsidy_source.py` verifies exact
Git blob SHA before compilation. The amount/parameter headers under `shims/`
provide only int64 CAmount and one interval field: they are not Core consensus
validation, a chain, cryptography or a mainnet node. No upstream source is edited.

The native64 driver calls the actual pinned functions with interval200000 for
the independently reviewed source table and interval150 for unchanged REGTEST.
Genesis is separate; treasury cutoff400000 is tested independently of subsidy;
all fees are miner-owned. This source evidence complements genuine disposable
Core output/UTXO/maturity tests. It cannot mark high-height binary, frozen UI,
physical device, v0.1.12 or mainnet qualification PASS. No updater is implemented.

Run `python scripts/check_wam_subsidy_source.py --output NEW_RECEIPT.json`.
A missing compiler fails explicitly; it is not a silently skipped PASS.
