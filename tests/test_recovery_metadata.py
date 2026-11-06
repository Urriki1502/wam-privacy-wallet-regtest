"""Public hints never replace encrypted journals, original chain or native CAS."""
import copy
import unittest
from wam_regtest.recovery_metadata import PATHS, VERSION, validate_public_metadata
from wam_regtest.wsp_live import REGTEST_GENESIS


class RecoveryMetadataContracts(unittest.TestCase):
    def fixture(self):
        return {'version':VERSION,'chain':{'network':'regtest','genesis':REGTEST_GENESIS},
                'birthday':1,'mining_descriptors':None,'paths':dict(PATHS),
                'hrp':'wamrtsp','label_high_water_mark':0}

    def test_exact_public_contract_detached_from_caller(self):
        value = self.fixture(); before = copy.deepcopy(value)
        result = validate_public_metadata(value)
        self.assertEqual(value,before);self.assertEqual(result,value)
        result['paths']['scan']='tampered';result['chain']['network']='mainnet'
        self.assertEqual(value,before)
        self.assertFalse(any(k in value for k in ('seed','signer_allowed','broadcast_allowed','reservation','password')))

    def test_foreign_network_derivation_hrp_descriptors_and_extra_secrets_denied(self):
        changes = [('version','native-checkpoint-v1'),('chain',{'network':'regtest','genesis':'0'*64}),
                   ('chain',{'network':'mainnet','genesis':REGTEST_GENESIS}),
                   ('paths',{'scan':"m/352'/5718349'/0'/1'/0",'spend':PATHS['spend']}),
                   ('hrp','wamrt'),('hrp','wamsp'),('mining_descriptors',[]),
                   ('mining_descriptors','xprv-synthetic-marker'),('seed','synthetic-secret-marker')]
        for key,v in changes:
            value=self.fixture();value[key]=v
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'^RECOVERY_PUBLIC_METADATA_DENIED$'):
                validate_public_metadata(value)

    def test_strict_bounds_and_no_optional_fields(self):
        for key in ('birthday','label_high_water_mark'):
            for v in (True,False,-1,None,1.5,'1',2**32):
                value=self.fixture();value[key]=v
                with self.subTest(key=key,kind=type(v).__name__),self.assertRaises(ValueError):
                    validate_public_metadata(value)
        for key in self.fixture():
            value=self.fixture();del value[key]
            with self.assertRaises(ValueError):validate_public_metadata(value)


if __name__=='__main__':unittest.main()
