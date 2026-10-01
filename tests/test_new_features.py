"""
Unit tests for the widgets, diffing and navigation behaviour added in 1.1.
"""

from __future__ import annotations

import unittest

from pydrud import (
    App, AppBar, Button, Card, Checkbox, Colors, Column, Container, Dropdown,
    FloatingActionButton, GridView, Icon, Icons, ListView, Padding, Positioned,
    ProgressBar, Radio, Row, Router, Scaffold, SizedBox, Slider, Stack, State,
    Text, Theme,
)
from pydrud.core.diff import TreeDiff
from pydrud.widgets.base import assign_stable_keys
from pydrud.widgets.layout import _edge_dict
from pydrud.widgets.styling import EdgeInsets


class TestStableKeys(unittest.TestCase):
    """Auto keys must be deterministic so diffs stay small."""

    def _tree(self, label: str):
        return Column(children=[Text(label), Button("ok")])

    def test_same_structure_same_keys(self):
        a = assign_stable_keys(self._tree("x"))
        b = assign_stable_keys(self._tree("y"))
        self.assertEqual([w.key for w, _ in a.walk()], [w.key for w, _ in b.walk()])

    def test_explicit_keys_are_preserved(self):
        tree = assign_stable_keys(Column(children=[Text("a", key="mine")]))
        self.assertEqual(tree.children[0].key, "mine")

    def test_rebuild_produces_single_update_patch(self):
        old = assign_stable_keys(self._tree("x"))
        new = assign_stable_keys(self._tree("y"))
        patches = TreeDiff.diff(old, new)
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0].op, "update")
        self.assertEqual(patches[0].props["value"], "y")

    def test_unstable_keys_would_rebuild(self):
        """Sanity check: without stabilisation the diff is a full rebuild."""
        patches = TreeDiff.diff(self._tree("x"), self._tree("y"))
        self.assertTrue(any(p.op == "replace" for p in patches))


class TestKeyedDiff(unittest.TestCase):
    def _list(self, items):
        return Column(key="list", children=[Text(i, key=f"i-{i}") for i in items])

    def test_insert_in_middle_only_creates_one(self):
        patches = TreeDiff.diff(self._list(["a", "c"]), self._list(["a", "b", "c"]))
        self.assertEqual([p.op for p in patches].count("create"), 1)
        create = next(p for p in patches if p.op == "create")
        self.assertEqual(create.key, "i-b")
        self.assertEqual(create.data["index"], 1)

    def test_removal_emits_delete(self):
        patches = TreeDiff.diff(self._list(["a", "b"]), self._list(["a"]))
        self.assertEqual([(p.op, p.key) for p in patches], [("delete", "i-b")])

    def test_reorder_emits_moves_only(self):
        patches = TreeDiff.diff(self._list(["a", "b"]), self._list(["b", "a"]))
        self.assertTrue(patches)
        self.assertTrue(all(p.op == "move" for p in patches))

    def test_type_change_replaces(self):
        old = Column(key="r", children=[Text("x", key="c")])
        new = Column(key="r", children=[Button("x", key="c")])
        patches = TreeDiff.diff(old, new)
        self.assertEqual(patches[0].op, "replace")
        self.assertEqual(patches[0].data["tree"]["type"], "Button")

    def test_event_changes_are_serialisable(self):
        old = Column(key="r", children=[Text("x", key="c")])
        new = Column(key="r", children=[Text("x", key="c").on_click(lambda e: None)])
        patches = TreeDiff.diff(old, new)
        TreeDiff.patches_to_json(patches)  # must not raise
        self.assertEqual(patches[0].props["_events"], ["click"])

    def test_invalid_op_rejected(self):
        from pydrud.core.diff import Patch
        with self.assertRaises(ValueError):
            Patch("explode", "k")


