"""API ergonomics: the gaps an adversarial stress test of v2.0.2 found.

Each test here maps to a reported bug or limitation: design-token names
that did not exist, a canvas painter whose signature nobody could guess,
no way to show a widget conditionally on state, ``column("id", …)``
reading its name as a type, and read-modify-write races in the Store and
the navigation stack.
"""

from __future__ import annotations

import threading
import unittest

from pydrud import (
    Canvas, Colors, Column, Computed, Elevation, Hidden, Icons, Motion,
    NavItem, NavigationItem, Radius, ReactiveList, Router, Spacing, ShowWhen,
    State, Store, Text, Visible,
)
from pydrud.commands.analyzer import _analyze_file
from pydrud.core.responsive import MediaQuery
from pydrud.core.tasks import Timer
from pydrud.data import Database, Model, column
from pydrud.runtime.navigation import NavigationStack
from pydrud.widgets.canvas import Size


class TestDesignTokens(unittest.TestCase):
    """BUG-001/002/003 + DX-001: missing names and unhelpful errors."""

    def test_material_elevation_scale_exists(self):
        self.assertEqual(Elevation.D4, 4)
        self.assertEqual(Elevation.D0, 0)
        self.assertEqual(Elevation.D24, 24)
        self.assertEqual(Elevation.CARD, 2)
        self.assertEqual(Elevation.dp(99), 24)

    def test_palette_covers_the_common_material_hues(self):
        for name in ("AMBER", "DEEP_ORANGE", "DEEP_PURPLE", "LIGHT_BLUE",
                     "LIGHT_GREEN", "BLUE_GREY", "TEAL"):
            with self.subTest(colour=name):
                self.assertTrue(getattr(Colors, name).startswith("#FF"))

    def test_colour_names_are_spelling_insensitive(self):
        self.assertEqual(Colors.amber, Colors.AMBER)
        self.assertEqual(Colors.deepOrange, Colors.DEEP_ORANGE)
        self.assertEqual(Colors.deep_orange, Colors.DEEP_ORANGE)
        self.assertEqual(Colors.GRAY, Colors.GREY)

    def test_radius_full_is_an_alias_for_pill(self):
        self.assertEqual(Radius.FULL, Radius.PILL)
        self.assertEqual(Radius.full, Radius.CIRCLE)

    def test_unknown_token_suggests_the_real_names(self):
        for registry, bad, expected in ((Colors, "purlpe", "PURPLE"),
                                        (Elevation, "D44", "D4"),
                                        (Radius, "FULLL", "FULL"),
                                        (Spacing, "MDD", "MD"),
                                        (Motion, "FSAT", "FAST")):
            with self.subTest(token=bad):
                with self.assertRaises(AttributeError) as ctx:
                    getattr(registry, bad)
                message = str(ctx.exception)
                self.assertIn(expected, message)
                self.assertIn("names()", message)

    def test_icons_keep_their_packs_and_gain_suggestions(self):
        self.assertEqual(Icons.home, Icons.HOME)
        Icons.register("BRAND_TEST", "brand_test")
        try:
            self.assertEqual(Icons.brandTest, "brand_test")
        finally:
            Icons._external.pop("BRAND_TEST", None)
        with self.assertRaises(AttributeError) as ctx:
            Icons.hoem
        self.assertIn("HOME", str(ctx.exception))

    def test_analyzer_flags_tokens_that_do_not_exist(self):
        source = ("from pydrud import Colors, Elevation\n"
                  "a = Colors.amber\n"
                  "b = Elevation.D4\n"
                  "c = Colors.purlpe\n")
        issues = _analyze_file(source, "x.py")
        self.assertEqual([i["line"] for i in issues], [4])
        self.assertEqual(issues[0]["severity"], "error")


