"""v1.3 UI: canvas painting, advanced widgets, controllers and navigation."""

from __future__ import annotations

import time
import unittest

from pydrud import (
    AnimationController, App, Canvas, CameraPreview, InfiniteList, MapView,
    Markdown, Marker, Paint, Path, ReorderableList, RichText, Router, Span,
    Text, Tween, curve, parse_url,
)
from pydrud.core.controllers import Sequence_
from pydrud.navigation import TRANSITIONS, Route


def props(widget) -> dict:
    return widget.to_dict()["props"]


class TestCanvas(unittest.TestCase):

    def test_primitives_are_recorded_in_order(self):
        canvas = (Canvas(height=120)
                  .rect(0, 0, 1, 0.5, radius=0.1, color="#FF000000")
                  .circle(0.5, 0.5, 0.2, fill=True)
                  .text("hi", 0.5, 0.9, align="center"))
        ops = props(canvas)["ops"]
        self.assertEqual([op["op"] for op in ops], ["rect", "circle", "text"])
        self.assertEqual(ops[0]["paint"]["color"], "#FF000000")
        self.assertTrue(ops[1]["paint"]["fill"])
        self.assertEqual(ops[2]["align"], "center")

    def test_paint_object_is_reusable(self):
        paint = Paint(color="#FFFF0000", width=4, cap="round", dash=[4, 2])
        canvas = Canvas().line(0, 0, 1, 1, paint=paint).line(0, 1, 1, 0, paint=paint)
        ops = props(canvas)["ops"]
        self.assertEqual(ops[0]["paint"], ops[1]["paint"])
        self.assertEqual(ops[0]["paint"]["cap"], "round")
        self.assertEqual(ops[0]["paint"]["dash"], [4, 2])

    def test_paint_validates_its_arguments(self):
        with self.assertRaises(ValueError):
            Paint(cap="pointy")
        with self.assertRaises(ValueError):
            Paint(alpha=3)
        with self.assertRaises(ValueError):
            Canvas(units="inches")
        with self.assertRaises(ValueError):
            Canvas().text("x", 0, 0, align="middle")

    def test_path_building_and_smoothing(self):
        path = Path().move_to(0, 0).line_to(1, 1).quad_to(0.5, 0, 1, 0).close()
        self.assertEqual([op["op"] for op in path.to_list()],
                         ["move", "line", "quad", "close"])
        smooth = Path().smooth([(0, 0), (0.5, 1), (1, 0)])
        self.assertEqual(smooth.ops[0]["op"], "move")
        self.assertTrue(all(op["op"] == "cubic" for op in smooth.ops[1:]))

    def test_path_must_be_a_path(self):
        with self.assertRaises(TypeError):
            Canvas().path([{"op": "move"}])

    def test_sparkline_and_pie_helpers(self):
        canvas = Canvas().sparkline([1, 4, 2, 8], fill=True)
        kinds = [op["op"] for op in props(canvas)["ops"]]
        self.assertEqual(kinds, ["path", "path"])

        pie = Canvas().pie([1, 1, 2], hole=0.5)
        ops = props(pie)["ops"]
        self.assertEqual(len([o for o in ops if o["op"] == "arc"]), 3)
        self.assertEqual(ops[-1]["op"], "circle")          # the hole
        self.assertAlmostEqual(sum(o["sweep"] for o in ops if o["op"] == "arc"),
                               360.0)

    def test_transform_stack(self):
        canvas = Canvas().save().translate(0.1, 0.1).rotate(45).scale(2).restore()
        self.assertEqual([op["op"] for op in props(canvas)["ops"]],
                         ["save", "translate", "rotate", "scale", "restore"])

    def test_on_draw_reruns_on_every_serialisation(self):
        counter = {"n": 0}

        def draw(canvas):
            counter["n"] += 1
            canvas.circle(0.5, 0.5, 0.1 * counter["n"])

        canvas = Canvas(on_draw=draw)
        first = props(canvas)["ops"][0]["r"]
        second = props(canvas)["ops"][0]["r"]
        self.assertEqual(counter["n"], 2)
        self.assertNotEqual(first, second)         # redrawn, not accumulated
        self.assertEqual(len(props(canvas)["ops"]), 1)

    def test_grid_draws_the_right_number_of_lines(self):
        canvas = Canvas().grid(rows=4, columns=3)
        self.assertEqual(len(props(canvas)["ops"]), 3 + 2)


