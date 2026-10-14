#!/usr/bin/env python3
"""Independent internal evaluator; never imports or executes wallet runtime.

Review-derived AST contracts + crash-state exploration + direct byte identity.
Not external human review, full formal verification or a second build witness.
"""
import argparse,ast,hashlib,json,subprocess
from pathlib import Path

PINS={'wamd':'7298de701e467eb28b4806cbcbe35edb393861b4b97117017fee4c1b194e3068',
      'wam-cli':'81a031ebf9b3060b19061b29756d43bcd09b32ad778348b8c3d8321397076e82'}
WSP='ac55f13423620252bdbf848c7e8a280c3b84721e'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def name(node):
    if isinstance(node,ast.Name): return node.id
    if isinstance(node,ast.Attribute): return name(node.value)+'.'+node.attr
    if isinstance(node,ast.Call): return name(node.func)
    return ''
def method(tree,label):
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='WalletSession')
    return next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==label)
def events(fn):
    return [(n.lineno,name(n.func),n) for n in ast.walk(fn) if isinstance(n,ast.Call)]
def line(calls,label): return min(n for n,k,_ in calls if k==label)
def contracts(tree):
    s,b=method(tree,'sign'),method(tree,'broadcast'); se,be=events(s),events(b)
    lease=all(any(isinstance(n,ast.With) and any(name(i.context_expr)=='self.vault.anchor.lease'
              for i in n.items) for n in ast.walk(f)) for f in (s,b))
    return {'sign_broadcast_lease':lease,
       'exact_sign_review_before_crypto':any(isinstance(n,ast.Compare) and n.lineno<line(se,'Signer.sign')
           and any(name(x)=='self._review.commitment' for x in (n.left,*n.comparators)) for n in ast.walk(s)),
       'exact_broadcast_review_before_submission':any(isinstance(n,ast.Compare) and n.lineno<line(be,'Wallet.broadcast')
           and any(name(x)=='self._review.commitment' for x in (n.left,*n.comparators)) for n in ast.walk(b)),
       'live_inputs_before_sensitive_operations':line(se,'self._unchanged_inputs')<line(se,'Signer.sign') and line(be,'self._unchanged_inputs')<line(be,'Wallet.broadcast'),
       'sign_anchor_precedes_crypto':line(se,'Wallet.mark_signed')<line(se,'self._save')<line(se,'Signer.sign'),
       'broadcast_anchor_precedes_submission':line(be,'self._save')<line(be,'Wallet.broadcast'),
       'uncertain_before_submission':any(isinstance(n,ast.Constant) and isinstance(n.value,str)
           and "state='uncertain'" in n.value and n.lineno<line(be,'self._save') for n in ast.walk(b)),
       'faults_on_crypto_or_submission_failure':all(any(isinstance(n,ast.Assign)
           and any(name(t)=='self.faulted' for t in n.targets)
           and isinstance(n.value,ast.Constant) and n.value.value is True for n in ast.walk(f)) for f in (s,b))}

def state_check(*,early_signature=False,early_network=False,forget_unknown=False,replay=False):
    # Inspect every crash boundary independently of application code/evidence.
    events=['approve_sign','persist_signed','crypto','approve_broadcast','persist_uncertain','submit','unknown']
    if early_signature: events[1],events[2]=events[2],events[1]
    if early_network: events[4],events[5]=events[5],events[4]
    violations=[]
    for stop in range(len(events)+1):
        durable='draft'; signed=sent=False; sign_consent=broadcast_consent=False
        for event in events[:stop]:
            if event=='approve_sign': sign_consent=True
            elif event=='persist_signed': durable='signed'
            elif event=='crypto':
                if durable!='signed' or not sign_consent: violations.append('signature_without_anchor_or_consent')
                signed=True;sign_consent=False
            elif event=='approve_broadcast': broadcast_consent=True
            elif event=='persist_uncertain': durable='uncertain'
            elif event=='submit':
                if durable!='uncertain' or not signed or not broadcast_consent: violations.append('submission_without_uncertainty_or_consent')
                sent=True;broadcast_consent=False
            elif event=='unknown' and forget_unknown: durable='draft'
        # Crash clears volatile approvals/signatures; durable identities stay.
        if sent and durable!='uncertain': violations.append('submitted_identity_forgotten')
        if replay and signed: violations.append('approval_replayed_after_crash')
    return sorted(set(violations))

