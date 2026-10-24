"""Fail-closed CI aggregation; never wallet authority or release approval."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import zipfile
import tarfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from wam_regtest.a06_artifact_gate import assess_artifacts
from wam_regtest.q05_artifact_gate import assess_gui_artifacts
from wam_regtest.q17_layout import assess_artifacts as assess_q17_layout


def assess(needs, required, *, conditional_core_build=False):
    if (type(needs) is not dict or type(required) is not list or not required
            or any(type(name) is not str for name in required)
            or len(set(required)) != len(required)
            or 'a06-core-crash' not in required):
        raise ValueError('CI_GATE_INPUT_DENIED')
    names = list(required)
    reused = False
    if conditional_core_build:
        flag = needs.get('native-contracts', {}).get('outputs', {}).get('core_changed')
        result = needs.get('developer-core', {}).get('result')
        if flag == 'false' and result == 'skipped':
            # Optional rebuild was not requested. Required native/frozen jobs
            # still authenticate the immutable reviewed developer Core bytes.
            reused = True
        else:
            names.append('developer-core')
            if flag not in ('true', 'false'):
                raise ValueError('CI_CORE_BUILD_SCOPE_UNKNOWN')
    statuses = {name: needs.get(name, {}).get('result', 'missing') for name in names}
    if any(type(value) is not str for value in statuses.values()):
        raise ValueError('CI_GATE_RESULT_SHAPE_DENIED')
    failed = [name for name, value in statuses.items() if value != 'success']
    return {'status': 'FAIL' if failed else 'PASS',
            'required_job_results': statuses, 'nonpassing_required_jobs': failed,
            'reviewed_immutable_core_reused_without_optional_rebuild': reused}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--platform', required=True,
                        choices=('macos-arm64', 'windows-x64', 'linux-x86_64'))
    parser.add_argument('--required-jobs', required=True)
    parser.add_argument('--conditional-core-build', action='store_true')
    parser.add_argument('--evidence-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    receipt = {'schema': 'wam-platform-ci-release-gate/v2', 'platform': args.platform,
        'scope': 'platform CI only; overall REGTEST acceptance requires every platform plus independent gates',
        'automatic_release_authorized': False, 'mainnet_allowed': False,
        'physical_accepted': False, 'dev_reviewed': False}
    try:
        raw = os.environ['JOB_RESULTS']
        if len(raw) > 65536:
            raise ValueError('CI_GATE_INPUT_SIZE_DENIED')
        head = os.environ['WAM_SOURCE_HEAD']
        if not re.fullmatch('[0-9a-f]{40}', head):
            raise ValueError('CI_GATE_SOURCE_IDENTITY_DENIED')
        checkout=os.environ['WAM_CHECKOUT_SHA']
        if not re.fullmatch('[0-9a-f]{40}',checkout):
            raise ValueError('CI_GATE_CHECKOUT_IDENTITY_DENIED')
        required=json.loads(args.required_jobs)
        expected={
            'macos-arm64':{'real-wamd','native-app-dmg','a06-core-crash'},
            'windows-x64':{'win64-native-credential-cas','a06-core-crash'},
            'linux-x86_64':{'native-contracts','headless-wallet','native-qt-wallet','frozen-wallet','a06-core-crash'},
        }[args.platform]
        if (type(required) is not list or set(required)!=expected
                or args.conditional_core_build != (args.platform=='linux-x86_64')):
            raise ValueError('CI_PLATFORM_REQUIRED_ROLES_DENIED')
        receipt.update(source_head_sha=head,checkout_sha=checkout, **assess(json.loads(raw),
            required, conditional_core_build=args.conditional_core_build))
        receipt['a06_recovery_acceptance']=assess_artifacts(args.evidence_root,args.platform,head,checkout)
        receipt['historical_no_reindex_sigkill_is_release_requirement']=False
        receipt['managed_gui_lifecycle_acceptance']=assess_gui_artifacts(args.evidence_root,args.platform,head,checkout)
        receipt['q17_geometry_acceptance']=assess_q17_layout(args.evidence_root,args.platform,head,checkout)
        if receipt['managed_gui_lifecycle_acceptance']['status'] != 'PASS':
            receipt['status']='FAIL'
    except (ValueError, KeyError, TypeError, AttributeError, OSError, zipfile.BadZipFile, tarfile.TarError):
        receipt.update(status='FAIL', error_code='CI_GATE_INPUT_OR_SOURCE_UNVERIFIED')
    # Never rewrite an earlier result or infer PASS from a missing/skipped job.
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, sort_keys=True, indent=2)
        stream.write('\n')
    print('PLATFORM_CI_RELEASE_GATE_'+receipt['status'])
    return 0 if receipt['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
