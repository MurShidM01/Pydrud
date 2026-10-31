"""Regression tests for the audit findings.

Each test pins one defect that was confirmed by execution against 2.1.6, so
the behaviour cannot silently come back:

* SEC-01  dev server is opt-in and debug-only; no release APK listens
* SEC-02  hot reload cannot write outside the sync directory
* SEC-05  the DevServer line buffer is bounded
* SEC-03  the preview server binds loopback by default
* BUG-01  a TOML inline comment is not part of a requirement
* BUG-02  an invalid --accent is a clean error, not a traceback
* BUG-03  a zero-interval Timer does not busy-spin
* BUG-04  the running interpreter wins when its version matches
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import time
import unittest

import pydrud
from pydrud import App, Text
from pydrud.core.tasks import MIN_TIMER_INTERVAL, Timer
from pydrud.platforms.android import devserver as devserver_module
from pydrud.runtime._hotreload import _safe_synced_path
from pydrud.utils.toml import unquote

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _app() -> App:
    return App(target=lambda page: page.add(Text("hi")), dev_server=False)


class TestDevServerIsOptIn(unittest.TestCase):
    """SEC-01: the dev server must never be on by default."""

    def test_app_defaults_to_no_dev_server(self):
        app = App(target=lambda page: None)
        self.assertFalse(app._dev_server_enabled)

    def test_generated_entry_points_ask_for_a_debug_build(self):
        for template in ("python/main.py.j2", "python/app/android_main.py.j2"):
            text = (ROOT / "pydrud" / "android" / "templates" / template).read_text(
                encoding="utf-8")
            self.assertIn("dev_server=dev_server_allowed()", text,
                          f"{template} must gate the dev server on a debug build")
            self.assertIn("from pydrud.platforms.android.devserver import",
                          text)

    def test_activity_sets_the_debug_property(self):
        text = (ROOT / "pydrud" / "android" / "templates" / "android"
                / "MainActivity.java.j2").read_text(encoding="utf-8")
        self.assertIn("FLAG_DEBUGGABLE", text)
        self.assertIn('System.setProperty("pydrud.dev_server", "1")', text)

    def test_host_opt_in_is_explicit(self):
        saved = os.environ.pop("PYDRUD_DEV_SERVER", None)
        try:
            self.assertFalse(devserver_module.dev_server_allowed())
            os.environ["PYDRUD_DEV_SERVER"] = "1"
            self.assertTrue(devserver_module.dev_server_allowed())
        finally:
            os.environ.pop("PYDRUD_DEV_SERVER", None)
            if saved is not None:
                os.environ["PYDRUD_DEV_SERVER"] = saved


class _FakeSocket:
    """Just enough of a socket for DevServer._client_handler."""

    def __init__(self, chunks):
        self._chunks = list(chunks)
        self.sent: list[bytes] = []
        self.closed = False

    def recv(self, _size):
        return self._chunks.pop(0) if self._chunks else b""

    def sendall(self, data):
        self.sent.append(data)

    def close(self):
        self.closed = True


class TestDevServerFrameCap(unittest.TestCase):
    """SEC-05: a client that never sends a newline cannot exhaust memory."""

    def test_cap_is_finite(self):
        self.assertLess(devserver_module.MAX_FRAME_BYTES, 64 * 1024 * 1024)

    def test_oversized_frame_is_refused(self):
        server = devserver_module.DevServer(_app(), host="127.0.0.1", port=0)
        server._running = True  # the handler loops while the server is live
        chunk = b"x" * 65536
        rounds = devserver_module.MAX_FRAME_BYTES // len(chunk) + 2
        fake = _FakeSocket([chunk] * rounds)
        server._client_handler(fake)
        self.assertTrue(fake.closed)
        self.assertTrue(fake.sent, "the client must be told why it was dropped")
        payload = json.loads(fake.sent[0].decode("utf-8").splitlines()[0])
        self.assertEqual(payload["status"], "error")
        self.assertIn("Frame", payload["error"])

    def test_normal_frames_still_work(self):
        server = devserver_module.DevServer(_app(), host="127.0.0.1", port=0)
        server._running = True
        fake = _FakeSocket([(json.dumps({"cmd": "ping"}) + "\n").encode()])
        server._client_handler(fake)
        payload = json.loads(fake.sent[0].decode("utf-8").splitlines()[0])
        self.assertEqual(payload["status"], "ok")


class TestHotReloadPathContainment(unittest.TestCase):
    """SEC-02: host-supplied paths may not escape the sync directory."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pydrud-sync-")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_safe_paths_are_accepted(self):
        self.assertTrue(_safe_synced_path(self.tmp, "app/screens/home.py"))
        self.assertTrue(_safe_synced_path(self.tmp, "src/app/main.py"))

    def test_traversal_and_absolute_paths_are_rejected(self):
        for candidate in ("../escape.py", "a/../../escape.py", "/etc/passwd",
                          "C:/Windows/evil.py", "..", "", "src/../x.py"):
            with self.subTest(candidate=candidate):
                self.assertIsNone(_safe_synced_path(self.tmp, candidate))

    def test_apply_hot_reload_refuses_to_write_outside(self):
        app = _app()
        app._get_sync_dir = lambda: self.tmp  # type: ignore[method-assign]
        escape = os.path.join(os.path.dirname(self.tmp), "pydrud_escape.py")
        if os.path.exists(escape):
            os.remove(escape)
        result = app.apply_hot_reload([{"path": "../pydrud_escape.py",
                                        "content": "ESCAPED = True\n"}])
        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("error_type"), "InvalidPath")
        self.assertFalse(os.path.exists(escape))


