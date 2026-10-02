"""v1.5 — fully customisable bottom navigation and tabs."""

import unittest

from pydrud import (
    BottomNavigationBar, Icons, MediaQuery, NavItem, NavigationBar, Scaffold,
    Tab, TabBar, Tabs, Text,
)
from pydrud.widgets.base import Widget


def props(widget: Widget) -> dict:
    return widget.to_dict()["props"]


class TestBottomNavigationBar(unittest.TestCase):
    def setUp(self):
        MediaQuery.reset()

    def items(self):
        return [NavItem("Home", icon=Icons.HOME),
                NavItem("Cart", icon=Icons.SETTINGS, badge=3)]

    def test_alias_matches_flutter_naming(self):
        self.assertIs(NavigationBar, BottomNavigationBar)

    def test_defaults_are_sane(self):
        p = props(BottomNavigationBar(self.items()))
        self.assertEqual(p["selected"], 0)
        self.assertEqual(p["indicator"], "pill")
        self.assertEqual(p["labelBehavior"], "always")
        self.assertTrue(p["animate"])
        self.assertTrue(p["safeArea"])
        self.assertNotIn("native", p)

    def test_every_knob_is_serialised(self):
        bar = BottomNavigationBar(
            self.items(),
            selected=1,
            height=68, bg="#FFFFFFFF", elevation=12, radius=24,
            floating=True, margin=10,
            border_color="#14000000", border_width=1,
            shadow_color="#22000000", top_divider=True,
            divider_color="#11000000", item_padding=8, icon_label_gap=4,
            indicator="circle", indicator_color="#1A6366F1",
            indicator_width=48, indicator_height=48, indicator_radius=999,
            selected_color="#FF6366F1", unselected_color="#FF9CA3AF",
            icon_size=22, selected_icon_size=26,
            label_behavior="selected", label_size=11, selected_label_size=12,
            bold_selected=False, max_label_lines=2,
            badge_color="#FFEF4444", badge_text_color="#FFFFFFFF",
            type="shifting", ripple=False, ripple_color="#1A000000",
            animate=False, duration=120, haptic=True, native=True,
        )
        p = props(bar)
        self.assertEqual(p["height"], 68)
        self.assertEqual(p["radius"], 24)
        self.assertTrue(p["floating"])
        self.assertEqual(p["margin"], 10)
        self.assertEqual(p["indicator"], "circle")
        self.assertEqual(p["indicatorWidth"], 48)
        self.assertEqual(p["labelBehavior"], "selected")
        self.assertEqual(p["maxLabelLines"], 2)
        self.assertEqual(p["type"], "shifting")
        self.assertFalse(p["ripple"])
        self.assertFalse(p["animate"])
        self.assertEqual(p["duration"], 120)
        self.assertTrue(p["haptic"])
        self.assertTrue(p["native"])
        self.assertFalse(p["boldSelected"])

    def test_item_level_overrides(self):
        bar = BottomNavigationBar([
            NavItem("Home", icon=Icons.HOME, active_icon=Icons.SETTINGS,
                    color="#FF111111", unselected_color="#FF999999",
                    badge="dot", badge_color="#FFEF4444", tooltip="Go home",
                    route="/", bg="#FFF5F5F5"),
        ])
        item = props(bar)["items"][0]
        self.assertEqual(item["activeIcon"], Icons.SETTINGS)
        self.assertEqual(item["color"], "#FF111111")
        self.assertEqual(item["badge"], "dot")
        self.assertEqual(item["badgeColor"], "#FFEF4444")
        self.assertEqual(item["tooltip"], "Go home")
        self.assertEqual(item["route"], "/")

    def test_invalid_values_are_rejected(self):
        with self.assertRaises(ValueError):
            BottomNavigationBar(self.items(), indicator="sparkles")
        with self.assertRaises(ValueError):
            BottomNavigationBar(self.items(), label_behavior="sometimes")
        with self.assertRaises(ValueError):
            BottomNavigationBar(self.items(), type="floaty")

    def test_show_labels_false_implies_never(self):
        self.assertEqual(
            props(BottomNavigationBar(self.items(), show_labels=False))["labelBehavior"],
            "never")

    def test_selection_helpers(self):
        bar = BottomNavigationBar([
            NavItem("Home", icon=Icons.HOME, route="/"),
            NavItem("Settings", icon=Icons.SETTINGS, route="/settings"),
        ])
        self.assertEqual(bar.select(1).selected, 1)
        self.assertEqual(bar.current.label, "Settings")
        self.assertEqual(bar.select_route("/").selected, 0)
        self.assertEqual(bar.select(99).selected, 1)      # clamped
        self.assertEqual(bar.badge(0, 7).items[0].badge, 7)

    def test_layout_hints_for_the_renderer(self):
        bar = BottomNavigationBar(self.items(), height=72)
        self.assertEqual(bar.style["width"], "match")
        self.assertEqual(bar.style["height"], 72)
        # The bar draws its own gesture inset.
        self.assertFalse(bar.style["safeAreaBottom"])

    def test_effective_height_includes_floating_margin(self):
        self.assertEqual(
            BottomNavigationBar(self.items(), height=60, floating=True,
                                margin=10).effective_height, 80)

    def test_scaffold_lifts_the_fab_above_a_tall_bar(self):
        from pydrud import FloatingActionButton

        fab = FloatingActionButton("+", key="fab")
        Scaffold(
            key="s",
            body=Text("x"),
            bottom_navigation=BottomNavigationBar(self.items(), height=80),
            floating_action_button=fab,
        ).to_dict()
        self.assertEqual(fab.style["bottom"], 24 + 80)


