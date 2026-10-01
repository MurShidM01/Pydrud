"""v1.3 native services: secure storage, background work, hardware, push.

These run against :class:`~pydrud.testing.FakeDevice`, which speaks the real
NDJSON protocol, so the assertions cover the exact commands the Android side
will receive.
"""

from __future__ import annotations

import unittest

from pydrud import App, Text
from pydrud.testing import FakeDevice, run_app


class ServiceTestCase(unittest.TestCase):

    def setUp(self):
        self.device = FakeDevice().start()
        self.app = App(target=lambda page: page.add(Text("hi")))
        run_app(self.app, self.device)
        self.assertTrue(self.device.wait_for(lambda d: d.full_renders >= 1))
        self.page = self.app.page

    def tearDown(self):
        self.app.stop()
        self.device.stop()

    def request(self, cmd: str) -> dict:
        found = self.device.wait_for_request(cmd)
        self.assertIsNotNone(found, f"no {cmd} command was sent")
        return found


class TestSecureStorage(ServiceTestCase):

    def test_round_trip(self):
        self.device.on_command("secure_set", True)
        self.device.on_command("secure_get", "jwt-token")
        self.page.secure.set("token", "jwt-token")
        self.assertEqual(self.request("secure_set")["key"], "token")

        value = self.page.secure.get("token").wait(timeout=2)
        self.assertEqual(value, "jwt-token")

    def test_delete_keys_clear_and_availability(self):
        for cmd, value in (("secure_remove", True), ("secure_keys", ["a"]),
                           ("secure_clear", True), ("secure_available", True)):
            self.device.on_command(cmd, value)
        self.assertTrue(self.page.secure.delete("token").wait(timeout=2))
        self.assertEqual(self.page.secure.keys().wait(timeout=2), ["a"])
        self.assertTrue(self.page.secure.clear().wait(timeout=2))
        self.assertTrue(self.page.secure.available().wait(timeout=2))


class TestBackground(ServiceTestCase):

    def test_schedule_sends_constraints(self):
        self.device.on_command("work_schedule", "sync")
        self.page.background.schedule("sync", every=900, network="unmetered",
                                      charging=True, inputs={"full": True})
        request = self.request("work_schedule")
        self.assertEqual(request["name"], "sync")
        self.assertEqual(request["every"], 900.0)
        self.assertEqual(request["network"], "unmetered")
        self.assertTrue(request["charging"])
        self.assertEqual(request["inputs"], {"full": True})

    def test_periodic_minimum_is_enforced(self):
        with self.assertRaises(ValueError):
            self.page.background.schedule("sync", every=60)
        with self.assertRaises(ValueError):
            self.page.background.schedule("sync", network="carrier-pigeon")

    def test_boolean_network_shorthand(self):
        self.device.on_command("work_schedule", "x")
        self.page.background.schedule("x", network=True)
        self.assertEqual(self.request("work_schedule")["network"], "connected")

    def test_jobs_are_registered_and_runnable(self):
        seen = []

        @self.page.background.job("report")
        def _report(inputs):
            seen.append(inputs)
            return "done"

        self.assertEqual(self.page.background.jobs, ["report"])
        self.assertEqual(self.page.background.run_job("report", {"n": 1}),
                         "done")
        self.assertEqual(seen, [{"n": 1}])
        with self.assertRaises(KeyError):
            self.page.background.run_job("missing")
        with self.assertRaises(TypeError):
            self.page.background.job("bad")("not callable")

    def test_worker_event_round_trip(self):
        """A `job` event from WorkManager must answer with `job_result`."""
        self.page.background.register("sync", lambda inputs: {"ok": inputs})
        self.device.send_event("job", "", {"name": "sync", "inputs": {"n": 2}})
        self.assertTrue(self.device.wait_for_command("job_result"))
        reply = [c for c in self.device.commands
                 if c.get("cmd") == "job_result"][-1]
        self.assertTrue(reply["ok"])
        self.assertEqual(reply["value"], {"ok": {"n": 2}})

    def test_failing_job_reports_an_error(self):
        def explode(inputs):
            raise RuntimeError("nope")

        self.page.background.register("boom", explode)
        self.device.send_event("job", "", {"name": "boom", "inputs": {}})
        self.assertTrue(self.device.wait_for_command("job_result"))
        reply = [c for c in self.device.commands
                 if c.get("cmd") == "job_result"][-1]
        self.assertFalse(reply["ok"])
        self.assertIn("nope", reply["error"])

    def test_foreground_service_commands(self):
        for cmd in ("service_start", "service_update", "service_stop"):
            self.device.on_command(cmd, True)
        self.page.background.start_service(title="Syncing", message="0/10")
        self.assertEqual(self.request("service_start")["title"], "Syncing")
        self.page.background.update_service(progress=50)
        self.assertEqual(self.request("service_update")["progress"], 50)
        self.page.background.stop_service()
        self.request("service_stop")

    def test_cancel_all(self):
        self.device.on_command("work_cancel", True)
        self.page.background.cancel_all()
        self.assertTrue(self.request("work_cancel")["all"])


