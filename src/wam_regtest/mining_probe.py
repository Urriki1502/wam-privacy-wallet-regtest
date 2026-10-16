"""Genuine disposable mining-account acceptance, source and frozen entrypoints.

Never accepts an owner datadir/wallet/endpoint. Core generates fixture-only keys;
only fixed public scalar/address observations leave the temporary directory.
"""
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from .core import verified_core_paths,_port,_write_private_config,_read_cli,CoreSmokeError
from .core_process import OwnedCoreBinding
from .json_rpc import ManagedReadRpc
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
    node,cli,receipt=verified_core_paths(core)
    with tempfile.TemporaryDirectory(prefix='wam-mining-owned-') as temp:
        root=Path(temp).resolve();data=root
        if sys.platform=='win32':
            from .custody import create_directory
            data=root/'chain';create_directory(data)
            from .windows_core_regtest_smoke import _host_env
            env=_host_env(data)
        else:
            data.chmod(0o700);env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','HOME':str(data),'LC_ALL':'C'}
        rpc_port,peer_port=_port(),_port()
        if rpc_port==peer_port:raise ValueError('MINING_FIXTURE_PORT_COLLISION_DENIED')
        _write_private_config(data,rpc_port,peer_port)
        proc=None
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
                'createwallet','getnewaddress','getaddressinfo','getwalletinfo','getbalances',
                'listunspent','sendtoaddress','gettransaction','lockunspent','generatetoaddress','stop'}
            if not scope or scope[0] not in allowed or any(a.startswith('-') for a in scope):
                raise ValueError('MINING_FIXTURE_RPC_SCOPE_DENIED')
            _,checked_cli,_=verify(core)
            if checked_cli!=cli:raise ValueError('MINING_FIXTURE_CLI_IDENTITY_DENIED')
            try:return _rpc(cli,data,local_rpc_port(data),env,*args,timeout=timeout)
            except (ValueError,OSError):raise CoreSmokeError('MINING_FIXTURE_WINDOWS_RPC_DENIED') from None
        try:
            with (data/'core-output.log').open('xb') as log:
                proc=subprocess.Popen([str(node),f'-datadir={data}','-daemon=0'],
                    stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                    cwd=node.parent if sys.platform=='win32' else data,env=env,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0) if sys.platform=='win32' else 0)
            deadline=time.monotonic()+90
            while True:
                if proc.poll() is not None:raise ValueError('MINING_FIXTURE_CORE_EXITED')
                try:
                    if rpc('getblockchaininfo')['chain']=='regtest':break
                except CoreSmokeError:pass
                if time.monotonic()>deadline:raise ValueError('MINING_FIXTURE_START_TIMEOUT')
                time.sleep(.2)
            binding=OwnedCoreBinding(proc,core,data)
            with ManagedReadRpc(core,data,authorized_readonly=True,binding=binding) as read:
                if read.call('getblockhash',[0])!=REGTEST_GENESIS or rpc('getconnectioncount')!=0:
                    raise ValueError('MINING_FIXTURE_NETWORK_DENIED')
                yield rpc,receipt,read
        finally:
            if proc is not None and proc.poll() is None:
                try:rpc('stop',timeout=8);proc.wait(timeout=15)
                except Exception:
                    proc.terminate()
                    try:proc.wait(timeout=8)
                    except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=8)


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
        coinbase=block['tx'][0];txid=coinbase['txid']
        own_out=next(o['n'] for o in coinbase['vout'] if o['scriptPubKey']['hex']==owned['scriptPubKey'])
        rpc('generatetoaddress','98',external);maturity=[]
        for depth in (99,100,101):
            if rpc('getblockcount')!=depth:raise ValueError('MINER_DEPTH_DENIED')
            utxo=rpc('gettxout',txid,str(own_out));b=balance()
            if utxo['confirmations']!=depth or utxo['coinbase'] is not True:raise ValueError('MINER_COINBASE_UTXO_DENIED')
            if depth<101:
                if (b.available_atoms,b.trusted_atoms,b.immature_atoms)!=(0,0,4750000000):raise ValueError('MINER_EARLY_AVAILABLE_DENIED')
                before=rpc('getrawmempool')
                try:wallet('sendtoaddress',external,'0.00100000')
                except CoreSmokeError:pass
                else:raise ValueError('MINER_EARLY_WALLET_SPEND_ACCEPTED')
                if rpc('getrawmempool')!=before or balance()!=b:raise ValueError('MINER_REFUSED_SPEND_MUTATED')
                accepted=False
            else:
                if (b.available_atoms,b.trusted_atoms,b.immature_atoms)!=(4750000000,4750000000,0):raise ValueError('MINER_MATURE_AVAILABLE_DENIED')
                payment=wallet('sendtoaddress',external,'0.00100000');accepted=True
                if payment not in rpc('getrawmempool'):raise ValueError('MINER_MATURE_PAYMENT_NOT_ACCEPTED')
            maturity.append({'depth':depth,'balance_before_send':asdict(b),'wallet_send_accepted':accepted})
            if view is not None:
                view.render_snapshot(read.mining_snapshot(authorized_readonly=True));app.processEvents()
                directory=Path('fusion-ui-review');directory.mkdir(exist_ok=True)
                name=f"{receipt['platform']}-mining-depth-{depth}.png"
                if not view.widget.grab().save(str(directory/name)):raise ValueError('MINING_GUI_CAPTURE_DENIED')
                gui_depths.append(depth);screenshots.append(name)
            if depth<101:rpc('generatetoaddress','1',external)
        fee=rpc_atoms(abs(wallet('gettransaction',payment)['fee']))
        paid_block=rpc('generatetoaddress','1',address)[0];_,fee_audit=audit(paid_block,fee)
        if fee<=0 or fee_audit.owned_miner_atoms!=4750000000+fee or fee_audit.treasury_paid_atoms!=250000000:
            raise ValueError('MINER_FEE_ALLOCATION_DENIED')
        after=balance()
        if after.immature_atoms!=4750000000+fee or after.available_atoms!=4750000000-100000-fee:
            raise ValueError('MINER_POST_PAYMENT_BALANCE_DENIED')
        # Exercise actual Core UTXO lock eligibility; never Fusion signed/
        # uncertain reservation release. Only this generated Core fixture.
        coins=wallet('listunspent','0');change=next(u for u in coins if u['txid']==payment)
        import json
        lock=json.dumps([{'txid':change['txid'],'vout':change['vout']}],separators=(',',':'))
        if wallet('lockunspent','false',lock) is not True:raise ValueError('MINER_LOCK_DENIED')
        locked=balance()
        if locked.available_atoms!=0 or locked.trusted_atoms!=after.trusted_atoms:raise ValueError('MINER_LOCKED_BALANCE_DENIED')
        if wallet('lockunspent','true',lock) is not True or balance()!=after:raise ValueError('MINER_FIXTURE_UNLOCK_DENIED')
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
        return {'status':'REAL_CORE_REGTEST_MINING_ACCOUNT_MATURITY_PASS','platform':receipt['platform'],
            'core_version':'v0.1.11','wamd_sha256':receipt['wamd_sha256'],'wam_cli_sha256':receipt['wam_cli_sha256'],
            'owned_http_matches_independent_cli':True,'http_without_cli_or_full_rehash':True,
            'native_gui_depths':gui_depths,'gui_stale_values_cleared':gui,
            'gui_screenshots':screenshots,'physical_appearance_acceptance':'PENDING_OPERATOR',
            'regtest_halving_interval':150,'treasury_last_height':400000,'maturity':maturity,
            'coinbase_audits':boundaries,'fee_atoms':fee,'after_payment_balance':asdict(after),
            'locked_available_atoms':locked.available_atoms,'treasury_owned_by_fixture':False,
            'source_main_schedule_200000_is_not_regtest_interval':True,'sunset_height_runtime_qualified':False,
            'no_fusion_reservation_released':True,'elapsed_seconds':round(time.monotonic()-start,3),
            'synthetic_rpc':False,'owner_data_accessed':False,'mainnet_allowed':False,
            'core_wallet_probe_not_bip39_signer_qualification':True}
