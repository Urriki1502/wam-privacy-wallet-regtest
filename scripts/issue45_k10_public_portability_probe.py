"""K-10 public disposable WSP portability probe for 3-OS source/CI runs.

Run only with --disposable-public-fixture. This command uses a widely
known 256-bit PUBLIC test entropy constant: NOT a wallet/mnemonic for funds.
No caller seed, files, Core RPC, OS native credential, encrypted wallet,
user wallet.dat, miner data, signing or broadcast are accepted.

The receipt is NOT signed CI provenance or physical acceptance. A designated reviewer must separately record the immutable HEAD and native runner proof.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

from mnemonic import Mnemonic

from wam_regtest.bip39_wallet import Bip39RegtestKeys
from wam_regtest.k10_portability import probe_original_bip39_identity


def public_probe(*, authorized=False):
    if authorized is not True:
        raise ValueError("K10_DISPOSABLE_FIXTURE_CONSENT_REQUIRED")
    source=Path(importlib.util.find_spec("wam_sp").origin).resolve().parents[2]
    phrase=Mnemonic("english").to_mnemonic(bytes([0x35])*32)
    passphrase="PUBLIC_DISPOSABLE_ONLY_K10"
    with Bip39RegtestKeys(
            phrase,source=source,passphrase=passphrase,
            authorized_disposable=True) as keys:
        trusted=keys.public_metadata(0)
    result=probe_original_bip39_identity(
        phrase,passphrase=passphrase,account=0,
        prior_trusted_public=trusted,wsp_source=source,authorized=True)
    # Only a hash of the PUBLIC receive identity; never output a seed,
    # phrase, private key, source path, native anchor or wallet file name.
    return result


def main():
    parser=argparse.ArgumentParser(
        description="K10 known-PUBLIC-fixture WSP contract probe ONLY")
    parser.add_argument("--disposable-public-fixture",action="store_true",
                        help="Explicitly approve known public REGTEST fixture")
    args=parser.parse_args()
    result=public_probe(authorized=args.disposable_public_fixture)
    print(json.dumps(result,sort_keys=True,separators=(",",":"),
                     ensure_ascii=True))


if __name__=="__main__":
    main()
