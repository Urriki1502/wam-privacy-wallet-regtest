"""Fresh-profile mnemonic restoration from real historical REGTEST blocks.

Qualification only: three NEW namespaces, two Core owners at a time. A second
participant is positively stopped before a fresh participant restores the seed
and syncs historical blocks from the sole coordinator. No chain/vault/anchor is
copied; restored custody remains read-only and original reservations survive.
"""
from hashlib import sha256
import json
from pathlib import Path
import re
import secrets
import time
from .wallet_executor import WalletExecutor, WalletExecutorError
from .bip39_owner_backend import Bip39ReadOnlyBackend
from .shared_regtest import SharedRegtestProfile
from .custody import create_directory


def qualify(core, source, parent, adapter):
    lab = parent / ('same-chain-restore-' + secrets.token_hex(8))
    create_directory(lab)
    report = {'status':'FAIL','synthetic_rpc':False,'mainnet_allowed':False,
              'physical_accepted':False,'independent_reviewed':False,
              'chain_copied':False,'native_anchor_copied':False,
              'old_profile_overwritten':False,'restored_signer_enabled':False,
              'platform':adapter.platform_id,'ports':[[29554,29555],[29556,29557]]}
    profiles = [SharedRegtestProfile('127.0.0.1',coordinator=True,
                    rpc_port=29554,p2p_port=29555,peer_port=29557),
                SharedRegtestProfile('127.0.0.1',coordinator=False,
                    rpc_port=29556,p2p_port=29557,peer_port=29555)]
    workers = []
    password = b'public-disposable-same-chain-profile-restore'
    phrase = None
    def step(name):
        report['stage'] = name
        print('Q06_SAME_CHAIN_RESTORE_STAGE=' + name, flush=True)
    def start(index, mode, mnemonic=''):
        root = lab / ('wam-fusion-core-' + secrets.token_hex(8))
        worker = WalletExecutor(lambda:Bip39ReadOnlyBackend(
            root,core,source,shared_profile=profiles[index],_anchor_factory=adapter.make_anchor))
        workers.append(worker)
        opened = worker.request('open',password,mode,mnemonic,timeout=120)
        return worker, opened
    def wait(predicate):
        deadline = time.monotonic() + 120
        while not predicate():
            if time.monotonic() >= deadline:
                raise ValueError('Q06_SAME_CHAIN_RESTORE_SYNC_TIMEOUT')
            time.sleep(.1)
    def state(worker):
        return worker.request('network_status',timeout=30)
    def stop(worker):
        worker.request('quit',timeout=60)
        if not worker.join(15) or not worker.closed:
            raise ValueError('Q06_SAME_CHAIN_RESTORE_ORIGINAL_OWNER_LIVE')
    try:
        step('NEW_COORDINATOR_AND_PARTICIPANT')
        a, opened = start(0,'create')
        phrase = opened['mnemonic_once']
        a.request('acknowledge_create_pending',opened['seed_folder'],timeout=30)
        positions = (1,6,12)
        answers = tuple(phrase.split()[i-1] for i in positions)
        if a.request('backup_verify',positions,answers,timeout=30) is not True:
            raise ValueError('Q06_SAME_CHAIN_RESTORE_BACKUP_DENIED')
        answers = None
        b, unused = start(1,'create')
        unused = None
        wait(lambda:state(a)['connected'] and state(b)['connected'])
        peers = state(a)['peers'] + state(b)['peers']
        if not peers or any(p['subver']!='/WAM:0.1.13/' or p['version']!=70016 for p in peers):
            raise ValueError('Q06_SAME_CHAIN_RESTORE_PEER_IDENTITY_DENIED')
        report['observed_peer_subversions'] = sorted({p['subver'] for p in peers})
        report['observed_peer_protocols'] = sorted({p['version'] for p in peers})
        try:b.request('mine',timeout=30)
        except WalletExecutorError as error:
            if error.args != ('SHARED_SINGLE_COORDINATOR_REQUIRED',):raise
        else:raise ValueError('Q06_SAME_CHAIN_RESTORE_PARTICIPANT_MINED')
        step('REAL_HISTORICAL_FUNDS_AND_PAYMENT')
        a.request('mine',timeout=240)
        active = a.request('activate',timeout=240)
        from mnemonic import Mnemonic
        from .bip39_12 import Bip39Regtest12Keys
        with Bip39Regtest12Keys(Mnemonic('english').to_mnemonic(bytes([2]*16)),
                                source=source,authorized_disposable=True) as payee:
            destination = payee.public_metadata()['receive_code']
        draft = a.request('prepare',destination,50_000,1_000,timeout=240)
        a.request('sign',draft.commitment,timeout=240)
        txid = a.request('broadcast',draft.commitment,timeout=240)
        confirmed = a.request('confirm',txid,timeout=240)
        before = a.request('snapshot',timeout=240)
        if (confirmed['txid']!=txid or before['history_count_shown']<2
                or before['reservation_count']!=1):
            raise ValueError('Q06_SAME_CHAIN_RESTORE_ORIGINAL_HISTORY_DENIED')
        wait(lambda:state(b)['tip']==before['tip'])
        step('VERIFIED_ORIGINAL_PARTICIPANT_SHUTDOWN')
        stop(b)
        report['original_participant_shutdown_verified'] = True
        step('NEW_PROFILE_RESTORE_THEN_SYNC_HISTORICAL_CHAIN')
        c, restored = start(1,'restore',phrase)
        if (restored['receive_code']!=opened['receive_code'] or restored['mnemonic_once']
                or restored['account_id']!=opened['account_id']
                or restored['signer_allowed'] is not False):
            raise ValueError('Q06_SAME_CHAIN_RESTORE_FRESH_IDENTITY_DENIED')
        wait(lambda:state(a)['connected'] and state(c)['connected']
                       and state(c)['tip']==before['tip'])
        recovered = c.request('snapshot',timeout=240)
        after = a.request('snapshot',timeout=240)
        expected = {row['txid'] for row in before['history']}
        actual = {row['txid'] for row in recovered['history']}
        if (recovered['height']!=before['height'] or recovered['tip']!=before['tip']
                or recovered['receive_code']!=opened['receive_code']
                or recovered['confirmed_atoms']!=before['confirmed_atoms']
                or recovered['signer_allowed'] is not False
                or txid not in actual or actual!=expected
                or after['reservation_count']!=before['reservation_count']
                or after['confirmed_atoms']!=before['confirmed_atoms']):
            raise ValueError('Q06_SAME_CHAIN_RESTORE_FUNDS_HISTORY_DENIED')
        report.update(status='FRESH_PROFILE_SAME_CHAIN_HISTORY_RESTORE_PASS',
            restored_receive_code_sha256=sha256(restored['receive_code'].encode('ascii')).hexdigest(),
            confirmed_txid=txid,confirmed_height=before['height'],confirmed_tip=before['tip'],
            confirmed_atoms=before['confirmed_atoms'],history_count=len(actual),
            original_irreversible_reservations_preserved=True,
            mnemonic_does_not_restore_signed_reservations=True)
        step('RESTORED_AND_ORIGINAL_OWNERS_CLEAN_SHUTDOWN')
        stop(c)
        stop(a)
    except Exception as error:
        report['status'] = 'FAIL'
        code = error.args[0] if len(error.args)==1 and type(error.args[0]) is str else ''
        report['failure_code'] = code if re.fullmatch('[A-Z0-9_]{5,100}',code) else 'Q06_SAME_CHAIN_RESTORE_DENIED'
    finally:
        clean = True
        for worker in reversed(workers):
            if worker.closed:continue
            if worker.busy:
                clean = False
                continue
            try:stop(worker)
            except Exception:clean = False
        report['all_original_owners_shutdown_verified'] = clean
        if not clean:report['status']='FAIL'
        phrase = None
        (lab/'public-evidence.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
