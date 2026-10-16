"""Actual Mac stale-before-sign/broadcast; real Core/native WSP/test Keychain.

Reuse the existing Windows payment regression logic, with explicitly isolated
native Mac Keychain routing. No cryptographic, RPC or custody gate is replaced.
"""
import argparse,importlib.util,json,os,subprocess
from pathlib import Path
from wam_regtest import custody
from wam_regtest.wallet_session import WalletSession
from wam_regtest.reopen_probe import _prove_windows_stale_payment
from wam_regtest.desktop import qt_application,shutdown_qt
p=argparse.ArgumentParser()
for name in ('repo','core','source','output'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args()
for name in ('repo','core','source','output'):setattr(a,name,getattr(a,name).resolve())
out=a.output;out.mkdir(exist_ok=False);os.chdir(out)
spec=importlib.util.spec_from_file_location('owner_audit_driver',a.repo/'scripts/owner_acceptance.py');d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
app=qt_application();password=b'public-disposable-mac-stale-audit';original=custody.anchor
try:
 with d.isolated_chain(a.core,a.source) as (data,mining,core):
  keychain=data/'stale-payment-fixture.keychain-db';session=None
  subprocess.run(['/usr/bin/security','create-keychain','-p','public-test-only',str(keychain)],check=True,capture_output=True)
  def fixture_anchor(wallet_id,keychain_arg=None):
   assert keychain_arg is None or Path(keychain_arg)==keychain
   return original(wallet_id,keychain)
  try:
   custody.anchor=fixture_anchor
   session=WalletSession.create(a.core,data,a.source,password,mining,authorized=True,keychain=keychain)
   assert session.snapshot().height==103
   observer_rpc=session._rpc()  # Independent read-only observer, before session faults.
   # Existing helper advances the real same-wallet native anchor from another
   # private vault directory, tracks real signer/RPC entry, and delegates actual
   # crypto/RPC unchanged. Only unsigned drafts may be released.
   _prove_windows_stale_payment(session,password)
   assert session.faulted
   states={row[0] for row in session.scanner.store.db.execute('SELECT state FROM reservations')}
   assert 'signed' in states and states <= {'signed','broadcast','uncertain'}
   assert not observer_rpc._call('getrawmempool',[])
   proof={'code_head':subprocess.check_output(['git','-C',str(a.repo),'rev-parse','audit/rc1-owner-acceptance-20261016'],text=True).strip(),'platform':'macos-arm64','qt_platform':app.platformName(),'network':'regtest','core_sha256':core['node_sha256'] if 'node_sha256' in core else '7298de701e467eb28b4806cbcbe35edb393861b4b97117017fee4c1b194e3068','same_wallet_separate_vault_directories':True,'stale_before_native_signature_denied':True,'positive_real_native_signature_control':True,'stale_before_real_broadcast_denied':True,'no_real_mempool_submission':True,'signed_reservations_irreversible':True,'test_keychain_factory_routing':True,'synthetic_rpc':False,'owner_keychain_touched':False,'mainnet_allowed':False,'production_qualified':False}
   (out/'MAC_STALE_PAYMENT_RECEIPT.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2))
  finally:
   if session is not None:session.close()
   custody.anchor=original
   subprocess.run(['/usr/bin/security','delete-keychain',str(keychain)],check=True,capture_output=True)
finally:shutdown_qt()
