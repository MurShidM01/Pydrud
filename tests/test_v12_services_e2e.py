"""End-to-end tests for native services, page commands and the AppTester harness.

These run a real ``App`` against the in-process device emulator, so they
exercise the whole path: Python widget → bridge JSON → device → event →
handler → patch → rendered tree.
"""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from pydrud import (
    Button, Chip, Column, GestureDetector, ListTile, Scaffold, Tab,
    Tabs, Text, TextField,
)
from pydrud.testing import AppTester


class TestNativeServices(unittest.TestCase):
    """page.dialog / page.storage / page.clipboard round trips."""

    def test_confirm_dialog_resolves_callback(self):
        log = []

        def main(page):
            def ask(_event):
                page.dialog.confirm("Delete this note?", title="Careful") \
                    .then(lambda yes: log.append(yes))

            page.add(Button("Delete", key="delete", on_click=ask))

        with AppTester(main) as app:
            app.answer("dialog", True)
            app.tap("delete")
            request = app.requested("dialog")
            self.assertEqual(request["kind"], "confirm")
            self.assertEqual(request["message"], "Delete this note?")
            self.assertTrue(app.device.wait_for(lambda d: log == [True]))

    def test_failed_call_runs_catch(self):
        errors = []

        def main(page):
            def ask(_event):
                page.storage.get("token").catch(errors.append)

            page.add(Button("Load", key="load", on_click=ask))

        with AppTester(main) as app:
            app.answer("prefs_get", lambda msg: (_ for _ in ()).throw(
                RuntimeError("prefs unavailable")))
            app.tap("load")
            self.assertTrue(app.device.wait_for(lambda d: errors))
            self.assertIn("prefs unavailable", errors[0])

    def test_storage_set_then_get(self):
        values = []

        def main(page):
            def save(_event):
                page.storage.set("profile", {"name": "Ada"})
                page.storage.get("profile").then(values.append)

            page.add(Button("Save", key="save", on_click=save))

        store = {}
        with AppTester(main) as app:
            app.answer("prefs_set", lambda msg: store.setdefault(
                msg["key"], msg["value"]) is None or True)
            app.answer("prefs_get", lambda msg: store.get(msg["key"]))
            app.tap("save")
            self.assertTrue(app.device.wait_for(lambda d: values))
            self.assertEqual(values[0], {"name": "Ada"})

    def test_permission_names_are_resolved(self):
        def main(page):
            page.add(Button("Ask", key="ask", on_click=lambda e:
                            page.permissions.request("camera", "location")))

        with AppTester(main) as app:
            app.answer("permission_request", {"android.permission.CAMERA": True})
            app.tap("ask")
            request = app.requested("permission_request")
            self.assertEqual(request["permissions"],
                             ["android.permission.CAMERA",
                              "android.permission.ACCESS_FINE_LOCATION"])

    def test_unknown_permission_raises_in_python(self):
        def main(page):
            page.add(Text("x"))

        with AppTester(main) as app:
            with self.assertRaises(ValueError):
                app.app.page.permissions.request("telepathy")

    def test_haptics_map_to_vibrate_durations(self):
        def main(page):
            page.add(Button("Buzz", key="buzz",
                            on_click=lambda e: page.haptics.impact("heavy")))

        with AppTester(main) as app:
            app.answer("vibrate", True)
            app.tap("buzz")
            self.assertEqual(app.requested("vibrate")["duration"], 50)

    def test_share_helpers_build_intents(self):
        def main(page):
            page.add(Button("Call", key="call",
                            on_click=lambda e: page.share.dial("+923001234567")))

        with AppTester(main) as app:
            app.answer("open_url", True)
            app.tap("call")
            self.assertEqual(app.requested("open_url")["url"],
                             "tel:+923001234567")

    def test_result_fails_fast_without_a_bridge(self):
        from pydrud import App

        app = App(target=lambda page: page.add(Text("offline")))
        app.build()
        result = app.page.dialog.alert("hi")
        self.assertTrue(result.done)
        self.assertEqual(result.error, "bridge not connected")


