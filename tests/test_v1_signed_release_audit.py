"""Offline transport negative tests; no synthetic signature can qualify WAM Core."""
import io
from pathlib import Path
import tempfile
import unittest
from urllib import request

from scripts.verify_v012_signed_release import (
    _RestrictedRedirect, _allowed, _download, AuditDenied, KEY, RELEASE)
from wam_regtest.core_release_preflight import ASSETS


class FakeResponse:
    def __init__(self, data=b"fixture", *, status=200, url=RELEASE+"SHA256SUMS"):
        self.body = io.BytesIO(data)
        self.status = status
        self.url = url
        self.headers = {}
    def read(self, n): return self.body.read(n)
    def __enter__(self): return self
    def __exit__(self, *unused): return False


class FakeOpener:
    def __init__(self, **kwargs): self.kwargs = kwargs
    def open(self, req, timeout):
        return FakeResponse(**self.kwargs)


class OfficialReleaseTransportTests(unittest.TestCase):
    def test_only_exact_trusted_https_hosts(self):
        self.assertTrue(_allowed(KEY))
        self.assertTrue(_allowed(RELEASE + "SHA256SUMS"))
        for url in (
            "http://github.com/data", "https://invalid.example.com/data",
            "file:///tmp/keys", "https://github.com:8443/data",
            "https://localhost/data", "https://user:pass@github.com/release",
            "https://github.com/data#fragment",
        ):
            with self.subTest(url=url): self.assertFalse(_allowed(url))

    def test_redirect_to_foreign_or_http_host_denied(self):
        handler = _RestrictedRedirect()
        for url in ("https://evil.example/data", "http://github.com/unsafe",
                    "file:///tmp/local"):
            with self.subTest(url=url), self.assertRaisesRegex(
                    AuditDenied, "V012_RELEASE_REDIRECT_DENIED"):
                handler.redirect_request(
                    request.Request(KEY), None, 302, "redirect", {}, url)

    def test_only_bounded_https_copy_succeeds(self):
        with tempfile.TemporaryDirectory() as t:
            dest = Path(t) / "SHA256SUMS"
            _download(FakeOpener(data=b"abc"), RELEASE+"SHA256SUMS", dest, 3)
            self.assertEqual(dest.read_bytes(), b"abc")
            with self.assertRaisesRegex(AuditDenied, "V012_RELEASE_SIZE_DENIED"):
                _download(FakeOpener(data=b"abcd"), RELEASE+"SHA256SUMS",
                          Path(t)/"overlarge", 3)
            with self.assertRaisesRegex(AuditDenied, "V012_RELEASE_HTTP_DENIED"):
                _download(FakeOpener(status=403), RELEASE+"SHA256SUMS",
                          Path(t)/"forbidden", 10)

    def test_network_empty_or_foreign_host_never_passes(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaisesRegex(AuditDenied, "V012_RELEASE_EMPTY_DENIED"):
                _download(FakeOpener(data=b""), RELEASE+"SHA256SUMS",
                          Path(t)/"empty", 100)
            with self.assertRaisesRegex(AuditDenied, "V012_RELEASE_HTTP_DENIED"):
                _download(FakeOpener(url="https://bad.example/data"),
                          RELEASE+"SHA256SUMS", Path(t)/"foreign", 100)

    def test_platforms_are_official_wam_coin_archive_only(self):
        self.assertEqual(set(ASSETS), {"macos-arm64", "windows-x64", "linux-x64"})
        self.assertEqual(len(set(ASSETS.values())), 3)
        self.assertTrue(all(a.startswith("wam-coin-v0.1.12-")
                            for a in ASSETS.values()))


if __name__ == "__main__":
    unittest.main()
