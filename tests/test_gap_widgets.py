"""The §15.2 gap widgets that need no native code.

PYDRUD listed ``Flex`` (high), a ``LayoutBuilder``-style builder (medium)
and ``ExpansionPanelList`` (low) as missing. All three are compositions of
widgets the renderer already understands, so they live in Python and must
serialise as the primitives they stand for.
"""

from __future__ import annotations

import unittest

from pydrud import (
    Column,
    Constraints,
    ExpansionPanel,
    ExpansionPanelList,
    Flex,
    LayoutBuilder,
    Row,
    State,
    Text,
)
from pydrud.testing import AppTester


class TestFlex(unittest.TestCase):

    def test_horizontal_serialises_as_a_row(self):
        data = Flex(direction="horizontal",
                    children=[Text("a"), Text("b")]).to_dict()
        self.assertEqual(data["type"], "Row")
        self.assertEqual(data["style"]["mainAxis"], "horizontal")
        self.assertEqual(len(data["children"]), 2)

    def test_vertical_serialises_as_a_column(self):
        data = Flex(direction="vertical", children=[Text("a")]).to_dict()
        self.assertEqual(data["type"], "Column")
        self.assertEqual(data["style"]["mainAxis"], "vertical")

    def test_axis_aliases_agree(self):
        for spelling in ("horizontal", "row", "x", "ROW", " Row "):
            with self.subTest(direction=spelling):
                self.assertEqual(
                    Flex(direction=spelling).to_dict()["type"], "Row")
        for spelling in ("vertical", "column", "y"):
            with self.subTest(direction=spelling):
                self.assertEqual(
                    Flex(direction=spelling).to_dict()["type"], "Column")

    def test_unknown_direction_is_rejected(self):
        with self.assertRaises(ValueError):
            Flex(direction="diagonal")

    def test_flutter_alignment_names_map_onto_the_right_axis(self):
        horizontal = Flex(direction="horizontal",
                          main_alignment="space_between",
                          cross_alignment="center").to_dict()["style"]
        self.assertEqual(horizontal["mainAxisAlignment"], "space_between")
        self.assertEqual(horizontal["crossAxisAlignment"], "center")
        vertical = Flex(direction="vertical",
                        main_alignment="center",
                        cross_alignment="start").to_dict()["style"]
        self.assertEqual(vertical["mainAxisAlignment"], "center")
        self.assertEqual(vertical["crossAxisAlignment"], "start")

    def test_pydrud_alignment_names_still_work(self):
        style = Flex(direction="horizontal",
                     horizontal_alignment="center",
                     vertical_alignment="bottom").to_dict()["style"]
        self.assertEqual(style["mainAxisAlignment"], "center")
        self.assertEqual(style["crossAxisAlignment"], "bottom")

    def test_spacing_axis_sizes_and_weight_are_forwarded(self):
        style = Flex(direction="horizontal", spacing=12,
                     main_axis_size="min", cross_axis_size="max").to_dict()
        self.assertEqual(style["style"]["spacing"], 12)
        self.assertEqual(style["style"]["width"], "wrap")
        self.assertEqual(style["style"]["height"], "match")
        self.assertEqual(Flex(direction="horizontal", expand=2).to_dict()["expand"], 2)

    def test_style_and_visibility_are_forwarded(self):
        data = Flex(direction="horizontal", style={"bg": "#FF000000"},
                    visible=False).to_dict()
        self.assertEqual(data["style"]["bg"], "#FF000000")
        self.assertFalse(data["visible"])

    def test_add_rebuilds_the_underlying_row(self):
        flex = Flex(direction="horizontal", children=[Text("a")])
        flex.add(Text("b"))
        self.assertEqual(len(flex.to_dict()["children"]), 2)

    def test_the_tree_walks_through_the_axis_widget(self):
        flex = Flex(direction="vertical", children=[Text("a")])
        types = [w._widget_type for w, _ in flex.walk()]
        self.assertEqual(types, ["Flex", "Column", "Text"])


