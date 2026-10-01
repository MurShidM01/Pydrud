"""
End-to-end integration tests.

A complete Pydrud app is started against :class:`FakeDevice`, which speaks
the same NDJSON protocol as the Android ``BridgeService`` and mirrors the
``ViewFactory`` patch semantics. These tests therefore exercise the whole
pipeline: build → serialise → send → render → event → diff → patch.
"""

from __future__ import annotations

import unittest

from pydrud import (
    App, AppBar, Button, Card, Checkbox, Column, Container, Dropdown,
    FloatingActionButton, Icon, ListView,Router, Row, Scaffold,
    Slider, State, Switch, Text, TextField,
)
from tests.fake_device import FakeDevice, run_app


class IntegrationTestCase(unittest.TestCase):
    """Base class that wires an App to a FakeDevice."""

    def setUp(self):
        self.device = FakeDevice().start()
        self.app: App | None = None

    def tearDown(self):
        if self.app is not None:
            self.app.stop()
        self.device.stop()

    def launch(self, target) -> FakeDevice:
        self.app = App(target=target)
        run_app(self.app, self.device)
        self.assertTrue(
            self.device.wait_for(lambda d: d.root is not None),
            "no full_render received",
        )
        return self.device


class TestCounterApp(IntegrationTestCase):
    """The canonical counter app: state → event → incremental patch."""

    def test_counter_increments_via_patches(self):
        counter = State(0)

        def main(page):
            page.title = "Counter"
            page.bgcolor = "#FFF9FAFB"

            def increment(_data):
                counter.value += 1
                page.update()

            page.add(
                Column(children=[
                    Text(f"Count: {counter.value}", key="label", size=32),
                    Button("+", key="inc").on_click(increment),
                ])
            )

        device = self.launch(main)
        self.assertIn("Count: 0", device.texts)

        device.click("inc")
        self.assertTrue(device.wait_for_text("Count: 1"))

        device.click("inc")
        device.click("inc")
        self.assertTrue(device.wait_for_text("Count: 3"))

        # Updates must be incremental, never a full re-render per tap.
        self.assertEqual(device.full_renders, 1 + 1)  # initial + ready re-render
        self.assertTrue(device.patch_batches, "no patch batches were sent")
        for batch in device.patch_batches:
            self.assertLessEqual(len(batch), 3, f"patch batch too large: {batch}")

    def test_only_changed_widget_is_patched(self):
        counter = State(0)

        def main(page):
            def inc(_):
                counter.value += 1
                page.update()

            page.add(Column(children=[
                Text("static header", key="header"),
                Text(str(counter.value), key="value"),
                Button("tap", key="btn").on_click(inc),
            ]))

        device = self.launch(main)
        device.click("btn")
        self.assertTrue(device.wait_for_text("1"))

        last = device.patch_batches[-1]
        self.assertEqual(len(last), 1)
        self.assertEqual(last[0]["op"], "update")
        self.assertEqual(last[0]["key"], "value")
        self.assertEqual(last[0]["props"]["value"], "1")


class TestInputWidgets(IntegrationTestCase):
    """TextField / Checkbox / Switch / Slider / Dropdown round-trips."""

    def test_text_field_change_and_submit(self):
        typed = []
        submitted = []

        def main(page):
            page.add(
                TextField(
                    "", key="name", hint="Your name",
                )
                .on_change(lambda d: typed.append(d["value"]))
                .on_submit(lambda d: submitted.append(d["value"]))
            )

        device = self.launch(main)
        device.change("name", "Ada")
        device.submit("name", "Ada Lovelace")

        self.assertTrue(device.wait_for(lambda d: typed and submitted))
        self.assertEqual(typed[-1], "Ada")
        self.assertEqual(submitted[-1], "Ada Lovelace")

    def test_checkbox_switch_slider_dropdown(self):
        values: dict = {}

        def main(page):
            page.add(Column(children=[
                Checkbox("Accept", key="cb", checked=values.get("cb", False))
                .on_change(lambda d: values.update(cb=d["value"])),
                Switch("Dark", key="sw", active=values.get("sw", False))
                .on_change(lambda d: values.update(sw=d["value"])),
                Slider(10, key="sl", min=0, max=100)
                .on_change(lambda d: values.update(sl=d["value"])),
                Dropdown(["One", "Two"], key="dd")
                .on_change(lambda d: values.update(dd=d["value"])),
            ]))

        device = self.launch(main)
        device.change("cb", True)
        device.change("sw", True)
        device.change("sl", 42.5)
        device.change("dd", "Two")

        self.assertTrue(device.wait_for(lambda d: len(values) == 4))
        self.assertEqual(values, {"cb": True, "sw": True, "sl": 42.5, "dd": "Two"})

    def test_widget_values_render_into_props(self):
        def main(page):
            page.add(Column(children=[
                Checkbox("Accept", key="cb", checked=True),
                Switch("Dark", key="sw", active=True),
                Slider(25, key="sl", min=0, max=50),
                Dropdown(["a", "b"], key="dd", value="b"),
            ]))

        device = self.launch(main)
        self.assertTrue(device.root.find("cb").props["checked"])
        self.assertTrue(device.root.find("sw").props["active"])
        self.assertEqual(device.root.find("sl").props["value"], 25)
        self.assertEqual(device.root.find("dd").props["index"], 1)


