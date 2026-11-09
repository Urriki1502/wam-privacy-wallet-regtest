"""V19 physical-acceptance regressions (macOS Reconcile clipping, shared fault code).

Source/widget contracts only; genuine-Core reproduction evidence is retained
separately and is not inferred from these tests.
"""
import json
import os
import sys
import unittest

if sys.platform == "linux" and not os.environ.get("DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import test_q05_core_supervisor as fixture
from wam_regtest.shared_regtest import SharedRegtestError
from wam_regtest.supervisor_store import read_exact

class SharedFaultDiagnostic(unittest.TestCase):
    setUp = fixture.SupervisorLifecycleUnit.setUp
    owner = fixture.SupervisorLifecycleUnit.owner

    def test_unexpected_shared_peer_is_recorded_with_its_public_code(self):
        owner = self.owner()
        owner._record_failure('status', SharedRegtestError('SHARED_UNEXPECTED_PEER_DENIED'))
        self.assertEqual(json.loads(read_exact(owner.root, 'supervisor.failure')),
                         {'stage': 'status', 'code': 'SHARED_UNEXPECTED_PEER_DENIED'})

    def test_shared_error_with_free_text_still_never_echoes(self):
        owner = self.owner()
        owner._record_failure('status', SharedRegtestError('peer 192.168.1.9 secret'))
        raw = read_exact(owner.root, 'supervisor.failure')
        self.assertNotIn(b'192.168', raw)
        self.assertEqual(json.loads(raw)['code'], 'MANAGED_UNCLASSIFIED_FAILURE')


if __name__ == '__main__':
    unittest.main()