class TestLayoutBuilder(unittest.TestCase):

    def test_the_builder_receives_the_live_constraints(self):
        seen = []

        def build(c):
            seen.append(c)
            return Text(str(c.max_width), key="probe")

        with AppTester(lambda page: page.add(LayoutBuilder(build))) as app:
            # The device's own metrics arrive a moment after the first frame.
            app.device.wait_for(
                lambda d: d.root.find("probe").props["value"] == "400")
            self.assertTrue(seen)
            self.assertIsInstance(seen[0], Constraints)
            self.assertEqual(seen[-1].max_width, 400)
            self.assertEqual(seen[-1].max_height, 800)

    def test_it_serialises_as_the_built_widget(self):
        data = LayoutBuilder(lambda c: Row(children=[Text("x")])).to_dict()
        self.assertEqual(data["type"], "Row")

    def test_a_non_callable_builder_is_rejected(self):
        with self.assertRaises(TypeError):
            LayoutBuilder("nope")

    def test_it_rebuilds_when_the_window_changes(self):
        def build(c):
            return Text("wide" if c.max_width >= 600 else "narrow",
                        key="probe")

        with AppTester(lambda page: page.add(LayoutBuilder(build)),
                       width=400) as app:
            app.device.wait_for(
                lambda d: d.root.find("probe").props["value"] == "narrow")
            app.device.resize(800, 800)
            self.assertTrue(app.device.wait_for(
                lambda d: d.root.find("probe").props["value"] == "wide"))
            # The media query is process-global; put it back for later tests.
            app.device.resize(400, 800)
            app.device.wait_for(
                lambda d: d.root.find("probe").props["value"] == "narrow")


class TestConstraints(unittest.TestCase):

    def setUp(self):
        self.c = LayoutBuilder(lambda c: Text("x")).constraints

    def test_bounds_come_from_the_screen(self):
        self.assertEqual(self.c.min_width, 0)
        self.assertEqual(self.c.min_height, 0)
        self.assertGreater(self.c.max_width, 0)
        self.assertGreater(self.c.max_height, 0)
        self.assertEqual(self.c.width, self.c.max_width)
        self.assertEqual(self.c.height, self.c.max_height)

    def test_size_class_predicates_are_plain_booleans(self):
        for name in ("is_phone", "is_tablet", "is_desktop", "is_landscape",
                     "is_portrait", "is_dark"):
            with self.subTest(name=name):
                self.assertIsInstance(getattr(self.c, name), bool)

    def test_columns_and_grid_agree_with_responsive(self):
        from pydrud.core.responsive import Responsive

        self.assertEqual(self.c.columns(180),
                         Responsive.columns(180))
        self.assertEqual(self.c.grid(180), Responsive.grid(180))

    def test_breakpoint_helpers_are_exposed(self):
        self.assertIsInstance(self.c.breakpoint, str)
        self.assertIsInstance(self.c.at_least("compact"), bool)
        self.assertIsInstance(self.c.matches(min_width=100), bool)

    def test_raw_screen_metrics_fall_through(self):
        self.assertIn(self.c.device_type, ("phone", "tablet", "desktop",
                                           "tv", "watch"))

    def test_an_unknown_attribute_names_what_is_available(self):
        with self.assertRaises(AttributeError) as caught:
            self.c.definitely_not_a_metric  # noqa: B018
        self.assertIn("max_width", str(caught.exception))


