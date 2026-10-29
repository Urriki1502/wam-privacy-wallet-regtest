"""One persistent in-process wallet execution thread, separate from Qt workers.

No socket, process adoption, generic RPC dispatch, secrets in results or writes
retried on timeout. Failed shutdown retains the original owner/execution thread.
"""
from concurrent.futures import Future,TimeoutError
from dataclasses import dataclass,fields,is_dataclass,replace
from queue import Queue
import re
import threading


class WalletExecutorError(ValueError):pass


class FrozenDict(dict):
    def _deny(self,*args,**kwargs):raise TypeError('IMMUTABLE_WALLET_RESULT')
    __setitem__=__delitem__=clear=pop=popitem=setdefault=update=__ior__=_deny


def immutable(value):
    if value is None or type(value) in (str,int,bool,float,bytes):return value
    if type(value) in (tuple,list):return tuple(immutable(v) for v in value)
    if type(value) is dict:return FrozenDict((k,immutable(v)) for k,v in value.items())
    if is_dataclass(value) and value.__dataclass_params__.frozen:
        return replace(value,**{f.name:immutable(getattr(value,f.name)) for f in fields(value)})
    raise WalletExecutorError('WALLET_EXECUTOR_RESULT_DENIED')


@dataclass(frozen=True)
class ExecutorState:
    generation:int=0
    locked:bool=True
    faulted:bool=False
    reauthentication_required:bool=False
    core_alive:bool|None=False


COMMANDS=frozenset(('open','snapshot','prepare','sign','broadcast','cancel','lock',
    'unlock','backup','recover','complete_recovery','recovery_status','network',
    'disclose','mine','core_status','core_start','core_restart','control','quit'))


class WalletExecutor:
    def __init__(self,backend_factory):
        self._factory=backend_factory;self._backend=None
        self._queue=Queue(maxsize=1);self._guard=threading.Lock()
        self._pending=None;self._closed=False;self._state=ExecutorState()
        # Deliberately non-daemon: window close cannot abandon a live owner.
        self._thread=threading.Thread(target=self._run,name='WAM-wallet-owner',daemon=False)
        self._thread.start()

    @property
    def state(self):
        with self._guard:return self._state

    @property
    def busy(self):
        with self._guard:return self._pending is not None

    @property
    def closed(self):
        with self._guard:return self._closed

    def submit(self,action,*args,**kwargs):
        future=Future()
        with self._guard:
            if (action not in COMMANDS or self._closed or self._pending is not None
                    or threading.get_ident()==self._thread.ident):
                future.set_exception(WalletExecutorError('WALLET_EXECUTOR_BUSY_OR_CLOSED'))
                return future
            self._pending=future
            self._queue.put_nowait((action,args,kwargs,future))
        return future

    def request(self,action,*args,timeout=90,**kwargs):
        future=self.submit(action,*args,**kwargs)
        try:return future.result(timeout=timeout)
        except TimeoutError:
            # The operation remains owned/in flight. NEVER cancel/resubmit a
            # signing or broadcast operation because a caller stopped waiting.
            raise WalletExecutorError('WALLET_EXECUTOR_OPERATION_STILL_PENDING') from None

    def join(self,timeout=5):
        self._thread.join(timeout)
        return not self._thread.is_alive()

    def _run(self):
        while True:
            action,args,kwargs,future=self._queue.get()
            result=error=None;exit_owner=False
            active=future.set_running_or_notify_cancel()
            try:
                if active:
                    if self._backend is None and action!='quit':
                        self._backend=self._factory()
                        if isinstance(self._backend,ManagedWalletBackend):self._backend.attach_executor(self)
                    result=immutable(self._backend.execute(action,args,kwargs)) if self._backend is not None else None
                    exit_owner=action=='quit'
            except Exception as failure:
                code=failure.args[0] if len(failure.args)==1 else None
                from .gui_errors import operation_error,INPUT_ERRORS
                public=operation_error(action,failure)
                if public in INPUT_ERRORS:code=public
                if type(code) is not str or not re.fullmatch('[A-Z][A-Z0-9_]{1,95}',code):
                    code='WALLET_EXECUTOR_DENIED'
                error=WalletExecutorError(code)
            finally:
                # State and idle transition precede delivery, so a caller that
                # received a result may submit exactly one next operation.
                try:
                    observed=self._backend.public_state() if self._backend is not None else {}
                    if (type(observed) is not dict or set(observed)-{'locked','faulted',
                            'reauthentication_required','core_alive'}
                            or any(type(v) is not bool for v in observed.values())):raise ValueError
                except Exception:
                    observed=dict(locked=True,faulted=True,core_alive=None)
                    error=WalletExecutorError('WALLET_EXECUTOR_STATE_UNVERIFIED')
                if exit_owner and observed.get('core_alive',False) is not False:
                    exit_owner=False;error=WalletExecutorError('WALLET_EXECUTOR_OWNER_STILL_LIVE')
                with self._guard:
                    self._state=ExecutorState(generation=self._state.generation+1,**observed)
                    self._pending=None
                    if exit_owner:self._closed=True
                if active:
                    if error is None:future.set_result(result)
                    else:future.set_exception(error)
                self._queue.task_done()
                args=();kwargs={}
            if exit_owner:return


