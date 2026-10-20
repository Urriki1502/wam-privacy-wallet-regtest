"""Genuine disposable mining-account acceptance, source and frozen entrypoints.

Never accepts an owner datadir/wallet/endpoint. Core generates fixture-only keys;
only fixed public scalar/address observations leave the temporary directory.
"""
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
import sys
import time
from .core import _read_cli,CoreSmokeError
from .mining_account import CoinbaseAudit,MiningWalletBalance,RewardSplit,COIN
from .v1_contracts import rpc_atoms
from .wsp_live import REGTEST_GENESIS,public_regtest_mining_address


@contextmanager
def _presentation(enabled):
    if not enabled:
        yield None,None;return
    from .desktop import qt_application
    from .mining_gui import MiningAccountPage
    from .fusion_ui import fusion_stylesheet
    from PySide6.QtCore import QCoreApplication,QEvent
    app=qt_application();prior=app.quitOnLastWindowClosed();view=None
    app.setQuitOnLastWindowClosed(False)
    try:
        view=MiningAccountPage();view.widget.setStyleSheet(fusion_stylesheet('dark'))
        view.widget.resize(960,760);view.widget.show();app.processEvents()
        yield app,view
    finally:
        if view is not None:
            view.widget.close();view.widget.deleteLater()
            QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
            app.processEvents()
        app.setQuitOnLastWindowClosed(prior)


@contextmanager
def _owned_chain(core):
    from .owned_start import disposable_core
    with disposable_core(core,authorized=True) as owned:
        data,cli,receipt,env=owned.directory,owned.cli,owned.receipt,owned.environment
        def rpc(*args,timeout=30):
            if sys.platform!='win32':return _read_cli([str(cli),f'-datadir={data}',*args],timeout=timeout)
            # This private acceptance context owns a newly generated datadir,
            # process and test wallet. Do not broaden the application's CLI
            # allowlist to grant mining-fixture wallet mutation to ordinary UI.
            from .windows_core_transport import verified_core_paths as verify,local_rpc_port
            from .windows_core_regtest_smoke import _rpc
            scope=args[1:] if args and args[0]=='-rpcwallet=test' else args
            allowed={'getblockchaininfo','getconnectioncount','getblockcount','getblock',
                'getrawmempool','gettxout','getdevfeeinfo','getemissionschedule',
                'getnetworkinfo','getmempoolinfo','getmempoolentry','estimatesmartfee',
                'createwallet','getnewaddress','getaddressinfo','getwalletinfo','getbalances','validateaddress',
                'listunspent','listlockunspent','sendtoaddress','gettransaction','lockunspent','generatetoaddress','stop'}
            if not scope or scope[0] not in allowed or any(a.startswith('-') for a in scope):
                raise ValueError('MINING_FIXTURE_RPC_SCOPE_DENIED')
            _,checked_cli,_=verify(core)
            if checked_cli!=cli:raise ValueError('MINING_FIXTURE_CLI_IDENTITY_DENIED')
            try:return _rpc(cli,data,local_rpc_port(data),env,*args,timeout=timeout)
            except (ValueError,OSError):raise CoreSmokeError('MINING_FIXTURE_WINDOWS_RPC_DENIED') from None
        yield rpc,receipt,owned.read


def probe_core_mining(core,source,*,gui=False):
    if type(gui) is not bool:raise ValueError('MINING_GUI_SCOPE_DENIED')
    try:return _probe_core_mining(core,source,gui=gui)
    except Exception as error:
        from .acceptance_failure import failure_site
        print('MINING_FAILURE_SITE='+failure_site(error),flush=True)
        raise