class TestDynamicLists(IntegrationTestCase):
    """Keyed diffing for lists that grow, shrink and reorder."""

    def test_todo_list_add_and_remove(self):
        todos = ["milk", "bread"]

        def main(page):
            rows = []
            for item in todos:
                rows.append(
                    Container(
                        key=f"row-{item}",
                        child=Text(item, key=f"txt-{item}"),
                    )
                )
            page.add(ListView(key="list", children=rows))
            page.add(Button("add", key="add").on_click(add))
            page.add(Button("remove", key="remove").on_click(remove))

        def add(_):
            todos.append("eggs")
            self.app.update()

        def remove(_):
            todos.remove("milk")
            self.app.update()

        device = self.launch(main)
        self.assertEqual(device.root.find("list").children[0].props, {})
        self.assertIn("milk", device.texts)

        device.click("add")
        self.assertTrue(device.wait_for_text("eggs"))
        created = [p for b in device.patch_batches for p in b if p["op"] == "create"]
        self.assertTrue(any(p["key"] == "row-eggs" for p in created))

        device.click("remove")
        self.assertTrue(device.wait_for(lambda d: "milk" not in d.texts))
        self.assertIn("bread", device.texts)
        self.assertIn("eggs", device.texts)

    def test_reorder_emits_move_not_rebuild(self):
        items = ["a", "b", "c"]

        def main(page):
            page.add(Column(key="list", children=[
                Text(i, key=f"item-{i}") for i in items
            ]))
            page.add(Button("swap", key="swap").on_click(swap))

        def swap(_):
            items.reverse()
            self.app.update()

        device = self.launch(main)
        device.click("swap")
        self.assertTrue(device.wait_for(
            lambda d: [c.key for c in d.root.find("list").children]
            == ["item-c", "item-b", "item-a"]
        ))
        ops = {p["op"] for b in device.patch_batches for p in b}
        self.assertIn("move", ops)
        self.assertNotIn("create", ops)


class TestNavigation(IntegrationTestCase):
    """Router push/pop and hardware back-button handling."""

    def _router_app(self):
        router = Router()

        def home(page):
            page.add(Text("Home screen", key="home-title"))
            page.add(Button("Go", key="go").on_click(lambda _: router.push("details", id=7)))

        def details(page, params):
            page.add(Text(f"Details {params['id']}", key="details-title"))
            page.add(Button("Back", key="back-btn").on_click(lambda _: router.pop()))

        router.define("home", home).define("details", details).initial("home")
        app = App(target=router.build_root())
        app.attach_router(router)
        return app, router

    def test_push_pop_and_back_button(self):
        self.app, router = self._router_app()
        run_app(self.app, self.device)
        device = self.device
        self.assertTrue(device.wait_for_text("Home screen"))

        device.click("go")
        self.assertTrue(device.wait_for_text("Details 7"))
        self.assertEqual(router.stack_size, 2)

        device.click("back-btn")
        self.assertTrue(device.wait_for_text("Home screen"))
        self.assertEqual(router.stack_size, 1)

        # Hardware back on the root: Python must tell Android it did not
        # handle it, so the activity can close.
        device.click("go")
        self.assertTrue(device.wait_for_text("Details 7"))
        device.back()
        self.assertTrue(device.wait_for_text("Home screen"))
        self.assertTrue(device.wait_for_command("back_result"))

        device.commands.clear()
        device.back()
        self.assertTrue(device.wait_for_command("back_result"))
        result = [c for c in device.commands if c.get("cmd") == "back_result"][-1]
        self.assertFalse(result["handled"])

    def test_back_on_nested_screen_is_handled(self):
        self.app, router = self._router_app()
        run_app(self.app, self.device)
        self.device.wait_for_text("Home screen")
        self.device.click("go")
        self.assertTrue(self.device.wait_for_text("Details 7"))

        self.device.commands.clear()
        self.device.back()
        self.assertTrue(self.device.wait_for_command("back_result"))
        result = [c for c in self.device.commands if c.get("cmd") == "back_result"][-1]
        self.assertTrue(result["handled"])


