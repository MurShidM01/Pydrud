"""``pydrud.components`` — higher-level widgets with no native code.

PYDRUD §15.3 asked for a widget catalogue that can grow in pure Python.
These composites are built entirely from the primitives, so they must
serialise, key and diff like any built-in, and the catalogue must be
reachable from the top-level package.
"""

from __future__ import annotations

import unittest

from pydrud import Button, Icon, Text, Widget
from pydrud.components import (
    EmptyPlaceholder,
    FormRow,
    GlassPanel,
    InfoRow,
    KeyValueRow,
    PillButton,
    ProgressRow,
    SectionLabel,
    StatBlock,
    StatRow,
    Toolbar,
)
from pydrud.testing import AppTester
from pydrud.widgets.theme import Colors, Spacing, Theme


def _texts(node) -> list:
    """Every visible label in a serialised subtree, in document order."""
    out: list = []
    stack = [node]
    while stack:
        current = stack.pop()
        if not isinstance(current, dict):
            continue
        props = current.get("props") or {}
        for field in ("value", "text", "label"):
            if field in props:
                out.append(props[field])
                break
        for child in reversed(current.get("children", ()) or ()):
            stack.append(child)
    return out


class TestCatalogueShape(unittest.TestCase):
    """Every composite is a real widget that serialises to a known root."""

    CASES = (
        (SectionLabel("Recent"), "Row"),
        (StatBlock("Steps", "8,412"), "Column"),
        (StatRow([StatBlock("a", "1")]), "Row"),
        (Toolbar(title="Inbox"), "Row"),
        (GlassPanel(child=Text("x")), "Container"),
        (KeyValueRow("CPU", "42%"), "Row"),
        (InfoRow("settings", "Settings"), "Row"),
        (FormRow("Email", Text("")), "Column"),
        (ProgressRow("Load", 0.4), "Column"),
        (PillButton("Go"), "Button"),
        (EmptyPlaceholder(), "Card"),
    )

    def test_each_composite_is_a_widget(self):
        for widget, _ in self.CASES:
            with self.subTest(widget=type(widget).__name__):
                self.assertIsInstance(widget, Widget)

    def test_each_composite_serialises_to_the_expected_root(self):
        for widget, root in self.CASES:
            with self.subTest(widget=type(widget).__name__):
                self.assertEqual(widget.to_dict()["type"], root)


class TestSectionLabel(unittest.TestCase):

    def test_uppercases_by_default(self):
        self.assertIn("RECENT ACTIVITY", _texts(SectionLabel("Recent activity").to_dict()))

    def test_can_keep_the_original_case(self):
        self.assertIn("Recent activity",
                      _texts(SectionLabel("Recent activity", uppercase=False).to_dict()))

    def test_renders_an_optional_trailing_action(self):
        data = SectionLabel("Inbox", action=Button("See all")).to_dict()
        self.assertIn("See all", _texts(data))


class TestStatBlock(unittest.TestCase):

    def test_shows_the_value_and_label(self):
        texts = _texts(StatBlock("Steps", "8,412").to_dict())
        self.assertIn("8,412", texts)
        self.assertIn("Steps", texts)

    def test_optional_icon_is_rendered(self):
        with_icon = StatBlock("Steps", "8,412", icon="trending_up").to_dict()
        self.assertTrue(_has_type(with_icon, "Icon"))
        without = StatBlock("Steps", "8,412").to_dict()
        self.assertFalse(_has_type(without, "Icon"))

    def test_stat_row_weights_every_block(self):
        data = StatRow([StatBlock("a", "1"), StatBlock("b", "2")]).to_dict()
        self.assertEqual([c.get("expand") for c in data["children"]], [1, 1])

    def test_stat_row_leaves_an_explicit_weight_alone(self):
        block = StatBlock("a", "1", expand=2)
        data = StatRow([block]).to_dict()
        self.assertEqual(data["children"][0].get("expand"), 2)


class TestToolbar(unittest.TestCase):

    def test_orders_leading_title_actions(self):
        data = Toolbar(title="Inbox", leading=Icon("menu"),
                       actions=[Icon("search")]).to_dict()
        types = [c["type"] for c in data["children"]]
        self.assertEqual(types, ["Icon", "Text", "Icon"])

    def test_title_only(self):
        data = Toolbar(title="Inbox").to_dict()
        self.assertEqual(_texts(data), ["Inbox"])