class ManagedWalletBackend:
    """Original Core + wallet stay in this executor for their entire lifetime."""
    def __init__(self,root,core,source,*,keychain=None,mining_address=None,_anchor_factory=None):
        self.root=root;self.core=core;self.source=source;self.keychain=keychain
        self.mining_address=mining_address;self.owner=self.session=None
        self._executor=None;self._anchor_factory=_anchor_factory;self._anchor_ready=False
        self._control_thread=None;self._control_fault=False

    def attach_executor(self,executor):
        if self._executor is not None:raise WalletExecutorError('WALLET_EXECUTOR_ALREADY_BOUND')
        self._executor=executor

    def _serve_control(self):
        try:self.owner.serve()
        except (OSError,ValueError,RuntimeError):
            if not self.owner._release_requested and self.owner.listener is not None:self._control_fault=True
        if self.owner._release_requested and not self._executor.closed:
            try:self._executor.request('quit')
            except WalletExecutorError:pass  # Explicit release cannot force a busy/live owner out.

    def public_state(self):
        s=self.session;p=self.owner.process if self.owner is not None else None
        return dict(locked=s is None or s.locked,faulted=self._control_fault or s is not None and s.faulted,
            reauthentication_required=s is not None and s._core_reauthentication_required,
            core_alive=p is not None and p.poll() is None)

    def _core(self):
        if self._executor is None:raise WalletExecutorError('WALLET_EXECUTOR_OWNER_REQUIRED')
        if self.owner is None:
            from .core_supervisor import CoreSupervisor
            from .custody import create_directory
            if not self.root.exists() and not self.root.is_symlink():
                if not re.fullmatch('wam-fusion-core-[0-9a-f]{16}',self.root.name):
                    raise WalletExecutorError('MANAGED_PROFILE_NAME_DENIED')
                create_directory(self.root)
            self.owner=CoreSupervisor(self.root,self.core,authorized=True)
            self.owner._control_bridge=lambda op:self._executor.request('control',op)
            self._control_thread=threading.Thread(target=self._serve_control,name='WAM-control-io',daemon=True)
            self._control_thread.start()
        if self.owner.process is None:self.owner.start(timeout=90)
        return self.owner

    def _open(self,password,create=False):
        from .wallet_session import WalletSession
        if type(password) is not bytes or not 12<=len(password)<=1024 or type(create) is not bool:
            raise WalletExecutorError('WALLET_MANAGED_INPUT_DENIED')
        if self.session is not None and not self.session.locked:
            raise WalletExecutorError('WALLET_ALREADY_UNLOCKED')
        owner=self._core()
        if self._anchor_factory is not None and not self._anchor_ready:
            self.keychain=self._anchor_factory(self.root);self._anchor_ready=True
        self.session=WalletSession.open_owned(owner,self.source,password,authorized=True,
            create=create,keychain=self.keychain,mining_address=self.mining_address)
        return self.session.snapshot()

    def _lock(self):
        if self.session is not None:self.session.lock()

    def execute(self,action,args,kwargs):
        if action=='open':return self._open(*args,**kwargs)
        if action=='unlock':
            if len(args)!=2 or args[1] is not False:
                raise WalletExecutorError('WALLET_MANAGED_EXPLICIT_RECOVERY_REQUIRED')
            return self._open(args[0])
        if action=='lock':self._lock();return None
        if action=='recovery_status':
            from .wallet_recovery import _records
            from .managed_wallet_checkpoint import _read_reference,_owned
            owner=self._core();_owned(owner);wallet=_read_reference(owner);rows,_=_records(owner,wallet)
            return {'pending_action':rows[-1]['action'] if rows and rows[-1]['state']=='BEGIN' else None}
        if action in ('recover','complete_recovery'):
            self._lock()
            from .wallet_recovery import recover_checkpoint,complete_recovery
            owner=self._core()
            if action=='recover':
                if len(args)!=1:raise WalletExecutorError('WALLET_MANAGED_EXPLICIT_RECOVERY_REQUIRED')
                return recover_checkpoint(owner,self.source,args[0],authorized=True,keychain=self.keychain)
            if len(args)!=2:raise WalletExecutorError('WALLET_MANAGED_EXPLICIT_RECOVERY_REQUIRED')
            return complete_recovery(owner,self.source,args[0],action=args[1],authorized=True,keychain=self.keychain)
        if action=='core_start':return self._core().status()
        if action=='core_status':
            if self.owner is None:
                from .supervisor_protocol import public_status
                return public_status(state='stopped')
            return self.owner.status()
        if action=='control':
            if self.owner is None or len(args)!=1:
                raise WalletExecutorError('MANAGED_CONTROL_OPERATION_DENIED')
            if args[0]!='status':self._lock()
            return self.owner.control_operation(args[0])
        if action in ('core_restart','quit'):
            self._lock()
            owner=self.owner
            if owner is not None:
                p=owner.process
                if p is not None and p.poll() is None:
                    if owner._faulted:owner.recover_stop()
                    else:owner.shutdown()
                elif p is not None:owner.recover_dead()
                if action=='quit':owner.release();owner.close()
                else:owner.start()
            return None
        if self.session is None:raise WalletExecutorError('WALLET_LOCKED_OR_FAULTED')
        methods={'snapshot':self.session.snapshot,'prepare':self.session.prepare,
            'sign':self.session.sign,'broadcast':self.session.broadcast,'cancel':self.session.cancel,
            'backup':self.session.backup,'network':self.session.network_diagnostics,
            'disclose':self.session.disclose_record,'mine':self.session.mine}
        if action not in methods:raise WalletExecutorError('WALLET_EXECUTOR_COMMAND_DENIED')
        result=methods[action](*args,**kwargs)
        return {'saved':True} if action=='backup' else result


