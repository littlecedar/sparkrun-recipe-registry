"""The wire: one JSON line per request, and the refusals a broken or hostile peer gets."""

from __future__ import annotations

import io
import os
import socketserver
import tempfile
import threading
import unittest

from sparkrun_campaign import protocol


class _Echo(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        message = protocol.read_message(self.rfile)
        self.wfile.write(protocol.encode({"op": "ack", "echo": message["op"]}))
        self.wfile.flush()


class RoundTrip(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "director.sock")

    def serve(self, requests: int) -> None:
        server = socketserver.UnixStreamServer(self.path, _Echo)
        server.timeout = 5.0
        self.addCleanup(server.server_close)

        def loop() -> None:
            for _ in range(requests):
                server.handle_request()

        threading.Thread(target=loop, daemon=True).start()

    def test_a_request_gets_one_reply(self) -> None:
        self.serve(1)
        self.assertEqual(protocol.request(self.path, protocol.poll("w1")),
                         {"op": "ack", "echo": "poll"})

    def test_each_request_is_its_own_connection(self) -> None:
        self.serve(3)
        for message in (protocol.poll("w1"), protocol.beat("arm@1"), protocol.report("arm@1", 4)):
            reply = protocol.request(self.path, message)
            self.assertEqual(reply["echo"], message["op"])

    def test_a_newline_in_a_value_cannot_break_framing(self) -> None:
        payload = protocol.encode({"op": "ack", "note": "line\nwith newline"})
        self.assertEqual(payload.count(b"\n"), 1)
        self.assertTrue(payload.endswith(b"\n"))


class Refusals(unittest.TestCase):
    def test_a_non_object_message_is_refused(self) -> None:
        with self.assertRaises(protocol.ProtocolError):
            protocol.decode(b"[1, 2, 3]\n")

    def test_a_message_without_an_op_is_refused(self) -> None:
        with self.assertRaises(protocol.ProtocolError):
            protocol.decode(b'{"worker": "w1"}\n')

    def test_a_message_over_the_limit_is_refused_before_parsing(self) -> None:
        with self.assertRaises(protocol.ProtocolError):
            protocol.decode(b"x" * (protocol.MAX_LINE + 1))

    def test_garbage_is_refused(self) -> None:
        with self.assertRaises(protocol.ProtocolError):
            protocol.decode(b"not json at all\n")

    def test_a_peer_that_closes_without_a_message_is_refused(self) -> None:
        with self.assertRaises(protocol.ProtocolError):
            protocol.read_message(io.BytesIO(b""))


if __name__ == "__main__":
    unittest.main()