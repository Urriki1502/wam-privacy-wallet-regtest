"""R-02 immutable version profile and fail-closed release classification tests.

Synthetic public fields are NOT release signature or native Core E2E evidence.
Authenticated genuine Core getnetworkinfo is exercised by native RPC CI.
"""
import unittest

from wam_regtest.r02_compatibility import (
    COMPATIBLE_RPC_V011,
    R02CompatibilityError,
    SIGNER_FINGERPRINT,
    V011_OFFICIAL_MEMBER_PINS,
    classify_release_candidate,
    matches_v011_native_rpc,
)
from wam_regtest.json_rpc import _result, RpcError, SUPPORTED_RPC


class R02CompatibilityContracts(unittest.TestCase):
    def known(self, platform="macos-arm64", **change):
        # Adversarial inputs must reach the actual classifier. Use known-good
        # PUBLIC macOS digests when constructing an invalid platform fixture;
        # the candidate platform itself is passed through unchanged.
        profile = V011_OFFICIAL_MEMBER_PINS.get(platform) if type(platform) is str else None
        if profile is None:
            profile = V011_OFFICIAL_MEMBER_PINS["macos-arm64"]
        kw = dict(platform=platform, version="v0.1.11", network="regtest",
                  wamd_sha256=profile["wamd"], wam_cli_sha256=profile["wam_cli"],
                  signer_fingerprint=SIGNER_FINGERPRINT,
                  signed_archive_verified=True)
        kw.update(change)
        return kw

    def test_current_v011_rpc_binding_exact(self):
        live = {"version":111, "subversion":"/WAM:0.1.11/",
                "protocolversion":70016}
        self.assertEqual(SUPPORTED_RPC, COMPATIBLE_RPC_V011)
        self.assertTrue(matches_v011_native_rpc(live))
        self.assertIs(_result("getnetworkinfo", live), live)

    def test_newer_rpc_never_auto_approved(self):
        good = {"version":111, "subversion":"/WAM:0.1.11/",
                "protocolversion":70016}
        for key,value in (("version",112),("version",True),
                          ("protocolversion",70017),
                          ("protocolversion",True),
                          ("subversion","/WAM:0.1.12/"),
                          ("subversion","/WAM:0.1.11//"),
                          ("subversion",None)):
            with self.subTest(key=key,value=value):
                malformed=dict(good); malformed[key]=value
                self.assertFalse(matches_v011_native_rpc(malformed))
                with self.assertRaisesRegex(RpcError,"RPC_VERSION_CAPABILITY_DENIED"):
                    _result("getnetworkinfo",malformed)

    def test_official_v011_known_mac_and_windows_pins_are_component_only(self):
        for platform in ("macos-arm64","windows-x64"):
            with self.subTest(platform=platform):
                outcome=classify_release_candidate(**self.known(platform))
                self.assertEqual(outcome["status"],"R02_V011_PUBLIC_MEMBER_PINS_MATCH_ONLY")
                self.assertTrue(outcome["public_member_pins_matched"])
                self.assertFalse(outcome["r02_full_p0_qualified"])
                for name in ("observed_release_is_genuinely_authenticated_here",
                             "runtime_process_and_core_attested_here",
                             "cross_platform_core_e2e_qualified",
                             "wsp_and_signer_e2e_qualified",
                             "descriptor_import_and_recovery_qualified",
                             "frozen_gui_and_os_custody_qualified",
                             "core_activation_allowed",
                             "wallet_signing_or_broadcast_allowed",
                             "mainnet_allowed"):
                    self.assertFalse(outcome[name], name)

    def test_signed_v012_never_becomes_approved(self):
        for platform in ("macos-arm64","windows-x64"):
            with self.subTest(platform=platform):
                receipt=classify_release_candidate(**self.known(platform,version="v0.1.12"))
                self.assertEqual(receipt["status"],"R02_NEW_VERSION_REQUALIFICATION_PENDING")
                self.assertFalse(receipt["public_member_pins_matched"])
                self.assertFalse(receipt["core_activation_allowed"])

    def test_unknown_signed_version_refused(self):
        outcome=classify_release_candidate(**self.known(version="v0.1.13"))
        self.assertEqual(outcome["status"],"R02_UNKNOWN_PROFILE_DENIED")
        self.assertFalse(outcome["core_activation_allowed"])

    def test_linux_developer_core_not_misrepresented_as_official(self):
        outcome=classify_release_candidate(
            platform="linux-x64",version="v0.1.11",network="regtest",
            wamd_sha256="a"*64,wam_cli_sha256="b"*64,
            signer_fingerprint=SIGNER_FINGERPRINT,signed_archive_verified=True)
        self.assertEqual(outcome["status"],"R02_LINUX_NATIVE_PROVENANCE_AND_CLI_PENDING")
        self.assertFalse(outcome["public_member_pins_matched"])
        self.assertFalse(outcome["r02_full_p0_qualified"])

    def test_untrusted_or_wrong_signing_key_refused(self):
        for bad in ({"signed_archive_verified":False},
                    {"signer_fingerprint":"A"*40}):
            with self.subTest(bad=bad):
                r=classify_release_candidate(**self.known(**bad))
                self.assertEqual(r["status"],"R02_UNTRUSTED_RELEASE_DENIED")
                self.assertFalse(r["core_activation_allowed"])

    def test_observed_hash_mismatch_or_cross_platform_swap_refused(self):
        mac=self.known()
        win=self.known("windows-x64")
        for changed in (
            {"wamd_sha256":"0"*64},
            {"wam_cli_sha256":"0"*64},
            {"wamd_sha256":win["wamd_sha256"]},
            {"wam_cli_sha256":win["wam_cli_sha256"]},
        ):
            with self.subTest(changed=changed):
                r=classify_release_candidate(**self.known(**changed))
                self.assertEqual(r["status"],"R02_OFFICIAL_MEMBER_HASH_DENIED")
                self.assertFalse(r["public_member_pins_matched"])
                self.assertFalse(r["core_activation_allowed"])

    def test_non_regtest_refused_even_with_valid_pins(self):
        for chain in ("main","test","", "regtest "):
            with self.subTest(chain=chain):
                r=classify_release_candidate(**self.known(network=chain))
                self.assertEqual(r["status"],"R02_NON_REGTEST_DENIED")
                self.assertFalse(r["core_activation_allowed"])

    def test_unknown_os_refused(self):
        r=classify_release_candidate(**self.known(platform="darwin-unknown"))
        self.assertEqual(r["status"],"R02_UNKNOWN_PROFILE_DENIED")
        self.assertEqual(r["platform"],"unrecognized")

    def test_corrupt_metadata_refused_before_classification(self):
        for changed in (
            {"signed_archive_verified":1},
            {"wamd_sha256":"A"*64},
            {"wam_cli_sha256":"d"*63},
            {"signer_fingerprint":"a"*40},
            {"version":1},
            {"platform":None},
            {"network":True},
        ):
            with self.subTest(changed=changed):
                with self.assertRaises(R02CompatibilityError):
                    classify_release_candidate(**self.known(**changed))


if __name__=="__main__":
    unittest.main()
