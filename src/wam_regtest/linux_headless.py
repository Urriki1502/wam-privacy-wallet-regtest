"""Linux text frontend over the SAME WalletSession; no Qt or alternate signer."""
import getpass
import json
from pathlib import Path
import shlex
import sys
import warnings
from .amounts import parse_amount,_parse_atoms
from .wallet_session import WalletSession,WalletSessionError
from .wallet_read import format_wam


def history_view(snap):
    return {'history_count':snap.history_count,'history_offset':snap.history_offset,
            'history_complete':snap.history_complete,'receive_count':snap.receive_count,
            'rows':[row.__dict__ for row in snap.history]}


def passphrase(prompt):
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        raise WalletSessionError('HEADLESS_PRIVATE_TERMINAL_REQUIRED')
    with warnings.catch_warnings():
        warnings.simplefilter('error',getpass.GetPassWarning)
        value=getpass.getpass(prompt)
    return value.encode('utf-8')


class HeadlessWallet:
    def __init__(self,session):self.session=session;self.review=None;self.signed=False
    def prepare(self,recipient,amount,fee):
        self.review=self.session.prepare(recipient,parse_amount(amount),_parse_atoms(fee,1,1_000_000))
        self.signed=False
        return self.review
    def sign(self,approval):
        if self.review is None or approval!='SIGN '+self.review.commitment:
            raise WalletSessionError('HEADLESS_EXACT_SIGN_APPROVAL_REQUIRED')
        result=self.session.sign(self.review.commitment);self.signed=True;return result
    def broadcast(self,approval):
        if self.review is None or not self.signed or approval!='BROADCAST '+self.review.commitment:
            raise WalletSessionError('HEADLESS_EXACT_BROADCAST_APPROVAL_REQUIRED')
        result=self.session.broadcast(self.review.commitment);self.review=None;self.signed=False;return result
    def clear(self):self.review=None;self.signed=False


def show_review(review):
    print('REGTEST REVIEW — signing reserves inputs irreversibly')
    print('Recipient: '+review.code)
    print('Amount: '+format_wam(review.atoms)+' WAM')
    print('Fee: '+format_wam(review.fee)+' WAM')
    print('Change: '+format_wam(review.change_atoms)+' WAM')
    print('Inputs: '+str(review.input_count)+'\nCommitment: '+review.commitment)


def open_session(core,datadir,source,mining,password,backup=None):
    """One startup path for interactive recovery and real fresh-chain acceptance."""
    if backup is None:
        return WalletSession.create(core,datadir,source,password,mining,authorized=True)
    backup=Path(backup).expanduser().absolute()
    return WalletSession.from_backup(core,datadir,source,backup.parent,backup.name,
        password,mining,authorized=True)


def _core_reauth_prompt(session):
    """Explicit headless approval to reauthenticate the same owned process."""
    if not session._core_reauthentication_required:
        return True
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        raise WalletSessionError('HEADLESS_PRIVATE_TERMINAL_REQUIRED')
    response=input('Core authentication lost — type REAUTH to reauthenticate the same owned REGTEST process: ').strip()
    if response!='REAUTH':
        raise WalletSessionError('WALLET_CORE_REAUTHENTICATION_REQUIRED')
    return True


