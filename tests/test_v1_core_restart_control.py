"""Supplemental authenticated lifecycle contracts; not real-Core acceptance."""
import json
import threading
import unittest
from unittest.mock import Mock

from wam_regtest.core_supervisor import CoreSupervisor
from wam_regtest.supervisor_protocol import PROTOCOL, ReplayGuard, request_proof, SupervisorProtocolError


class FirstStartAfterExit(unittest.TestCase):
    def setUp(self):
        self.secret=b'x'*32
        self.owner=CoreSupervisor.__new__(CoreSupervisor)
        self.owner._lock=threading.RLock()
        self.owner._guard=ReplayGuard(self.secret)
        self.owner._state='ready'
        self.owner._busy_until=0.0
        self.old_process=self.owner.process=Mock()
        self.old_read=self.owner.read=Mock()
        self.owner.binding=Mock()
        self.owner.read.attest.return_value={'chain':'regtest','blocks':101,'initialblockdownload':False}
        self.new_process=Mock()
        self.new_process.poll.return_value=None
        def start():
            self.assertIsNone(self.owner.process)
            self.old_read.close.assert_called_once_with()
            self.owner.process=self.new_process
            self.owner.binding=Mock()
            self.owner.read=Mock()
            self.owner.read.attest.return_value={'chain':'regtest','blocks':101,'initialblockdownload':False}
        self.owner.start=Mock(side_effect=start)

    def frame(self, secret=None):
        nonce='1'*32
        return (json.dumps({'protocol':PROTOCOL,'op':'start','nonce':nonce,
            'proof':request_proof(secret or self.secret,'start',nonce)})+'\n').encode('ascii')

    def test_first_authenticated_start_reaps_dead_child_and_starts_once(self):
        self.old_process.poll.return_value=-9
        result=self.owner.handle(self.frame())
        self.assertEqual(result['state'],'ready')
        self.assertEqual(result['height'],101)
        self.assertIs(self.owner.process,self.new_process)
        self.owner.start.assert_called_once_with()

    def test_live_child_is_never_duplicated(self):
        self.old_process.poll.return_value=None
        result=self.owner.handle(self.frame())
        self.assertEqual(result['state'],'ready')
        self.assertIs(self.owner.process,self.old_process)
        self.owner.start.assert_not_called()
        self.old_read.close.assert_not_called()

    def test_bad_authentication_cannot_even_poll_child(self):
        with self.assertRaises(SupervisorProtocolError):
            self.owner.handle(self.frame(b'y'*32))
        self.old_process.poll.assert_not_called()
        self.owner.start.assert_not_called()
        self.old_read.close.assert_not_called()

    def test_replay_cannot_restart_or_poll_again(self):
        self.old_process.poll.return_value=-9
        frame=self.frame()
        self.owner.handle(frame)
        polls=self.new_process.poll.call_count
        with self.assertRaises(SupervisorProtocolError):self.owner.handle(frame)
        self.assertEqual(self.new_process.poll.call_count,polls)
        self.owner.start.assert_called_once_with()

    def test_live_unverified_child_is_not_discarded_or_replaced(self):
        self.old_process.poll.return_value=None
        self.owner.binding._assert_image.side_effect=ValueError('PUBLIC_TEST_IMAGE_MISMATCH')
        result=self.owner.handle(self.frame())
        self.assertEqual(result['state'],'recovery-needed')
        self.assertFalse(result['core_process_owned'])
        self.assertIs(self.owner.process,self.old_process)
        self.owner.start.assert_not_called()
        self.old_read.close.assert_not_called()
