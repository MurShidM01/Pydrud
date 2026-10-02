"""
Native events that used to fall on the floor.

``push_token``, ``audio_complete`` and ``protocol_error`` are emitted by the
generated Java but had no handler in :class:`~pydrud.runtime.app.App`, so the
features they drive (token refresh, playback completion, a rejected render)
silently did nothing.  These run against the real NDJSON protocol via
:class:`~pydrud.testing.FakeDevice`.
"""

from __future__ import annotations

import unittest

from pydrud import App, Text
from pydrud.testing import FakeDevice, run_app


class EventTestCase(unittest.TestCase):

    def setUp(self):
        self.device = FakeDevice().start()
        self.app = App(target=lambda page: page.add(Text("hi")))

    def start(self):
        run_app(self.app, self.device)
        self.assertTrue(self.device.wait_for(lambda d: d.full_renders >= 1))

    def tearDown(self):
        self.app.stop()
        self.device.stop()


class TestPushToken(EventTestCase):

    def test_token_reaches_the_handler(self):
        seen = []
        self.app.on_push_token(seen.append)
        self.start()
        self.device.send_event("push_token", "", {"token": "fcm-abc"})
        self.assertTrue(self.device.wait_for(lambda _d: seen))
        self.assertEqual(["fcm-abc"], seen)

    def test_no_handler_is_harmless(self):
        self.start()
        self.device.send_event("push_token", "", {"token": "x"})
        self.assertTrue(self.device.wait_for(lambda d: d.full_renders >= 1))


class TestAudioComplete(EventTestCase):

    def test_completion_payload_is_delivered(self):
        seen = []
        self.app.on_audio_complete(seen.append)
        self.start()
        self.device.send_event("audio_complete", "", {"source": "ping.mp3"})
        self.assertTrue(self.device.wait_for(lambda _d: seen))
        self.assertEqual("ping.mp3", seen[0]["source"])


class TestProtocolError(EventTestCase):

    def test_protocol_error_is_reported(self):
        errors = []
        self.app.on_error(errors.append)
        self.start()
        self.device.send_event("protocol_error", "",
                               {"code": 7, "message": "unknown op"})
        self.assertTrue(self.device.wait_for(lambda _d: errors))
        self.assertIn("unknown op", str(errors[0]))
        self.assertIn("7", str(errors[0]))


if __name__ == "__main__":
    unittest.main()