def launch(core,datadir,source,mining,*,backup=None):
    from . import custody
    password=passphrase('Backup passphrase: ' if backup is not None else 'New disposable REGTEST passphrase: ')
    try:session=open_session(core,datadir,source,mining,password,backup)
    finally:password=None
    frontend=HeadlessWallet(session)
    print('REGTEST ONLY. Commands: receive balance history sync prepare sign broadcast cancel backup lock unlock recover mine quit')
    try:
        while True:
            try:
                raw=input('wam-regtest> ')
                if len(raw)>1024:raise ValueError
                args=shlex.split(raw)
                if not args:continue
                command=args[0]
                if command=='quit' and len(args)==1:break
                if command in ('receive','balance','sync') and len(args)==1:
                    snap=session.snapshot()
                    if command=='receive':
                        print(snap.receive_code)
                        if type(snap.receive_count) is int:
                            print(str(snap.receive_count)+' confirmed credit record(s)')
                    else:print(f'Confirmed {format_wam(snap.confirmed_atoms)} WAM; height {snap.height}; UTXOs {snap.confirmed_utxos}')
                elif command=='history' and len(args) in (1,2):
                    offset=0
                    if len(args)==2:
                        if not args[1].isdigit() or int(args[1])<0:
                            raise ValueError
                        offset=int(args[1])
                    print(json.dumps(history_view(session.snapshot(history_offset=offset)),sort_keys=True))
                elif command=='prepare' and len(args)==4:show_review(frontend.prepare(*args[1:]))
                elif command=='sign' and len(args)==1:
                    if frontend.review is None:raise ValueError
                    show_review(frontend.review)
                    frontend.sign(input('Type SIGN followed by the exact commitment, or Cancel: '));print('SIGNED — Broadcast needs separate approval')
                elif command=='broadcast' and len(args)==1:
                    if frontend.review is None:raise ValueError
                    show_review(frontend.review)
                    print(frontend.broadcast(input('Type BROADCAST followed by the exact commitment, or Cancel: ')))
                elif command=='cancel' and len(args)==1:session.cancel();frontend.clear()
                elif command=='backup' and len(args)==2:
                    folder=Path(args[1]).expanduser().absolute();custody.create_directory(folder)
                    session.backup(folder,'wallet-backup.enc');print('Latest encrypted backup saved')
                elif command=='lock' and len(args)==1:session.lock();frontend.clear();print('LOCKED')
                elif command=='unlock' and len(args)==1:
                    password=passphrase('Wallet passphrase: ')
                    try:
                        reauth_approved=_core_reauth_prompt(session)
                        session.unlock(password,reauth_approved)
                    finally:password=None
                elif command=='recover' and len(args)==2:
                    password=passphrase('Backup passphrase: ')
                    try:
                        reauth_approved=_core_reauth_prompt(session)
                        session.recover_backup(Path(args[1]).expanduser().absolute(),'wallet-backup.enc',password,reauth_approved);frontend.clear()
                    finally:password=None
                elif command=='mine' and len(args)==1:session.mine();print('One disposable REGTEST block mined')
                else:raise ValueError
            except (EOFError,KeyboardInterrupt):break
            except Exception:
                if session.locked or session.faulted:frontend.clear()
                print('DENIED — state/reservations retained; verify chain and unlock/recover before retry. No automatic broadcast retry.')
        return {'status':'LINUX_HEADLESS_DISPOSABLE_SESSION_CLOSED','mainnet_allowed':False}
    finally:frontend.clear();session.close()


def run(args):
    from .linux_runtime import configure
    from .core import smoke_real_core
    try:
        core=args.core_dir.expanduser().absolute();source=args.wsp_source_root.expanduser().absolute()
        configure(core,args.manifest_sha256,args.anchor_socket.expanduser().absolute(),
            authorized=args.confirm_experimental_developer_regtest)
        if (args.confirm_headless_e2e or args.confirm_qt_e2e or args.gui) and args.recover_backup is not None:
            raise WalletSessionError('HEADLESS_RECOVERY_ACCEPTANCE_MODE_CONFLICT')
        def callback(c,d,s,m):return launch(c,d,s,m,backup=args.recover_backup)
        if args.confirm_headless_e2e:
            from .linux_headless_probe import probe
            callback=probe
        elif args.confirm_qt_e2e:
            from .linux_qt_probe import probe
            callback=probe
        elif args.gui:
            from .operational_gui import launch_disposable_wallet
            def callback(c,d,s,m):
                if launch_disposable_wallet(c,d,s,m)!=0:
                    raise WalletSessionError('LINUX_QT_WINDOW_DENIED')
                return {'status':'LINUX_QT_DISPOSABLE_SESSION_CLOSED','mainnet_allowed':False}
        result=smoke_real_core(core,explicit_consent=args.confirm_experimental_developer_regtest,
            wsp_source=source,wsp_payment_e2e=True,headless_callback=callback,
            q02_e2e=bool(args.confirm_headless_e2e or args.confirm_qt_e2e))
        result.update({'official_signed_release':False,'developer_manifest_sha256':args.manifest_sha256,
            'frozen_runtime':bool(getattr(sys,'frozen',False)),
            'linux_headless':not (args.gui or args.confirm_qt_e2e),'qt_imported':any(n.startswith('PySide6') for n in sys.modules)})
        if args.report:
            with args.report.open('x') as output:json.dump(result,output,indent=2);output.write('\n')
        print('LINUX_NATIVE_REAL_REGTEST_COMPLETED')
        return 0
    except Exception as error:
        import re
        text=str(error)
        print(text if type(error).__name__ in ('WalletSessionError','CoreSmokeError','LinuxCoreError','LinuxWitnessError','LinuxStorageError')
            and re.fullmatch('[A-Z0-9_]{5,120}',text) else 'LINUX_HEADLESS_REGTEST_DENIED',file=sys.stderr)
        return 2