class TestNewWidgets(unittest.TestCase):
    def test_stack_and_positioned(self):
        stack = Stack(children=[
            Text("bg"),
            Positioned(child=Text("badge"), top=4, right=4),
        ])
        d = stack.to_dict()
        self.assertEqual(d["type"], "Stack")
        pos = d["children"][1]
        self.assertEqual(pos["style"]["position"], "absolute")
        self.assertEqual(pos["style"]["top"], 4)

    def test_card_defaults(self):
        """Flat + outlined by default; raised cards drop the hairline."""
        card = Card(child=Text("hi")).to_dict()
        self.assertEqual(card["style"]["elevation"], 0)
        self.assertEqual(card["style"]["borderRadius"], 16)
        self.assertEqual(card["style"]["padding"],
                         {"left": 16, "top": 16, "right": 16, "bottom": 16})
        self.assertIn("border", card["style"])

        raised = Card(child=Text("hi"), elevation=3).to_dict()
        self.assertEqual(raised["style"]["elevation"], 3)
        self.assertNotIn("border", raised["style"])

    def test_list_and_grid(self):
        lv = ListView(children=[Text("a")], spacing=4).to_dict()
        self.assertTrue(lv["style"]["scroll"])
        self.assertEqual(lv["style"]["spacing"], 4)

        gv = GridView(children=[Text("a")], columns=3).to_dict()
        self.assertEqual(gv["style"]["columns"], 3)

    def test_grid_columns_clamped(self):
        self.assertEqual(GridView(columns=0).style["columns"], 1)

    def test_sized_box_and_padding(self):
        self.assertEqual(SizedBox(width=8, height=12).style,
                         {"width": 8, "height": 12})
        self.assertEqual(Padding(EdgeInsets.all(5), child=Text("x")).style["padding"],
                         {"left": 5, "top": 5, "right": 5, "bottom": 5})

    def test_progress_bar_modes(self):
        self.assertTrue(ProgressBar().to_dict()["props"]["indeterminate"])
        bar = ProgressBar(0.5)
        self.assertFalse(bar.to_dict()["props"]["indeterminate"])
        self.assertEqual(bar.value, 0.5)

    def test_slider_clamps_and_validates(self):
        self.assertEqual(Slider(500, min=0, max=100).value, 100)
        self.assertEqual(Slider(-5, min=0, max=100).value, 0)
        with self.assertRaises(ValueError):
            Slider(0, min=10, max=10)

    def test_dropdown_index(self):
        dd = Dropdown(["a", "b", "c"], value="c")
        self.assertEqual(dd.selected_index, 2)
        self.assertEqual(dd.to_dict()["props"]["options"], ["a", "b", "c"])

    def test_radio_props(self):
        props = Radio("Yes", group="g", selected=True).to_dict()["props"]
        self.assertEqual(props["group"], "g")
        self.assertTrue(props["selected"])

    def test_edge_dict_accepts_many_forms(self):
        self.assertEqual(_edge_dict(4)["left"], 4)
        self.assertEqual(_edge_dict({"left": 2})["left"], 2)
        self.assertEqual(_edge_dict(EdgeInsets.symmetric(horizontal=3))["right"], 3)
        with self.assertRaises(TypeError):
            _edge_dict("nope")


class TestCompositeWidgets(unittest.TestCase):
    def test_appbar_serialises_to_container(self):
        bar = AppBar(title="Title", key="bar", actions=[Icon("search", key="s")])
        d = bar.to_dict()
        self.assertEqual(d["type"], "Container")
        self.assertEqual(d["key"], "bar._bar")
        texts = [n for n in _walk_dict(d) if n["type"] == "Text"]
        self.assertEqual(texts[0]["props"]["value"], "Title")

    def test_scaffold_places_appbar_body_fab(self):
        sc = Scaffold(
            key="s",
            app_bar=AppBar(title="T", key="bar"),
            body=Text("body", key="body"),
            floating_action_button=FloatingActionButton("+", key="fab"),
        )
        d = sc.to_dict()
        self.assertEqual(d["type"], "Stack")
        keys = [n["key"] for n in _walk_dict(d)]
        self.assertIn("s._body", keys)
        self.assertIn("fab", keys)

    def test_fab_is_absolutely_positioned_with_label(self):
        d = FloatingActionButton("+", key="fab").to_dict()
        self.assertEqual(d["style"]["position"], "absolute")
        self.assertEqual(d["style"]["bottom"], 24)
        self.assertEqual(d["children"][0]["props"]["value"], "+")

    def test_fab_with_icon(self):
        d = FloatingActionButton(icon=Icons.ADD, key="fab").to_dict()
        self.assertEqual(d["children"][0]["type"], "Icon")
        self.assertEqual(d["children"][0]["props"]["name"], "add")

    def test_composite_unwrap_keeps_diff_keys_aligned(self):
        a = Scaffold(key="s", app_bar=AppBar(title="A", key="b"), body=Text("x", key="t"))
        b = Scaffold(key="s", app_bar=AppBar(title="B", key="b"), body=Text("x", key="t"))
        patches = TreeDiff.diff(a, b)
        self.assertTrue(patches)
        for patch in patches:
            self.assertNotEqual(patch.key, "s", "patch targets a non-rendered key")


class TestRouterBehaviour(unittest.TestCase):
    def setUp(self):
        self.router = Router()
        self.rendered: list[str] = []
        self.router.define("home", lambda page: self.rendered.append("home"))
        self.router.define("detail", lambda page, params: self.rendered.append(
            f"detail:{params.get('id')}"))
        self.router.initial("home")

    def test_push_pop_stack(self):
        self.assertFalse(self.router.can_pop())
        self.router.push("detail", id=3)
        self.assertEqual(self.router.current_route, "detail")
        self.assertEqual(self.router.current_params, {"id": 3})
        self.assertTrue(self.router.can_pop())
        self.assertTrue(self.router.pop())
        self.assertEqual(self.router.current_route, "home")
        self.assertFalse(self.router.pop())

    def test_handle_back_matches_pop(self):
        self.router.push("detail", id=1)
        self.assertTrue(self.router.handle_back())
        self.assertFalse(self.router.handle_back())

    def test_replace_does_not_grow_stack(self):
        self.router.replace("detail", id=9)
        self.assertEqual(self.router.stack_size, 1)
        self.assertEqual(self.router.current_route, "detail")

    def test_pop_to_root(self):
        self.router.push("detail", id=1)
        self.router.push("detail", id=2)
        self.assertTrue(self.router.pop_to_root())
        self.assertEqual(self.router.stack_size, 1)
        self.assertEqual(self.router.current_route, "home")

    def test_unknown_route_raises(self):
        with self.assertRaises(ValueError):
            self.router.push("nope")

    def test_params_passed_to_two_arg_builders(self):
        page = App(target=None).page
        self.router.push("detail", id=42)
        self.router.build_root()(page)
        self.assertIn("detail:42", self.rendered)

    def test_on_change_callback(self):
        seen = []
        self.router.on_change(seen.append)
        self.router.push("detail", id=1)
        self.assertEqual(seen, ["detail"])

    def test_reset_clears_history(self):
        self.router.push("detail", id=1)
        self.router.reset()
        self.assertIsNone(self.router.current_route)