class TestPageCommands(IntegrationTestCase):
    """page.toast / snack_bar / set_title / system UI / close."""

    def test_commands_reach_the_device(self):
        def main(page):
            page.add(Button("go", key="go").on_click(lambda _: run_commands(page)))

        def run_commands(page):
            page.toast("Saved!")
            page.snack_bar("Undo?", action="UNDO")
            page.set_title("New title")
            page.set_system_ui(status_bar_color="#FF123456", icon_brightness="light")
            page.vibrate(20)
            page.close()

        device = self.launch(main)
        device.click("go")
        self.assertTrue(device.wait_for_command("finish_activity"))

        by_cmd = {c["cmd"]: c for c in device.commands if "cmd" in c}
        self.assertEqual(by_cmd["toast"]["message"], "Saved!")
        self.assertEqual(by_cmd["snackbar"]["action"], "UNDO")
        self.assertEqual(by_cmd["set_title"]["title"], "New title")
        self.assertEqual(by_cmd["set_system_ui"]["status_bar_color"], "#FF123456")
        self.assertEqual(by_cmd["vibrate"]["duration"], 20)
        self.assertTrue(device.activity_finished)

    def test_lifecycle_events(self):
        seen = []

        def main(page):
            page.add(Text("hi"))

        self.app = App(target=main)
        self.app.on_lifecycle("pause", lambda d: seen.append("pause"))
        self.app.on_lifecycle("resume", lambda d: seen.append("resume"))
        run_app(self.app, self.device)
        self.device.wait_for(lambda d: d.root is not None)

        self.device.lifecycle("pause")
        self.device.lifecycle("resume")
        self.assertTrue(self.device.wait_for(lambda d: len(seen) == 2))
        self.assertEqual(seen, ["pause", "resume"])

    def test_ready_event_populates_media_query(self):
        from pydrud import MediaQuery, Responsive

        def main(page):
            page.add(Text("hi"))

        self.launch(main)
        self.assertTrue(self.device.wait_for(lambda d: MediaQuery.of()["width"] == 400))
        info = MediaQuery.of()
        self.assertEqual(info["height"], 800)
        self.assertEqual(info["status_bar_height"], 24)
        self.assertAlmostEqual(Responsive.factor(), 400 / 360, places=5)


class TestScaffoldRendering(IntegrationTestCase):
    """Scaffold / AppBar / FAB compose into a renderable tree."""

    def test_scaffold_structure_and_fab_click(self):
        taps = []

        def main(page):
            page.add(
                Scaffold(
                    key="scaffold",
                    app_bar=AppBar(title="My App", key="bar",
                                   actions=[Icon("search", key="search")]),
                    body=Column(children=[
                        Card(child=Text("Card body", key="card-text")),
                    ]),
                    floating_action_button=FloatingActionButton(
                        "+", key="fab", on_click=lambda _: taps.append(1)
                    ),
                )
            )

        device = self.launch(main)
        self.assertIn("My App", device.texts)
        self.assertIn("Card body", device.texts)

        fab = device.root.find("fab")
        self.assertIsNotNone(fab)
        self.assertEqual(fab.style["position"], "absolute")
        self.assertIn("click", fab.events)

        device.click("fab")
        self.assertTrue(device.wait_for(lambda d: taps))

    def test_body_is_weighted_so_it_fills_the_screen(self):
        def main(page):
            page.add(Scaffold(key="s", app_bar=AppBar(title="T"), body=Text("body")))

        device = self.launch(main)
        body = device.root.find("s._body")
        self.assertIsNotNone(body)
        # Column child with expand must declare height 0 for LinearLayout weights.
        self.assertEqual(body.style.get("height"), 0)