def _probe_core_mining(core,source,*,gui=False):
    start=time.monotonic();external=public_regtest_mining_address(source)
    gui_depths=[];screenshots=[]
    with _presentation(gui) as (app,view), _owned_chain(core) as (rpc,receipt,read):
        rpc('createwallet','test')
        # F-07: use public-only Base58Check fixtures with zero private
        # keys or source-controlled real user wallet. These are REGTEST
        # address types and a negative mainnet version mismatch, not a
        # claim to have started or queried a mainnet Core.
        from .f07_address_parity import (
            inspect_legacy_public,verify_core_regtest_legacy,
        )
        regtest_legacy_cases=(
            'TBDeDSETJdmttTFUwFVL8Qpw4SV87XAYEj',
            'tjtGH5pUR8i7GweABGcPgFzic8Fv8mYLvq',
        )
        for public_address in regtest_legacy_cases:
            public_facts=inspect_legacy_public(public_address,network='regtest')
            checked=verify_core_regtest_legacy(
                public_address,core_reply=rpc('validateaddress',public_address))
            if (not checked.address_accepted_by_core
                    or not checked.expected_script_matches_core
                    or public_facts.core_bech32_prefix_collision):
                raise ValueError('F07_REAL_CORE_REGTEST_ADDRESS_PARITY_DENIED')
        collision_fixtures=(
            'WamAskWnsuS1LBhLhgGQSo9HACyE4aHLER',
            'waMSB1joxWLA9nFTHpNT9HHKpavsLW7WXG',
        )
        for public_address in collision_fixtures:
            offline=inspect_legacy_public(public_address,network='main')
            invalid_on_regtest=rpc('validateaddress',public_address)
            if (not offline.core_bech32_prefix_collision
                    or type(invalid_on_regtest) is not dict
                    or invalid_on_regtest.get('isvalid') is not False):
                raise ValueError('F07_MAINNET_ADDRESS_ON_REGTEST_NOT_REFUSED')
        def wallet(*args):return rpc('-rpcwallet=test',*args)
        address=wallet('getnewaddress');owned=wallet('getaddressinfo',address)
        if owned['ismine'] is not True:raise ValueError('MINER_OWNERSHIP_REQUIRED')
        treasury=rpc('getdevfeeinfo');wallet_info=wallet('getwalletinfo')
        if wallet('getaddressinfo',treasury['address'])['ismine'] is not False:
            raise ValueError('MINER_TREASURY_OWNERSHIP_DENIED')
        def audit(blockhash,fees=0):
            block=rpc('getblock',blockhash,'2');core_audit=rpc('getdevfeeinfo',blockhash)['block']
            result=CoinbaseAudit.from_core(chain='regtest',genesis=REGTEST_GENESIS,block=block,
                treasury_info=treasury,owned_address_infos=[owned],fees=fees)
            if (core_audit['compliant'] is not True or rpc_atoms(core_audit['subsidy'])!=result.subsidy_atoms
                    or rpc_atoms(core_audit['paid'])!=result.treasury_paid_atoms):raise ValueError('MINER_CORE_AUDIT_MISMATCH')
            return block,result
        def balance():
            unspent=wallet('listunspent','0');outputs={}
            for u in unspent:
                out=rpc('gettxout',u['txid'],str(u['vout']))
                if out is None:raise ValueError('MINER_UTXO_CHANGED')
                outputs[(u['txid'],u['vout'])]=out
            expected=MiningWalletBalance.from_core(chain='regtest',genesis=REGTEST_GENESIS,
                wallet_info=wallet_info,balances=wallet('getbalances'),unspent=unspent,
                txouts=outputs,treasury_script=treasury['script'])
            # These guards only forbid CLI/full-image hashing. Every result is
            # from the genuine authenticated owned Core HTTP endpoint.
            from unittest.mock import patch
            with patch('wam_regtest.core._read_cli',side_effect=AssertionError('MINING_READ_CLI_FORBIDDEN')), \
                 patch('wam_regtest.core_process.verified_core_paths',side_effect=AssertionError('MINING_READ_REHASH_FORBIDDEN')):
                snapshot=read.mining_snapshot(authorized_readonly=True)
            if snapshot.balance!=expected:raise ValueError('MINING_HTTP_CLI_DISAGREE')
            if view is not None:
                from .wallet_read import format_wam
                view.render_snapshot(snapshot);app.processEvents()
                for field,widget in view.values.items():
                    if widget.text()!=format_wam(getattr(expected,field))+' WAM':raise ValueError('MINING_GUI_AMOUNT_MISMATCH')
                view.render_snapshot(None)
                if any(widget.text()!='—' for widget in view.values.values()):raise ValueError('MINING_GUI_STALE_AMOUNT')
            return expected
        first=rpc('generatetoaddress','1',address)[0];block,first_audit=audit(first)
        if first_audit.owned_miner_atoms!=4750000000 or first_audit.treasury_paid_atoms!=250000000:
            raise ValueError('MINER_FIRST_REWARD_DENIED')
        # F-01 adversarial verification anchored in a GENUINE Core coinbase.
        # Mutate only an in-memory copy of the public RPC response: changing
        # the miner's output script must never create a false wallet balance.
        from copy import deepcopy
        wrong_script='0014'+'ee'*20
        if wrong_script in (owned['scriptPubKey'],treasury['script']):
            raise ValueError('F01_PUBLIC_FIXTURE_COLLISION_DENIED')
        forged=deepcopy(block)
        original_miner=next(
            item for item in forged['tx'][0]['vout']
            if item['scriptPubKey']['hex']==owned['scriptPubKey'])
        original_miner['scriptPubKey']['hex']=wrong_script
        try:
            CoinbaseAudit.from_core(
                chain='regtest',genesis=REGTEST_GENESIS,block=forged,
                treasury_info=treasury,owned_address_infos=[owned],fees=0)
        except ValueError as error:
            if str(error)!='MINER_COINBASE_AUDIT_DENIED':
                raise
        else:
            raise ValueError('F01_REAL_CORE_UNOWNED_REWARD_ACCEPTED')
        coinbase=block['tx'][0];txid=coinbase['txid']
        own_out=next(o['n'] for o in coinbase['vout'] if o['scriptPubKey']['hex']==owned['scriptPubKey'])
        rpc('generatetoaddress','98',external);maturity=[]
        for depth in (99,100,101):
            if rpc('getblockcount')!=depth:raise ValueError('MINER_DEPTH_DENIED')
            utxo=rpc('gettxout',txid,str(own_out));b=balance()
            if utxo['confirmations']!=depth or utxo['coinbase'] is not True:raise ValueError('MINER_COINBASE_UTXO_DENIED')
            # F-02: independently bind *this* owned coinbase UTXO, native
            # Core chain height, and Core wallet's immature/available model.
            # A coincidentally rejected RPC is not maturity evidence.
            from .f02_maturity import DisposableCoinbaseMaturity
            f02=DisposableCoinbaseMaturity.from_core(
                chain='regtest',genesis=REGTEST_GENESIS,
                height=rpc('getblockcount'),origin_height=1,
                utxo=utxo,wallet_balance=b,
                owned_script=owned['scriptPubKey'],
                miner_atoms=first_audit.owned_miner_atoms)
            if f02.depth!=depth or f02.wallet_send_allowed_by_maturity!=(depth==101):
                raise ValueError('F02_MATURITY_PROOF_MISMATCH')
            if depth<101:
                if (b.available_atoms,b.trusted_atoms,b.immature_atoms)!=(0,0,4750000000):raise ValueError('MINER_EARLY_AVAILABLE_DENIED')
                before=rpc('getrawmempool')
                try:wallet('sendtoaddress',external,'0.00100000')
                except CoreSmokeError:pass
                else:raise ValueError('MINER_EARLY_WALLET_SPEND_ACCEPTED')
                # The node must still serve the same wallet/chain after the
                # negative send; network/transport failures cannot stand in
                # for a genuine immature-coinbase refusal.
                current_wallet=wallet('getwalletinfo')
                if (current_wallet.get('walletname')!='test'
                        or current_wallet.get('format')!='sqlite'
                        or current_wallet.get('descriptors') is not True
                        or current_wallet.get('private_keys_enabled') is not True
                        or rpc('getblockcount')!=depth
                        or rpc('getrawmempool')!=before
                        or balance()!=b):
                    raise ValueError('F02_IMMATURE_CORE_STATE_CHANGED')
                accepted=False
            else:
                if (b.available_atoms,b.trusted_atoms,b.immature_atoms)!=(4750000000,4750000000,0):raise ValueError('MINER_MATURE_AVAILABLE_DENIED')
                # F-03: the real Core wallet must reject an obviously
                # sub-dust 1-atom output before the legitimate test payment.
                # Check no mempool or trusted/available balance mutation.
                before_dust=rpc('getrawmempool')
                try:wallet('sendtoaddress',external,'0.00000001')
                except CoreSmokeError:pass
                else:raise ValueError('F03_REAL_CORE_SUBDUST_ACCEPTED')
                if rpc('getrawmempool')!=before_dust or balance()!=b:
                    raise ValueError('F03_SUBDUST_REFUSAL_STATE_CHANGED')
                payment=wallet('sendtoaddress',external,'0.00100000');accepted=True
                if payment not in rpc('getrawmempool'):raise ValueError('MINER_MATURE_PAYMENT_NOT_ACCEPTED')
            if accepted!=f02.wallet_send_allowed_by_maturity:
                raise ValueError('F02_DISPOSABLE_CORE_SEND_DISAGREE')
            maturity.append({'depth':depth,'balance_before_send':asdict(b),
                             'wallet_send_accepted':accepted,
                             'f02_core_maturity_witness':asdict(f02)})
            if view is not None:
                view.render_snapshot(read.mining_snapshot(authorized_readonly=True));app.processEvents()
                directory=Path('fusion-ui-review');directory.mkdir(exist_ok=True)
                name=f"{receipt['platform']}-mining-depth-{depth}.png"
                if not view.widget.grab().save(str(directory/name)):raise ValueError('MINING_GUI_CAPTURE_DENIED')
                gui_depths.append(depth);screenshots.append(name)
            if depth<101:rpc('generatetoaddress','1',external)
        fee=rpc_atoms(abs(wallet('gettransaction',payment)['fee']))
        # F-03: genuine accepted Core transaction's fee/vsize and the
        # locally authenticated Core relay/mempool minimum fee policies.
        # Do not infer a fee from a block finder or a Bitcoin default.
        from .f03_fee_policy import CoreFeeWitness,optional_core_estimate
        f03=CoreFeeWitness.from_core(
            network_info=rpc('getnetworkinfo'),
            mempool_info=rpc('getmempoolinfo'),
            entry=rpc('getmempoolentry',payment),
            actual_fee_atoms=fee)
        if not f03.mempool_entry_relay_eligible:
            raise ValueError('F03_CORE_RELAY_POLICY_DENIED')
        try:
            estimate=rpc('estimatesmartfee','2')
        except CoreSmokeError:
            # No fabricated fee estimate after an unsupported/insufficient
            # estimator response from a short isolated REGTEST chain.
            estimate=None
            estimate_rpc_unavailable=True
        else:
            estimate_rpc_unavailable=False
        if estimate is None:
            estimate_available=False
            estimate_rate=None
        else:
            estimate_available,estimate_rate=optional_core_estimate(estimate)
        paid_block=rpc('generatetoaddress','1',address)[0];_,fee_audit=audit(paid_block,fee)
        if fee<=0 or fee_audit.owned_miner_atoms!=4750000000+fee or fee_audit.treasury_paid_atoms!=250000000:
            raise ValueError('MINER_FEE_ALLOCATION_DENIED')
        after=balance()
        if after.immature_atoms!=4750000000+fee or after.available_atoms!=4750000000-100000-fee:
            raise ValueError('MINER_POST_PAYMENT_BALANCE_DENIED')
        # Exercise actual Core UTXO lock eligibility; never Fusion signed/
        # uncertain reservation release. Only this generated Core fixture.
        coins=wallet('listunspent','0');change=next(u for u in coins if u['txid']==payment)
        from .f04_funds import CoreFundsBuckets
        change_owner=wallet('getaddressinfo',change['address'])
        if (change_owner.get('ismine') is not True
                or change_owner.get('scriptPubKey')!=change['scriptPubKey']):
            raise ValueError('F04_CORE_CHANGE_OWNER_DENIED')
        if wallet('listlockunspent')!=[]:
            raise ValueError('F04_PREEXISTING_CORE_LOCK_DENIED')
        unlocked_funds=CoreFundsBuckets.from_core(
            chain='regtest',genesis=REGTEST_GENESIS,balance=after,
            locked_outpoints=[],locked_txouts={},
            unlocked_outpoints=coins,owned_script=change['scriptPubKey'],
            treasury_script=treasury['script'])
        if (unlocked_funds.locked_core_atoms!=0 or
                unlocked_funds.available_atoms!=after.available_atoms):
            raise ValueError('F04_CORE_UNLOCKED_BUCKETS_DENIED')
        import json
        lock=json.dumps([{'txid':change['txid'],'vout':change['vout']}],separators=(',',':'))
        if wallet('lockunspent','false',lock) is not True:raise ValueError('MINER_LOCK_DENIED')
        locked=balance()
        if locked.available_atoms!=0 or locked.trusted_atoms!=after.trusted_atoms:raise ValueError('MINER_LOCKED_BALANCE_DENIED')
        locked_points=wallet('listlockunspent')
        if locked_points!=[{'txid':change['txid'],'vout':change['vout']}]:
            raise ValueError('F04_CORE_LOCK_OUTPOINT_MISMATCH')
        locked_txout=rpc('gettxout',change['txid'],str(change['vout']))
        core_locked=CoreFundsBuckets.from_core(
            chain='regtest',genesis=REGTEST_GENESIS,balance=locked,
            locked_outpoints=locked_points,
            locked_txouts={(change['txid'],change['vout']):locked_txout},
            unlocked_outpoints=wallet('listunspent','0'),
            owned_script=change['scriptPubKey'],
            treasury_script=treasury['script'])
        if (core_locked.locked_core_atoms!=after.available_atoms or
                core_locked.immature_atoms!=after.immature_atoms or
                core_locked.available_atoms!=0 or
                core_locked.unattributed_trusted_atoms!=0):
            raise ValueError('F04_CORE_LOCKED_BUCKETS_DENIED')
        if wallet('lockunspent','true',lock) is not True or balance()!=after:raise ValueError('MINER_FIXTURE_UNLOCK_DENIED')
        if wallet('listlockunspent')!=[]:
            raise ValueError('F04_CORE_UNLOCK_RECORD_RETAINED')
        boundaries=[asdict(first_audit),asdict(fee_audit)]
        for height in (150,151,300,301,450,451):
            count=height-rpc('getblockcount')
            hashes=rpc('generatetoaddress',str(count),address,timeout=90)
            _,result=audit(hashes[-1]);boundaries.append(asdict(result))
            split=RewardSplit.regtest(height)
            if result.owned_miner_atoms!=split.miner_atoms:raise ValueError('MINER_HALVING_BOUNDARY_DENIED')
        schedule=rpc('getemissionschedule')
        if [(x['first_height'],x['last_height']) for x in schedule[:3]]!=[(1,150),(151,300),(301,450)]:raise ValueError('MINER_REGTEST_INTERVAL_DENIED')
        if rpc('getconnectioncount')!=0:raise ValueError('MINER_EXTERNAL_PEERS_DENIED')
        # F-09: 64 bounded sequential reads through the real authenticated
        # persistent HTTP transport, on this disposable owned Core only.
        # No additional CLI subprocess, daemon restart, network peer or
        # wallet mutation; a short CI soak does not prove days of uptime.
        from .f09_operational_soak import verify_owned_core_read_soak
        observed_height=read.call('getblockcount')
        observed_tip=read.call('getbestblockhash')
        observed_genesis=read.call('getblockhash',[0])
        f09=verify_owned_core_read_soak(
            call=read.call,expected_genesis=observed_genesis,
            height=observed_height,tip=observed_tip)
        if (f09.cycles_completed!=64 or f09.read_only_rpc_calls!=192
                or not f09.stable_tip or f09.long_hours_days_qualified):
            raise ValueError('F09_GENUINE_CORE_SOAK_DENIED')
        if rpc('getblockcount')!=observed_height or rpc('getconnectioncount')!=0:
            raise ValueError('F09_SOAK_CHANGED_CHAIN_OR_PEERS')
        return {'status':'REAL_CORE_REGTEST_MINING_ACCOUNT_MATURITY_PASS','platform':receipt['platform'],
            'core_version':'v0.1.11','wamd_sha256':receipt['wamd_sha256'],'wam_cli_sha256':receipt['wam_cli_sha256'],
            'owned_http_matches_independent_cli':True,'http_without_cli_or_full_rehash':True,
            'native_gui_depths':gui_depths,'gui_stale_values_cleared':gui,
            'gui_screenshots':screenshots,'physical_appearance_acceptance':'PENDING_OPERATOR',
            'regtest_halving_interval':150,'treasury_last_height':400000,'maturity':maturity,
            'coinbase_audits':boundaries,'fee_atoms':fee,'after_payment_balance':asdict(after),
            'f03_real_core_mempool_fee_and_vsize':asdict(f03),
            'f03_estimate_available':estimate_available,
            'f03_estimate_atoms_per_kvb':estimate_rate,
            'f03_estimate_rpc_unavailable':estimate_rpc_unavailable,
            'f03_target_seconds_from_pinned_consensus_source':120,
            'f03_confirmation_time_guaranteed':False,
            'f03_policy_not_applied_to_actual_user_wallet':True,
            'f03_native_core_one_atom_dust_send_refused_without_mutation':True,
            'f01_real_core_unowned_miner_script_negative_denied':True,
            'f01_all_miner_fees_core_owned_and_treasury_separate':True,
            'locked_available_atoms':locked.available_atoms,'treasury_owned_by_fixture':False,
            'f04_genuine_core_before_lock':asdict(unlocked_funds),
            'f04_genuine_core_after_lock':asdict(core_locked),
            'f04_core_lock_proof_from_listlockunspent_and_gettxout':True,
            'f04_core_unlock_restored_only_eligibility_not_new_money':True,
            'f04_wsp_reservations_not_conflated_with_core_coinlocks':True,
            'source_main_schedule_200000_is_not_regtest_interval':True,'sunset_height_runtime_qualified':False,
            'f02_real_core_immature_99_100_and_mature_101_verified':True,
            'f02_no_early_send_or_mempool_mutation':True,
            'f02_no_general_wallet_signer_authority':True,
            'f07_genuine_regtest_p2pkh_p2sh_validateaddress_parity':True,
            'f07_mainnet_collision_public_fixture_network_refusal_regtest':True,
            'f07_native_mainnet_parser_runtime_qualified':False,
            'f07_public_only_no_import_private_key_or_node_network':True,
            'f09_genuine_core_bounded_read_soak':asdict(f09),
            'f09_long_hours_days_runtime_qualified':False,
            'f09_multi_node_peer_sync_qualified':False,
            'f09_low_disk_resource_pressure_qualified':False,
            'no_fusion_reservation_released':True,'elapsed_seconds':round(time.monotonic()-start,3),
            'synthetic_rpc':False,'owner_data_accessed':False,'mainnet_allowed':False,
            'core_wallet_probe_not_bip39_signer_qualification':True}