class TestCanvasPainter(unittest.TestCase):
    """BUG-006/009 + LIMIT-001 + FM-002: the canvas drawing contract."""

    def ops(self, canvas: Canvas) -> list:
        return canvas.to_dict()["props"]["ops"]

    def test_text_weight_accepts_css_names(self):
        canvas = Canvas()
        canvas.text("bold", 0.5, 0.5, weight="bold")
        canvas.text("normal", 0.5, 0.6, weight="normal")
        canvas.text("medium", 0.5, 0.7, weight="Medium")
        canvas.text("numeric", 0.5, 0.8, weight=700)
        canvas.text("string", 0.5, 0.9, weight="700")
        self.assertEqual([op["weight"] for op in canvas.ops],
                         [700, 400, 500, 700, 700])

    def test_unknown_weight_names_still_fail_loudly(self):
        with self.assertRaises(ValueError):
            Canvas().text("x", 0, 0, weight="chonky")

    def test_canvas_exposes_its_size(self):
        canvas = Canvas(height=160)
        self.assertIsInstance(canvas.size, Size)
        self.assertEqual(canvas.height, 160)
        self.assertEqual(canvas.width, MediaQuery.viewport()[0])
        canvas.measure(300, 90)
        self.assertEqual(tuple(canvas.size), (300.0, 90.0))
        canvas.measure()
        self.assertEqual(canvas.height, 160)

    def test_on_draw_accepts_one_two_or_three_arguments(self):
        def one(canvas):
            canvas.circle(0.5, 0.5, 0.4)

        def two(canvas, size):
            canvas.rect(0, 0, size.width, size.height)

        def three(canvas, width, height):
            canvas.line(0, 0, width, height)

        single = Canvas(height=100, on_draw=one)
        pair = Canvas(height=100, on_draw=two).measure(200, 100)
        triple = Canvas(height=100, on_draw=three).measure(200, 100)
        splat = Canvas(height=100, on_draw=lambda *a: a[0].circle(0, 0, 1))

        self.assertEqual(self.ops(single)[0]["op"], "circle")
        self.assertEqual(self.ops(pair)[0]["w"], 200)
        self.assertEqual(self.ops(triple)[0]["x2"], 200)
        self.assertEqual(self.ops(splat)[0]["op"], "circle")

    def test_on_draw_is_rerun_on_every_serialisation(self):
        frames = []
        canvas = Canvas(on_draw=lambda c: frames.append(1))
        canvas.to_dict()
        canvas.to_dict()
        self.assertEqual(len(frames), 2)
        self.assertEqual(len(canvas.ops), 0)

    def test_a_failing_painter_does_not_break_the_rebuild(self):
        def painter(canvas):
            canvas.circle(0.5, 0.5, 0.2)
            raise RuntimeError("boom")

        canvas = Canvas(on_draw=painter)
        rendered = canvas.to_dict()
        self.assertEqual(len(rendered["props"]["ops"]), 1)
        self.assertIsInstance(canvas.last_draw_error, RuntimeError)


class TestConditionalRendering(unittest.TestCase):
    """BUG-007 + LIMIT-002: show a subtree based on state, not on width."""

    def child_type(self, widget) -> str:
        return widget.to_dict()["type"]

    def test_visible_follows_a_state_object(self):
        flag = State(False)
        widget = Visible(Text("shown"), when=flag)
        self.assertEqual(self.child_type(widget), "Container")   # placeholder
        flag.value = True
        self.assertEqual(self.child_type(widget), "Text")

    def test_visible_accepts_bools_callables_and_stores(self):
        store = Store({"ready": False})
        cases = [
            Visible(Text("a"), True),
            Visible(Text("b"), condition=lambda: True),
            Visible(Text("c"), visible=Computed(lambda: 1 + 1 == 2)),
            Visible(Text("d"), when=ReactiveList([1])),
            Visible(Text("e"), when=store.select("ready")),
        ]
        self.assertEqual([w.matches() for w in cases],
                         [True, True, True, True, False])
        store.set("ready", True)
        self.assertTrue(cases[-1].matches())

    def test_otherwise_renders_the_fallback(self):
        widget = Visible(Text("on"), when=False, otherwise=Text("off"))
        self.assertEqual(widget.to_dict()["props"]["value"], "off")

    def test_hidden_is_the_inverse(self):
        empty = State(True)
        widget = Hidden(Text("checkout"), when=empty)
        self.assertEqual(self.child_type(widget), "Container")
        empty.value = False
        self.assertEqual(self.child_type(widget), "Text")

    def test_only_one_condition_keyword_is_allowed(self):
        with self.assertRaises(TypeError):
            Visible(Text("x"), when=True, condition=False)

    def test_show_when_combines_state_with_breakpoints(self):
        MediaQuery.update(width=900, height=600)
        try:
            flag = State(True)
            widget = ShowWhen(Text("tips"), min_width=600, condition=flag)
            self.assertTrue(widget.matches())
            flag.value = False
            self.assertFalse(widget.matches())
        finally:
            MediaQuery.reset()

    def test_navigation_item_is_an_alias_for_nav_item(self):
        self.assertIs(NavigationItem, NavItem)
        self.assertIsInstance(NavigationItem("Home"), NavItem)


class TestColumnSpellings(unittest.TestCase):
    """BUG-005 + LIMIT-005: naming a column, including ``id``."""

    def test_named_columns_build_a_working_model(self):
        class ScoreEntry(Model):
            id = column("id", primary_key=True)
            player = column("player", str)
            score = column("score", "int", index=True)
            meta = column(dict)

        db = Database(":memory:")
        db.bind(ScoreEntry)
        ScoreEntry.create_table()

        entry = ScoreEntry(player="Ali", score=42, meta={"level": 3})
        self.assertIsNone(entry.id)        # allocated by SQLite on save
        entry.save()
        self.assertEqual(entry.id, 1)
        self.assertEqual(ScoreEntry.where(score__gt=10).first().meta,
                         {"level": 3})
        self.assertIs(ScoreEntry.__fields__["score"].type, int)

    def test_every_accepted_spelling_resolves_the_same_way(self):
        self.assertIs(column(str).type, str)
        self.assertIs(column("int").type, int)
        self.assertIs(column("tags", "list").type, list)
        self.assertIs(column("count", type_=int).type, int)
        self.assertIs(column("id", primary_key=True).type, int)
        self.assertIs(column("title").type, str)

    def test_a_name_that_contradicts_the_attribute_is_rejected(self):
        with self.assertRaises(TypeError) as ctx:
            class Bad(Model):
                points = column("score", int)
        self.assertIn("score", str(ctx.exception))

    def test_unknown_types_still_fail(self):
        with self.assertRaises(TypeError):
            column("name", "timestamp")


