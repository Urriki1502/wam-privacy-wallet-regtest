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


def launch(core,datadir,source,mining):
    from . import custody
    password=passphrase('New disposable REGTEST passphrase: ')
    session=WalletSession.create(core,datadir,source,password,mining,authorized=True)
    password=None;frontend=HeadlessWallet(session)
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
                if command in ('receive','balance','history','sync') and len(args)==1:
                    snap=session.snapshot()
                    if command=='receive':print(snap.receive_code)
                    elif command=='history':
                        print(json.dumps([row.__dict__ for row in snap.history],sort_keys=True))
                    else:print(f'Confirmed {format_wam(snap.confirmed_atoms)} WAM; height {snap.height}; UTXOs {snap.confirmed_utxos}')
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
                    try:session.unlock(password)
                    finally:password=None
                elif command=='recover' and len(args)==2:
                    password=passphrase('Backup passphrase: ')
                    try:session.recover_backup(Path(args[1]).expanduser().absolute(),'wallet-backup.enc',password);frontend.clear()
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
        callback=launch
        if args.confirm_headless_e2e:
            from .linux_headless_probe import probe
            callback=probe
        result=smoke_real_core(core,explicit_consent=args.confirm_experimental_developer_regtest,
            wsp_source=source,wsp_payment_e2e=True,headless_callback=callback)
        result.update({'official_signed_release':False,'developer_manifest_sha256':args.manifest_sha256,
            'linux_headless':True,'qt_imported':any(n.startswith('PySide6') for n in sys.modules)})
        if args.report:
            with args.report.open('x') as output:json.dump(result,output,indent=2);output.write('\n')
        print('LINUX_HEADLESS_REAL_REGTEST_COMPLETED')
        return 0
    except Exception as error:
        import re
        text=str(error)
        print(text if type(error).__name__ in ('WalletSessionError','CoreSmokeError','LinuxCoreError','LinuxWitnessError','LinuxStorageError')
            and re.fullmatch('[A-Z0-9_]{5,120}',text) else 'LINUX_HEADLESS_REGTEST_DENIED',file=sys.stderr)
        return 2