class TestAdvancedWidgets(unittest.TestCase):

    def test_camera_preview_defaults_and_validation(self):
        cam = CameraPreview(key="cam", facing="front", scan=True)
        data = props(cam)
        self.assertEqual(data["facing"], "front")
        self.assertTrue(data["scan"])
        with self.assertRaises(ValueError):
            CameraPreview(facing="sideways")
        with self.assertRaises(ValueError):
            CameraPreview(flash="disco")

    def test_camera_preview_enables_scanning_when_a_handler_is_given(self):
        cam = CameraPreview(on_scan=lambda e: None)
        self.assertTrue(props(cam)["scan"])
        self.assertIn("scan", cam.event_handlers)

    def test_map_markers_and_bounds_checking(self):
        view = MapView(center=(24.86, 67.0), zoom=12,
                       markers=[Marker(24.86, 67.0, title="Karachi")])
        data = props(view)
        self.assertEqual(data["lat"], 24.86)
        self.assertEqual(data["markers"][0]["title"], "Karachi")
        with self.assertRaises(ValueError):
            Marker(100, 0)
        with self.assertRaises(ValueError):
            MapView(zoom=99)
        with self.assertRaises(ValueError):
            MapView(provider="bing")

    def test_map_accepts_dict_markers_and_polylines(self):
        view = MapView(markers=[{"lat": 1, "lon": 2}], polyline=[(1, 2), (3, 4)])
        self.assertEqual(props(view)["markers"][0]["lat"], 1.0)
        self.assertEqual(props(view)["polyline"], [[1.0, 2.0], [3.0, 4.0]])

    def test_rich_text_spans(self):
        text = RichText([
            Span("Signed in as "),
            Span("ada@example.com", weight=700),
            "plain",
            {"text": " link", "link": "app://x"},
        ])
        spans = props(text)["spans"]
        self.assertEqual(len(spans), 4)
        self.assertEqual(spans[1]["weight"], 700)
        self.assertTrue(spans[3]["underline"])      # links imply underline
        self.assertEqual(text.text, "Signed in as ada@example.complain link")

    def test_markdown_parses_headings_lists_and_code(self):
        md = Markdown("""# Title

Some **bold** and `code` and [a link](https://x.dev).

- one
- [x] done

1. first
2. second

> quote

```python
print("hi")
```

---
""")
        blocks = md.blocks()
        kinds = [b["kind"] for b in blocks]
        self.assertEqual(kinds, ["heading", "paragraph", "list", "list",
                                 "quote", "code", "rule"])
        self.assertEqual(blocks[0]["level"], 1)
        paragraph = blocks[1]["spans"]
        self.assertTrue(any(s.get("weight") == 700 for s in paragraph))
        self.assertTrue(any(s.get("mono") for s in paragraph))
        self.assertTrue(any(s.get("link") == "https://x.dev" for s in paragraph))
        self.assertIs(blocks[2]["items"][1]["checked"], True)
        self.assertTrue(blocks[3]["ordered"])
        self.assertEqual(blocks[5]["language"], "python")
        self.assertIn('print("hi")', md.text)

    def test_markdown_handles_empty_source(self):
        self.assertEqual(Markdown("").blocks(), [])

    def test_reorderable_list_helper(self):
        rows = [Text(str(i)) for i in range(3)]
        widget = ReorderableList(rows, on_reorder=lambda e: None,
                                 swipe_to_remove=True)
        self.assertEqual(len(widget.children), 3)
        self.assertTrue(props(widget)["swipeToRemove"])
        self.assertEqual(widget.reorder(["a", "b", "c"], 0, 2),
                         ["b", "c", "a"])
        with self.assertRaises(TypeError):
            ReorderableList(["not a widget"])

    def test_infinite_list_virtualises_rows(self):
        rows = [Text(str(i)) for i in range(500)]
        widget = InfiniteList(rows, window=25, on_load_more=lambda e: None)
        data = props(widget)
        self.assertEqual(len(widget.children), 25)
        self.assertEqual(data["total"], 500)
        self.assertTrue(data["hasMore"])
        self.assertTrue(data["virtualized"])

    def test_infinite_list_empty_state(self):
        empty = Text("Nothing here")
        widget = InfiniteList([], empty=empty)
        self.assertEqual(widget.children, [empty])
        self.assertIsNone(props(widget).get("hasMore"))

    def test_infinite_list_validates_arguments(self):
        with self.assertRaises(ValueError):
            InfiniteList([], threshold=0)
        with self.assertRaises(ValueError):
            InfiniteList([], window=0)