class TestReactiveListErgonomics(unittest.TestCase):
    """BUG-004, FM-003 and PERF-002."""

    def test_named_lists_match_the_store_api(self):
        enemies = ReactiveList(name="enemies")
        self.assertEqual(enemies.name, "enemies")
        self.assertIn("enemies", repr(enemies))
        self.assertEqual(repr(ReactiveList([1])), "ReactiveList([1])")
        self.assertEqual(Computed(lambda: 2, name="two").name, "two")

    def test_iteration_is_a_snapshot(self):
        items = ReactiveList([1, 2, 3, 4])
        seen = []
        for item in items:
            seen.append(item)
            items.remove(item)
        self.assertEqual(seen, [1, 2, 3, 4])

    def test_replace_all_does_not_notify_when_nothing_changed(self):
        items = ReactiveList([1, 2, 3])
        notifications = []
        items.subscribe(lambda value: notifications.append(value))
        items.replace_all([1, 2, 3])
        self.assertEqual(notifications, [])
        items.replace_all([1, 2])
        self.assertEqual(notifications, [[1, 2]])


class TestConcurrencyHardening(unittest.TestCase):
    """RACE-002, FM-004 and LIMIT-003."""

    def test_concurrent_actions_do_not_lose_updates(self):
        store = Store({"n": 0})

        @store.action
        def increment(state):
            return {"n": state["n"] + 1}

        threads = [threading.Thread(target=lambda: [increment()
                                                    for _ in range(100)])
                   for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(store.get("n"), 400)

    def test_navigation_stack_pops_atomically(self):
        stack = NavigationStack()
        stack.push("home")
        for index in range(50):
            stack.push(f"page-{index}")

        def drain():
            while stack.pop(keep_root=True) is not None:
                pass

        threads = [threading.Thread(target=drain) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(stack.routes(), ["home"])

    def test_pop_to_root_keeps_the_root_entry(self):
        router = Router()
        router.define("home", lambda page: None)
        router.define("detail", lambda page: None)
        router.initial("home")
        router.push("detail")
        router.push("detail")
        self.assertEqual(router.stack_size, 3)
        self.assertTrue(router.pop_to_root())
        self.assertEqual(router.history, ["home"])
        self.assertFalse(router.pop_to_root())

    def test_a_repeating_timer_can_give_up_on_a_broken_callback(self):
        def always_fails():
            raise RuntimeError("boom")

        timer = Timer(0.001, always_fails, repeat=True, max_errors=3).start()
        timer._thread.join(timeout=2)
        self.assertFalse(timer.active)
        self.assertGreaterEqual(timer.errors, 3)
        self.assertIsInstance(timer.last_error, RuntimeError)

    def test_a_timer_still_survives_an_occasional_failure(self):
        ticks = []

        def flaky():
            ticks.append(1)
            if len(ticks) == 1:
                raise RuntimeError("first frame")

        timer = Timer(0.005, flaky, repeat=True).start()
        try:
            deadline = 200
            while len(ticks) < 3 and deadline:
                deadline -= 1
                timer._cancelled.wait(0.01)
        finally:
            timer.cancel()
        self.assertGreaterEqual(len(ticks), 3)
        self.assertEqual(timer.consecutive_errors, 0)


class TestTesterWaits(unittest.TestCase):
    """LIMIT-004: taps that land one rebuild early."""

    def _late_app(self):
        """An app whose second screen appears a beat after the tap."""
        from pydrud import App, Button

        shown = State(False)

        def reveal(_event):
            def flip():
                shown.value = True
                app = App.current()
                if app is not None:
                    app.update()

            threading.Timer(0.05, flip).start()

        def build(page):
            children = [Button("Go", key="go").on_click(reveal)]
            if shown.value:
                children.append(Text("Loaded", key="late"))
            page.add(Column(key="root", children=children))

        return build

    def test_wait_for_rides_out_a_late_rebuild(self):
        from pydrud.testing import AppTester

        with AppTester(self._late_app(), title="late") as tester:
            tester.tap("go")
            self.assertFalse(tester.exists("late"))
            tester.wait_for("late", timeout=2.0)
            self.assertTrue(tester.exists("late"))

    def test_a_missing_widget_still_reports_what_is_on_screen(self):
        from pydrud.testing import AppTester

        with AppTester(self._late_app(), title="late") as tester:
            with self.assertRaises(AssertionError) as ctx:
                tester.wait_for("nope", timeout=0.05)
            self.assertIn("Go", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
