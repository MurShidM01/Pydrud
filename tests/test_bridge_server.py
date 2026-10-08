"""The host-backend device bridge (``pydrud dev --bridge``).

A host-backend APK embeds no interpreter, so the device dials *out* to the
developer's machine. These tests attach a client that plays the device side —
connects, sends ``ready`` and reads frames — and assert the app's real render
protocol comes back, with no preview handshake in between.
"""

from __future__ import annotations

import json
import socket
import threading
import time
import unittest

from pydrud import App, Column, Text
from pydrud.core.bridge_server import BridgeServer


def _make_app():
    def main(page):
        page.add(Column(key="root", children=[Text("hello", key="t")]))

    return App(target=main, title="bridge", dev_server=False)


class _DeviceClient:
    """The device side of the bridge: dial out, speak NDJSON."""

    def __init__(self, host: str, port: int):
        self.sock = socket.create_connection((host, port), timeout=5)
        self.sock.settimeout(5)
        self._buffer = b""
        self.frames: list[dict] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()

    def _read(self) -> None:
        while not self._stop.is_set():
            try:
                data = self.sock.recv(65536)
            except OSError:
                break
            if not data:
                break
            self._buffer += data
            while b"\n" in self._buffer:
                line, self._buffer = self._buffer.split(b"\n", 1)
                text = line.decode("utf-8").strip()
                if text:
                    self.frames.append(json.loads(text))

    def send(self, message: dict) -> None:
        self.sock.sendall((json.dumps(message) + "\n").encode("utf-8"))

    def send_ready(self, **metrics) -> None:
        data = {
            "width": 400, "height": 800, "density": 2.0,
            "capabilities": {"native_view": True,
                             "widget_types": ["Column", "Text"]},
        }
        data.update(metrics)
        self.send({"type": "ready", "key": "", "data": data})

    def wait_for(self, predicate, timeout: float = 3.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate(self.frames):
                return True
            time.sleep(0.01)
        return False

    def close(self) -> None:
        self._stop.set()
        try:
            self.sock.close()
        except OSError:
            pass


class TestBridgeServer(unittest.TestCase):

    def setUp(self):
        self.app = _make_app()
        self.server = BridgeServer(self.app, host="127.0.0.1", port=0)
        self.host, self.port = self.server.start()
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()
        self.client = None

    def tearDown(self):
        if self.client is not None:
            self.client.close()
        self.server.stop()
        self.app.stop()

    def test_a_device_attaches_and_receives_the_render_protocol(self):
        self.client = _DeviceClient(self.host, self.port)
        self.client.send_ready()
        self.assertTrue(self.client.wait_for(
            lambda frames: any(f.get("cmd") == "theme" for f in frames)),
            "the app should push its palette")
        self.assertTrue(self.client.wait_for(
            lambda frames: any(
                f.get("cmd") in ("render_transaction", "full_render")
                for f in frames)),
            "the app should push an initial snapshot")

    def test_the_snapshot_contains_the_real_widget_tree(self):
        self.client = _DeviceClient(self.host, self.port)
        self.client.send_ready()

        def has_tree(frames):
            for frame in frames:
                tree = frame.get("tree")
                if tree and _find_key(tree, "t"):
                    return True
            return False

        self.assertTrue(self.client.wait_for(has_tree),
                        "the device should see the app's own widgets")

    def test_only_one_renderer_is_served_at_a_time(self):
        self.client = _DeviceClient(self.host, self.port)
        self.client.send_ready()
        deadline = time.time() + 3
        while time.time() < deadline and not self.server.active:
            time.sleep(0.01)
        self.assertTrue(self.server.active)

        second = _DeviceClient(self.host, self.port)
        try:
            # The second connection is closed rather than served.
            second.send_ready()
            time.sleep(0.2)
            self.assertFalse(any(f.get("cmd") == "theme"
                                 for f in second.frames))
        finally:
            second.close()


def _find_key(node: dict, key: str) -> bool:
    if node.get("key") == key:
        return True
    return any(_find_key(child, key)
               for child in node.get("children") or [])


class TestBridgeCli(unittest.TestCase):

    def _project(self, tmp_path):
        import pathlib
        project = pathlib.Path(tmp_path) / "demo"
        project.mkdir()
        (project / "pydrud.yaml").write_text("app_name: Demo\n", encoding="utf-8")
        (project / "src" / "app").mkdir(parents=True)
        return project

    def test_dev_bridge_flag_routes_to_the_bridge_runner(self):
        import tempfile
        from click.testing import CliRunner

        from pydrud.commands import bridge as bridge_module
        from pydrud.commands.cli import main as cli

        with tempfile.TemporaryDirectory() as tmp:
            project = self._project(tmp)
            calls = {}

            class _FakeRunner:
                def __init__(self, root, **kwargs):
                    calls["root"] = root
                    calls.update(kwargs)

                def run(self):
                    calls["ran"] = True
                    return 0

            original = bridge_module.BridgeRunner
            bridge_module.BridgeRunner = _FakeRunner
            try:
                result = CliRunner().invoke(
                    cli, ["dev", str(project), "--bridge", "--port", "9001",
                          "--no-reverse"])
            finally:
                bridge_module.BridgeRunner = original

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertTrue(calls.get("ran"))
            self.assertEqual(calls.get("port"), 9001)
            self.assertEqual(calls.get("reverse"), False)
            # A wildcard bind is reduced to loopback for the device bridge.
            self.assertEqual(calls.get("host"), "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
