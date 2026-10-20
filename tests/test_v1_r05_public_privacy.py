"""R-05 public artifact privacy negative tests; no actual wallet secrets."""
import tempfile
from pathlib import Path
import unittest

from wam_regtest.r05_public_privacy import (
    PrivacyAuditError, audit_public_output,
)


class R05PublicPrivacyContracts(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="wam-r05-public-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "release"
        self.root.mkdir()
        (self.root / "RELEASE_CANDIDATE_MANIFEST.json").write_text(
            '{"schema":"public-test-only","network":"regtest"}\n',encoding="utf-8")
        (self.root / "SHA256SUMS.txt").write_text("public fixture only\n",encoding="utf-8")
        (self.root / "readme.md").write_text(
            "This is a synthetic public test explaining rpcpassword and mnemonic.\n",
            encoding="utf-8")

    def refuse_content(self, content, filename="receipt.json"):
        (self.root / filename).write_text(content, encoding="utf-8")
        with self.assertRaisesRegex(PrivacyAuditError,"^R05_PLAINTEXT_SECRET_MARKER_DENIED$"):
            audit_public_output(self.root)

    def test_public_docs_and_manifest_are_scoped_not_release_approved(self):
        r = audit_public_output(self.root)
        self.assertEqual(r["status"], "R05_PUBLIC_TEXT_AND_PATH_AUDIT_PASS")
        self.assertEqual(r["text_files_examined"],3)
        for field in ("binary_archive_payloads_scanned",
                      "screenshot_pixels_reviewed", "runtime_dns_or_telemetry_audited",
                      "external_security_reviewed", "production_qualified",
                      "mainnet_allowed"):
            self.assertIs(r[field],False)

    def test_private_wallet_and_os_storage_file_names_denied(self):
        for name in (
            "wam.conf","wallet.dat","debug.log",".cookie",".env",
            "vault.sqlite","recovery.sqlite-wal","profile.enc",
            "backup.keychain-db","keychain.pem","secrets.json",
            "keys.mnemonic","encryption.pfx",
        ):
            with self.subTest(name=name):
                p=self.root/name
                p.write_text("synthetic no secret bytes", encoding="utf-8")
                with self.assertRaisesRegex(PrivacyAuditError,"^R05_PRIVATE_FILENAME_DENIED$"):
                    audit_public_output(self.root)
                p.unlink()

    def test_nested_private_filename_denied(self):
        folder=self.root/"ui-scale"
        folder.mkdir()
        p=folder/"wallet.sqlite"
        p.write_bytes(b"public dummy")
        with self.assertRaises(PrivacyAuditError):
            audit_public_output(self.root)

    def test_plaintext_credential_and_seed_keys_denied(self):
        for content in (
            "rpcpassword=synthetic-string",
            '  RPCPASSWORD = synthetic-string\n',
            '{"rpcpassword": "public-test-token"}',
            '{"rpc_password": "public-test-token"}',
            '{"seed_phrase": "word1 word2 word3"}',
            '{"mnemonic": "word1 word2 word3"}',
            '{"private_key": "public-test-only"}',
            "-----BEGIN PRIVATE KEY-----\npublic fixture",
            "-----BEGIN OPENSSH PRIVATE KEY-----\npublic fixture",
            "Authorization: Basic YWJjZGVmZ2hpamtsbW5vcA==",
            "xprv" + "1"*36,
        ):
            with self.subTest(marker=content[:18]):
                self.refuse_content(content)

    def test_public_education_text_without_values_is_allowed(self):
        (self.root/"explanations.txt").write_text(
            "Never publish rpcpassword, seed_phrase or private_key.\n"
            "Never store a real .cookie file in the output.\n",
            encoding="utf-8")
        self.assertEqual(audit_public_output(self.root)["text_files_examined"],4)

    def test_bad_utf8_and_binary_text_refused(self):
        p=self.root/"bad.json"
        p.write_bytes(b"not-utf8-\xff")
        with self.assertRaisesRegex(PrivacyAuditError,"R05_PUBLIC_TEXT_UNREADABLE"):
            audit_public_output(self.root)
        p.write_bytes(b"secret\x00encoded")
        with self.assertRaisesRegex(PrivacyAuditError,"R05_PUBLIC_TEXT_BINARY_DENIED"):
            audit_public_output(self.root)

    def test_overlarge_text_is_not_silently_skipped(self):
        # Sparse file avoids allocating 16 MiB in memory.
        p=self.root/"oversized.log"
        with p.open("wb") as stream:
            stream.truncate(16*1024*1024+1)
        with self.assertRaisesRegex(PrivacyAuditError,"R05_PUBLIC_TEXT_TYPE_OR_SIZE_DENIED"):
            audit_public_output(self.root)

    def test_untrusted_symlink_denied(self):
        link=self.root/"extra-link.json"
        try:
            link.symlink_to(self.root/"readme.md")
        except OSError:
            self.skipTest("HOST_SYMLINK_CREATION_UNAVAILABLE")
        with self.assertRaisesRegex(PrivacyAuditError,"R05_PUBLIC_TREE_DENIED"):
            audit_public_output(self.root)

    def test_no_private_values_in_errors(self):
        raw="rpcpassword=public-test-PRIVATE-IDENTIFIER"
        (self.root/"credentials.txt").write_text(raw,encoding="utf-8")
        try:
            audit_public_output(self.root)
        except PrivacyAuditError as exc:
            self.assertNotIn("public-test-PRIVATE-IDENTIFIER",str(exc))
        else:
            self.fail("private-looking marker was not refused")

    def test_read_only_does_not_modify_outputs(self):
        p=self.root/"readme.md"
        old=p.read_bytes()
        audit_public_output(self.root)
        self.assertEqual(p.read_bytes(),old)


if __name__=="__main__":
    unittest.main()
