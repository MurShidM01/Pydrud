"""The 1.6 native services: BLE, NFC, camera extras, speech, location.

The Java side cannot run here, so these tests pin the three things that
actually broke in the past: every Python command has a native handler, the
handler classes are generated and wired into the bridge, and the streaming
events they emit are routed to an App callback.
"""

import json
import os
import re
import unittest

from pydrud.commands.project import _JAVA_TEMPLATES
from pydrud.services.native import UNIMPLEMENTED_COMMANDS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "pydrud", "android", "templates", "android")

BLUETOOTH = ["bt_enabled", "bt_enable", "bt_scan", "bt_scan_stop",
             "bt_connect", "bt_disconnect", "bt_services", "bt_read",
             "bt_write", "bt_notify", "bt_bonded"]
NFC = ["nfc_available", "nfc_read", "nfc_write", "nfc_cancel"]
CAMERA = ["camera_flash", "camera_zoom", "camera_record",
          "camera_record_stop", "camera_scan"]
MISC = ["speech_listen", "color_picker", "location_watch", "notify_channel"]


def read(name):
    with open(os.path.join(TEMPLATES, name), encoding="utf-8") as handle:
        return handle.read()


class TestEverythingIsImplemented(unittest.TestCase):
    def test_no_command_is_left_unimplemented(self):
        self.assertEqual(set(UNIMPLEMENTED_COMMANDS), set())

    def test_connectivity_handles_bluetooth_and_nfc(self):
        source = read("ConnectivityServices.java.j2")
        for cmd in BLUETOOTH + NFC:
            with self.subTest(cmd=cmd):
                self.assertIn(f'case "{cmd}":', source)

    def test_capture_handles_camera_extras_and_friends(self):
        source = read("CaptureServices.java.j2")
        for cmd in CAMERA + MISC:
            with self.subTest(cmd=cmd):
                self.assertIn(f'case "{cmd}":', source)

    def test_every_handler_answers_exactly_once(self):
        """Each command case must end in a handler call, never fall through."""
        for name in ("CaptureServices", "ConnectivityServices"):
            source = read(f"{name}.java.j2")
            cases = re.findall(r'case "([a-z_]+)":(.*)', source)
            for cmd, tail in cases:
                if cmd in {"min", "low", "high", "urgent"}:
                    continue  # importance mapping, not a command
                with self.subTest(service=name, cmd=cmd):
                    self.assertIn("return true;", tail)


class TestWiring(unittest.TestCase):
    def test_the_new_classes_are_generated(self):
        self.assertIn("CaptureServices", _JAVA_TEMPLATES)
        self.assertIn("ConnectivityServices", _JAVA_TEMPLATES)
        for name in _JAVA_TEMPLATES:
            with self.subTest(template=name):
                self.assertTrue(
                    os.path.isfile(os.path.join(TEMPLATES, f"{name}.java.j2")))

    def test_the_bridge_dispatches_to_them(self):
        bridge = read("BridgeService.java.j2")
        self.assertIn("capture.handle(cmd, json)", bridge)
        self.assertIn("connectivity.handle(cmd, json)", bridge)

    def test_the_activity_forwards_results_and_disposes(self):
        activity = read("MainActivity.java.j2")
        self.assertIn("bridge.capture().onActivityResult(", activity)
        self.assertIn("bridge.connectivity().onActivityResult(", activity)
        self.assertIn("bridge.connectivity().dispose()", activity)

    def test_camera_extras_exist_on_the_activity(self):
        activity = read("MainActivity.java.j2")
        for method in ("setTorch", "setZoom", "startRecording",
                       "stopRecording", "setScanning"):
            with self.subTest(method=method):
                self.assertIn(f"public {'boolean' if method in {'setTorch', 'stopRecording'} else ''}".strip(),
                              activity)
                self.assertIn(method, activity)

    def test_gradle_has_the_new_dependencies(self):
        with open(os.path.join(ROOT, "pydrud", "android", "templates",
                               "android", "app", "build.gradle.kts.j2"),
                  encoding="utf-8") as handle:
            gradle = handle.read()
        self.assertIn("androidx.camera:camera-video", gradle)
        self.assertIn("com.google.mlkit:barcode-scanning", gradle)


class TestStreamingEvents(unittest.TestCase):
    """`location`, `bluetooth` and `recording` must reach an App callback."""

    def setUp(self):
        from pydrud.main import App
        self.app = App(target=lambda page: None)

    def test_location_events(self):
        seen = []
        self.app.on_location(seen.append)
        self.app._handle_raw_event(json.dumps(
            {"type": "location", "key": "", "data": {"latitude": 1.5}}))
        self.assertEqual(seen, [{"latitude": 1.5}])

    def test_bluetooth_events(self):
        seen = []
        self.app.on_bluetooth(seen.append)
        self.app._handle_raw_event(json.dumps(
            {"type": "bluetooth", "key": "",
             "data": {"event": "notify", "value": [1, 2]}}))
        self.assertEqual(seen[0]["event"], "notify")

    def test_recording_events(self):
        seen = []
        self.app.on_recording(seen.append)
        self.app._handle_raw_event(json.dumps(
            {"type": "recording", "key": "",
             "data": {"path": "/a.mp4", "ok": True}}))
        self.assertEqual(seen, [{"path": "/a.mp4", "ok": True}])

    def test_a_broken_handler_does_not_kill_the_loop(self):
        def boom(_):
            raise RuntimeError("nope")

        errors = []
        self.app.on_error(errors.append)
        self.app.on_location(boom)
        self.app._handle_raw_event(json.dumps(
            {"type": "location", "key": "", "data": {}}))
        self.assertEqual(len(errors), 1)


if __name__ == "__main__":
    unittest.main()
