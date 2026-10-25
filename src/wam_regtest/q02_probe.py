"""Disposable Q02 acceptance. No owner state, fake node or automatic repair."""
import secrets
from .rpc_credentials import CredentialSource


def probe_gui_auth_loss(app,window):
    """Actual signed CLI receives authentication failure from genuine Core."""
    from PySide6.QtCore import QEventLoop,QTimer,QCoreApplication,QEvent
    from .wallet_probe import _await_gui_idle
    from .rpc_scope import _contexts,reauthenticate_owned
    _await_gui_idle(app,window)
    session=window.session
    accounts=session.ring.accounts()
    rows=tuple(tuple(r) for r in session.scanner.store.db.execute('SELECT * FROM reservations'))
    anchor=session.vault.anchor.read()
    context=_contexts[str(session.datadir.resolve(strict=True))]
    config=session.datadir/'wam.conf';original=config.read_bytes()
    # Deliberate fixture-only credential change plus fresh credential snapshot:
    # permits sending wrong auth to the VERIFIED genuine Core to prove its
    # actual rejection. Ordinary runtime changes instead fail snapshot custody.
    changed=b'\n'.join(b'rpcpassword='+secrets.token_hex(32).encode() if l.startswith(b'rpcpassword=') else l
                       for l in original.splitlines())+b'\n'
    loop=QEventLoop();deadline=QTimer();deadline.setSingleShot(True);denied=[]
    def failed(code):denied.append(code);loop.quit()
    window.snapshot_failed.connect(failed);deadline.timeout.connect(loop.quit)
    try:
        config.write_bytes(changed);context.credentials=CredentialSource(session.datadir)
        deadline.start(15000);QTimer.singleShot(0,window.request_sync);loop.exec()
        if window._worker is not None:assert window._worker.wait(15000)
        app.processEvents();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        assert denied and window._snapshot is None and window.balance_text.text()=='—','Q02_GUI_UNVERIFIED_VIEW_REQUIRED'
        assert session.faulted,'Q02_GUI_AUTH_FAILURE_MUST_FAULT_WALLET'
        assert not any(b.isEnabled() for b in (window.prepare_button,window.sign_button,window.broadcast_button)),'Q02_GUI_MUTATIONS_MUST_BE_DISABLED'
        assert denied==['WALLET_CORE_AUTHENTICATION_DENIED'],'Q02_GUI_SAFE_AUTH_CATEGORY_REQUIRED'
        assert session.ring.accounts()==accounts and session.vault.anchor.read()==anchor
        assert tuple(tuple(r) for r in session.scanner.store.db.execute('SELECT * FROM reservations'))==rows
    finally:
        deadline.stop();window.snapshot_failed.disconnect(failed)
        config.write_bytes(original)
        # Explicit test-operator action. No automatic runtime refresh, unlock,
        # anchor reset, write replay or uncertain-reservation release.
        reauthenticate_owned(session.datadir,authorized=True)
    assert session.faulted and window._snapshot is None
    return {'real_core_cli_auth_failure_gui_fail_closed':True,
        'original_accounts_anchor_reservations_retained':True,
        'explicit_transport_reauthentication_did_not_unlock_wallet':True,'synthetic_rpc':False}

from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from . import cli_rpc
from .core import _read_cli,_port,_write_private_config,verified_core_paths,CoreSmokeError
from .cli_rpc import CliRpcError
from .rpc_scope import register,unregister,reauthenticate_owned,identity
from .wsp_live import LiveCoreReadOnlyCli,RealWspScanError,REGTEST_GENESIS


class Q02ProbeError(ValueError):pass


def _expect(codes,action):
    try:action()
    except (CoreSmokeError,CliRpcError,RealWspScanError) as error:
        if error.args and error.args[0] in codes:return error.args[0]
        raise Q02ProbeError('Q02_UNEXPECTED_FIXED_REFUSAL') from None
    raise Q02ProbeError('Q02_REQUIRED_REFUSAL_MISSING')


