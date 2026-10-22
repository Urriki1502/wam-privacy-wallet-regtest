"""Actual kernel socket regressions; not blockchain E2E substitutes."""
import socket
import sys
import unittest
from wam_regtest.core_supervisor import _listener


class ControlListenerRestart(unittest.TestCase):
    @unittest.skipIf(sys.platform=='win32','POSIX TIME_WAIT contract; Windows exclusive binding unchanged')
    def test_server_closed_ipc_can_rebind_immediately(self):
        first=_listener(0)
        port=first.getsockname()[1]
        with socket.create_connection(('127.0.0.1',port),timeout=2) as peer:
            connection,_=first.accept()
            connection.close()  # server is active closer, leaves TIME_WAIT
            self.assertEqual(peer.recv(1),b'')
        first.close()
        with _listener(port) as restarted:
            self.assertEqual(restarted.getsockname(),('127.0.0.1',port))

    def test_active_listener_cannot_be_shared(self):
        with _listener(0) as active:
            port=active.getsockname()[1]
            with self.assertRaises(OSError):
                _listener(port)
            # No connection/authentication traffic was sent by failed bind.
            active.settimeout(.05)
            with self.assertRaises(socket.timeout):active.accept()


if __name__=='__main__':unittest.main()
