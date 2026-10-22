"""Record the unchanged historical SIGKILL diagnostic, never qualify recovery.

The original probe and raw FAIL remain unchanged. Only an authenticated complete
PASS/continuity-loss observation can be RECORDED; probe ERROR, bad provenance,
wrong pins, missing cleanup or damaged block bytes still fail this CI job.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import re
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from wam_regtest.a06_acceptance import core_pair
from wam_regtest.r04_package_audit import _unique_pairs


def record(raw, exit_code, *, source, checkout):
    if any(type(s) is not str or re.fullmatch('[0-9a-f]{40}',s) is None for s in (source,checkout)):
        raise ValueError('A06_HISTORICAL_SOURCE_DENIED')
    p = raw['test_source_provenance']
    if (p['source_head_sha'] != source or p['checkout_sha'] != checkout
            or p['tracked_source_matches_head'] is not True
            or p['source_unchanged_across_build'] is not True
            or raw['schema'] != 'wam-a06-native-fresh-core-crash/v1'
            or raw['network'] != 'regtest' or raw['core_version'] != 'v0.1.11'
            or raw['wsp_source_commit'] != 'ac55f13423620252bdbf848c7e8a280c3b84721e'
            or (raw['wamd_sha256'],raw['wam_cli_sha256']) != core_pair(raw['platform'])
            or raw['status'] not in ('PASS','FAIL')
            or type(exit_code) is not int or exit_code != (0 if raw['status']=='PASS' else 1)
            or raw['before_crash']['height'] != 101
            or type(raw['prior_owned_child_exit_code']) is not int or raw['prior_owned_child_exit_code']==0
            or raw['before_crash']['known_tip_header']['rpc_success'] is not True
            or not raw['before_crash']['block_files']
            or raw['same_directory_identity'] is not True
            or any(raw[k] is not True for k in ('cleanup_verified','complete_block_file_bytes_unchanged',
                'protected_config_unchanged','protected_profile_unchanged'))
            or any(raw[k] is not False for k in ('synthetic_rpc','mainnet_allowed',
                'reindex_performed','recovery_mutation_performed','automatic_payment_retry',
                'wallet_keys_used','wallet_anchor_used','clean_stop_before_crash'))
            or raw['before_crash']['block_files'] != raw['after_exit_block_files']
            or raw['before_crash']['block_files'] != raw['after_restart_block_files']):
        raise ValueError('A06_HISTORICAL_OBSERVATION_UNVERIFIED')
    if raw['status']=='FAIL':
        if (raw['fresh_tip_preserved'] is not False
                or not raw['restart_observations']
                or any(type(o['height']) is not int or not 0<=o['height']<101
                       or o['tip_matches'] is not False for o in raw['restart_observations'])
                or raw['original_header_after_restart']['rpc_error_code_minus5'] is not True):
            raise ValueError('A06_HISTORICAL_FAILURE_UNCLASSIFIED')
    elif raw['fresh_tip_preserved'] is not True:
        raise ValueError('A06_HISTORICAL_PASS_UNVERIFIED')
    return {'schema':'wam-a06-historical-observation/v1','status':'RECORDED',
        'original_probe_status':raw['status'],'source_head_sha':source,'checkout_sha':checkout,
        'platform':raw['platform'],'recovery_qualified':False,'release_authorized':False,
        'historical_raw_receipt_unchanged':True}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--receipt',type=Path,required=True)
    ap.add_argument('--probe-exit',type=int,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    try:
        raw=args.receipt.read_bytes()
        if not 1<=len(raw)<=8*1024*1024:raise ValueError
        result=record(json.loads(raw,object_pairs_hook=_unique_pairs),args.probe_exit,source=os.environ['WAM_SOURCE_HEAD'],
            checkout=os.environ['WAM_CHECKOUT_SHA'])
    except (ValueError,KeyError,TypeError,OSError):
        result={'status':'ERROR','error_code':'A06_HISTORICAL_OBSERVATION_UNVERIFIED'}
    with args.output.open('x') as out:json.dump(result,out,sort_keys=True,indent=2);out.write('\n')
    print('A06_HISTORICAL_'+result['status'])
    return 0 if result['status']=='RECORDED' else 1


if __name__=='__main__':raise SystemExit(main())
