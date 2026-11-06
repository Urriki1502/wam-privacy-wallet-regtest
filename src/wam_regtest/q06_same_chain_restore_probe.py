"""Fresh-profile mnemonic restoration from real historical REGTEST blocks.

Qualification only: three NEW namespaces, two Core owners at a time. A second
participant is positively stopped before a fresh participant on new ports restores the seed
and syncs historical blocks from the sole coordinator. No chain/vault/anchor is
copied; restored custody remains read-only and original reservations survive.
"""
from hashlib import sha256
import json
import errno
from pathlib import Path
import re
import secrets
import time
from .wallet_executor import WalletExecutor, WalletExecutorError
from .bip39_owner_backend import Bip39ReadOnlyBackend
from .shared_regtest import SharedRegtestProfile
from .custody import create_directory


def qualify(core, source, parent, adapter, *, port_base=29554):
    if type(port_base) is not int or not 1024<=port_base<=65530:
        raise ValueError('Q06_SAME_CHAIN_RESTORE_PORT_SCOPE_DENIED')
    lab = parent / ('same-chain-restore-' + secrets.token_hex(8))
    create_directory(lab)
    report = {'status':'FAIL','synthetic_rpc':False,'mainnet_allowed':False,
              'physical_accepted':False,'independent_reviewed':False,
              'chain_copied':False,'native_anchor_copied':False,
              'old_profile_overwritten':False,'restored_signer_enabled':False,
              'platform':adapter.platform_id,'ports':[[port_base+i,port_base+i+1] for i in (0,2,4)]}
    profiles = [SharedRegtestProfile('127.0.0.1',coordinator=True,
                    rpc_port=port_base,p2p_port=port_base+1,peer_port=port_base+3),
                SharedRegtestProfile('127.0.0.1',coordinator=False,
                    rpc_port=port_base+2,p2p_port=port_base+3,peer_port=port_base+1),
                SharedRegtestProfile('127.0.0.1',coordinator=False,
                    rpc_port=port_base+4,p2p_port=port_base+5,peer_port=port_base+1)]
    workers = []
    password = b'public-disposable-same-chain-profile-restore'
    phrase = None
    restore_tip = None
    def step(name):
        report['stage'] = name
        print('Q06_SAME_CHAIN_RESTORE_STAGE=' + name, flush=True)
    class ObservedBackend(Bip39ReadOnlyBackend):
        def _start_core(self):
            self.owner.start(timeout=90,
                _defer_shared_network=self.shared_profile is profiles[2])

        def execute(self, action, args, kwargs):
            try:
                result=super().execute(action,args,kwargs)
                if action=='open' and self.shared_profile is profiles[2]:
                    # Hold P2P inactive through original-process/HTTP
                    # attestation AND native seed opening. Only then enable
                    # this disposable participant and await real blocks.
                    from .core import _read_cli
                    owner=self.owner
                    prefix=[str(owner.cli),'-datadir='+str(owner.directory)]
                    _read_cli(prefix+['setnetworkactive','true'])
                    deadline=time.monotonic()+120
                    while True:
                        remaining=deadline-time.monotonic()
                        if remaining<=0:
                            raise ValueError('Q06_RESTORED_CORE_BOOTSTRAP_SYNC_TIMEOUT')
                        info=_read_cli(prefix+['getblockchaininfo'],timeout=min(15,remaining))
                        if (info['blocks'],info['bestblockhash'])==restore_tip:break
                        if info['blocks']>restore_tip[0]:
                            raise ValueError('Q06_RESTORED_CORE_BOOTSTRAP_TIP_DENIED')
                        time.sleep(.1)
                    from .managed_wallet_checkpoint import _owned
                    _owned(owner)  # Unchanged HTTP and custody checks after sync.
                    report['restored_core_attested_before_network_sync']=True
                    report['restored_core_synced_before_history_scan']=True
                return result
            except Exception as error:
                # Public type/errno only: never exception strings, args,
                # mnemonic, credentials, chain records or signed payloads.
                report['backend_failure']={'action':action,
                    'type':type(error).__name__,
                    'errno':error.errno if isinstance(error,OSError) else None}
                owner=self.owner
                if owner is not None:
                    report['backend_failure']['owner_state']=owner.state
                    report['backend_failure']['owner_faulted']=owner._faulted
                    from .supervisor_store import read_exact
                    from .core_supervisor import DIAGNOSTIC_CODES
                    try:
                        failure=json.loads(read_exact(owner.root,'supervisor.failure'))
                        if (type(failure) is dict and set(failure)=={'stage','code'}
                                and failure['stage'] in ('start','status','recover-stop')
                                and failure['code'] in DIAGNOSTIC_CODES|{'MANAGED_UNCLASSIFIED_FAILURE'}):
                            report['backend_failure']['supervisor_failure']=failure
                    except (OSError,ValueError,TypeError):pass
                # Seed custody intentionally masks underlying owner failures.
                # Retain only these fixed public categories, never exception
                # text/arguments, paths, credentials or arbitrary cause strings.
                cause=error.__context__
                if (cause is not None and cause.args in (
                        ('MANAGED_WALLET_ORIGINAL_OWNER_REQUIRED',),
                        ('MANAGED_WALLET_RUNNING_JOURNAL_REQUIRED',),
                        ('MANAGED_WALLET_OWNED_CORE_UNVERIFIED',))):
                    report['backend_failure']['owner_failure_code']=cause.args[0]
                frames=[]
                tb=error.__traceback__
                while tb is not None:
                    if tb.tb_frame.f_code.co_filename.endswith('/core_supervisor.py'):
                        frames.append({'function':tb.tb_frame.f_code.co_name,'line':tb.tb_lineno})
                    tb=tb.tb_next
                if frames:report['backend_failure']['supervisor_frames']=frames
                print('Q06_SAME_CHAIN_BACKEND_FAILURE='+json.dumps(report['backend_failure']),flush=True)
                raise
    def start(index, mode, mnemonic='', existing_root=None):
        root = existing_root or lab / ('wam-fusion-core-' + secrets.token_hex(8))
        options = ({'_anchor_factory':adapter.make_anchor} if mode != 'reopen' else
                   {'keychain':adapter.reopen_anchor(root) if adapter.platform_id=='macos-arm64' else None})
        worker = WalletExecutor(lambda:ObservedBackend(
            root,core,source,shared_profile=profiles[index],**options))
        workers.append(worker)
        # Covers bounded Core bootstrap (90s) plus historical sync (120s).
        opened = worker.request('open',password,mode,mnemonic,timeout=240)
        return worker, opened, root
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
        a, opened, _ = start(0,'create')
        phrase = opened['mnemonic_once']
        a.request('acknowledge_create_pending',opened['seed_folder'],timeout=30)
        positions = (1,6,12)
        answers = tuple(phrase.split()[i-1] for i in positions)
        if a.request('backup_verify',positions,answers,timeout=30) is not True:
            raise ValueError('Q06_SAME_CHAIN_RESTORE_BACKUP_DENIED')
        answers = None
        b, unused, _ = start(1,'create')
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
        # Do not adopt/reuse an endpoint whose old TCP lifetime may remain
        # reserved after clean shutdown. The new participant initiates its
        # one manual connection to A; A's unchanged inbound peer policy still
        # attests the configured private host and exact Core subversion.
        from .shared_regtest import reserve_ports
        try:
            with reserve_ports(profiles[1]):pass
            report['retired_endpoint_available'] = True
        except OSError as error:
            if error.errno != errno.EADDRINUSE:raise
            report['retired_endpoint_available'] = False
            report['retired_endpoint_not_adopted'] = True
        restore_tip = (before['height'],before['tip'])
        c, restored, restored_root = start(2,'restore',phrase)
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
        step('RESTORED_PROFILE_CORE_RESTART_AND_HISTORY')
        stop(c)
        c, reopened, _ = start(2,'reopen',existing_root=restored_root)
        wait(lambda:state(a)['connected'] and state(c)['connected']
                       and state(c)['tip']==before['tip'])
        reopened_view = c.request('snapshot',timeout=240)
        if (reopened['mnemonic_once'] or reopened['receive_code']!=opened['receive_code']
                or reopened_view['confirmed_atoms']!=before['confirmed_atoms']
                or {row['txid'] for row in reopened_view['history']}!=expected
                or reopened_view['signer_allowed'] is not False):
            raise ValueError('Q06_SAME_CHAIN_RESTORE_POST_RESTART_HISTORY_DENIED')
        report['restored_same_owner_core_reopened'] = True
        step('RESTORED_AND_ORIGINAL_OWNERS_CLEAN_SHUTDOWN')
        stop(c)
        stop(a)
    except Exception as error:
        report['status'] = 'FAIL'
        code = error.args[0] if len(error.args)==1 and type(error.args[0]) is str else ''
        report['failure_code'] = code if re.fullmatch('[A-Z0-9_]{5,100}',code) else 'Q06_SAME_CHAIN_RESTORE_DENIED'
        print('Q06_SAME_CHAIN_RESTORE_FAILURE=' + report['failure_code'], flush=True)
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