class ManagedWalletProxy:
    """Qt's temporary workers see public values, never the live keyring/session."""
    def __init__(self,executor,root,core,source):
        self.executor=executor;self.datadir=root/'chain';self.core_dir=core;self.source=source
    @property
    def locked(self):return self.executor.state.locked
    @property
    def faulted(self):return self.executor.state.faulted
    @property
    def _core_reauthentication_required(self):return self.executor.state.reauthentication_required
    def snapshot(self,history_offset=0):return self.executor.request('snapshot',history_offset=history_offset)
    def prepare(self,*args):return self.executor.request('prepare',*args)
    def sign(self,*args):return self.executor.request('sign',*args)
    def broadcast(self,*args):return self.executor.request('broadcast',*args)
    def cancel(self):return self.executor.request('cancel')
    def lock(self):return self.executor.request('lock')
    def close(self):return self.lock()
    def unlock(self,*args):return self.executor.request('unlock',*args)
    def backup(self,*args):return self.executor.request('backup',*args)
    def network_diagnostics(self):return self.executor.request('network')
    def disclose_record(self,*args,**kwargs):return self.executor.request('disclose',*args,**kwargs)
    def recover_backup(self,*args):raise WalletExecutorError('WALLET_MANAGED_EXPLICIT_RECOVERY_REQUIRED')
    def mine(self):return self.executor.request('mine')
