"""T-09 supplemental receipt-denial tests; no mocked Core passes as E2E."""
import copy
import unittest
from wam_regtest.t09_rpc_acceptance import require_direct_rpc_evidence,T09EvidenceError


class T09ReceiptDenials(unittest.TestCase):
    def setUp(self):
        # Public stand-in receipts exercise validator only. Real Core E2E
        # directly executes this gate in the native and frozen entrypoints.
        self.owned={
            "status":"REAL_CORE_OWNED_HTTP_READ_COMPONENT_PASS",
            "height":102,
            "rpc_compatibility_profile":{
                "version":111,"subversion":"/WAM:0.1.11/","protocolversion":70016},
            "repeated_authenticated_reads":8,
            "t03_live_height_tip_parity_on_owned_core":True,
            "t04_post_launch_pair_stable_during_core_hash":True,
            "process_image_and_established_socket_before_auth":True,
            "wrong_process_endpoint_denied_before_any_http_bytes":True,
            "genuine_core_invalid_auth_denied":True,
            "write_denied_before_wire":True,
            "synthetic_core_rpc":False,
            "mainnet_allowed":False,
            "node_busy_read_component":{
                "status":"REAL_CORE_BUSY_READ_RECOVERY_PASS",
                "read_attempt_limit":3,"observed_busy_attempts":3,
                "queue_response_503":10,
                "recovered_without_daemon_restart":True,
                "no_synthetic_rpc":True},
            "idle_read_component":{
                "status":"REAL_CORE_IDLE_READ_RECONNECT_PASS",
                "old_socket_closed_before_request":True,
                "request_replayed":False},
        }
        self.wsp={"scanner_transport":"owned-http",
                  "cli_and_rehash_forbidden_during_scan":True,
                  "real_core_rpc":True,"synthetic_rpc":False,
                  "wsp_bip352_payment_confirmed":True,
                  "regtest_fixture_broadcast_confirmed":True}
        self.wallet={"real_core_rpc":True,"synthetic_rpc":False,
                     "mainnet_allowed":False,
                     "native_qt_prepare_sign_broadcast":True,
                     "real_core_lost_broadcast_reply_lock_retained":True,
                     "operational_snapshot_http":{
                         "transport":"owned-http",
                         "cli_and_rehash_forbidden":True}}

    def check(self,*,platform="macos-arm64",operational=True,
              contention=True):
        return require_direct_rpc_evidence(
            platform=platform,height=102,owned=self.owned,wsp=self.wsp,
            wallet=self.wallet,operational=operational,contention=contention)

    def test_component_receipt_is_scoped_and_never_physical_or_release(self):
        for platform in ("macos-arm64","windows-x64","linux-x86_64"):
            with self.subTest(platform=platform):
                evidence=self.check(platform=platform,operational=False)
                self.assertEqual(evidence["status"],
                                 "T09_REAL_CORE_DIRECT_RPC_COMPONENT_PASS")
                self.assertEqual(evidence["platform"],platform)
                self.assertFalse(evidence["physical_accepted"])
                self.assertFalse(evidence["dev_reviewed"])
                self.assertFalse(evidence["synthetic_rpc"])
                self.assertFalse(evidence["mainnet_allowed"])
        self.assertTrue(self.check()["operational_wallet_checked"])

    def test_no_historical_or_incomplete_trust_proof_can_pass(self):
        for name,value in (
            ("genuine_core_invalid_auth_denied",False),
            ("wrong_process_endpoint_denied_before_any_http_bytes",False),
            ("t03_live_height_tip_parity_on_owned_core",False),
            ("t04_post_launch_pair_stable_during_core_hash",False),
            ("repeated_authenticated_reads",7),
            ("write_denied_before_wire",False),
            ("synthetic_core_rpc",True),
        ):
            with self.subTest(name=name):
                original=self.owned[name]
                self.owned[name]=value
                with self.assertRaises(T09EvidenceError):self.check()
                self.owned[name]=original
        for value in (None,{},True,1,"green"):
            with self.subTest(owned=value):
                with self.assertRaises(T09EvidenceError):
                    require_direct_rpc_evidence(platform="macos-arm64",height=102,
                      owned=value,wsp=self.wsp,wallet=self.wallet,
                      contention=True,operational=True)

    def test_actual_core_503_and_idle_must_be_both_measured(self):
        for field,wrong in (
                ("read_attempt_limit",4),
                ("observed_busy_attempts",1),
                ("queue_response_503",0),
                ("recovered_without_daemon_restart",False)):
            with self.subTest(field=field):
                busy=self.owned["node_busy_read_component"]
                original=busy[field];busy[field]=wrong
                with self.assertRaises(T09EvidenceError):self.check()
                busy[field]=original
        idle=self.owned["idle_read_component"]
        idle["request_replayed"]=True
        with self.assertRaises(T09EvidenceError):self.check()

    def test_native_wsp_and_uncertain_spend_are_nonoptional(self):
        self.wsp["scanner_transport"]="pinned-cli"
        with self.assertRaises(T09EvidenceError):self.check()
        self.wsp["scanner_transport"]="owned-http"
        self.wallet["real_core_lost_broadcast_reply_lock_retained"]=False
        with self.assertRaises(T09EvidenceError):self.check()

    def test_linux_headless_uncertain_and_gui_approval_distinct(self):
        self.wallet={"status":"REAL_LINUX_CORE_ROOT_WITNESS_HEADLESS_WALLET_E2E_PASS",
                     "real_core_rpc":True,"synthetic_rpc":False,
                     "mainnet_allowed":False,
                     "lost_actual_broadcast_reply_retained":True}
        self.assertTrue(self.check(platform="linux-x86_64")["operational_wallet_checked"])
        self.wallet["lost_actual_broadcast_reply_retained"]=False
        with self.assertRaises(T09EvidenceError):
            self.check(platform="linux-x86_64")


if __name__=="__main__":unittest.main()