class TestPageCommands(unittest.TestCase):

    def test_ui_commands_reach_the_device(self):
        def main(page):
            def run(_event):
                page.open_drawer()
                page.hide_keyboard()
                page.keep_awake(True)
                page.set_orientation("portrait")
                page.fullscreen(True)
                page.scroll_to("bottom")
                page.end_refresh()
                page.set_theme_mode("dark")

            page.add(Button("Go", key="go", on_click=run))

        with AppTester(main) as app:
            app.tap("go")
            app.device.wait_for_command("theme_mode")
            sent = [c["cmd"] for c in app.device.commands]
            for expected in ("drawer", "keyboard", "keep_awake", "orientation",
                             "fullscreen", "scroll_to", "end_refresh",
                             "theme_mode"):
                self.assertIn(expected, sent)

    def test_invalid_command_arguments_raise(self):
        def main(page):
            page.add(Text("x"))

        with AppTester(main) as app:
            page = app.app.page
            with self.assertRaises(ValueError):
                page.set_orientation("sideways")
            with self.assertRaises(ValueError):
                page.set_theme_mode("neon")
            with self.assertRaises(ValueError):
                page.open_drawer("middle")

    def test_theme_mode_switches_the_palette(self):
        from pydrud import Theme

        def main(page):
            page.add(Button("Dark", key="dark",
                            on_click=lambda e: page.set_theme_mode("dark")))

        try:
            with AppTester(main) as app:
                app.tap("dark")
                self.assertTrue(Theme.dark_mode)
        finally:
            Theme.light()