class TestPushAndShortcuts(ServiceTestCase):

    def test_token_and_topics(self):
        self.device.on_command("push_token", "abc123")
        self.device.on_command("push_subscribe", True)
        self.assertEqual(self.page.push.token().wait(timeout=2), "abc123")
        self.page.push.subscribe("news")
        self.assertEqual(self.request("push_subscribe")["topic"], "news")

    def test_push_events_reach_the_handler(self):
        received = []
        self.app.on_push(received.append)
        self.device.send_event("push", "", {"title": "Hi", "route": "/inbox"})
        self.assertTrue(self.device.wait_for(lambda d: received))
        self.assertEqual(received[0]["route"], "/inbox")

    def test_shortcuts_are_validated(self):
        self.device.on_command("shortcuts_set", 2)
        self.page.shortcuts.set([
            {"id": "new", "label": "New note", "route": "/new"},
            {"id": "search", "label": "Search", "route": "/search"},
        ])
        request = self.request("shortcuts_set")
        self.assertEqual(len(request["shortcuts"]), 2)
        self.assertEqual(request["shortcuts"][0]["route"], "/new")

        with self.assertRaises(ValueError):
            self.page.shortcuts.set([{"label": "no id"}])
        with self.assertRaises(ValueError):
            self.page.shortcuts.set([{"id": str(i), "label": str(i)}
                                     for i in range(5)])

    def test_home_screen_widget_update(self):
        self.device.on_command("appwidget_update", True)
        self.page.shortcuts.update_widget({"count": 3})
        self.assertEqual(self.request("appwidget_update")["values"],
                         {"count": 3})


class TestDeepLinks(ServiceTestCase):

    def test_handler_receives_the_url(self):
        seen = []
        self.app.on_deep_link(seen.append)
        self.device.send_event("deep_link", "", {"url": "myapp://items/7"})
        self.assertTrue(self.device.wait_for(lambda d: seen))
        self.assertEqual(seen[0], "myapp://items/7")

    def test_links_arriving_before_a_handler_are_not_lost(self):
        self.device.send_event("deep_link", "", {"url": "myapp://late"})
        self.assertTrue(self.device.wait_for(
            lambda d: self.app._pending_deep_link is not None))
        seen = []
        self.app.on_deep_link(seen.append)
        self.assertEqual(seen, ["myapp://late"])

    def test_router_resolves_the_link(self):
        from pydrud.navigation import Router

        visited = []
        router = Router()
        router.define("/", lambda page: None)
        router.define("/items/:id",
                      lambda page, params: visited.append(params["id"]))
        router.initial("/")
        self.app.attach_router(router)

        self.device.send_event("deep_link", "", {"url": "myapp://items/12"})
        self.assertTrue(self.device.wait_for(lambda d: visited))
        self.assertEqual(visited[0], 12)


