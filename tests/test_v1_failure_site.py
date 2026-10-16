"""Acceptance diagnostics must never disclose arbitrary exception/path text."""
import unittest
from wam_regtest.acceptance_failure import failure_site
class FailureSiteRedaction(unittest.TestCase):
 def test_unknown_path_and_error_payload_are_not_returned(self):
  try:raise ValueError('password-private-key-CANARY')
  except ValueError as error:
   self.assertEqual(failure_site(error),'UNCLASSIFIED_REVIEWED_SITE')
   self.assertNotIn('CANARY',failure_site(error))