class TestExpansionPanelList(unittest.TestCase):

    def _panels(self):
        return [
            ExpansionPanel("Shipping", children=[Text("3-5 days")]),
            ExpansionPanel("Returns", children=[Text("30 days")]),
        ]

    def test_it_serialises_as_a_column_of_tiles(self):
        data = ExpansionPanelList(self._panels()).to_dict()
        self.assertEqual(data["type"], "Column")
        self.assertEqual([c["type"] for c in data["children"]],
                         ["ExpansionTile", "ExpansionTile"])
        self.assertEqual([c["props"]["title"] for c in data["children"]],
                         ["Shipping", "Returns"])

    def test_panel_bodies_are_rendered(self):
        data = ExpansionPanelList(self._panels()).to_dict()
        first_body = data["children"][0]["children"][0]
        self.assertEqual(first_body["props"]["value"], "3-5 days")

    def test_panels_keep_their_own_expanded_state_without_accordion(self):
        panels = self._panels()
        panels[1].expanded = True
        data = ExpansionPanelList(panels).to_dict()
        self.assertEqual([c["props"]["expanded"] for c in data["children"]],
                         [False, True])

    def test_accordion_opens_exactly_the_selected_panel(self):
        index = State(0)
        widget = ExpansionPanelList(self._panels(), accordion=True,
                                    open_index=index, key="faq")
        self.assertEqual([c["props"]["expanded"]
                          for c in widget.to_dict()["children"]],
                         [True, False])
        index.value = 1
        self.assertEqual([c["props"]["expanded"]
                          for c in widget.to_dict()["children"]],
                         [False, True])

    def test_accordion_reads_a_callable_too(self):
        current = {"i": 1}
        widget = ExpansionPanelList(self._panels(), accordion=True,
                                    open_index=lambda: current["i"])
        self.assertEqual([c["props"]["expanded"]
                          for c in widget.to_dict()["children"]],
                         [False, True])

    def test_on_change_reports_the_tapped_index(self):
        seen = []
        widget = ExpansionPanelList(self._panels(), accordion=True,
                                    open_index=0, on_change=seen.append)
        widget.to_dict()  # materialise the tiles
        tile = widget.children[1]
        self.assertIn("expand", tile.event_handlers)
        tile.event_handlers["expand"]({"expanded": True})
        self.assertEqual(seen, [{"index": 1, "expanded": True}])

    def test_no_on_change_means_no_handler_side_effects(self):
        widget = ExpansionPanelList(self._panels())
        widget.to_dict()
        # Firing the tile's event must not raise when nobody is listening.
        widget.children[0].event_handlers["expand"]({"expanded": True})

    def test_tile_keys_are_stable_across_rebuilds(self):
        index = State(0)
        widget = ExpansionPanelList(self._panels(), accordion=True,
                                    open_index=index, key="faq")
        before = [c["key"] for c in widget.to_dict()["children"]]
        index.value = 1
        after = [c["key"] for c in widget.to_dict()["children"]]
        self.assertEqual(before, after)

    def test_add_appends_a_panel(self):
        widget = ExpansionPanelList(self._panels())
        widget.add(ExpansionPanel("Warranty", children=[Text("2 years")]))
        self.assertEqual(len(widget.to_dict()["children"]), 3)

    def test_an_accordion_renders_and_updates_end_to_end(self):
        # The open panel is app state, so it must outlive the build function
        # (a State declared inside main() is recreated on every rebuild).
        index = State(0)

        def main(page):
            panels = [
                ExpansionPanel("Shipping", children=[Text("3-5 days")]),
                ExpansionPanel("Returns", children=[Text("30 days")]),
            ]

            def choose(event):
                index.value = event["index"]
                page.update()

            page.add(ExpansionPanelList(panels, accordion=True,
                                        open_index=index, on_change=choose,
                                        key="faq"))

        with AppTester(main) as app:
            self.assertTrue(app.prop("faq.panel0", "expanded"))
            self.assertFalse(app.prop("faq.panel1", "expanded"))

            # The native header dispatches "expand"; the app owns the state.
            app.device.send_event("expand", "faq.panel1", {"expanded": True})
            app.settle()

            self.assertFalse(app.prop("faq.panel0", "expanded"))
            self.assertTrue(app.prop("faq.panel1", "expanded"))


if __name__ == "__main__":
    unittest.main()