class TestAnimationControllers(unittest.TestCase):

    def test_curves_are_bounded(self):
        for name in ("linear", "ease_in", "ease_out", "ease_in_out", "bounce",
                     "elastic", "decelerate", "accelerate"):
            fn = curve(name)
            self.assertAlmostEqual(fn(0.0), 0.0, places=3)
            self.assertAlmostEqual(fn(1.0), 1.0, places=3)
        with self.assertRaises(ValueError):
            curve("nope")

    def test_controller_runs_to_completion(self):
        controller = AnimationController(0.12, curve="linear", fps=60)
        values, done = [], []
        controller.on_tick(values.append).on_complete(lambda: done.append(True))
        controller.forward()
        deadline = time.time() + 2
        while not done and time.time() < deadline:
            time.sleep(0.01)
        controller.dispose()
        self.assertTrue(done)
        self.assertAlmostEqual(values[-1], 1.0, places=5)
        self.assertTrue(all(b >= a - 1e-9 for a, b in zip(values, values[1:])))

    def test_reverse_and_stop(self):
        controller = AnimationController(0.1, curve="linear", fps=60)
        controller.reset(1.0)
        controller.reverse()
        time.sleep(0.05)
        controller.stop()
        self.assertFalse(controller.running)
        self.assertLess(controller.value, 1.0)

    def test_repeat_ping_pongs_without_completing(self):
        controller = AnimationController(0.05, curve="linear", fps=60)
        done = []
        controller.on_complete(lambda: done.append(True))
        controller.repeat(reverse=True)
        time.sleep(0.2)
        self.assertTrue(controller.running)
        controller.dispose()
        self.assertEqual(done, [])

    def test_controller_validates_arguments(self):
        with self.assertRaises(ValueError):
            AnimationController(0)
        with self.assertRaises(ValueError):
            AnimationController(1, fps=500)
        with self.assertRaises(TypeError):
            AnimationController(1).on_tick("nope")

    def test_tween_interpolates_numbers_colours_and_tuples(self):
        self.assertEqual(Tween(0, 100).at(0.5), 50)
        self.assertEqual(Tween(0.0, 1.0).at(0.25), 0.25)
        self.assertEqual(Tween("#FF000000", "#FFFFFFFF").at(0.5), "#FF808080")
        self.assertEqual(Tween("#00FF0000", "#FFFF0000").at(0.5), "#80FF0000")
        self.assertEqual(Tween((0, 0), (10, 20)).at(0.5), (5, 10))
        self.assertEqual(Tween("a", "b").at(0.9), "b")
        # Values are clamped.
        self.assertEqual(Tween(0, 10).at(5), 10)

    def test_tween_chain_feeds_a_setter(self):
        seen = []
        controller = AnimationController(0.08, curve="linear", fps=60)
        Tween(0, 100).chain(controller, seen.append)
        controller.forward()
        time.sleep(0.2)
        controller.dispose()
        self.assertTrue(seen)
        self.assertLessEqual(seen[-1], 100)

    def test_sequence_plays_steps_in_order(self):
        order = []
        first = AnimationController(0.05, curve="linear", fps=60)
        second = AnimationController(0.05, curve="linear", fps=60)
        first.on_complete(lambda: order.append("first"))
        second.on_complete(lambda: order.append("second"))
        Sequence_(first, second).play()
        deadline = time.time() + 2
        while len(order) < 2 and time.time() < deadline:
            time.sleep(0.01)
        first.dispose()
        second.dispose()
        self.assertEqual(order, ["first", "second"])

    def test_page_animation_is_bound_to_the_app(self):
        app = App()
        controller = app.page.animation(0.05, curve="linear", fps=60)
        values = []
        controller.on_tick(values.append)
        controller.forward()
        time.sleep(0.2)
        controller.dispose()
        self.assertTrue(values)


