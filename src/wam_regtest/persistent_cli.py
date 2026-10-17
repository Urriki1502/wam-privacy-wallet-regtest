"""Issue #45 T05: operator-only REGTEST candidate profile inspection.

Invoke: python -m wam_regtest.persistent_cli --profile-root <new isolated path>
  --genesis-sha256 <independently measured> --node-sha256 <pinned WAM v0.1.11>
  --cli-sha256 <pinned matching CLI> --acknowledge-regtest-only

This is NOT a launcher, recovery tool, attacher, installer or signing path.
No wallet/node data or private paths are emitted in success/denial receipts.
"""
import argparse
import json
from pathlib import Path
import re
import sys

from .persistent_profile import inspect_profile, PersistentProfileError
from .persistent_lease import hold_profile


def main(argv=None):
    ap=argparse.ArgumentParser(description='Public identity-only REGTEST profile preflight')
    ap.add_argument('--profile-root',required=True,type=Path)
    ap.add_argument('--genesis-sha256',required=True)
    ap.add_argument('--node-sha256',required=True)
    ap.add_argument('--cli-sha256',required=True)
    ap.add_argument('--acknowledge-regtest-only',action='store_true')
    ap.add_argument('--require-single-writer',action='store_true')
    args=ap.parse_args(argv)
    if args.acknowledge_regtest_only is not True:
        print('PROFILE_PREFLIGHT_CONSENT_REQUIRED',file=sys.stderr)
        return 2
    pins={'expected_genesis':args.genesis_sha256,
          'expected_node_sha256':args.node_sha256,
          'expected_cli_sha256':args.cli_sha256}
    try:
        if args.require_single_writer:
            with hold_profile(args.profile_root,**pins) as receipt:
                if not receipt['pins_matched']:
                    raise PersistentProfileError('PROFILE_TRUST_PINS_MISMATCH')
        else:
            receipt=inspect_profile(args.profile_root,**pins)
        assert receipt['persistent_runtime_qualified'] is False
        assert receipt['attach_authorized'] is False
        assert receipt['signing_authorized'] is False
        print(json.dumps({
            'schema':'wam-t05-operator-preflight/v1',
            'status':'PUBLIC_PROFILE_PREFLIGHT_PASS',
            'chain':'regtest','core_version':'v0.1.11',
            'independent_pins_matched':True,
            'cooperative_lease_observed':bool(args.require_single_writer),
            'persistent_core_e2e_pass':False,
            'runtime_authorized':False,'mainnet_allowed':False,
        },sort_keys=True))
        return 0
    except PersistentProfileError as error:
        text=str(error)
        reason=text if re.fullmatch('PROFILE_[A-Z0-9_]{3,100}',text) else 'PROFILE_PREFLIGHT_UNVERIFIED'
        print(reason,file=sys.stderr)
        return 2
    except Exception:
        # Even unexpected OS exceptions cannot leak filenames or credentials.
        print('PROFILE_PREFLIGHT_UNVERIFIED',file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
