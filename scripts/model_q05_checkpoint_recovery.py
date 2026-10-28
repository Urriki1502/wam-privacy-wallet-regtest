"""Independent design model, NOT a wallet recovery implementation or E2E proof.

Checks every proposed publication boundary and detects deliberately unsafe
alternatives. Symbolic ciphertext/locks stand for authenticated native evidence;
no cryptography, Core, Keychain, SQLite repair or custody mutation is executed.
"""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess

ACTIONS=('authenticate','begin','copy','publish','anchor','commit','sync','lock')
MUTANTS=('early_commit','trust_orphan','forget_uncertain','overwrite_old',
         'replay_uncertain','delete_runtime','ignore_identity','ignore_cas')


def initial():
    payload={'wallet':'same-wallet','locks':{'S':'signed','U':'uncertain'}}
    files={'old/1':{'digest':'A','payload':deepcopy(payload)},
           'old/2':{'digest':'ORPHAN','payload':{'wallet':'same-wallet','locks':{}}},
           'old/runtime':{'digest':'UNKNOWN','payload':None}}
    return {'files':files,'original':deepcopy(files),'anchor':(1,'A'),
            'source_record':(1,'A'),'target_record':(2,'B'),'source_payload':payload,
            'authenticated':False,'reference':'old','commit_record':None,
            'native_target_id':'owned-target','reference_target_id':'owned-target',
            'writes':[],'submissions':0,'refused':False}


def visible(state,*,ignore_identity=False):
    if (state['reference']!='new' or state['refused']
            or not ignore_identity and state['native_target_id']!=state['reference_target_id']):
        return None
    row=state['files'].get('new/'+str(state['anchor'][0]))
    if row is None or row['digest']!=state['anchor'][1]:return None
    return row['payload']


def step(state,action,mutation):
    if state['refused']:return
    if action=='authenticate':state['authenticated']=True
    elif action=='begin':state['reference']='pending'
    elif action=='copy':state['files']['new/1']=deepcopy(state['files']['old/1'])
    elif action=='publish':
        payload=deepcopy(state['source_payload'])
        if mutation=='forget_uncertain':payload['locks'].pop('U')
        if mutation=='trust_orphan':payload=deepcopy(state['files']['old/2']['payload'])
        destination='old/2' if mutation=='overwrite_old' else 'new/2'
        state['files'][destination]={'digest':'B','payload':payload}
        if mutation=='early_commit':
            state['reference']='new';state['commit_record']=state['anchor']
    elif action=='anchor':
        if mutation=='ignore_cas':state['anchor']=(3,'EXTERNAL_ADVANCE')
        before=state['anchor']
        if before!=state['source_record'] and mutation!='ignore_cas':
            state['refused']=True;return
        row=state['files'].get('new/2')
        if row is None:state['refused']=True;return
        state['writes'].append((before,state['target_record'],deepcopy(row['payload']),state['authenticated']))
        state['anchor']=state['target_record']
    elif action=='commit':
        state['reference']='new';state['commit_record']=state['anchor']
        if mutation=='ignore_identity':state['native_target_id']='foreign-target'
    elif action=='sync':
        if mutation=='replay_uncertain':state['submissions']+=1
    elif action=='lock':
        if mutation=='delete_runtime':state['files'].pop('old/runtime')


def violations(state,mutation=None):
    errors=[]
    if any(state['files'].get(name)!=row for name,row in state['original'].items()):
        errors.append('original_or_unknown_evidence_changed')
    if state['submissions']:errors.append('automatic_transaction_replay')
    if state['reference']=='new' and state['commit_record']!=state['target_record']:
        errors.append('reference_committed_before_target_anchor')
    for before,after,payload,authenticated in state['writes']:
        if not authenticated:errors.append('unauthenticated_source')
        if before!=state['source_record'] or after[0]!=before[0]+1:
            errors.append('stale_or_nonmonotonic_anchor_write')
        if payload['wallet']!=state['source_payload']['wallet']:
            errors.append('wallet_identity_replaced')
        if any(payload['locks'].get(token)!=value for token,value in state['source_payload']['locks'].items()):
            errors.append('irreversible_reservation_forgotten')
    exposed=visible(state,ignore_identity=mutation=='ignore_identity')
    if exposed is not None:
        if state['native_target_id']!=state['reference_target_id']:
            errors.append('foreign_container_accepted')
        if exposed!=state['source_payload']:errors.append('visible_state_diverged')
    return sorted(set(errors))


def explore(mutation=None):
    traces=[]
    for boundary in range(len(ACTIONS)+1):
        state=initial()
        for action in ACTIONS[:boundary]:step(state,action,mutation)
        traces.append({'boundary':boundary,'violations':violations(state,mutation),
                       'balance_visible':visible(state) is not None})
    return traces


def evaluate():
    safe=explore();counterexamples={}
    assert all(not row['violations'] for row in safe)
    assert safe[-1]['balance_visible']
    for mutation in MUTANTS:
        bad=next((row for row in explore(mutation) if row['violations']),None)
        if bad is None:raise ValueError('RECOVERY_MODEL_MUTATION_NOT_DETECTED')
        counterexamples[mutation]=bad
    return {'schema':'q05-recovery-design-model/v1','status':'INTERNAL_MODEL_CHECKED',
            'boundaries_checked':len(safe),'counterexamples':counterexamples,
            'runtime_recovery_implemented':False,'cryptography_or_native_storage_executed':False,
            'core_executed':False,'independent_approval':False,'q05_acceptance':False,
            'limitation':'Symbolic single-owner/no-new-chain-events model; not formal verification, real recovery or crash evidence.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=evaluate()
    root=Path(__file__).resolve().parents[1]
    result['source_sha']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    result['model_source_sha256']=sha256(Path(__file__).read_bytes()).hexdigest()
    result['clean_worktree']=not bool(subprocess.check_output(['git','status','--porcelain'],cwd=root))
    with args.output.open('x') as out:json.dump(result,out,indent=2);out.write('\n')
    print(result['status'])
