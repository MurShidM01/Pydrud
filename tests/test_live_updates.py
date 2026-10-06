"""
Regression tests for live-update ("the change doesn't show up") bugs.

Each test pins down a defect that made the on-device UI disagree with the
Python state: a snackbar action that went nowhere, children that were
never attached by the renderer, patch indices that drifted out of step
with the native view tree, and prop changes that were silently dropped.
"""

from __future__ import annotations

import pathlib
import unittest

from pydrud import App, Column, State, Tabs, Text
from pydrud.core.diff import TreeDiff
from pydrud.widgets.material import ExpansionTile
from tests.fake_device import FakeDevice, run_app


# ── snackbar actions ─────────────────────────────────────────────────────────


class TestSnackbarAction(unittest.TestCase):
    """``page.snack_bar(action=..., on_action=...)`` must call back."""

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
        self.assertTrue(self.device.wait_for(lambda d: d.root is not None))
        return self.device

    def test_undo_restores_the_previous_value(self):
        counter = State(7)

        def main(page):
            def reset(_event):
                previous = counter.value
                counter.value = 0

                def undo():
                    counter.value = previous
                    page.update()

                page.snack_bar("Counter reset", action="Undo", on_action=undo)
                page.update()

            page.add(Column(children=[
                Text(f"Count: {counter.value}", key="label"),
                Text("Reset", key="reset", on_click=reset),
            ]))

        device = self.launch(main)
        device.click("reset")
        self.assertTrue(device.wait_for_text("Count: 0"))

        bar = device.last_request("snackbar") or device.commands_named("snackbar")[-1]
        self.assertEqual(bar["action"], "Undo")
        self.assertTrue(bar["callback_id"], "no callback id was sent to Android")

        self.assertTrue(device.tap_snackbar_action())
        self.assertTrue(device.wait_for_text("Count: 7"),
                        "tapping Undo did not run the callback")

    def test_dismissal_runs_on_dismiss_and_frees_the_callback(self):
        seen = []

        def main(page):
            def show(_event):
                page.snack_bar("Saved", action="Undo",
                               on_action=lambda: seen.append("action"),
                               on_dismiss=lambda: seen.append("dismiss"))

            page.add(Text("go", key="go", on_click=show))

        device = self.launch(main)
        device.click("go")
        self.assertTrue(device.wait_for_command("snackbar"))
        self.assertTrue(device.dismiss_snackbar())
        self.assertTrue(device.wait_for(lambda _d: seen == ["dismiss"]))

        # The callback is one-shot: a late action event must not re-fire it.
        device.tap_snackbar_action()
        device.wait_for(lambda _d: False, timeout=0.2)
        self.assertEqual(seen, ["dismiss"])

    def test_plain_snackbar_sends_no_callback_id(self):
        def main(page):
            page.add(Text("x", key="x", on_click=lambda _e: page.snack_bar("hi")))

        device = self.launch(main)
        device.click("x")
        self.assertTrue(device.wait_for_command("snackbar"))
        self.assertEqual(device.commands_named("snackbar")[-1]["callback_id"], "")


# ── diff / index integrity ───────────────────────────────────────────────────


class TestHiddenChildrenKeepIndices(unittest.TestCase):
    """Invisible children stay in the tree so indices line up natively."""

    def test_hidden_child_is_serialised(self):
        tree = Column(children=[Text("a", visible=False), Text("b")]).to_dict()
        self.assertEqual(len(tree["children"]), 2)
        self.assertFalse(tree["children"][0]["visible"])

    def test_insert_index_matches_the_rendered_tree(self):
        before = Column(key="col", children=[
            Text("a", key="a", visible=False),
            Text("c", key="c"),
        ])
        after = Column(key="col", children=[
            Text("a", key="a", visible=False),
            Text("b", key="b"),
            Text("c", key="c"),
        ])
        patches = [p for p in TreeDiff.diff(before, after) if p.op == "create"]
        self.assertEqual(len(patches), 1)
        # Index 1 is only correct if the hidden child occupies index 0 on
        # the device as well — which is exactly what to_dict() now does.
        self.assertEqual(patches[0].index, 1)
        rendered_keys = [c["key"] for c in before.to_dict()["children"]]
        self.assertEqual(rendered_keys.index("c"), 1)

    def test_toggling_visibility_is_an_update_not_a_rebuild(self):
        before = Column(key="col", children=[Text("a", key="a")])
        after = Column(key="col", children=[Text("a", key="a", visible=False)])
        patches = TreeDiff.diff(before, after)
        self.assertEqual([p.op for p in patches], ["update"])
        self.assertFalse(patches[0].props["_visible"])


