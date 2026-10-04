"""
Tests for Flutter-style Hot Reload, Hot Restart, DevServer, DevRunner, and TUI formatting.
"""

from __future__ import annotations

import json
import os
import socket
import tempfile
import unittest
from unittest import mock

from pydrud import App, State, Text
from pydrud.core.devserver import DevServer
from pydrud.runtime.navigation import Router
from pydrud.utils import tui
from pydrud.commands.devrunner import DevRunner, _KeyReader


class TestDevServerProtocol(unittest.TestCase):
    """Test the DevServer socket protocol and commands."""

    def setUp(self):
        self.count = State(10, name="count")
        self.app = App(target=lambda page: page.add(Text(f"Count: {self.count.value}")), dev_server=False)
        self.app.bind(self.count)
        self.server = DevServer(self.app, host="127.0.0.1", port=0)
        self.assertTrue(self.server.start())
        self.port = self.server.port

    def tearDown(self):
        self.server.stop()
        self.app.stop()

    def _send_cmd(self, payload: dict) -> dict:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", self.port))
        sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
        rfile = sock.makefile(encoding="utf-8")
        line = rfile.readline()
        sock.close()
        return json.loads(line)

    def test_ping_command(self):
        resp = self._send_cmd({"cmd": "ping"})
        self.assertEqual(resp["status"], "ok")
        self.assertIn("hot_reload", resp["capabilities"])
        self.assertIn("hot_restart", resp["capabilities"])
        self.assertIn("stream_errors", resp["capabilities"])

    def test_hot_reload_applies_code_and_preserves_state(self):
        # Initial state is 10
        self.assertEqual(self.count.value, 10)
        self.count.value = 42

        # Send a hot reload payload with a modified module
        py_code = """
from pydrud import State
count = State(0, name="count")
def get_val():
    return count.value * 2
"""
        resp = self._send_cmd({
            "cmd": "hot_reload",
            "files": [{"path": "src/app/state.py", "content": py_code}],
        })

        self.assertEqual(resp["status"], "ok")
        self.assertIn("app.state", resp["reloaded"])
        self.assertGreaterEqual(resp["states_preserved"], 1)
        self.assertIn("duration_ms", resp)
        # Value 42 must be preserved after reload
        self.assertEqual(self.count.value, 42)

    def test_hot_reload_syntax_error_is_caught_safely(self):
        bad_code = """
def broken_fn(
    return "missing parenthesis"
"""
        resp = self._send_cmd({
            "cmd": "hot_reload",
            "files": [{"path": "src/app/screens/home.py", "content": bad_code}],
        })

        self.assertEqual(resp["status"], "error")
        self.assertEqual(resp["error_type"], "SyntaxError")
        self.assertIn("lineno", resp)
        self.assertIn("traceback", resp)
        # Running app did not crash
        self.assertTrue(self.server.is_running)

    def test_hot_restart_resets_state_and_router(self):
        router = Router()
        router.define("home", lambda page: page.add(Text("Home")))
        router.define("details", lambda page: page.add(Text("Details")))
        router.initial("home")

        self.app.attach_router(router)
        router.go("details")
        self.assertEqual(router.current_route, "details")

        resp = self._send_cmd({"cmd": "hot_restart"})
        self.assertEqual(resp["status"], "ok")
        self.assertTrue(resp["restarted"])
        # Router must be reset to its configured initial route.
        self.assertEqual(router.current_route, "home")

    def test_dump_tree_command(self):
        resp = self._send_cmd({"cmd": "dump_tree"})
        self.assertEqual(resp["status"], "ok")
        self.assertIsNotNone(resp.get("tree"))

    def test_eval_command(self):
        resp = self._send_cmd({"cmd": "eval", "code": "2 + 2"})
        self.assertEqual(resp["status"], "ok")
        self.assertEqual(resp["result"], "4")

    def test_error_broadcasting(self):
        # Client listens for error broadcast
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", self.port))
        # Receive ping to establish
        sock.sendall((json.dumps({"cmd": "ping"}) + "\n").encode("utf-8"))
        rfile = sock.makefile(encoding="utf-8")
        _ = rfile.readline()

        # Trigger broadcast error
        try:
            raise ValueError("Test error message")
        except Exception as exc:
            self.server.broadcast_error(exc, title="Test Error")

        # Read broadcast line
        line = rfile.readline()
        sock.close()
        msg = json.loads(line)
        self.assertEqual(msg["type"], "error")
        self.assertEqual(msg["error_type"], "ValueError")
        self.assertIn("Test error message", msg["message"])


