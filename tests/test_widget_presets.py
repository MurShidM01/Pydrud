"""Coverage for the 130+ widget catalogue and Flutter-style presets."""

from __future__ import annotations

import inspect
import unittest

import pydrud
import pydrud.widgets as widgets
from pydrud.widgets.base import Widget


class TestWidgetCatalogue(unittest.TestCase):

    def test_public_catalogue_contains_at_least_130_widget_classes(self):
        classes = {
            name: getattr(widgets, name)
            for name in widgets.__all__
            if inspect.isclass(getattr(widgets, name, None))
            and issubclass(getattr(widgets, name), Widget)
        }
        self.assertGreaterEqual(len(classes), 130, sorted(classes))
        for name in classes:
            self.assertIs(getattr(pydrud, name), classes[name], name)

    def test_labelled_switch_fills_row_but_icon_switch_stays_compact(self):
        labelled = pydrud.Switch("Dark mode", key="theme")
        compact = pydrud.Switch("", key="compact")
        opted_out = pydrud.Switch("Compact", key="opt", full_width=False)
        self.assertEqual(labelled.style["width"], "match")
        self.assertNotIn("width", compact.style)
        self.assertNotIn("width", opted_out.style)

    def test_switch_list_tile_places_control_after_expanding_title(self):
        tile = pydrud.SwitchListTile(
            "Dark mode", value=True, control_key="dark_switch",
            on_change=lambda event: None, key="dark_tile")
        data = tile.to_dict()
        self.assertEqual(data["type"], "ListTile")
        self.assertEqual(data["props"]["title"], "Dark mode")
        self.assertEqual(data["children"][0]["type"], "Switch")
        self.assertEqual(data["children"][0]["key"], "dark_switch")
        self.assertTrue(data["children"][0]["props"]["active"])
        self.assertIn("change", data["children"][0]["events"])

    def test_layout_presets_reuse_native_renderer_types(self):
        cases = [
            (pydrud.Expanded(pydrud.Text("x"), key="e"), "Container"),
            (pydrud.Align(pydrud.Text("x"), key="a"), "Container"),
            (pydrud.Wrap(children=[pydrud.Text("x")], key="w"), "GridView"),
            (pydrud.SingleChildScrollView(pydrud.Text("x"), key="s"),
             "ListView"),
            (pydrud.ButtonBar(children=[pydrud.Button("OK")], key="b"),
             "Row"),
        ]
        for widget, native_type in cases:
            with self.subTest(widget=widget.__class__.__name__):
                self.assertEqual(widget.to_dict()["type"], native_type)

    def test_common_state_widgets_build_complete_native_trees(self):
        states = [
            pydrud.EmptyState(action="Create", on_action=lambda event: None),
            pydrud.ErrorState(on_retry=lambda event: None),
            pydrud.LoadingState(),
            pydrud.InfoCard("Offline", "Using cached data"),
            pydrud.StatCard("Downloads", 42, trend="+12%"),
        ]
        for state in states:
            with self.subTest(widget=state.__class__.__name__):
                data = state.to_dict()
                self.assertTrue(data.get("children"))
                self.assertNotEqual(data["type"], "Widget")

    def test_presets_validate_invalid_inputs(self):
        with self.assertRaises(ValueError):
            pydrud.Expanded(flex=0)
        with self.assertRaises(ValueError):
            pydrud.Gap(8, axis="diagonal")
        with self.assertRaises(ValueError):
            pydrud.Heading("Bad", level=0)
        with self.assertRaises(ValueError):
            pydrud.NetworkImage("assets/photo.png")


if __name__ == "__main__":
    unittest.main()