class TestTomlInlineComments(unittest.TestCase):
    """BUG-01: a comment after a requirement must not reach Gradle."""

    def test_unquote_drops_a_trailing_comment(self):
        self.assertEqual(unquote(' ">=2.31"  # pinned'), ">=2.31")
        self.assertEqual(unquote("'2.0' # old"), "2.0")
        self.assertEqual(unquote(">=1.0"), ">=1.0")

    def test_unquote_keeps_hashes_inside_quotes(self):
        self.assertEqual(unquote('"==1.0 # not a comment"'), "==1.0 # not a comment")

    def test_requirements_load_strips_comments(self):
        from pydrud.commands.packages import Requirements

        project = tempfile.mkdtemp(prefix="pydrud-toml-")
        try:
            with open(os.path.join(project, "pydrud.toml"), "w",
                      encoding="utf-8") as handle:
                handle.write('[python.packages]\n'
                             'requests = ">=2.31"  # pinned for the API client\n'
                             'yt-dlp = ""\n')
            self.assertEqual(Requirements(project).load(),
                             {"requests": ">=2.31", "yt-dlp": ""})
        finally:
            import shutil
            shutil.rmtree(project, ignore_errors=True)


class TestCreateRejectsBadAccent(unittest.TestCase):
    """BUG-02: invalid input is a message, not a traceback."""

    def test_invalid_accent_exits_cleanly(self):
        from click.testing import CliRunner

        from pydrud.commands.cli import main

        previous = os.getcwd()
        workdir = tempfile.mkdtemp(prefix="pydrud-create-")
        try:
            os.chdir(workdir)
            result = CliRunner().invoke(
                main, ["create", "badaccent", "--accent", "notacolor"])
        finally:
            os.chdir(previous)
            import shutil
            shutil.rmtree(workdir, ignore_errors=True)

        self.assertEqual(result.exit_code, 1)
        self.assertNotIn("Traceback", result.output)
        self.assertIn("notacolor", result.output)
        self.assertFalse(os.path.exists(os.path.join(workdir, "badaccent")))


