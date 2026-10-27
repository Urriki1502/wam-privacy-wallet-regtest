"""Refuse narrow or invented Q04 runtime claims before ledger promotion."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest


class Q04ProvenanceContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=Path(__file__).resolve().parents[1]/'scripts/update_q04_ledger.py'
        spec=importlib.util.spec_from_file_location('q04_import_contract',path)
        cls.update=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.update)
    def receipt(self):
        return {'status':'Q04_MINER_COEXISTENCE_PASS','synthetic_rpc':False,
            'platform':'macos-arm64','execution':'FROZEN',
            'core_sha256':self.update.proof.PINS['macos-arm64'],
            'wsp_source_commit':self.update.proof.WSP,'write_denied':True,'port_change_detected':True,
            'miner_heights':[1,1,2,2,3],'height_before':0,'reconnect_height':3,
            'reconnect_real_tcp_reset_count':1,'reconnect_fresh_attachment':True,
            'changed_cookie_reconnect_denied_before_auth':True,
            'restored_cookie_still_requires_new_authorization':True,'credential_fault_actor':'disposable_fixture_operator',
            'genuine_busy':{'status':'Q04_GENUINE_BUSY_PATH_PASS','synthetic_busy':False,
                'attachment_http_503_count':4,'read_attempts':4,'coalesced_read_calls':0,
                'write_boundary_attempts':1,'write_retried':False,
                'fresh_socket_process_attestation_per_attempt':True,'recovered_height':3,
                'retry_intervals_seconds':[.1,.2,.4],'gui_coalescing':'PASS'}}
    def test_injected_busy_cannot_qualify_genuine_case(self):
        receipt=self.receipt();receipt['genuine_busy']['synthetic_busy']=True
        with self.assertRaises(ValueError):self.update.check_runtime(receipt,'macos-arm64',True,True)
    def test_headless_cannot_qualify_gui_case(self):
        receipt=self.receipt();receipt['genuine_busy']['gui_coalescing']='NOT_APPLICABLE_NO_QT'
        with self.assertRaises(ValueError):self.update.check_runtime(receipt,'macos-arm64',True,True)
    def test_wrong_platform_core_and_wrong_execution_refused(self):
        for key,value in [('core_sha256',self.update.proof.PINS['linux-x86_64']),('execution','SOURCE_NATIVE')]:
            receipt=self.receipt();receipt[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.update.check_runtime(receipt,'macos-arm64',True,True)
    def test_no_busy_or_no_miner_progress_refused(self):
        for change in ('busy','miner'):
            receipt=self.receipt()
            if change=='busy':receipt['genuine_busy']['attachment_http_503_count']=0
            else:receipt['miner_heights']=[1]*5
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.update.check_runtime(receipt,'macos-arm64',True,True)
    def test_complete_required_shape_can_be_checked(self):
        self.update.check_runtime(self.receipt(),'macos-arm64',True,True)