class TestTUIFormatting(unittest.TestCase):
    """Test clean terminal TUI rendering components."""

    def test_render_header_banner(self):
        banner = tui.render_header_banner(
            app_name="my_app",
            package_name="com.example.my_app",
            device_name="emulator-5554",
        )
        self.assertIn("Pydrud Native Runner", banner)
        self.assertIn("com.example.my_app", banner)
        self.assertIn("emulator-5554", banner)

    def test_hot_reload_badge(self):
        badge = tui.hot_reload_success(42.5, ["app.screens.home"], states_kept=2)
        self.assertIn("Hot reload", badge)
        self.assertIn("42ms", badge)
        self.assertIn("app.screens.home", badge)
        self.assertIn("kept 2 state(s)", badge)

    def test_hot_restart_badge(self):
        badge = tui.hot_restart_success(78.2)
        self.assertIn("Hot restart", badge)
        self.assertIn("78ms", badge)

    def test_error_box_rendering(self):
        tb = """Traceback (most recent call last):
  File "src/app/screens/home.py", line 42, in home_screen
    val = 1 / 0
ZeroDivisionError: division by zero"""
        box = tui.render_error_box(
            title="Python Runtime Error",
            message="",
            traceback_str=tb,
            filename="src/app/screens/home.py",
            lineno=42,
        )
        self.assertIn("Python Runtime Error", box)
        self.assertIn("ZeroDivisionError: division by zero", box)
        self.assertIn("src/app/screens/home.py", box)

    def test_syntax_error_box_rendering(self):
        box = tui.render_syntax_error_box(
            filename="src/app/main.py",
            lineno=15,
            offset=10,
            text="def broken_func(",
            message="'(' was never closed",
        )
        self.assertIn("Hot Reload Syntax Error", box)
        self.assertIn("src/app/main.py", box)
        self.assertIn("SyntaxError: '(' was never closed", box)

    def test_shortcuts_bar_and_help_box(self):
        bar = tui.render_shortcuts_bar()
        self.assertIn("[r]", bar)
        self.assertIn("[R]", bar)
        self.assertIn("[q]", bar)

        help_box = tui.render_help_box()
        self.assertIn("Hot reload", help_box)
        self.assertIn("Hot restart", help_box)
        self.assertIn("Dump widget tree", help_box)


class TestKeyReaderAndDevRunner(unittest.TestCase):
    """Test interactive key reader and DevRunner helpers."""

    def test_key_reader_dispatches_keys(self):
        received = []
        reader = _KeyReader(lambda k: received.append(k))
        reader._handle_key = lambda k: received.append(k)
        reader.callback("r")
        reader.callback("R")
        reader.callback("c")
        self.assertEqual(received, ["r", "R", "c"])

    def test_devrunner_initialization(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src", "app")
            os.makedirs(src_dir)
            with open(os.path.join(tmpdir, "pydrud.yaml"), "w") as fp:
                fp.write("package: com.test.app\n")

            runner = DevRunner(tmpdir, device="test-device-123", interactive=False)
            self.assertEqual(runner.device, "test-device-123")
            self.assertFalse(runner.interactive)
            self.assertEqual(runner.dev_port, 8596)

    def test_logcat_is_scoped_to_the_app_process(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "pydrud.yaml"), "w") as fp:
                fp.write("package: com.test.app\n")
            runner = DevRunner(tmpdir, device="serial", interactive=False)
            runner.package_name = "com.test.app"
            answer = mock.Mock(returncode=0, stdout="4242\n")
            with mock.patch("subprocess.run", return_value=answer) as run:
                command = runner._logcat_command()
            self.assertIn("--pid=4242", command)
            self.assertIn("System.err:W", command)
            self.assertEqual(runner._app_pid, "4242")
            self.assertIn("pidof", run.call_args.args[0])
            self.assertIn("com.test.app", run.call_args.args[0])

    def test_logcat_fallback_omits_global_system_error_noise(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "pydrud.yaml"), "w") as fp:
                fp.write("package: com.test.app\n")
            runner = DevRunner(tmpdir, interactive=False)
            answer = mock.Mock(returncode=1, stdout="")
            with mock.patch("subprocess.run", return_value=answer):
                command = runner._logcat_command()
            self.assertFalse(any(part.startswith("--pid=") for part in command))
            self.assertNotIn("System.err:W", command)
            self.assertNotIn("AndroidRuntime:E", command)


if __name__ == "__main__":
    unittest.main()