class TestTimerMinimumInterval(unittest.TestCase):
    """BUG-03: a zero interval used to spin a core at ~60 kHz."""

    def test_zero_interval_is_clamped(self):
        timer = Timer(0.0, lambda: None)
        self.assertAlmostEqual(timer.interval, MIN_TIMER_INTERVAL)

    def test_negative_interval_is_clamped(self):
        self.assertAlmostEqual(Timer(-5, lambda: None).interval,
                               MIN_TIMER_INTERVAL)

    def test_ticks_are_bounded_by_the_clamp(self):
        ticks = {"n": 0}

        def tick():
            ticks["n"] += 1

        timer = Timer(0.0, tick, repeat=True).start()
        try:
            time.sleep(0.15)
        finally:
            timer.cancel()
        self.assertLess(ticks["n"], 100,
                        "a zero-interval timer must not busy-spin")


class TestBuildPythonPrefersRunningInterpreter(unittest.TestCase):
    """BUG-04: a 3.11 venv on a 3.12 PATH must pick the venv."""

    def test_running_interpreter_wins_when_versions_match(self):
        from pydrud.commands import project

        current = f"{sys.version_info.major}.{sys.version_info.minor}"
        self.assertEqual(project._detect_build_python(current),
                         sys.executable.replace("\\", "/"))


class TestPreviewBindsLoopback(unittest.TestCase):
    """SEC-03: the preview server is not a LAN service by default."""

    def test_preview_server_default_host(self):
        import inspect

        from pydrud.core.preview_server import PreviewServer

        default = inspect.signature(PreviewServer).parameters["host"].default
        self.assertEqual(default, "127.0.0.1")


class TestVersionHasOneSource(unittest.TestCase):
    """MAINT-01: the compatibility matrix follows pydrud.__version__."""

    def test_compatibility_matches_package_version(self):
        from pydrud.compatibility import COMPATIBILITY, HOST_COMPATIBILITY

        self.assertEqual(HOST_COMPATIBILITY.framework_version, pydrud.__version__)
        self.assertEqual(COMPATIBILITY.android_runtime_version, pydrud.__version__)


class TestVersionIsDerived(unittest.TestCase):
    """The release version is declared once, in project metadata."""

    def test_version_module_carries_no_release_literal(self):
        text = (ROOT / "pydrud" / "_version.py").read_text(encoding="utf-8")
        self.assertNotRegex(
            text, r'__version__\s*=\s*["\']\d',
            "pydrud/_version.py must resolve the version, not declare it")

    def test_pyproject_declares_the_version(self):
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertRegex(text, r'(?m)^version = "\d+\.\d+\.\d+"')

    def test_resolution_finds_the_declaration(self):
        from pydrud import _version as version

        self.assertNotEqual(version.resolve_version(), version._UNRESOLVED)

    def test_bundle_stamps_the_resolved_version(self):
        import importlib.util

        from pydrud.commands.project.bundle import _write_build_info

        target = tempfile.mkdtemp(prefix="pydrud-bundle-")
        try:
            _write_build_info(target)
            path = os.path.join(target, "_build_info.py")
            self.assertTrue(os.path.isfile(path))
            spec = importlib.util.spec_from_file_location("_bundle_info", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertEqual(module.__version__, pydrud.__version__)
        finally:
            import shutil
            shutil.rmtree(target, ignore_errors=True)


class TestSharedConstants(unittest.TestCase):
    """Ports and frame caps come from one module, not scattered literals."""

    def test_ports_are_defined_once(self):
        from pydrud.core import ports

        self.assertEqual(ports.DEFAULT_BRIDGE_PORT, 8595)
        self.assertEqual(ports.DEFAULT_DEV_PORT, 8596)
        self.assertEqual(ports.DEFAULT_PREVIEW_PORT, 8597)

    def test_devserver_shares_the_dev_port(self):
        from pydrud.core import ports
        from pydrud.platforms.android import devserver

        self.assertEqual(devserver.DEFAULT_DEV_PORT, ports.DEFAULT_DEV_PORT)

    def test_devserver_reuses_the_protocol_frame_cap(self):
        from pydrud.core import protocol
        from pydrud.platforms.android import devserver

        self.assertEqual(devserver.MAX_FRAME_BYTES, protocol.MAX_FRAME_BYTES)


if __name__ == "__main__":
    unittest.main()
