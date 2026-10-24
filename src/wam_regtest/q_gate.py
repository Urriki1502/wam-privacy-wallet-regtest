"""Read-only ledger consistency, not evidence attestation or merge authority."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

STATES={'PASS','FAIL','PENDING','BLOCKED','STALE'}
ORDER=[f'Q{i:02}' for i in range(1,21)]
GATES={f'G{i}' for i in range(8)}


def validate(ledger):
    def require(value):
        if not value:raise ValueError('Q_GATE_LEDGER_INCONSISTENT')
    require(type(ledger) is dict and ledger.get('schema')=='wam-issue45-sequential-q-ledger/v1')
    require(ledger.get('execution_order')==ORDER and set(ledger.get('allowed_case_states',[]))==STATES)
    require(ledger.get('automatic_merge_allowed') is False and ledger.get('mainnet_allowed') is False
        and ledger.get('production_qualified') is False)
    records=ledger.get('questions');require(type(records) is list and [r.get('id') for r in records]==ORDER)
    active=ledger.get('active_q');require(active in ORDER)
    require([r['id'] for r in records if r.get('processing')=='ACTIVE']==[active])
    ids=set()
    for index,r in enumerate(records):
        require(r.get('status') in STATES and type(r.get('accepted')) is bool)
        require(set(r.get('gates',{}))==GATES and all(g.get('status') in STATES for g in r['gates'].values()))
        require(all(g.get('applicable') is True or type(g.get('not_applicable_reason')) is str
            and len(g['not_applicable_reason'])>20 for g in r['gates'].values()))
        cases=r.get('cases');require(type(cases) is list)
        if r['id']==active:require(cases and r.get('coverage_identified') is True and r.get('coverage_total')==len(cases))
        for c in cases:
            require(type(c.get('id')) is str and c['id'].startswith(r['id']+'-') and c['id'] not in ids);ids.add(c['id'])
            require(c.get('status') in STATES and c.get('mandatory') is True and c.get('requirement_refs'))
            require(c.get('gates') and set(c['gates'])<=GATES and type(c.get('acceptance_evidence')) is list)
            if c['status']=='BLOCKED':
                require(type(c.get('blocker')) is dict and all(c['blocker'].get(k) for k in ('actor','missing_evidence','next_action')))
            if c['status']=='PASS':
                require(c['acceptance_evidence'])
                for e in c['acceptance_evidence']:
                    require(all(e.get(k) for k in ('source_sha','checkout_sha','timestamp_utc','platform','reference')))
                    require(all(re.fullmatch('[0-9a-f]{40}',e[k]) for k in ('source_sha','checkout_sha')))
                    if c['layer'] in ('CORE_E2E','FROZEN','MAIN'):
                        require(e.get('synthetic_rpc') is False and e.get('core_version')=='v0.1.11'
                            and e.get('wsp_source_commit')=='ac55f13423620252bdbf848c7e8a280c3b84721e')
                        require(all(e.get(k) for k in ('core_sha256','core_trust','workflow_run_id','job_id')))
                    if c['layer'] in ('FROZEN','MAIN'):require(re.fullmatch('[0-9a-f]{64}',e.get('artifact_sha256','')))
        if r['accepted']:
            require(cases and r['status']=='PASS' and all(c['status']=='PASS' for c in cases))
            require(all(g['status']=='PASS' for g in r['gates'].values()))
            require(r.get('owner_merge_authorization') and re.fullmatch('[0-9a-f]{40}',r.get('post_merge_main_sha','')))
        if index<ORDER.index(active):require(r['accepted'] is True)
        if index>ORDER.index(active):require(r.get('processing')=='QUEUED' and not r['accepted'])
    current=records[ORDER.index(active)]
    require(not any(c['status']=='FAIL' for c in current['cases']) or current['status']=='FAIL')
    return {'active_q':active,'coverage_identified':current['coverage_total'],
        'case_results':{state:Counter(c['status'] for c in current['cases'])[state] for state in ('PASS','FAIL','PENDING','BLOCKED','STALE')},
        'gates':{name:g['status'] for name,g in current['gates'].items()},
        'q_accepted':current['accepted'],'validation_is_not_qualification':True}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ledger',type=Path,default=Path('tests/acceptance/issue45.json'));args=ap.parse_args()
    print(json.dumps(validate(json.loads(args.ledger.read_text())),sort_keys=True))


if __name__=='__main__':main()
