"""Reconcile Q03 only from live successful Actions metadata and verified ZIP bytes.

No guessed hashes, source SHA substitution, OS trust promotion, or PASS fallback.
Requires downloaded artifacts; it never executes packaged binaries or Core.
"""
import argparse
from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import zipfile

REPO='Urriki1502/wam-privacy-wallet-regtest'
API='repos/'+REPO+'/'
URL='https://github.com/'+REPO
WSP='ac55f13423620252bdbf848c7e8a280c3b84721e'
PINS={
 'macos-arm64':{'wam-cli':'81a031ebf9b3060b19061b29756d43bcd09b32ad778348b8c3d8321397076e82','wamd':'7298de701e467eb28b4806cbcbe35edb393861b4b97117017fee4c1b194e3068'},
 'windows-x64':{'wam-cli.exe':'538a6d1b918b698ce76a949dda982fdda6776e33ba057efaac59b1af59e59d21','wamd.exe':'31717319535c5b784b2bed3b4d3c9a727f5c062e9534b4d27c59d2ffd04e95a1'},
 'linux-x86_64':{'wam-cli':'ada9dabd56d0859b9d64c0b20a05c33cb039b2573f75088443b45c35d5379652','wamd':'ccc9f0f1d299a1e98a49ff83859aa03e994e83e6ea4b7cd60c327eb1e0e8e4d6'}}
ZERO_COUNTERS=('verified_core_paths','cli_spawn','http_connection_create',
               'http_socket_connect','wallet_session_rpc_client_create')

def require(value):
    if not value:raise ValueError('Q03_EVIDENCE_UNVERIFIED')

def digest(stream):
    h=sha256()
    while chunk:=stream.read(1024*1024):h.update(chunk)
    return h.hexdigest()

