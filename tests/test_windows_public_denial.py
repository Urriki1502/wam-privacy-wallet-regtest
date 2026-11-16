"""Public failure visibility contracts; no native Windows/frozen PASS claim."""
import json
import unittest
from wam_regtest.windows_package_entry import _public_denial,public_failure_details
from wam_regtest.core import CoreSmokeError
from wam_regtest.q02_probe import Q02ProbeError


class WindowsPublicDenial(unittest.TestCase):
    def test_q02_case_and_bounded_fixed_causes_survive_windowed_entry(self):
        error=CoreSmokeError('Q02_ACCEPTANCE_UNAVAILABLE_FAILED')
        error.__context__=Q02ProbeError('Q02_NODE_START_TIMEOUT')
        error.__context__.__context__=CoreSmokeError('CORE_LOCAL_NETWORK_POLICY_DENIED')
        result=_public_denial(error)
        self.assertEqual(result['reason_code'],'Q02_ACCEPTANCE_UNAVAILABLE_FAILED')
        self.assertEqual(result['cause_codes'],['Q02_NODE_START_TIMEOUT','CORE_LOCAL_NETWORK_POLICY_DENIED'])
        self.assertFalse(result['mainnet_allowed'])

    def test_unknown_exception_text_and_unrecognized_causes_never_escape(self):
        for error in (AssertionError('private-canary'),ValueError('rpcpassword=private-canary'),
                      KeyError('private-canary'),RuntimeError('CORE_PRIVATE_CANARY_SECRET')):
            error.__context__=ValueError('CORE_PRIVATE_CANARY_SECRET')
            result=_public_denial(error)
            self.assertEqual(result['reason_code'],'WIN_BUNDLE_UNCLASSIFIED')
            self.assertEqual(result['cause_codes'],[])
            self.assertNotIn('canary',json.dumps(result).lower())

    def test_cyclic_exception_chain_is_bounded_without_formatting_exceptions(self):
        class Unprintable(Exception):
            def __str__(self):raise AssertionError('must not format exception')
        error=Unprintable('private-canary');error.__context__=error
        self.assertEqual(_public_denial(error)['exception_kind'],'OTHER')

    def test_payload_details_accept_only_finite_known_codes_and_kinds(self):
        for payload in ({'cause_codes':['CORE_PRIVATE_CANARY_SECRET'],'exception_kind':'private-canary'},
                        {'cause_codes':'private-canary','exception_kind':['private-canary']},
                        {'cause_codes':['Q02_NODE_START_TIMEOUT']*5,'exception_kind':'OTHER'}):
            result=public_failure_details(payload)
            self.assertEqual(result['cause_codes'],[])
            self.assertEqual(result['exception_kind'],'OTHER')