class TestTabs(unittest.TestCase):
    def tabs(self):
        return [Tab("One", content=Text("1")), Tab("Two", content=Text("2"))]

    def test_tabbar_alias(self):
        self.assertIs(TabBar, Tabs)

    def test_defaults(self):
        p = props(Tabs(self.tabs()))
        self.assertEqual(p["mode"], "fixed")
        self.assertEqual(p["indicator"], "line")
        self.assertEqual(p["indicatorSize"], "label")
        self.assertEqual(p["align"], "fill")

    def test_full_customisation(self):
        bar = Tabs(
            self.tabs(), selected=1, mode="scrollable",
            indicator="pill", indicator_color="#FF6366F1",
            indicator_height=32, indicator_radius=999, indicator_size="tab",
            label_color="#FF111827", unselected_label_color="#FF6B7280",
            label_size=15, selected_label_size=16, bold_selected=False,
            uppercase=True, show_labels=True,
            icon_size=18, icon_position="start", icon_color="#FF9CA3AF",
            selected_icon_color="#FF6366F1",
            bg="#FFFFFFFF", elevation=2, radius=16, tab_height=56,
            tab_min_width=120, padding=16, align="center",
            divider=True, divider_color="#11000000",
            ripple=False, ripple_color="#1A6366F1",
            animate=False, duration=100,
        )
        p = props(bar)
        self.assertEqual(p["selected"], 1)
        self.assertEqual(p["mode"], "scrollable")
        self.assertTrue(p["scrollable"])
        self.assertEqual(p["indicator"], "pill")
        self.assertEqual(p["indicatorSize"], "tab")
        self.assertEqual(p["iconPosition"], "start")
        self.assertEqual(p["tabHeight"], 56)
        self.assertEqual(p["align"], "center")
        self.assertTrue(p["divider"])
        self.assertTrue(p["uppercase"])
        self.assertFalse(p["ripple"])
        self.assertFalse(p["animate"])

    def test_invalid_values_rejected(self):
        for kwargs in ({"mode": "springy"}, {"indicator": "wave"},
                       {"indicator_size": "huge"}, {"icon_position": "under"},
                       {"align": "justify"}):
            with self.assertRaises(ValueError):
                Tabs(self.tabs(), **kwargs)

    def test_only_the_selected_body_is_serialised(self):
        bar = Tabs(self.tabs(), selected=1, key="t")
        data = bar.to_dict()
        self.assertEqual(len(data["children"]), 1)
        self.assertEqual(data["children"][0]["props"]["value"], "2")
        bar.select(0)
        self.assertEqual(bar.to_dict()["children"][0]["props"]["value"], "1")

    def test_per_tab_styling(self):
        tab = Tab("Inbox", icon=Icons.HOME, badge=12, color="#FFEF4444",
                  badge_color="#FF111111", tooltip="Inbox")
        p = props(Tabs([tab]))["tabs"][0]
        self.assertEqual(p["badge"], "12")
        self.assertEqual(p["color"], "#FFEF4444")
        self.assertEqual(p["badgeColor"], "#FF111111")
        self.assertEqual(p["tooltip"], "Inbox")


if __name__ == "__main__":
    unittest.main()


class TestAdaptiveScaffold(unittest.TestCase):
    """``Scaffold(adaptive=True)`` reshapes itself for the window."""

    def setUp(self):
        MediaQuery.reset()

    tearDown = setUp

    def build(self, **kwargs):
        return Scaffold(
            key="s",
            body=Text("x"),
            bottom_navigation=BottomNavigationBar(
                [NavItem("Home", icon=Icons.HOME),
                 NavItem("Settings", icon=Icons.SETTINGS)],
                key="nav"),
            **kwargs,
        )

    def types(self, scaffold):
        column = scaffold.to_dict()["children"][0]["children"]
        return [child["type"] for child in column]

    def test_phone_keeps_the_bottom_bar(self):
        MediaQuery.update(width=360, height=800, density=3.0)
        self.assertIn("BottomNavigationBar", self.types(self.build(adaptive=True)))

    def test_tablet_moves_destinations_into_a_rail(self):
        MediaQuery.update(width=900, height=1280, density=2.0)
        types = self.types(self.build(adaptive=True))
        self.assertNotIn("BottomNavigationBar", types)
        self.assertIn("Row", types)

    def test_adaptive_is_opt_in(self):
        MediaQuery.update(width=900, height=1280, density=2.0)
        self.assertIn("BottomNavigationBar", self.types(self.build()))

    def test_content_max_width_centres_the_body(self):
        scaffold = self.build(content_max_width=640)
        body = [c for c in scaffold.to_dict()["children"][0]["children"]
                if c["key"] == "s._body"][0]
        self.assertEqual(body["style"]["maxWidth"], 640)
        self.assertEqual(body["style"]["alignment"], "topCenter")
