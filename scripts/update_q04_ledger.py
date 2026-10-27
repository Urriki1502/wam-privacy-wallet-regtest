"""Q04-only evidence reconciliation. Abort without promotion on missing proof."""
import argparse
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import re
import subprocess

spec=importlib.util.spec_from_file_location('q03_provenance',Path(__file__).with_name('update_q03_ledger.py'))
proof=importlib.util.module_from_spec(spec);spec.loader.exec_module(proof)


def require(value):
    if not value:raise ValueError('Q04_EVIDENCE_UNVERIFIED')


def check_runtime(receipt,platform,frozen,gui):
    require(receipt['status']=='Q04_MINER_COEXISTENCE_PASS' and receipt['synthetic_rpc'] is False)
    require(receipt['platform']==platform and receipt['execution']==('FROZEN' if frozen else 'SOURCE_NATIVE'))
    pins={k.removesuffix('.exe'):v for k,v in proof.PINS[platform].items()}
    require(receipt['core_sha256']==pins and receipt['wsp_source_commit']==proof.WSP)
    require(receipt['write_denied'] is True and receipt['port_change_detected'] is True)
    heights=receipt['miner_heights']
    require(len(heights)==5 and all(type(h) is int for h in heights) and heights[-1]>heights[0])
    require(receipt['reconnect_height']>=receipt['height_before'])
    busy=receipt['genuine_busy']
    require(busy['status']=='Q04_GENUINE_BUSY_PATH_PASS' and busy['synthetic_busy'] is False)
    require(busy['attachment_http_503_count']==4 and busy['read_attempts']==4)
    require(busy['coalesced_read_calls']==0 and busy['write_boundary_attempts']==1 and busy['write_retried'] is False)
    require(busy['fresh_socket_process_attestation_per_attempt'] is True)
    require(busy['recovered_height']>=receipt['height_before'])
    delays=busy['retry_intervals_seconds']
    require(len(delays)==3 and all(type(d) in (int,float) and d>=.1*2**i*.9 for i,d in enumerate(delays)))
    require(busy['gui_coalescing']=='PASS' if gui else busy['gui_coalescing'] in ('PASS','NOT_APPLICABLE_NO_QT'))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('mac-run','windows-run','linux-run','windows-core-run','wsp-run'):ap.add_argument('--'+name,type=int,required=True)
    ap.add_argument('--artifacts',type=Path,required=True)
    ap.add_argument('--ledger',type=Path,default=Path('tests/acceptance/issue45.json'))
    ap.add_argument('--runtime-source',required=True)
    ap.add_argument('--check-only',action='store_true')
    args=ap.parse_args();native={};frozen={};head=None;run_records=[]
    require(re.fullmatch('[0-9a-f]{40}',args.runtime_source) is not None)
    jobspec={
        'macos-arm64':('Q04 macOS ARM64 solo-miner coexistence','Signed real Core + bundled WSP .app/.dmg macOS ARM64 E2E','q04-miner-coexistence-evidence-macos-arm64-'),
        'windows-x64':('Q04 Windows x64 solo-miner coexistence','win64-native-credential-cas','q04-miner-coexistence-evidence-windows-x64-'),
        'linux-x86_64':('q04-miner-coexistence','frozen-wallet (desktop)','q04-miner-coexistence-evidence-')}
    runids={'macos-arm64':args.mac_run,'windows-x64':args.windows_run,'linux-x86_64':args.linux_run}
    for rid in (args.mac_run,args.windows_run,args.linux_run,args.windows_core_run,args.wsp_run):
        run=proof.gh(f'actions/runs/{rid}')
        require(run['conclusion']=='success');head=head or run['head_sha'];require(run['head_sha']==head)
        require(not proof.git('diff','--name-only',args.runtime_source,head,'--','src/wam_regtest'))
        run_records.append({'run_id':rid,'source_sha':head,'conclusion':'success'})
    for platform,rid in runids.items():
        meta=proof.gh(f'actions/runs/{rid}/artifacts?per_page=100')['artifacts']
        jobs=proof.gh(f'actions/runs/{rid}/jobs?per_page=100')['jobs']
        def job(name,source_jobs=None):
            matches=[j for j in (source_jobs or jobs) if j['name']==name]
            require(len(matches)==1 and matches[0]['conclusion']=='success');return matches[0]
        def record(a,j,checkout):
            require(a['workflow_run']['head_sha']==head)
            logs=proof.gh(f"actions/jobs/{j['id']}/logs",raw=True)
            require(checkout in logs)
            return {'source_sha':head,'checkout_sha':checkout,'qualified_runtime_source_sha':args.runtime_source,'timestamp_utc':j['completed_at'],
                'platform':platform,'reference':j['html_url'],'workflow_run_id':j['run_id'],'job_id':j['id'],
                'artifact_id':a['id'],'artifact_sha256':a['digest'].removeprefix('sha256:'),
                'core_version':'v0.1.11','core_sha256':proof.PINS[platform],
                'core_trust':'reviewed-developer-source-build' if platform=='linux-x86_64' else 'official-signed-v0.1.11',
                'wsp_source_commit':proof.WSP,'synthetic_rpc':False}
        frozen[platform]=[]
        variants=[('WAM-Fusion-REGTEST-RC1-'+('linux-x86_64-desktop' if platform=='linux-x86_64' else platform)+'-',jobspec[platform][1],True)]
        if platform=='linux-x86_64':variants.append(('WAM-Fusion-REGTEST-RC1-linux-x86_64-headless-','frozen-wallet (headless)',False))
        for prefix,jname,gui in variants:
            a=proof.find_artifact(meta,prefix);j=job(jname)
            with proof.archive(args.artifacts/f"{a['id']}.zip",a)[0] as z:
                manifest,extra=proof.package_record(z,platform,head)
                if platform=='linux-x86_64':require(manifest['platform']==('linux-x86_64-desktop' if gui else 'linux-x86_64-headless'))
                names=[n for n in z.namelist() if n.endswith('/q04-frozen-evidence.json') or n=='q04-frozen-evidence.json']
                require(len(names)==1);name=names[0];receipt,rhash=proof.read_json(z,name)
                check_runtime(receipt,platform,True,gui)
                relative=name.removeprefix(extra['receipt_path'].removesuffix('RELEASE_CANDIDATE_MANIFEST.json'))
                require(manifest['files_sha256'][relative]==rhash)
                e=record(a,j,manifest['checkout_sha']);e.update(extra,q04_receipt_path=name,q04_receipt_sha256=rhash,
                    package_platform=manifest['platform'],genuine_busy=receipt['genuine_busy'])
                frozen[platform].append(e)
        if platform=='windows-x64':
            nrid=args.windows_core_run
            nmeta=proof.gh(f'actions/runs/{nrid}/artifacts?per_page=100')['artifacts']
            njobs=proof.gh(f'actions/runs/{nrid}/jobs?per_page=100')['jobs']
            j=job(jobspec[platform][0],njobs)
        else:nmeta=meta;j=job(jobspec[platform][0])
        a=proof.find_artifact(nmeta,jobspec[platform][2])
        with proof.archive(args.artifacts/f"{a['id']}.zip",a)[0] as z:
            receipt,rhash=proof.read_json(z,'q04-evidence.json');check_runtime(receipt,platform,False,False)
            e=record(a,j,frozen[platform][0]['checkout_sha']);e.update(q04_receipt_path='q04-evidence.json',
                q04_receipt_sha256=rhash,genuine_busy=receipt['genuine_busy'])
            native[platform]=e
    data=json.loads(args.ledger.read_text());before=deepcopy(data);q=data['questions'][3]
    require(data['active_q']=='Q04' and q['candidate_pr']==133 and q['accepted'] is False and len(q['cases'])==24)
    for case in q['cases']:
        if case['layer'] in ('PHYSICAL','DEV_REVIEWED'):
            require(case['status']=='BLOCKED' and not case['acceptance_evidence']);continue
        if case['layer']=='FROZEN':evidence=frozen[case['platform']]
        elif case['platform']!='shared':evidence=[native[case['platform']]]
        else:evidence=list(native.values())
        if case['id']=='Q04-BUSY-COALESCE':
            evidence=[e for values in frozen.values() for e in values if e['genuine_busy']['gui_coalescing']=='PASS']
            require({e['platform'] for e in evidence}==set(native))
        case.update(status='PASS',acceptance_evidence=deepcopy(evidence),blocker=None,
            requirement_refs=[proof.URL+'/issues/45'])
        for e in case['acceptance_evidence']:e['case_scope']=case['id']
    q.update(candidate_head_sha=head,qualified_runtime_source_sha=args.runtime_source,base_main_sha='fe6a9e93903800743a1b0e5f87658f71524d57e5',
        status='BLOCKED',accepted=False,engineering_status='TECHNICAL_COMPLETE_PENDING_EXTERNAL_AND_OWNER_INTEGRATION',
        owner_merge_authorization=None,post_merge_main_sha=None)
    q['evidence_qualification']={'workflow_source_sha':head,'qualified_runtime_source_sha':args.runtime_source,'runs':run_records,
        'policy':'Actual artifact source/checkout identities are immutable; later governance-only descendants require independent check-only verification.'}
    q['integration_blocker']={'actor':'OWNER_THEN_CI_OPERATOR','missing_evidence':'Separate Q04 merge authorization and exact-main postmerge qualification; no Q05 handoff yet.',
        'next_action':'Owner reviews Draft PR133 and authorizes integration separately, then qualify exact merged main; Q05 remains queued.'}
    for g in range(6):q['gates'][f'G{g}']['status']='PASS'
    for g in (6,7):q['gates'][f'G{g}']['status']='BLOCKED'
    require(data['questions'][:3]==before['questions'][:3] and data['questions'][4:]==before['questions'][4:])
    from wam_regtest.q_gate import validate
    result=validate(data);require(result['case_results']['PASS']==22 and result['case_results']['BLOCKED']==2)
    if not args.check_only:args.ledger.write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,OSError,subprocess.CalledProcessError,proof.zipfile.BadZipFile):
        raise SystemExit('Q04_EVIDENCE_UNVERIFIED: no ledger promotion written')
