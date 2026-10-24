"""Owned-process/credential identity scope for existing one-shot CLI calls.

No HTTP client, persistent RPC connection, automatic credential refresh or retry.
Only the creator's Popen handle is registered; external nodes are never adopted.
The socket probe sends zero bytes before the signed CLI is invoked. It is kernel
endpoint evidence, not atomic socket-to-CLI handoff against same-user malware.
"""
import os
from pathlib import Path
import socket
import sys
import threading
from .cli_rpc import CliRpcError,execute,validate,WRITES
from .core_process import OwnedCoreBinding,CoreBindingError
from .rpc_credentials import CredentialSource,CredentialError

_contexts={}
_lock=threading.RLock()


class _OwnedContext:
    def __init__(self,process,core,directory,authorized):
        self.binding=OwnedCoreBinding(process,core,directory)
        self.authorized=authorized is True
        self.credentials=None;self.faulted=False;self.ready=False
        self.lock=threading.RLock()

    def assert_endpoint(self,port):
        self.binding._assert_image()
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=2) as probe:
                self.binding.assert_socket(probe)
        except (ConnectionError,TimeoutError,OSError):
            raise CliRpcError('CORE_RPC_UNAVAILABLE') from None


def register(process,core,directory,*,authorized_disposable_mutation=False):
    key=str(directory.resolve(strict=True))
    with _lock:
        if key in _contexts:raise CliRpcError('CORE_RPC_SCOPE_ALREADY_EXISTS')
        context=_OwnedContext(process,core,directory,authorized_disposable_mutation)
        _contexts[key]=context
        return context


def unregister(directory):
    with _lock:context=_contexts.pop(str(directory.resolve(strict=True)),None)
    if context is not None:
        with context.lock:context.faulted=True;context.credentials=None


def identity(directory):
    with _lock:return _contexts.get(str(directory.resolve(strict=True)))


def reauthenticate_owned(directory,*,authorized=False):
    """Explicit fresh attestation of the SAME owned process. Never unlocks a wallet."""
    if authorized is not True:raise CliRpcError('CORE_RPC_REAUTHENTICATION_REQUIRED')
    with _lock:context=_contexts.get(str(directory.resolve(strict=True)))
    if context is None:raise CliRpcError('CORE_RPC_OWNED_SCOPE_REQUIRED')
    with context.lock:
        context.faulted=True
        context.binding._assert_image()
        source=CredentialSource(directory)
        context.assert_endpoint(source.port)
        # Only public, harmless attestation RPCs; no request replay or writes.
        context.credentials=source;context.faulted=False
        try:
            from .wsp_live import LiveCoreReadOnlyCli
            LiveCoreReadOnlyCli(context.binding.cli,directory).attest()
        except Exception:
            context.faulted=True;raise


def route(binary,directory,args,*,timeout=15):
    method,params=validate(args)
    with _lock:context=_contexts.get(str(directory.resolve(strict=True)))
    if context is None:raise CliRpcError('CORE_RPC_OWNED_SCOPE_REQUIRED')
    with context.lock:
        if context.faulted:raise CliRpcError('CORE_RPC_SCOPE_FAULTED')
        try:
            if not os.path.samefile(binary,context.binding.cli):raise CliRpcError('CORE_RPC_CLI_SCOPE_DENIED')
            if method in WRITES and not context.authorized:raise CliRpcError('CORE_RPC_MUTATION_CONSENT_REQUIRED')
            context.binding._assert_image()
            if context.credentials is None:context.credentials=CredentialSource(directory)
            source=context.credentials;source.attest();context.assert_endpoint(source.port)
            argv=[str(binary),'-datadir='+str(directory),'-rpcconnect=127.0.0.1',
                  '-rpcport='+str(source.port),*args]
            if sys.platform=='win32':
                from .windows_core_regtest_smoke import _host_env
                env=_host_env(directory)
            else:env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','HOME':str(directory),'LC_ALL':'C'}
            value=execute(argv,method,params,directory=binary.parent if sys.platform=='win32' else directory,
                env=env,timeout=timeout,creationflags=0x08000000 if sys.platform=='win32' else 0)
            source.attest()
            # stop can exit before CLI's response is collected. We still pin
            # credentials; every subsequent call refuses the exited Popen.
            if method!='stop':context.binding._assert_image()
            context.ready=True
            return value
        except (CliRpcError,CredentialError,CoreBindingError,OSError) as error:
            args=error.args
            bootstrap=(not context.ready and args in (('CORE_RPC_UNAVAILABLE',),('CORE_RPC_WARMUP',),
                ('RPC_CREDENTIAL_MISSING_OR_UNSAFE',)))
            if not bootstrap:context.faulted=True
            if type(error) is CliRpcError:raise
            if type(error) is CredentialError:raise CliRpcError('CORE_RPC_CREDENTIAL_CHANGED_OR_UNSAFE') from None
            raise CliRpcError('CORE_RPC_PROCESS_IDENTITY_DENIED') from None