class _Node:
    def __init__(self,core,*,cookie=False):
        self.core=core;self.cookie=cookie;self.proc=None
        self.temp=tempfile.TemporaryDirectory(prefix='wam-q02-owned-')
        self.root=Path(self.temp.name).resolve(strict=True);self.directory=self.root/'chain'
        from .custody import create_directory
        create_directory(self.directory)
        self.node,self.cli,self.receipt=verified_core_paths(core)
        self.port=_port();peer=_port()
        if self.port==peer:raise Q02ProbeError('Q02_PORT_COLLISION')
        _write_private_config(self.directory,self.port,peer)
        self.config=self.directory/'wam.conf'
        if cookie:
            # Fresh owned environment only. Use the existing strict native
            # owner/ACL constructor for the Core cookie parent; never repair
            # or relax custody on an existing external/owner directory.
            create_directory(self.directory/'regtest')
            raw=b'\n'.join(l for l in self.config.read_bytes().splitlines()
                if not l.startswith((b'rpcuser=',b'rpcpassword=')))+b'\n'
            self.config.write_bytes(raw)
        self.original=self.config.read_bytes()
    def call(self,*args,timeout=15):
        return _read_cli([str(self.cli),'-datadir='+str(self.directory),*args],timeout=timeout)
    def start(self):
        if sys.platform=='win32':
            from .windows_core_regtest_smoke import _host_env
            env=_host_env(self.directory)
        else:env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','HOME':str(self.directory),'LC_ALL':'C'}
        with (self.directory/('node-'+secrets.token_hex(4)+'.log')).open('xb') as log:
            self.proc=subprocess.Popen([str(self.node),'-datadir='+str(self.directory),'-daemon=0'],
                cwd=self.node.parent if sys.platform=='win32' else self.directory,env=env,
                stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0) if sys.platform=='win32' else 0)
        register(self.proc,self.core,self.directory,authorized_disposable_mutation=True)
        deadline=time.monotonic()+30;refusals=set()
        print('Q02_OWNED_BOOT_MODE='+('cookie' if self.cookie else 'config'),flush=True)
        while time.monotonic()<deadline:
            if self.proc.poll() is not None:raise Q02ProbeError('Q02_OWNED_NODE_EARLY_EXIT')
            try:
                assert self.call('getblockcount')==0
                return self
            except CoreSmokeError as error:
                code=error.args[0] if len(error.args)==1 else None
                allowed=('CORE_RPC_UNAVAILABLE','CORE_RPC_WARMUP','CORE_RPC_SCOPE_FAULTED',
                    'CORE_RPC_CREDENTIAL_CHANGED_OR_UNSAFE','CORE_RPC_PROCESS_IDENTITY_DENIED',
                    'CORE_RPC_AUTHENTICATION_DENIED','CORE_LOCAL_NETWORK_POLICY_DENIED',
                    'CORE_LOCAL_RPC_COMMAND_DENIED','CORE_RPC_DENIED')
                if code in allowed and code not in refusals:
                    refusals.add(code);print('Q02_BOOT_FIXED_REFUSAL='+code,flush=True)
                time.sleep(.1)
        # Diagnose only credential metadata on this owned fixture; never print
        # cookie/config contents, SID, datadir, process arguments or node logs.
        try:CredentialSource(self.directory).attest()
        except Exception as error:
            code=error.args[0] if len(error.args)==1 else None
            if code in ('RPC_CREDENTIAL_CUSTODY_DENIED','RPC_CREDENTIAL_MISSING_OR_UNSAFE',
                        'RPC_CREDENTIAL_SIZE_DENIED','RPC_COOKIE_FORMAT_DENIED','RPC_CONFIG_PROFILE_DENIED'):
                print('Q02_BOOT_CREDENTIAL_REFUSAL='+code,flush=True)
        raise Q02ProbeError('Q02_NODE_START_TIMEOUT')
    def reader(self):
        client=LiveCoreReadOnlyCli(self.cli,self.directory);client.attest();return client
    def state(self):
        return (self.call('getblockcount'),self.call('getbestblockhash'),
                tuple(self.call('listwallets')),tuple(self.call('getrawmempool')))
    def reauth(self):reauthenticate_owned(self.directory,authorized=True)
    def stop(self):
        if self.proc is not None:
            if self.proc.poll() is None:
                try:self.call('stop',timeout=5)
                except CoreSmokeError:pass
                try:self.proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    self.proc.terminate()
                    try:self.proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait(timeout=10)
            unregister(self.directory)
    def close(self):self.stop();self.temp.cleanup()
    def __enter__(self):
        try:return self.start()
        except Exception:self.close();raise
    def __exit__(self,*_):self.close()


@contextmanager
def _fault(method,mutate):
    """Negative output injection AFTER validation of the actual signed CLI reply.

    No synthetic server, fabricated positive history or substitute for real Core.
    CLI exposes result text, not the HTTP JSON-RPC envelope.
    """
    original=cli_rpc.decode;observed=[]
    def altered(raw,actual,params):
        value=original(raw,actual,params)
        if actual==method:
            observed.append(True)
            return original(mutate(raw,value),actual,params)
        return value
    cli_rpc.decode=altered
    try:yield observed
    finally:cli_rpc.decode=original