class TestGlassPanel(unittest.TestCase):

    def test_applies_the_opacity_to_the_fill(self):
        style = GlassPanel(child=Text("x"), opacity=0.5).to_dict()["style"]
        self.assertEqual(style["bg"], Colors.with_opacity(Theme.surface, 0.5))

    def test_defaults_to_the_card_radius(self):
        from pydrud import Tokens
        style = GlassPanel(child=Text("x")).to_dict()["style"]
        self.assertEqual(style["borderRadius"], Tokens.radius_card)

    def test_accepts_an_explicit_radius_and_padding(self):
        style = GlassPanel(child=Text("x"), border_radius=8,
                           padding=Spacing.SM).to_dict()["style"]
        self.assertEqual(style["borderRadius"], 8)


class TestTextRows(unittest.TestCase):

    def test_key_value_row_shows_both_sides(self):
        self.assertEqual(_texts(KeyValueRow("CPU", "42%").to_dict()),
                         ["CPU", "42%"])

    def test_key_value_row_can_be_monospaced(self):
        data = KeyValueRow("CPU", "42%", mono=True).to_dict()
        families = [c["style"]["font"].get("family")
                    for c in data["children"]]
        self.assertIn("monospace", families)

    def test_info_row_shows_the_subtitle_when_given(self):
        with_sub = _texts(InfoRow("settings", "Settings",
                                  subtitle="Manage").to_dict())
        self.assertEqual(with_sub, ["Settings", "Manage"])
        without = _texts(InfoRow("settings", "Settings").to_dict())
        self.assertEqual(without, ["Settings"])

    def test_info_row_can_carry_a_trailing_widget(self):
        data = InfoRow("settings", "Settings", trailing=Icon("chevron_right"))
        self.assertTrue(_has_type(data.to_dict(), "Icon", count=2))


class TestFormRow(unittest.TestCase):

    def test_helper_line_is_optional(self):
        control = Icon("mail")
        self.assertEqual(_texts(FormRow("Email", control).to_dict()), ["Email"])
        with_helper = _texts(FormRow("Email", control,
                                     helper="Private").to_dict())
        self.assertEqual(with_helper, ["Email", "Private"])


class TestProgressRow(unittest.TestCase):

    def test_renders_the_percentage(self):
        self.assertIn("42%", _texts(ProgressRow("Load", 0.42).to_dict()))

    def test_clamps_out_of_range_values(self):
        self.assertIn("100%", _texts(ProgressRow("Load", 1.8).to_dict()))
        self.assertIn("0%", _texts(ProgressRow("Load", -3).to_dict()))


class TestPillButton(unittest.TestCase):

    def test_is_a_tonal_pill_by_default(self):
        data = PillButton("Go").to_dict()
        self.assertEqual(data["props"]["text"], "Go")
        self.assertTrue(data["style"].get("pill"))
        self.assertEqual(data["style"].get("variant"), "tonal")

    def test_can_carry_a_leading_icon(self):
        style = PillButton("Go", icon="add").to_dict()["style"]
        self.assertEqual(style.get("icon"), "add")


class TestEmptyPlaceholder(unittest.TestCase):

    def test_shows_title_and_message(self):
        texts = _texts(EmptyPlaceholder("No results", message="Try again").to_dict())
        self.assertIn("No results", texts)
        self.assertIn("Try again", texts)

    def test_action_renders_a_button(self):
        data = EmptyPlaceholder(action="Retry").to_dict()
        self.assertTrue(_has_type(data, "Button"))
        self.assertIn("Retry", _texts(data))


class TestTopLevelExport(unittest.TestCase):

    def test_components_are_reachable_from_the_package(self):
        import pydrud

        self.assertIs(pydrud.components.StatBlock, StatBlock)
        self.assertIn("components", pydrud.__all__)


class TestCompositeRendering(unittest.TestCase):
    """A screen full of composites must boot, diff and update like any other."""

    def test_a_composite_screen_renders(self):
        def main(page):
            page.add(
                SectionLabel("Today"),
                StatRow([
                    StatBlock("Steps", "8,412", icon="trending_up"),
                    StatBlock("Goal", "78%", icon="verified"),
                ], key="stats"),
                InfoRow("settings", "Settings", subtitle="Manage"),
            )

        with AppTester(main) as app:
            self.assertIn("8,412", app.texts)
            self.assertIn("TODAY", app.texts)

    def test_composites_diff_in_place(self):
        def main(page):
            block = StatBlock("Steps", "0", key="steps")
            page.add(block,
                     Button("Tick", key="tick",
                            on_click=lambda e: page.update(
                                StatBlock("Steps", "1", key="steps"))))

        with AppTester(main) as app:
            app.tap("tick")
            self.assertIn("1", app.texts)


def _has_type(node, type_name: str, count: int = 1) -> bool:
    found = 0
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            if current.get("type") == type_name:
                found += 1
            stack.extend(current.get("children", ()) or ())
    return found >= count


if __name__ == "__main__":
    unittest.main()