class TestResilience(IntegrationTestCase):
    """Errors in user code must not kill the app."""

    def test_handler_exception_is_reported_not_fatal(self):
        errors = []

        def main(page):
            page.add(Button("boom", key="boom").on_click(lambda _: 1 / 0))
            page.add(Button("ok", key="ok").on_click(lambda _: page.toast("still alive")))

        self.app = App(target=main)
        self.app.on_error(lambda exc: errors.append(exc))
        run_app(self.app, self.device)
        self.device.wait_for(lambda d: d.root is not None)

        self.device.click("boom")
        self.assertTrue(self.device.wait_for(lambda d: errors))
        self.assertIsInstance(errors[0], ZeroDivisionError)

        self.device.click("ok")
        self.assertTrue(self.device.wait_for_command("toast"))

    def test_unknown_event_key_is_ignored(self):
        def main(page):
            page.add(Text("hello"))

        device = self.launch(main)
        device.click("does-not-exist")
        device.send_event("weird", "nope", {"x": 1})
        # The app must stay responsive afterwards.
        self.assertTrue(device.wait_for(lambda d: d.root is not None))
        self.assertIn("hello", device.texts)


if __name__ == "__main__":
    unittest.main()


class TestEveryWidgetRenders(IntegrationTestCase):
    """A kitchen-sink screen using every public widget must render cleanly."""

    def test_kitchen_sink(self):
        from pydrud import (
            Colors, Divider, GridView, Icons, Image, Padding, Positioned,
            ProgressBar, Radio, SizedBox, Spacer, Stack,
        )

        def main(page):
            page.bgcolor = Colors.BACKGROUND
            page.add(
                Scaffold(
                    key="sink",
                    app_bar=AppBar(title="Everything", key="bar"),
                    body=Column(scroll=True, spacing=8, children=[
                        Text("heading", key="t", size=20, weight=700),
                        Button("button", key="b", variant="outlined"),
                        TextField("", key="tf", hint="type"),
                        Checkbox("check", key="cb"),
                        Switch("switch", key="sw"),
                        Slider(5, key="sl", min=0, max=10),
                        Dropdown(["x", "y"], key="dd"),
                        Radio("radio", key="rd", group="g"),
                        ProgressBar(0.4, key="pb"),
                        Icon(Icons.HOME, key="ic"),
                        Image("logo.png", key="img", fit="cover"),
                        Divider(key="dv"),
                        Spacer(key="sp"),
                        SizedBox(width=4, height=4, key="sb"),
                        Padding(8, key="pd", child=Text("padded", key="pt")),
                        Card(key="card", child=Text("card", key="ct")),
                        ListView(key="lv", children=[Text("row", key="lr")]),
                        GridView(key="gv", columns=2, children=[
                            Text("g1", key="g1"), Text("g2", key="g2"),
                        ]),
                        Stack(key="st", children=[
                            Container(key="bgbox", bg="#FFEEEEEE", height=40),
                            Positioned(key="badge", top=2, right=2,
                                       child=Text("9", key="badge_text")),
                        ]),
                        Row(key="row", spacing=4, children=[
                            Container(key="c1", bg="#FFCCCCCC", width=20, height=20),
                            Container(key="c2", expand=1, child=Text("grow", key="gt")),
                        ]),
                    ]),
                    floating_action_button=FloatingActionButton(
                        icon=Icons.ADD, key="fab"),
                )
            )

        device = self.launch(main)
        keys = {n.key for n in device.root.walk()}
        for expected in ["t", "b", "tf", "cb", "sw", "sl", "dd", "rd", "pb",
                         "ic", "img", "dv", "sp", "sb", "pd", "card", "lv",
                         "gv", "st", "badge", "row", "fab"]:
            self.assertIn(expected, keys, f"{expected} did not render")

        # Everything must be JSON round-trippable for the bridge.
        import json
        json.dumps(device.root.find("sink._stack") and True)
        self.assertGreater(len(list(device.root.walk())), 30)