def probe(core):
    node,cli,receipt=verified_core_paths(core)
    originals={p.name:sha256(p.read_bytes()).hexdigest() for p in (node,cli)}
    records=[];stage='CONFIG-AUTH';injection_argv=None
    def case(name,action,*,fault=False):
        nonlocal stage
        stage=name;print('Q02_CASE='+name,flush=True);action()
        records.append({'case':name,'status':'PASS','genuine_core_observed':True,
            'negative_fault_injected':fault,
            'fault_scope':'after_validated_genuine_cli_result' if fault else None})
    try:
        with _Node(core) as a,_Node(core,cookie=True) as c:
            before=a.state();cbefore=c.state()
            assert before==(0,REGTEST_GENESIS,(),()) and cbefore==before
            case('CONFIG-AUTH',lambda: a.reader())
            case('COOKIE-AUTH',lambda: c.reader())
            case('CHAIN-GENESIS',lambda: a.reader())
            def fault_attest(method,mutate,code):
                rpc=a.reader()
                with _fault(method,mutate) as observed:_expect((code,),rpc.attest)
                assert observed and rpc._genesis is None
                _expect(('WSP_LIVE_METHOD_DENIED',),lambda:rpc.call('getblockcount'))
            version=a.call('getnetworkinfo')
            assert (version['version'],version['subversion'],version['protocolversion'])==(111,'/WAM:0.1.11/',70016)
            def version_faults():
                for key,bad in (('version',112),('version',111.0),('subversion','/WAM:0.1.12/'),('protocolversion',0)):
                    fault_attest('getnetworkinfo',lambda raw,v:json.dumps({**v,key:bad}).encode(),'WSP_LIVE_VERSION_DENIED')
            case('RPC-VERSION',version_faults,fault=True)
            case('PEERS',lambda:fault_attest('getconnectioncount',lambda *_:b'1','WSP_LIVE_PEERS_DENIED'),fault=True)
            def wrong_auth(key):
                raw=b'\n'.join((key+b'='+('disposable_'+secrets.token_hex(8) if key==b'rpcuser' else secrets.token_hex(32)).encode())
                    if l.startswith(key+b'=') else l for l in a.original.splitlines())+b'\n'
                try:
                    a.config.write_bytes(raw)
                    identity(a.directory).credentials=CredentialSource(a.directory)
                    _expect(('CORE_RPC_AUTHENTICATION_DENIED',),lambda:a.call('getblockcount'))
                    _expect(('CORE_RPC_SCOPE_FAULTED',),lambda:a.call('getblockcount'))
                finally:a.config.write_bytes(a.original);a.reauth()
            case('BAD-USER',lambda:wrong_auth(b'rpcuser'))
            case('BAD-PASSWORD',lambda:wrong_auth(b'rpcpassword'))
            cookie=c.directory/'regtest/.cookie';original=cookie.read_bytes()
            def cookie_wrong(raw,missing=False,replace=False,bind=False):
                try:
                    if missing:cookie.unlink()
                    elif replace:
                        tmp=cookie.with_name('replacement.cookie');tmp.write_bytes(raw);tmp.chmod(0o600);os.replace(tmp,cookie)
                    else:cookie.write_bytes(raw)
                    if bind:identity(c.directory).credentials=CredentialSource(c.directory)
                    _expect(('CORE_RPC_CREDENTIAL_CHANGED_OR_UNSAFE',),lambda:c.call('getblockcount')) if not bind else _expect(('CORE_RPC_AUTHENTICATION_DENIED',),lambda:c.call('getblockcount'))
                finally:
                    cookie.write_bytes(original);cookie.chmod(0o600);c.reauth()
            case('BAD-COOKIE',lambda:cookie_wrong(b'__cookie__:'+secrets.token_hex(32).encode()+b'\n',bind=True))
            case('MISSING-COOKIE',lambda:cookie_wrong(b'',missing=True))
            case('REPLACED-COOKIE',lambda:cookie_wrong(original,replace=True))
            def stale_cookie():
                prior=c.reader();c.stop();c.start()
                assert cookie.read_bytes()!=original
                _expect(('WSP_LIVE_RPC_IDENTITY_DENIED',),lambda:prior.call('getblockcount'))
                assert c.state()==cbefore
            case('STALE-COOKIE',stale_cookie)
            # Refresh the saved bytes after the genuine cookie-generating restart.
            original=cookie.read_bytes()
            def config_loss():
                saved=a.config.read_bytes()
                try:
                    a.config.unlink()
                    _expect(('CORE_LOCAL_NETWORK_POLICY_DENIED',),lambda:a.call('getblockcount'))
                finally:
                    a.config.write_bytes(saved);a.config.chmod(0o600)
                    _expect(('CORE_RPC_CREDENTIAL_CHANGED_OR_UNSAFE',),lambda:a.call('getblockcount'))
                    a.reauth()
            case('AUTH-LOSS',config_loss)
            case('WRONG-CHAIN',lambda:fault_attest('getblockchaininfo',lambda raw,v:json.dumps({**v,'chain':'main'}).encode(),'WSP_LIVE_CHAIN_DENIED'),fault=True)
            case('WRONG-GENESIS',lambda:fault_attest('getblockhash',lambda raw,v:b'0'*64,'WSP_LIVE_GENESIS_DENIED'),fault=True)
            def wrong_endpoint():
                changed=a.original.replace(('rpcport='+str(a.port)).encode(),('rpcport='+str(c.port)).encode())
                try:
                    a.config.write_bytes(changed);identity(a.directory).credentials=CredentialSource(a.directory)
                    _expect(('CORE_RPC_PROCESS_IDENTITY_DENIED',),lambda:a.call('getblockcount'))
                finally:a.config.write_bytes(a.original);a.reauth()
            case('WRONG-PROCESS',wrong_endpoint)
            def injection():
                for args in (['-rpcconnect=127.0.0.1','getblockcount'],['getblockcount','-rpcport='+str(c.port)],
                             ['getblockhash','-1'],['getblockhash','0','-conf=other']):
                    _expect(('CORE_LOCAL_RPC_METHOD_DENIED',),lambda:cli_rpc.validate(args))
            case('ENDPOINT',injection)
            def remote_profile():
                try:
                    a.config.write_bytes(a.original+b'rpcconnect=203.0.113.1\n')
                    _expect(('CORE_LOCAL_NETWORK_POLICY_DENIED',),lambda:a.call('getblockcount'))
                finally:a.config.write_bytes(a.original);a.reauth()
            case('REMOTE-PROFILE',remote_profile)
            def fault_result(raw):
                with _fault('getblockcount',lambda *_:raw) as observed:
                    _expect(('CORE_RPC_REPLY_DENIED',),lambda:a.call('getblockcount'))
                assert observed
                a.reauth()
            case('MALFORMED-JSON',lambda:fault_result(b'{"broken"'),fault=True)
            case('ENVELOPE',lambda:fault_result(b'{"result":0,"error":null,"id":1}'),fault=True)
            case('RESULT-SHAPE',lambda:fault_result(b'"0"'),fault=True)
            case('REPLY-BOUNDS',lambda:fault_result(b'0'+b' '*(cli_rpc.LIMIT)),fault=True)
            def timeout():
                start=time.monotonic()
                _expect(('CORE_RPC_TIMEOUT_UNCERTAIN',),lambda:a.call('waitfornewblock','10000',timeout=1))
                assert time.monotonic()-start<8
                _expect(('CORE_RPC_SCOPE_FAULTED',),lambda:a.call('getblockcount'));a.reauth()
            case('TIMEOUT',timeout)
            def unavailable():
                with _Node(core) as other:
                    stale=other.reader();other.stop()
                    _expect(('WSP_LIVE_RPC_IDENTITY_DENIED',),lambda:stale.call('getblockcount'))
            case('UNAVAILABLE',unavailable)
            def readonly():
                rpc=a.reader()
                for method in ('stop','sendrawtransaction','generatetoaddress','createwallet','dumpprivkey'):
                    _expect(('WSP_LIVE_METHOD_DENIED',),lambda:rpc.call(method,[]))
                assert a.state()==before
            case('READONLY',readonly)
            def no_consent():
                ctx=identity(a.directory);ctx.authorized=False
                try:_expect(('CORE_RPC_MUTATION_CONSENT_REQUIRED',),lambda:a.call('createwallet','test'))
                finally:ctx.authorized=True;a.reauth()
                assert a.state()==before
            case('WRITE-CONSENT',no_consent)
            def lost_write():
                with _Node(core) as owned:
                    owned.call('createwallet','test');address=owned.call('-rpcwallet=test','getnewaddress')
                    # A genuine Core accepted/mined EXACTLY ONE disposable block.
                    # Only its reply is damaged, once, after observed validation.
                    with _fault('generatetoaddress',lambda raw,v:b'[') as observed:
                        _expect(('CORE_RPC_REPLY_DENIED',),lambda:owned.call('generatetoaddress','1',address,timeout=90))
                    assert observed==[True]
                    _expect(('CORE_RPC_SCOPE_FAULTED',),lambda:owned.call('getblockcount'))
                    owned.reauth();assert owned.call('getblockcount')==1
            case('UNCERTAIN-NO-RETRY',lost_write,fault=True)
            def privacy():
                raw=a.original
                values=[l.split(b'=',1)[1].decode() for l in raw.splitlines() if l.startswith((b'rpcuser=',b'rpcpassword='))]
                public=json.dumps(records)+repr(identity(a.directory).credentials)+repr(identity(a.directory).binding)
                assert all(v not in public for v in values)
                assert all(not any(v in arg for v in values) for arg in a.proc.args)
            case('PRIVACY',privacy)
            def custody():
                saved=a.config.read_bytes()
                if os.name=='posix':
                    try:
                        a.config.chmod(0o644)
                        _expect(('CORE_LOCAL_NETWORK_POLICY_DENIED',),lambda:a.call('getblockcount'))
                    finally:a.config.chmod(0o600)
                hard=a.config.with_name('config-hardlink')
                try:
                    os.link(a.config,hard)
                    _expect(('CORE_LOCAL_NETWORK_POLICY_DENIED',),lambda:a.call('getblockcount'))
                finally:
                    if hard.exists():hard.unlink()
                    a.config.write_bytes(saved);a.reauth()
            case('NATIVE-CUSTODY',custody)
            def replacement():
                # Preserve the original signed bytes. Tamper only an independent
                # disposable copy; Linux's explicit-directory trust also denies.
                with tempfile.TemporaryDirectory(prefix='wam-q02-copy-') as tmp:
                    copied=Path(tmp).resolve()/'core'
                    from .custody import create_directory
                    create_directory(copied)
                    if sys.platform=='win32':
                        from .windows_core_transport import write_new
                        for name in ('wamd.exe','wam-cli.exe','receipt.json'):write_new(copied,name,(core/name).read_bytes())
                    else:
                        for name in ('wamd','wam-cli','receipt.json'):
                            if (core/name).exists():shutil.copy2(core/name,copied/name)
                    target=copied/node.name
                    with target.open('ab') as f:f.write(b'\0')
                    try:verified_core_paths(copied)
                    except (ValueError,CoreSmokeError):return
                    raise Q02ProbeError('Q02_CHANGED_CORE_ACCEPTED')
            case('BINARY-REPLACE',replacement)
            def reauth():
                _expect(('CORE_RPC_REAUTHENTICATION_REQUIRED',),lambda:reauthenticate_owned(a.directory))
                a.reauth();assert a.state()==before
            case('REAUTH',reauth)
            def borrowed():
                rpc=a.reader();del rpc
                assert a.proc.poll() is None and a.state()==before
            case('BORROWED-LIFECYCLE',borrowed)
            case('BEFORE-AFTER',lambda: (a.state()==before and c.state()==cbefore) or (_ for _ in ()).throw(AssertionError()))
            def native_identity():
                ctx=identity(a.directory);ctx.binding._assert_image();ctx.assert_endpoint(a.port)
                assert ctx.binding.process is a.proc and a.proc.poll() is None
            case('OS-IDENTITY',native_identity)
        assert len(records)==33
        assert originals=={p.name:sha256(p.read_bytes()).hexdigest() for p in (node,cli)}
        return {'status':'REAL_Q02_SIGNED_CLI_AUTH_FAIL_CLOSED_PASS','cases':records,
            'observed_genesis':before[1],'observed_rpc_version':version['version'],'core_version':'v0.1.11','core_sha256':originals,
            'genuine_core_processes':True,'synthetic_rpc_server':False,
            'negative_injections_are_not_observed_wrong_network_core':True,
            'persistent_shared_rpc_implemented':False,'mainnet_allowed':False,'production_qualified':False}
    except Exception as error:
        print('Q02_FAILED_CASE='+stage,flush=True)
        if type(error) in (CoreSmokeError,CliRpcError,RealWspScanError,Q02ProbeError) and len(error.args)==1:
            code=error.args[0]
            import re
            if type(code) is str and re.fullmatch('[A-Z0-9_]{3,100}',code):print('Q02_FIXED_REFUSAL='+code,flush=True)
        raise Q02ProbeError('Q02_ACCEPTANCE_'+stage.replace('-','_')+'_FAILED') from None