class TestConcurrency(unittest.TestCase):

    def test_run_task_and_run_on_ui(self):
        """Slow work happens off-thread; the UI is updated back on-thread."""
        def main(page):
            label = Text("idle", key="status")

            def work(_event):
                def background():
                    value = sum(range(10000))

                    def apply():
                        label.value = f"done {value}"
                        page.update(label)      # imperative, no rebuild

                    page.run_on_ui(apply)

                page.run_task(background)

            page.add(label, Button("Work", key="work", on_click=work))

        with AppTester(main) as app:
            app.tap("work")
            self.assertTrue(app.shows("done 49995000", timeout=3))

    def test_timers_fire_and_can_be_cancelled(self):
        ticks = []

        def main(page):
            page.add(Button("Start", key="start", on_click=lambda e:
                            page.every(0.01, lambda: ticks.append(1))))

        with AppTester(main) as app:
            app.tap("start")
            app.device.wait_for(lambda d: len(ticks) > 2, timeout=2)
            self.assertGreater(len(ticks), 2)
        # stopping the app shuts the task runner (and its timers) down
        count = len(ticks)
        import time
        time.sleep(0.08)
        self.assertLessEqual(len(ticks) - count, 2)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):                      # noqa: N802 - http.server API
        body = json.dumps({"path": self.path, "ok": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):                     # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(length)
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


class TestHttpClient(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _Handler)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_get_and_post_do_not_block_the_ui(self):
        received = []

        def main(page):
            page.http.configure(base_url=f"http://127.0.0.1:{self.port}")

            def fetch(_event):
                page.http.get("/posts", params={"page": 2}) \
                    .then(lambda r: received.append(r.json))

            def send(_event):
                page.http.post("/posts", json_body={"title": "hi"}) \
                    .then(lambda r: received.append(r.status))

            page.add(Button("Get", key="get", on_click=fetch),
                     Button("Post", key="post", on_click=send))

        with AppTester(main) as app:
            app.tap("get")
            self.assertTrue(app.device.wait_for(lambda d: received, timeout=5))
            self.assertEqual(received[0]["path"], "/posts?page=2")
            app.tap("post")
            self.assertTrue(app.device.wait_for(lambda d: len(received) > 1,
                                                timeout=5))
            self.assertEqual(received[1], 201)

    def test_network_errors_surface_through_catch(self):
        errors = []

        def main(page):
            def fetch(_event):
                page.http.get("http://127.0.0.1:1/nothing", timeout=0.5) \
                    .catch(errors.append)

            page.add(Button("Get", key="get", on_click=fetch))

        with AppTester(main) as app:
            app.tap("get")
            self.assertTrue(app.device.wait_for(lambda d: errors, timeout=5))

    def test_http_response_helpers(self):
        from pydrud.services.http import HttpResponse

        ok = HttpResponse(200, '{"a": 1}', {"Content-Type": "application/json"},
                          "http://x")
        self.assertTrue(ok.ok)
        self.assertEqual(ok.json, {"a": 1})
        self.assertEqual(ok.headers["content-type"], "application/json")
        bad = HttpResponse(500, "oops", {}, "http://x")
        self.assertFalse(bad)
        self.assertIsNone(bad.json)
        with self.assertRaises(RuntimeError):
            bad.raise_for_status()


class TestInteractiveWidgetsEndToEnd(unittest.TestCase):

    def test_tabs_switch_content(self):
        # State lives outside the builder, because page.update() re-runs it.
        state = {"index": 0}

        def main(page):
            def build():
                return Tabs(
                    [Tab("Home", content=Text("home screen", key="home")),
                     Tab("Profile", content=Text("profile screen", key="prof"))],
                    selected=state["index"], key="tabs", on_change=switch)

            def switch(event):
                state["index"] = event.value
                page.update()

            page.add(build())

        with AppTester(main) as app:
            self.assertTrue(app.shows("home screen"))
            app.device.change("tabs", 1)
            self.assertTrue(app.shows("profile screen"))
            self.assertNotIn("home screen", app.texts)

    def test_gestures_reach_python(self):
        seen = []

        def main(page):
            page.add(GestureDetector(
                key="canvas",
                child=Text("swipe me", key="label"),
                on_swipe_left=lambda e: seen.append(("left", e.data["dx"])),
                on_double_tap=lambda e: seen.append(("double", 0)),
            ))

        with AppTester(main) as app:
            self.assertEqual(app.prop("canvas", "gestures"),
                             ["double_tap", "swipe_left"])
            app.device.swipe("canvas", "left")
            app.device.gesture("canvas", "double_tap")
            self.assertTrue(app.device.wait_for(lambda d: len(seen) == 2))
            self.assertEqual(seen[0][0], "left")
            self.assertLess(seen[0][1], 0)

    def test_list_tile_and_chip_interactions(self):
        log = []

        def main(page):
            page.add(Column(children=[
                ListTile("Settings", key="settings",
                         on_click=lambda e: log.append("tile")),
                Chip("Python", variant="filter", key="chip",
                     on_change=lambda e: log.append(e.value)),
            ]))

        with AppTester(main) as app:
            app.tap("settings")
            app.device.send_event("change", "chip", {"selected": True})
            self.assertTrue(app.device.wait_for(lambda d: len(log) == 2))
            self.assertEqual(log, ["tile", True])

    def test_app_tester_resolves_widgets_by_text(self):
        def main(page):
            count = {"n": 0}
            label = Text("Count: 0", key="label")

            def bump(_event):
                count["n"] += 1
                label.value = f"Count: {count['n']}"
                page.update(label)

            page.add(label, Button("Increment", key="inc", on_click=bump))

        with AppTester(main) as app:
            app.tap("Increment")          # by text, not key
            app.tap("Increment")
            self.assertTrue(app.shows("Count: 2"))
            self.assertEqual(app.count("Button"), 1)

    def test_form_submits_through_the_bridge(self):
        from pydrud.widgets.forms import Form, FormField, email, required

        submitted = []

        def main(page):
            form = Form(
                FormField("email", TextField("", key="email"),
                          validators=[required(), email()]),
                on_submit=submitted.append,
            )
            page.add(Scaffold(
                key="s",
                body=Column(children=[
                    form,
                    Button("Sign in", key="submit",
                           on_click=lambda e: _submit(page, form)),
                ]),
            ))

        def _submit(page, form):
            if not form.submit():
                page.toast("Please fix the errors")
            page.update()

        with AppTester(main) as app:
            app.tap("submit")                      # empty → invalid
            self.assertTrue(app.device.wait_for_command("toast"))
            self.assertEqual(submitted, [])
            app.device.change("email", "ada@example.com")
            app.tap("submit")
            self.assertTrue(app.device.wait_for(lambda d: submitted))
            self.assertEqual(submitted[0], {"email": "ada@example.com"})


if __name__ == "__main__":
    unittest.main()