# ── the Java renderer ────────────────────────────────────────────────────────


TEMPLATES = (pathlib.Path(__file__).resolve().parent.parent
             / "pydrud" / "android" / "templates" / "android")


def _java(name: str) -> str:
    """The raw Java template source (Jinja placeholders and all)."""
    return (TEMPLATES / f"{name}.java.j2").read_text()


class TestViewFactoryTemplate(unittest.TestCase):
    """Static guarantees about the generated renderer."""

    @classmethod
    def setUpClass(cls):
        from tests import all_java_templates
        cls.factory = all_java_templates()
        cls.material = _java("MaterialViews")
        cls.bridge = _java("BridgeService")

    def test_material_views_get_their_children_attached(self):
        # Tabs, Drawer, gesture and animation wrappers used to render empty
        # on the first frame because only the built-in layouts attached
        # children.
        self.assertIn("attachChildren(view, json);", self.factory)
        self.assertIn("void attachChildren(", self.factory)

    def test_child_host_tag_is_honoured_by_patches(self):
        self.assertIn("static ViewGroup childHost(View view)", self.factory)
        self.assertIn("return childHost(parent);", self.factory)
        self.assertIn("R.id.pydrud_tag_children", self.factory)

    def test_tabs_and_expansion_tile_declare_a_content_host(self):
        self.assertEqual(
            self.material.count("setTag(R.id.pydrud_tag_children"), 2,
            "Tabs and ExpansionTile must both tag their content container")

    def test_tag_keys_are_application_specific(self):
        # View.setTag(key, …) throws "The key must be an
        # application-specific resource id" for framework ids such as
        # android.R.id.text1 — which used to kill every slider, switch
        # and checkbox mid-render. Only app ids are allowed from now on.
        for source in (self.factory, self.material):
            self.assertNotIn(
                "setTag(android.R.id.", source,
                "two-arg setTag with a framework id crashes at runtime")
            self.assertNotIn(
                "getTag(android.R.id.", source,
                "getTag with a framework id never matches an app tag")

    def test_preview_fill_list_matches_the_native_renderer(self):
        # tools/preview_ui.py promises to lay widgets out "with the same
        # rules ViewFactory uses". Its FILL_BY_DEFAULT set must therefore
        # agree with ViewFactory's fillsWidthByDefault() switch (the
        # preview additionally knows Stack/Center, which the Java side
        # handles in a separate branch).
        import re
        java = re.search(
            r"fillsWidthByDefault\(String type\) \{\s*switch \(type\) \{(.*?)\}",
            self.factory, re.S).group(1)
        java_types = set(re.findall(r'case "([^"]+)"', java))
        preview_src = (TEMPLATES.parent.parent.parent.parent
                       / "tools" / "preview_ui.py").read_text()
        python = re.search(
            r"FILL_BY_DEFAULT = \{(.*?)\}", preview_src, re.S).group(1)
        python_types = set(re.findall(r'"([^"]+)"', python))
        self.assertLessEqual(
            java_types, python_types,
            "preview is missing full-width types the device stretches")
        self.assertLessEqual(
            python_types - {"Stack"}, java_types,
            "preview stretches types the device leaves at wrap_content")
        # …and a Container must hug its child on both sides (it used to
        # swallow the whole row, hiding app-bar titles).
        self.assertNotIn("Container", java_types)
        self.assertNotIn("Container", python_types)

    def test_spacing_uses_margins_not_space_views(self):
        # Interleaved Space views shifted every native child index, so
        # insert/remove patches landed in the wrong place.
        self.assertNotIn("Space gap = new Space(activity);", self.factory)
        self.assertIn("void applySpacing(ViewGroup parent)", self.factory)

    def test_unhandled_prop_updates_rebuild_the_view(self):
        self.assertIn("boolean updateProps(", self.factory)
        self.assertIn("recreateInPlace(key, node);", self.factory)

    def test_image_source_updates_reload_the_bitmap(self):
        self.assertIn('view instanceof ImageView && p.has("src")', self.factory)

    def test_parent_map_is_filled_on_a_full_render(self):
        self.assertIn("indexParents(tree);", self.factory)

    def test_snackbar_action_reports_back_to_python(self):
        self.assertIn("sendSnackbarEvent(callbackId, true)", self.bridge)
        self.assertIn('sendEvent("snackbar", "", data)', self.bridge)
        self.assertNotIn("bar.setAction(action, v -> {});", self.bridge)


