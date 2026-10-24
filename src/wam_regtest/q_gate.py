"""Read-only ledger consistency, not evidence attestation or merge authority."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

STATES={'PASS','FAIL','PENDING','BLOCKED','STALE'}
ORDER=[f'Q{i:02}' for i in range(1,21)]
GATES={f'G{i}' for i in range(8)}


def _engineering_handoff_qualified(record, index):
    """Authorize change of engineering focus, NEVER declare full Q acceptance."""
    handoff=record.get('engineering_handoff')
    if type(handoff) is not dict or index>=len(ORDER)-1:return False
    owner_issue='https://github.com/Urriki1502/wam-privacy-wallet-regtest/issues/45#issuecomment-'
    sha=lambda value:type(value) is str and re.fullmatch('[0-9a-f]{40}',value) is not None
    if not (handoff.get('owner_authorized_handoff') is True
            and type(handoff.get('owner_decision_url')) is str
            and handoff['owner_decision_url'].startswith(owner_issue)
            and type(record.get('owner_merge_authorization')) is str
            and record['owner_merge_authorization'].startswith(
                'https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/')
            and handoff.get('engineering_status')=='INTEGRATED_PENDING_EXTERNAL'
            and handoff.get('next_q')==ORDER[index+1]
            and handoff.get('merged_pr')==record.get('candidate_pr')
            and sha(handoff.get('merged_main_sha'))
            and sha(handoff.get('qualified_runtime_source_sha'))
            and handoff['qualified_runtime_source_sha']==record.get('qualified_runtime_source_sha')
            and handoff.get('postmerge_status') in ('PENDING','PARTIAL_PASS','PASS')
            and record.get('accepted') is False and record.get('status')=='BLOCKED'):
        return False
    gates=record.get('gates',{})
    if any(gates.get(k,{}).get('status')!='PASS' for k in ('G0','G2','G3','G4','G5')):
        return False
    if any(gates.get(k,{}).get('status') not in ('PASS','BLOCKED') for k in ('G1','G6','G7')):
        return False
    cases=record.get('cases')
    if type(cases) is not list or not cases:return False
    unresolved={c['id'] for c in cases if c['status']!='PASS'}
    if not unresolved or handoff.get('unresolved_case_ids')!=sorted(unresolved):return False
    # No unresolved technical FAIL/PENDING/STALE may be bypassed. Only named
    # physical, independent or postmerge gates may be blocked for a handoff.
    return all(c['status']=='PASS' or (
        c['status']=='BLOCKED'
        and c.get('layer') in ('PHYSICAL','DEV_REVIEWED','MAIN')
        and type(c.get('blocker')) is dict
        and all(c['blocker'].get(k) for k in ('actor','missing_evidence','next_action'))
    ) for c in cases)


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
                    if c['layer']=='MAIN' and c['id'].endswith('-MERGE-AUTH'):
                        # Owner approval is an authoritative PR action, not a
                        # native Core or frozen-binary test receipt.
                        require(re.fullmatch('[0-9a-f]{40}',e.get('merged_main_sha',''))
                            and type(e.get('owner_decision_url')) is str
                            and e['owner_decision_url'].startswith(
                                'https://github.com/Urriki1502/wam-privacy-wallet-regtest/pull/'))
                    else:
                        if c['layer'] in ('CORE_E2E','FROZEN','MAIN'):
                            require(e.get('synthetic_rpc') is False and e.get('core_version')=='v0.1.11'
                                and e.get('wsp_source_commit')=='ac55f13423620252bdbf848c7e8a280c3b84721e')
                            require(all(e.get(k) for k in ('core_sha256','core_trust','workflow_run_id','job_id')))
                        if c['layer'] in ('FROZEN','MAIN'):
                            require(re.fullmatch('[0-9a-f]{64}',e.get('artifact_sha256','')))
        if r['accepted']:
            require(cases and r['status']=='PASS' and all(c['status']=='PASS' for c in cases))
            require(all(g['status']=='PASS' for g in r['gates'].values()))
            require(r.get('owner_merge_authorization') and re.fullmatch('[0-9a-f]{40}',r.get('post_merge_main_sha','')))
        if r.get('engineering_handoff') is not None:require(_engineering_handoff_qualified(r,index))
        if index<ORDER.index(active):require(r['accepted'] is True or _engineering_handoff_qualified(r,index))
        if index>ORDER.index(active):require(r.get('processing')=='QUEUED' and not r['accepted'])
    current=records[ORDER.index(active)]
    require(not any(c['status']=='FAIL' for c in current['cases']) or current['status']=='FAIL')
    return {'active_q':active,'engineering_active_q':active,
        'prior_engineering_handoffs':[r['id'] for r in records[:ORDER.index(active)]
            if not r['accepted'] and _engineering_handoff_qualified(r,ORDER.index(r['id']))],
        'coverage_identified':current['coverage_total'],
        'case_results':{state:Counter(c['status'] for c in current['cases'])[state] for state in ('PASS','FAIL','PENDING','BLOCKED','STALE')},
        'gates':{name:g['status'] for name,g in current['gates'].items()},
        'q_accepted':current['accepted'],'validation_is_not_qualification':True}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ledger',type=Path,default=Path('tests/acceptance/issue45.json'));args=ap.parse_args()
    print(json.dumps(validate(json.loads(args.ledger.read_text())),sort_keys=True))


if __name__=='__main__':main()