def real_digest(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None and value!='0'*64

def gh(path,*,raw=False):
    data=subprocess.check_output(['gh','api',API+path],stderr=subprocess.DEVNULL)
    return data.decode('utf8') if raw else json.loads(data)

def git(*args):
    return subprocess.check_output(['git',*args],text=True).strip()

def check_pins(platform,pair,trust):
    require(pair==PINS[platform])
    require(trust==('reviewed-developer-source-build' if platform=='linux-x86_64'
                    else 'official-signed-v0.1.11'))

def check_reuse(value):
    require(value.get('cycles')==5 and type(value.get('delta')) is dict)
    require(all(type(value['delta'].get(k)) is int and value['delta'][k]==0 for k in ZERO_COUNTERS))
    require(type(value['delta'].get('http_request')) is int and value['delta']['http_request']>=5)

def archive(path,metadata):
    require(not metadata.get('expired',True))
    expected=metadata.get('digest','').removeprefix('sha256:')
    require(real_digest(expected))
    with path.open('rb') as f:require(digest(f)==expected)
    return zipfile.ZipFile(path),expected

def read_json(z,name):
    raw=z.read(name)
    return json.loads(raw),sha256(raw).hexdigest()

def find_artifact(artifacts,prefix):
    found=[a for a in artifacts if a['name'].startswith(prefix)]
    require(len(found)==1)
    return found[0]

def package_record(z,platform,head):
    names=z.namelist()
    found=[n for n in names if n.endswith('RELEASE_CANDIDATE_MANIFEST.json')]
    require(len(found)==1)
    name=found[0];prefix=name.removesuffix('RELEASE_CANDIDATE_MANIFEST.json')
    m,mhash=read_json(z,name)
    require(m['source_head_sha']==head and m['wsp_source_commit']==WSP)
    require(re.fullmatch('[0-9a-f]{40}',m['checkout_sha']) is not None)
    require(m['native_final_executable_e2e_pass'] is True and m['network']=='regtest')
    require(m['production_qualified'] is False and m['dev_wam_reviewed'] is False)
    require(m['physical_or_human_acceptance']=='PENDING_OPERATOR')
    check_pins(platform,m['core_sha256'],m['core_provenance'])
    b,bhash=read_json(z,prefix+'BUILD_SOURCE_RECEIPT.json')
    require(b['source_head_sha']==head and b['checkout_sha']==m['checkout_sha'])
    require(b['tracked_source_matches_head'] is True and b['source_unchanged_across_build'] is True)
    # A PR merge checkout may have a different SHA, but must have the exact
    # source tree advertised by this workflow, not just similar file names.
    if m['checkout_sha']!=head:
        require(gh('git/commits/'+head)['tree']['sha']==
                gh('git/commits/'+m['checkout_sha'])['tree']['sha'])
    payloads={}
    for rel,expected in m['files_sha256'].items():
        require(real_digest(expected))
        if prefix+rel not in names:continue
        with z.open(prefix+rel) as f:require(digest(f)==expected)
        is_payload=rel.endswith(('.app.zip','.dmg','.tar.gz')) or rel.startswith('WAM-Privacy') and rel.endswith('.zip')
        if not is_payload:continue
        payloads[rel]=expected
        if rel.endswith('.dmg'):continue
        data=io.BytesIO(z.read(prefix+rel));core={}
        if rel.endswith('.zip'):
            with zipfile.ZipFile(data) as inner:
                for n in inner.namelist():
                    short=n.rsplit('/',1)[-1]
                    if short in PINS[platform] and '__MACOSX' not in n:
                        require(short not in core)
                        with inner.open(n) as f:core[short]=digest(f)
        else:
            with tarfile.open(fileobj=data,mode='r:gz') as inner:
                for member in inner:
                    short=member.name.rsplit('/',1)[-1]
                    if short in PINS[platform] and member.isfile():
                        require(short not in core)
                        with inner.extractfile(member) as f:core[short]=digest(f)
        require(core==PINS[platform])
    require(payloads)
    if platform=='macos-arm64':
        require(any(n.endswith('.dmg') for n in payloads) and any(n.endswith('.app.zip') for n in payloads))
    return m,{'receipt_path':name,'receipt_sha256':mhash,'manifest_sha256':mhash,
              'build_receipt_sha256':bhash,'payloads_sha256':payloads}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--artifacts',type=Path,required=True)
    ap.add_argument('--mac-run',type=int,required=True)
    ap.add_argument('--windows-run',type=int,required=True)
    ap.add_argument('--linux-run',type=int,required=True)
    ap.add_argument('--wsp-run',type=int,required=True)
    ap.add_argument('--runtime-source',required=True)
    ap.add_argument('--ledger',type=Path,default=Path('tests/acceptance/issue45.json'))
    args=ap.parse_args()
    require(re.fullmatch('[0-9a-f]{40}',args.runtime_source) is not None)
    source_head=None;native={};frozen={};run_records={};logs={}
    job_names={'macos-arm64':('Real signed Core → WSP BIP352 → native Qt Receive Balance History',
                              'Signed real Core + bundled WSP .app/.dmg macOS ARM64 E2E'),
               'windows-x64':('win64-native-credential-cas','win64-native-credential-cas'),
               'linux-x86_64':('native-qt-wallet','frozen-wallet (desktop)')}
    package_prefix={'macos-arm64':'WAM-Fusion-REGTEST-RC1-macos-arm64-',
                    'windows-x64':'WAM-Fusion-REGTEST-RC1-windows-x64-',
                    'linux-x86_64':'WAM-Fusion-REGTEST-RC1-linux-x86_64-desktop-'}
    native_prefix={'macos-arm64':'real-core-regtest-',
                   'windows-x64':'windows-operational-wallet-evidence-',
                   'linux-x86_64':'linux-qt-wallet-evidence-'}
    for platform,rid in [('macos-arm64',args.mac_run),('windows-x64',args.windows_run),('linux-x86_64',args.linux_run)]:
        run=gh('actions/runs/'+str(rid));require(run['conclusion']=='success')
        head=run['head_sha'];source_head=source_head or head;require(head==source_head)
        # Only governance/measurement-script descendants may reuse this runtime.
        changed=git('diff','--name-only',args.runtime_source,head,'--','src/wam_regtest')
        require(not changed)
        jobs=gh(f'actions/runs/{rid}/jobs?per_page=100')['jobs']
        artifacts=gh(f'actions/runs/{rid}/artifacts?per_page=100')['artifacts']
        run_records[platform]={'run_id':rid,'source_sha':head,'conclusion':run['conclusion']}
        def job(name):
            matches=[j for j in jobs if j['name']==name]
            require(len(matches)==1 and matches[0]['conclusion']=='success')
            j=matches[0]
            if j['id'] not in logs:logs[j['id']]=gh(f"actions/jobs/{j['id']}/logs",raw=True)
            return j
        def common(a,j,checkout):
            require(a['workflow_run']['head_sha']==head)
            require(checkout in logs[j['id']])
            return {'source_sha':head,'checkout_sha':checkout,'workflow_head_sha':head,
                'qualified_runtime_source_sha':args.runtime_source,
                'timestamp_utc':j['completed_at'],'platform':platform,
                'reference':f"{URL}/actions/runs/{rid}/job/{j['id']}",
                'workflow_run_id':rid,'job_id':j['id'],'core_version':'v0.1.11',
                'core_sha256':PINS[platform],'core_trust':'reviewed-developer-source-build' if platform=='linux-x86_64' else 'official-signed-v0.1.11',
                'wsp_source_commit':WSP,'synthetic_rpc':False,'artifact_id':a['id'],
                'artifact_sha256':a['digest'].removeprefix('sha256:')}
        frozen[platform]=[]
        variants=[(package_prefix[platform],job_names[platform][1])]
        if platform=='linux-x86_64':variants.append(('WAM-Fusion-REGTEST-RC1-linux-x86_64-headless-','frozen-wallet (headless)'))
        for prefix,jname in variants:
            a=find_artifact(artifacts,prefix);j=job(jname)
            with archive(args.artifacts/f"{a['id']}.zip",a)[0] as z:
                m,extra=package_record(z,platform,head)
                record=common(a,j,m['checkout_sha']);record.update(extra)
                reuse=[]
                for name in z.namelist():
                    if not name.endswith('.json'):continue
                    obj=json.loads(z.read(name))
                    if type(obj) is dict and type(obj.get('wallet_live_core')) is dict and 'q03_reuse' in obj['wallet_live_core']:
                        check_reuse(obj['wallet_live_core']['q03_reuse'])
                        reuse.append({'path':name,'sha256':sha256(z.read(name)).hexdigest()})
                if platform=='macos-arm64':
                    measured=[json.loads(line.split('Q03_REUSE_PASS ',1)[1]) for line in logs[j['id']].splitlines() if 'Q03_REUSE_PASS {' in line]
                    require(len(measured)>=2)
                    for value in measured:check_reuse(value)
                    record['reuse_job_log_executions']=len(measured)
                else:require(len(reuse)>=(3 if platform=='windows-x64' else 1))
                record['reuse_receipts']=reuse
                frozen[platform].append(record)
                checkout=m['checkout_sha']
        native[platform]=[]
        variants=[(native_prefix[platform],job_names[platform][0])]
        if platform=='linux-x86_64':variants.append(('linux-headless-wallet-evidence-','headless-wallet'))
        for prefix,jname in variants:
            a=find_artifact(artifacts,prefix);j=job(jname)
            with archive(args.artifacts/f"{a['id']}.zip",a)[0] as z:
                proofs=[]
                for name in z.namelist():
                    if not name.endswith('.json'):continue
                    obj=json.loads(z.read(name))
                    if type(obj.get('wallet_live_core')) is not dict or 'q03_reuse' not in obj['wallet_live_core']:continue
                    require(obj['chain']=='regtest' and obj['genesis']=='b88f3d262f285e38e184f50bf3eea1c8e615486ae67d3d9eaf0976fbd6d3d30d')
                    require(obj['q02_authentication']['core_sha256']==PINS[platform])
                    check_reuse(obj['wallet_live_core']['q03_reuse'])
                    require(obj.get('source_head_sha',checkout) in (head,checkout))
                    proofs.append({'path':name,'sha256':sha256(z.read(name)).hexdigest()})
                require(proofs)
                record=common(a,j,checkout);record['runtime_receipts']=proofs
                native[platform].append(record)
                if platform=='macos-arm64':
                    cookie,h=read_json(z,'q03-cookie-reuse.json')
                    check_reuse(cookie)
                    require(cookie['auth_mode']=='cookie' and cookie['core_sha256']==PINS[platform])
                    require(cookie['source_head_sha']==head and cookie['checkout_sha']==checkout)
                    require(cookie['wsp_source_commit']==WSP and cookie['synthetic_rpc'] is False)
                    record['cookie_receipt']={'path':'q03-cookie-reuse.json','sha256':h}
    vectors=gh('actions/runs/'+str(args.wsp_run))
    require(vectors['conclusion']=='success' and vectors['head_sha']==source_head)
    data=json.loads(args.ledger.read_text());before=deepcopy(data);q=data['questions'][2]
    require(data['active_q']=='Q03' and q['candidate_pr']==131 and q['accepted'] is False)
    for c in q['cases']:
        if c['layer'] in ('PHYSICAL','DEV_REVIEWED'):continue
        platform=c['platform']
        if c['layer']=='SOURCE':
            evidence=[{'source_sha':source_head,'checkout_sha':native['macos-arm64'][0]['checkout_sha'],
                       'timestamp_utc':native['macos-arm64'][0]['timestamp_utc'],'platform':platform,
                       'reference':URL+'/blob/'+source_head+'/tests/test_q03_json_rpc.py',
                       'scope':'Source/security contracts and all-three-OS native/frozen execution; negative unit servers are supplemental, not positive genuine-Core evidence.'}]
        elif platform=='shared':evidence=[e for values in native.values() for e in values]
        else:evidence=frozen[platform] if c['layer']=='FROZEN' else native[platform]
        c.update(status='PASS',acceptance_evidence=deepcopy(evidence),blocker=None)
        for e in c['acceptance_evidence']:
            e['case_scope']=c['id']
            if c['layer']=='NEGATIVE_INJECTION':
                e['negative_test_scope']='Focused supplemental local-HTTP/dummy-binding source contracts, plus separate genuine-Core/native/frozen positive receipts. Not a fabricated wrong-chain Core.'
    q.update(status='BLOCKED',accepted=False,base_main_sha='ea3bcd674a30178ab2ebc4b5d582e89707464d4e',
        candidate_head_sha=source_head,qualified_runtime_source_sha=args.runtime_source,
        engineering_status='TECHNICAL_COMPLETE_PENDING_EXTERNAL_AND_OWNER_INTEGRATION',
        full_acceptance_status='BLOCKED',owner_merge_authorization=None,post_merge_main_sha=None)
    q['evidence_qualification']={'workflow_source_sha':source_head,'runtime_source_sha':args.runtime_source,
        'runtime_identity':'All src/wam_regtest bytes equal runtime_source_sha; source/checkout are actual receipt identities, never the later ledger commit SHA.',
        'runs':run_records,'wsp_run_id':args.wsp_run,'wsp_source_commit':WSP}
    q['integration_blocker']={'actor':'REPOSITORY_OWNER_THEN_CI_OPERATOR','missing_evidence':'Q03 owner-approved merge and exact-main postmerge qualification. Q02 focus authorization does not authorize merging Q03.',
        'next_action':'Review concrete Draft PR #131; authorize integration separately, then qualify merged main. Keep Draft and Q04 queued.'}
    for gate in ('G0','G1','G2','G3','G4','G5'):q['gates'][gate]['status']='PASS'
    for gate in ('G6','G7'):q['gates'][gate]['status']='BLOCKED'
    require(data['questions'][:2]==before['questions'][:2] and data['questions'][3:]==before['questions'][3:])
    from wam_regtest.q_gate import validate
    result=validate(data)
    require(result['case_results']['PASS']==24 and result['case_results']['BLOCKED']==2)
    args.ledger.write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,OSError,zipfile.BadZipFile,subprocess.CalledProcessError):
        raise SystemExit('Q03_EVIDENCE_UNVERIFIED: no ledger promotion written')