class TestHardware(ServiceTestCase):

    def test_sensor_stream(self):
        self.device.on_command("sensor_start", True)
        readings = []
        self.page.sensors.listen("accelerometer", readings.append, rate="game")
        request = self.request("sensor_start")
        self.assertEqual((request["sensor"], request["rate"]),
                         ("accelerometer", "game"))

        self.device.send_event("sensor", "", {"sensor": "accelerometer",
                                              "x": 0.1, "y": 9.8, "z": 0.0})
        self.assertTrue(self.device.wait_for(lambda d: readings))
        self.assertEqual(readings[0]["y"], 9.8)

    def test_sensor_validation(self):
        with self.assertRaises(ValueError):
            self.page.sensors.listen("vibes", lambda d: None)
        with self.assertRaises(ValueError):
            self.page.sensors.listen("light", lambda d: None, rate="turbo")
        with self.assertRaises(TypeError):
            self.page.sensors.listen("light", "not callable")

    def test_shake_detector(self):
        self.device.on_command("sensor_start", True)
        shakes = []
        self.page.sensors.shake(shakes.append, threshold=15)
        self.assertEqual(self.request("sensor_start")["threshold"], 15.0)
        self.device.send_event("sensor", "", {"sensor": "shake",
                                              "magnitude": 18})
        self.assertTrue(self.device.wait_for(lambda d: shakes))

    def test_camera_commands(self):
        self.device.on_command("camera_capture", "/data/photo.jpg")
        self.device.on_command("camera_flash", True)
        path = self.page.camera.capture(key="cam", quality=80).wait(timeout=2)
        self.assertEqual(path, "/data/photo.jpg")
        self.assertEqual(self.request("camera_capture")["quality"], 80)
        self.page.camera.flash("torch", key="cam")
        self.assertEqual(self.request("camera_flash")["mode"], "torch")

        with self.assertRaises(ValueError):
            self.page.camera.capture(quality=0)
        with self.assertRaises(ValueError):
            self.page.camera.flash("strobe")
        with self.assertRaises(ValueError):
            self.page.camera.start(facing="sideways")

    def test_biometrics(self):
        self.device.on_command("biometric_available",
                               {"available": True, "enrolled": True})
        self.device.on_command("biometric_auth", True)
        status = self.page.biometrics.available().wait(timeout=2)
        self.assertTrue(status["available"])
        self.assertTrue(self.page.biometrics.authenticate(
            title="Unlock").wait(timeout=2))
        self.assertEqual(self.request("biometric_auth")["title"], "Unlock")

    def test_bluetooth_scan_and_write(self):
        self.device.on_command("bt_scan", [{"address": "AA:BB", "name": "Tag"}])
        self.device.on_command("bt_write", True)
        devices = self.page.bluetooth.scan(seconds=3).wait(timeout=2)
        self.assertEqual(devices[0]["name"], "Tag")
        self.page.bluetooth.write("AA:BB", "180f", "2a19", b"\x01\x02")
        self.assertEqual(self.request("bt_write")["value"], [1, 2])

    def test_nfc(self):
        self.device.on_command("nfc_read", {"id": "04A2", "records": []})
        tag = self.page.nfc.read(timeout=5).wait(timeout=2)
        self.assertEqual(tag["id"], "04A2")
        with self.assertRaises(ValueError):
            self.page.nfc.write([])
        with self.assertRaises(ValueError):
            self.page.nfc.write([{"type": "binary", "value": "x"}])

    def test_audio_record_and_play(self):
        self.device.on_command("audio_record", "/tmp/a.m4a")
        self.device.on_command("audio_record_stop",
                               {"path": "/tmp/a.m4a", "seconds": 3})
        self.device.on_command("audio_play", 12.5)
        self.assertEqual(self.page.audio.record().wait(timeout=2), "/tmp/a.m4a")
        self.assertEqual(
            self.page.audio.stop_recording().wait(timeout=2)["seconds"], 3)
        self.assertEqual(self.page.audio.play("/tmp/a.m4a").wait(timeout=2),
                         12.5)
        with self.assertRaises(ValueError):
            self.page.audio.record(format="flac")
        with self.assertRaises(ValueError):
            self.page.audio.play("/tmp/a.m4a", volume=4)

    def test_text_to_speech_and_recognition(self):
        self.device.on_command("tts_speak", True)
        self.device.on_command("speech_listen", "hello world")
        self.page.audio.speak("Hello", rate=1.2)
        self.assertEqual(self.request("tts_speak")["rate"], 1.2)
        self.assertEqual(self.page.audio.listen().wait(timeout=2),
                         "hello world")


class TestPageCommandsV13(ServiceTestCase):

    def test_route_transition_command(self):
        self.page.route_transition("slide_left", duration=300)
        self.assertTrue(self.device.wait_for_command("route_transition"))
        command = [c for c in self.device.commands
                   if c.get("cmd") == "route_transition"][-1]
        self.assertEqual(command["transition"], "slide_left")
        self.assertEqual(command["duration"], 300)
        with self.assertRaises(ValueError):
            self.page.route_transition("warp")


if __name__ == "__main__":
    unittest.main()