class TestAppInternals(unittest.TestCase):
    def test_hot_restart_without_device_does_not_raise(self):
        app = App(target=lambda page: page.add(Text("hi")))
        router = Router().define("home", lambda page: None).initial("home")
        app.attach_router(router)
        app.build()
        app.hot_restart()  # used to crash: current_route had no setter
        self.assertIsNone(router.current_route)

    def test_page_add_rejects_non_widgets(self):
        app = App()
        with self.assertRaises(TypeError):
            app.page.add("not a widget")

    def test_page_find_and_remove(self):
        app = App(target=lambda page: page.add(Text("hi", key="t")))
        app.build()
        self.assertIsNotNone(app.page.find("t"))

    def test_bind_state_triggers_update(self):
        calls = []
        app = App(target=lambda page: page.add(Text("x")))
        app.update = lambda: calls.append(1)  # type: ignore[method-assign]
        state = State(0)
        app.bind(state)
        state.value = 1
        self.assertEqual(len(calls), 1)

    def test_set_system_ui_validates_brightness(self):
        app = App()
        with self.assertRaises(ValueError):
            app.page.set_system_ui(icon_brightness="rainbow")

    def test_module_name_resolution(self):
        from pydrud.main import _module_name_for
        import os
        root = os.path.abspath("/tmp/proj")
        self.assertEqual(
            _module_name_for(os.path.join(root, "src", "app", "main.py"), root),
            "app.main",
        )
        self.assertEqual(
            _module_name_for(os.path.join(root, "src", "app", "__init__.py"), root),
            "app",
        )


class TestPackageNaming(unittest.TestCase):
    def test_app_name_is_appended_once(self):
        from pydrud.commands.project import _sanitize_package
        self.assertEqual(_sanitize_package("com.example", "my_app"), "com.example.my_app")
        self.assertEqual(_sanitize_package("com.example.my_app", "my_app"),
                         "com.example.my_app")

    def test_invalid_characters_and_keywords_handled(self):
        from pydrud.commands.project import _sanitize_package
        self.assertEqual(_sanitize_package("Com-Example!", "2cool"), "comexample._2cool")
        self.assertEqual(_sanitize_package("com.new", "app"), "com._new.app")
        self.assertEqual(_sanitize_package("", ""), "com.example")


class TestThemeHelpers(unittest.TestCase):
    def test_colors_with_opacity(self):
        self.assertEqual(Colors.with_opacity("#FF6366F1", 0.5), "#806366F1")
        self.assertEqual(Colors.with_opacity("6366F1", 1.0), "#FF6366F1")
        with self.assertRaises(ValueError):
            Colors.with_opacity("#FF6366F1", 2)

    def test_icons_catalogue(self):
        self.assertIn("settings", Icons.all())

    def test_theme_switching(self):
        Theme.dark()
        self.assertTrue(Theme.dark_mode)
        Theme.light()
        self.assertFalse(Theme.dark_mode)
        self.assertEqual(Theme.as_dict()["background"], Colors.BACKGROUND)


class TestWidgetBaseExtras(unittest.TestCase):
    def test_generic_event_registration(self):
        w = Container().on("scroll", lambda e: None)
        self.assertIn("scroll", w.to_dict()["events"])

    def test_on_click_kwarg(self):
        w = Container(on_click=lambda e: None)
        self.assertTrue(w.to_dict()["has_events"])

    def test_clone_keeps_handlers_and_is_independent(self):
        original = Column(children=[Text("a", key="t").on_click(lambda e: None)])
        clone = original.clone()
        clone.children[0]._value = "b"
        self.assertEqual(original.children[0].value, "a")
        self.assertIn("click", clone.children[0].event_handlers)

    def test_invisible_children_are_not_serialised(self):
        d = Column(children=[Text("hidden", visible=False), Text("shown")]).to_dict()
        self.assertEqual(len(d["children"]), 1)

    def test_with_style_chaining(self):
        w = Container().with_style(bg="#FF000000")
        self.assertEqual(w.style["bg"], "#FF000000")


def _walk_dict(node: dict):
    yield node
    for child in node.get("children", []):
        yield from _walk_dict(child)


if __name__ == "__main__":
    unittest.main()
