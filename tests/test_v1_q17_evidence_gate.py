"""Missing geometry or a fabricated visual approval cannot qualify Q17."""
from pathlib import Path
import unittest
from wam_regtest.q17_layout import check_component


class Q17EvidenceGate(unittest.TestCase):
    def test_prior_q05_pass_without_geometry_is_not_q17_acceptance(self):
        for missing in (None,{}, {'geometry_status':'PASS'},
                {'schema':'wam-q17-layout-component/v1','geometry_status':'PASS',
                 'visual_approval':'PENDING_REVIEW','full_q17_qualified':False,'evidence':[]}):
            with self.subTest(missing=missing),self.assertRaises(ValueError):
                check_component(missing,Path('/no-fixtures'),'windows-x64','a'*40,True,{'b'*64})

    def test_geometry_json_cannot_assert_visual_or_full_q17_approval(self):
        for field,value in (('visual_approval','PASS'),('full_q17_qualified',True)):
            component={'schema':'wam-q17-layout-component/v1','geometry_status':'PASS',
                'visual_approval':'PENDING_REVIEW','full_q17_qualified':False,'evidence':[]}
            component[field]=value
            with self.assertRaises(ValueError):
                check_component(component,Path('/no-fixtures'),'windows-x64','a'*40,True,{'b'*64})