class TestNavigationV13(unittest.TestCase):

    def setUp(self):
        self.seen = []
        self.router = Router()
        self.router.define("/", lambda page: self.seen.append(("/", {})))
        self.router.define("/items/:id",
                           lambda page, params: self.seen.append(("item", params)),
                           transition="slide_left")
        self.router.define("/files/*rest",
                           lambda page, params: self.seen.append(("files", params)))
        self.router.define("settings", lambda page: self.seen.append(("set", {})))
        self.router.initial("/")
        self.router.scheme("myapp")

    def test_path_parameters_are_captured_and_coerced(self):
        self.assertTrue(self.router.go("/items/7"))
        self.assertEqual(self.router.current_params["id"], 7)
        self.assertEqual(self.router.path(), "/items/7")
        self.assertEqual(self.router.url(), "myapp://items/7")

    def test_query_parameters_merge_into_params(self):
        self.router.go("/items/9?tab=specs&ref=home")
        params = self.router.current_params
        self.assertEqual((params["id"], params["tab"], params["ref"]),
                         (9, "specs", "home"))

    def test_wildcard_routes(self):
        self.assertTrue(self.router.go("/files/a/b/c.txt"))
        self.assertEqual(self.router.current_params["rest"], "a/b/c.txt")

    def test_specific_routes_beat_wildcards(self):
        self.router.define("/files/readme",
                           lambda page: self.seen.append(("readme", {})))
        self.router.go("/files/readme")
        self.assertEqual(self.router.current_route, "/files/readme")

    def test_deep_links_of_every_shape(self):
        self.assertEqual(parse_url("myapp://items/3"), ("/items/3", {}))
        self.assertEqual(parse_url("https://ex.dev/items/3?x=1"),
                         ("/items/3", {"x": "1"}))
        self.assertEqual(parse_url("myapp://settings"), ("/settings", {}))
        self.assertTrue(self.router.handle_link("myapp://items/42"))
        self.assertEqual(self.router.current_params["id"], 42)

    def test_unmatched_link_returns_false(self):
        self.assertFalse(self.router.go("/nowhere"))

    def test_not_found_screen(self):
        self.router.not_found(lambda page, params: self.seen.append(("404", params)))
        self.assertFalse(self.router.go("/nowhere"))
        self.assertEqual(self.router.current_route, "__not_found__")

    def test_guards_can_block_and_redirect(self):
        self.router.guard(lambda name, params: name != "settings")
        self.router.push("settings")
        self.assertNotEqual(self.router.current_route, "settings")

        redirected = Router()
        redirected.define("/login", lambda page: None)
        redirected.define("/secret", lambda page: None,
                          guard=lambda name, params: "/login")
        redirected.initial("/login")
        redirected.push("/secret")
        self.assertEqual(redirected.current_route, "/login")

    def test_route_level_validation(self):
        with self.assertRaises(ValueError):
            Route("x", lambda page: None, transition="warp")
        with self.assertRaises(TypeError):
            Route("x", lambda page: None, guard="nope")
        self.assertIn("slide_left", TRANSITIONS)

    def test_nested_navigator_consumes_back_first(self):
        tabs = Router()
        tabs.define("a", lambda page: None).define("b", lambda page: None)
        tabs.initial("a")
        self.router.nest("/items/:id", tabs)
        self.router.go("/items/1")
        tabs.push("b")

        self.assertIs(self.router.child("/items/:id"), tabs)
        self.assertIs(self.router.active_child(), tabs)
        self.assertIs(tabs.parent, self.router)

        self.assertTrue(self.router.handle_back())      # pops the child
        self.assertEqual(tabs.current_route, "a")
        self.assertEqual(self.router.current_route, "/items/:id")

        self.assertTrue(self.router.handle_back())      # now pops the parent
        self.assertEqual(self.router.current_route, "/")

    def test_nest_rejects_non_routers(self):
        with self.assertRaises(TypeError):
            self.router.nest("/", object())

    def test_build_path_requires_its_parameters(self):
        route = Route("/items/:id", lambda page, params: None)
        self.assertEqual(route.build_path({"id": 5}), "/items/5")
        with self.assertRaises(KeyError):
            route.build_path({})


if __name__ == "__main__":
    unittest.main()