def evaluate(root,core,app=None):
    tree=ast.parse((root/'src/wam_regtest/wallet_session.py').read_text())
    results=contracts(tree)
    results['crash_model_invariants']=not state_check()
    mutants={'signature_before_anchor':{'early_signature':True},'submission_before_anchor':{'early_network':True},
             'forget_uncertain':{'forget_unknown':True},'replay_consent':{'replay':True}}
    results['model_mutation_sensitivity']=all(state_check(**args) for args in mutants.values())
    # Mutate actual source ordering: the independent contract must reject it.
    mutated=ast.parse((root/'src/wam_regtest/wallet_session.py').read_text())
    f=method(mutated,'sign')
    for node in ast.walk(f):
        if isinstance(node,ast.Call) and name(node.func)=='Signer.sign': node.lineno=0
    results['source_mutation_sensitivity']=contracts(mutated)['sign_anchor_precedes_crypto'] is False
    lock_calls=events(method(tree,'lock'))
    results['lock_closes_keys_and_plaintext_runtime']=all(any(k==label for _,k,_ in lock_calls)
        for label in ('self.ring.close','self.scanner.close','self.runtime.unlink'))
    vault=ast.parse((root/'src/wam_regtest/vault.py').read_text())
    results['stale_writer_anchor_comparison']=any(isinstance(n,ast.Compare) and name(n.left)=='previous'
        and any(name(x)=='self._expected' for x in n.comparators) for n in ast.walk(vault))
    storage=ast.parse((root/'src/wam_regtest/encrypted_storage.py').read_text())
    storage_calls={name(n.func) for n in ast.walk(storage) if isinstance(n,ast.Call)}
    results['backup_create_only_publication_and_fsync']={'os.link','os.fsync','os.fchmod'}<=storage_calls
    results['both_core_hashes_independently_pinned']=all(sha(core/n)==h for n,h in PINS.items())
    if app is not None:
        import plistlib
        info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
        results['original_brand_identity']=sha(app/'Contents/Resources'/info['CFBundleIconFile'])=='dc8c4de2aeac66e062ac530b2a462e639646e02b3cfe5a7ba6f8c4bd8f571fb7'
        for n,h in PINS.items():
            members=[p for p in app.rglob(n) if p.is_file() and not p.is_symlink()]
            results['bundled_'+n+'_identity']=len(members)==1 and sha(members[0])==h
        wsp=root/'wsp-upstream'
        assert subprocess.check_output(['git','-C',str(wsp),'rev-parse','HEAD'],text=True).strip()==WSP
        assert not subprocess.check_output(['git','-C',str(wsp),'status','--porcelain','--untracked-files=no','--','src/wam_sp'],text=True).strip()
        source=app/'Contents/Resources/wsp-source/src/wam_sp'
        original=wsp/'src/wam_sp'
        expected={p.relative_to(original).as_posix():sha(p) for p in original.rglob('*.py')}
        actual={p.relative_to(source).as_posix():sha(p) for p in source.rglob('*.py')}
        results['bundled_scanner_independent_source_comparison']=expected==actual
    if not all(results.values()): raise ValueError('INDEPENDENT_WALLET_CONTRACT_DENIED')
    return {'schema':'wam-regtest-independent-contracts/v1','status':'INDEPENDENT_WALLET_CONTRACTS_PASS',
        'contracts':results,'core_sha256':PINS,'wsp_source_commit':WSP,'model_crash_boundaries':8,
        'mutation_classes_detected':list(mutants),'runtime_pass_flags_trusted':False,
        'external_reviewer_approval':False,'second_builder_witness':False,'formal_verification_complete':False,
        'production_qualified':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--core',type=Path,required=True)
    p.add_argument('--app',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=evaluate(a.root.resolve(),a.core.resolve(),a.app.resolve() if a.app else None)
    a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(result['status'])
if __name__=='__main__':
    try: main()
    except Exception: raise SystemExit('INDEPENDENT_WALLET_SECURITY_DENIED') from None