# ── tabs end to end ──────────────────────────────────────────────────────────


class TestTabsLiveSwitch(unittest.TestCase):
    """Switching tabs patches exactly the body, and the body starts filled."""

    def setUp(self):
        self.device = FakeDevice().start()
        self.app: App | None = None

    def tearDown(self):
        if self.app is not None:
            self.app.stop()
        self.device.stop()

    def test_first_render_contains_the_selected_tab_body(self):
        index = State(0)

        def main(page):
            def switch(event):
                index.value = int(event["value"])
                page.update()

            page.add(Tabs(
                key="tabs",
                tabs=["One", "Two"],
                selected=index.value,
                on_change=switch,
                children=[Text(f"Body {index.value}", key=f"body{index.value}")],
            ))

        self.app = App(target=main)
        run_app(self.app, self.device)
        self.assertTrue(self.device.wait_for(lambda d: d.root is not None))
        self.assertIn("Body 0", self.device.texts,
                      "the tab body must be in the very first render")

        self.device.change("tabs", 1)
        self.assertTrue(self.device.wait_for_text("Body 1"))
        self.assertNotIn("Body 0", self.device.texts)
        self.assertEqual(
            self.device.root.find("tabs").props["selected"], 1)


class TestExpansionTileBody(unittest.TestCase):
    """An ExpansionTile's children are part of its serialised tree."""

    def test_children_are_serialised(self):
        tile = ExpansionTile("More", key="tile", expanded=True,
                             children=[Text("hidden gem", key="gem")])
        data = tile.to_dict()
        self.assertEqual(data["children"][0]["key"], "gem")
        self.assertTrue(data["props"]["expanded"])


if __name__ == "__main__":
    unittest.main()


class TestWidgetErgonomics(unittest.TestCase):
    """Shorthands that used to be swallowed silently."""

    def test_children_kwarg_works_on_any_widget(self):
        # Tabs never declared `children=`; it used to vanish into props.
        tabs = Tabs(key="t", tabs=["One"], children=[Text("x", key="x")])
        self.assertEqual([c.key for c in tabs.children], ["x"])
        self.assertNotIn("children", tabs._serialise_props())

    def test_children_kwarg_rejects_non_widgets(self):
        with self.assertRaises(TypeError):
            Tabs(key="t2", tabs=["One"], children=["not a widget"])

    def test_tabs_accept_plain_labels(self):
        tabs = Tabs(key="tabs", tabs=["One", "Two"], selected=1)
        self.assertEqual([t.label for t in tabs.tabs], ["One", "Two"])
        self.assertEqual(tabs.selected, 1)

    def test_tabs_accept_tuples_and_dicts(self):
        tabs = Tabs(key="tabs", tabs=[("Inbox", "mail"), {"label": "Sent"}])
        self.assertEqual(tabs.tabs[0].icon, "mail")
        self.assertEqual(tabs.tabs[1].label, "Sent")

    def test_tabs_keep_explicit_children_when_no_tab_has_content(self):
        tabs = Tabs(key="tabs", tabs=["One"], children=[Text("body", key="b")])
        self.assertEqual([c.key for c in tabs.children], ["b"])

    def test_tab_content_still_wins(self):
        from pydrud.widgets.material import Tab
        tabs = Tabs(key="tabs",
                    tabs=[Tab("One", content=Text("from tab", key="t"))],
                    children=[Text("ignored", key="b")])
        self.assertEqual([c.key for c in tabs.children], ["t"])
