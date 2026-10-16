"""Supplemental adversarial/accounting vectors, not real-Core acceptance."""
from copy import deepcopy
from decimal import Decimal
import unittest
from wam_regtest.mining_account import RewardSplit,treasury_atoms,MiningWalletBalance,CoinbaseAudit,COIN
from wam_regtest.wsp_live import REGTEST_GENESIS

class MinerRules(unittest.TestCase):
 def test_regtest_interval_is_not_200000_and_cutoff_is_independent(self):
  for h,sub,treas in [(1,50*COIN,250000000),(150,50*COIN,250000000),(151,25*COIN,125000000),(300,25*COIN,125000000),(301,1250000000,62500000),(451,625000000,31250000),(4951,0,0)]:
   r=RewardSplit.regtest(h,141);self.assertEqual((r.subsidy_atoms,r.treasury_atoms,r.miner_atoms),(sub,treas,sub-treas+141))
  for amount in (50*COIN,25*COIN,1250000000,625000000,1):
   self.assertEqual(treasury_atoms(amount,400000),amount*5//100)
   for h in (0,400001,600001):self.assertEqual(treasury_atoms(amount,h),0)
  for h in (0,-1,True,1.0):
   with self.assertRaises(ValueError):RewardSplit.regtest(h)
 def balance_args(self,depth=101):
  script='0014'+'11'*20;txid='a'*64
  u={'txid':txid,'vout':0,'scriptPubKey':script,'amount':Decimal('47.5'),'confirmations':depth,'spendable':True,'solvable':True,'safe':True}
  return dict(chain='regtest',genesis=REGTEST_GENESIS,wallet_info={'format':'sqlite','descriptors':True,'private_keys_enabled':True},balances={'mine':{'trusted':Decimal('47.5'),'untrusted_pending':0,'immature':0}},unspent=[u],txouts={(txid,0):{'scriptPubKey':{'hex':script},'value':Decimal('47.5'),'confirmations':depth,'coinbase':True}},treasury_script='76a914'+'22'*20+'88ac')
 def test_maturity_trusted_and_unsafe_are_distinct(self):
  for depth in (99,100,101):
   a=self.balance_args(depth);r=MiningWalletBalance.from_core(**a);self.assertEqual(r.available_atoms,4750000000 if depth==101 else 0)
  for k in ('spendable','solvable','safe'):
   a=self.balance_args();a['unspent'][0][k]=False;self.assertEqual(MiningWalletBalance.from_core(**a).available_atoms,0)
  a=self.balance_args();a['unspent']=[];self.assertEqual(MiningWalletBalance.from_core(**a).available_atoms,0)
 def test_conflicting_duplicate_treasury_and_wrong_chain_fail(self):
  for mode in ('duplicate','treasury','amount','depth','missing','chain'):
   a=self.balance_args()
   if mode=='duplicate':a['unspent']*=2
   elif mode=='treasury':a['treasury_script']=a['unspent'][0]['scriptPubKey']
   elif mode=='amount':a['unspent'][0]['amount']='50'
   elif mode=='depth':a['unspent'][0]['confirmations']=100
   elif mode=='missing':a['txouts']={}
   else:a['chain']='main'
   with self.assertRaises(ValueError):MiningWalletBalance.from_core(**a)
 def test_coinbase_fee_belongs_entirely_to_miner_and_genesis_refused(self):
  own='0014'+'11'*20;treas='76a914'+'22'*20+'88ac'
  args=dict(chain='regtest',genesis=REGTEST_GENESIS,block={'height':1,'tx':[{'vin':[{'coinbase':'01'}],'vout':[{'n':0,'value':Decimal('47.50000141'),'scriptPubKey':{'hex':own}},{'n':1,'value':Decimal('2.5'),'scriptPubKey':{'hex':treas}}]}]},treasury_info={'script':treas,'percent':5,'start_height':1,'last_height':400000},owned_address_infos=[{'ismine':True,'scriptPubKey':own}],fees=141)
  r=CoinbaseAudit.from_core(**args);self.assertEqual(r.owned_miner_atoms,4750000141);self.assertEqual(r.treasury_paid_atoms,250000000)
  for mode in ('fee_to_treasury','genesis','unowned','overlap'):
   a=deepcopy(args)
   if mode=='fee_to_treasury':a['block']['tx'][0]['vout'][0]['value']-=Decimal('.00000141');a['block']['tx'][0]['vout'][1]['value']+=Decimal('.00000141')
   elif mode=='genesis':a['block']['height']=0
   elif mode=='unowned':a['owned_address_infos'][0]['ismine']=False
   else:a['owned_address_infos'][0]['scriptPubKey']=treas
   with self.assertRaises(ValueError):CoinbaseAudit.from_core(**a)
