"""
The Material Symbols variable axes (GAP #4).

Material Symbols is a variable font: weight, fill, grade and optical size are
its four axes, and an icon set without them draws one glyph at one weight.
These tests pin all three layers of the fix — the widget, the stylesheet keys
and the generated Java — because the axes only work end to end.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from pydrud import Icon
from pydrud.core.styles.manager import parse_pss
from pydrud.core.styles.resolver import resolve_styles
from pydrud.core.styles.schema import KEY_KIND, VALID_STYLE_KEYS, _KEBAB_CANONICAL
from pydrud.widgets.theme.icons import ICON_AXES, check_icon_axes

TEMPLATES = (Path(__file__).resolve().parent.parent / "pydrud" / "android"
             / "templates" / "android")

#: The axes, the range the font declares for each, and an out-of-range value.
AXES = {
    "weight": (100, 700, 900),
    "grade": (-50, 200, -500),
    "optical": (20, 48, 4),
}


def _read(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


class TestWidgetAxes(unittest.TestCase):
    """``Icon(...)`` carries the axes, and only the ones it was given."""

    def test_an_untouched_icon_serialises_just_its_name(self):
        self.assertEqual({"name": "star"}, Icon("star")._serialise_props())

    def test_each_axis_travels_on_its_own(self):
        for axis, (_, _, _) in AXES.items():
            with self.subTest(axis=axis):
                icon = Icon("star", **{axis: 200 if axis != "grade" else 100})
                props = icon._serialise_props()
                self.assertIn(axis, props)
                self.assertEqual(set(props), {"name", axis})

    def test_fill_is_a_boolean_axis(self):
        self.assertEqual({"name": "star", "fill": True},
                         Icon("star", fill=True)._serialise_props())
        self.assertEqual({"name": "star", "fill": False},
                         Icon("star", fill=False)._serialise_props())

    def test_svg_icons_take_the_axes_too(self):
        icon = Icon.svg("M12,2 L22,12 L12,22 L2,12 Z", weight=300, fill=False)
        props = icon._serialise_props()
        self.assertIn("path", props)
        self.assertEqual({"path", "weight", "fill"}, set(props))

    def test_a_mistyped_axis_is_an_error_not_a_silent_default(self):
        for bad in ("bold", "700", object()):
            with self.subTest(bad=bad):
                with self.assertRaises(TypeError):
                    Icon("star", weight=bad)
        with self.assertRaises(TypeError):
            Icon("star", grade="heavy")

    def test_booleans_are_not_weights(self):
        # ``isinstance(True, int)`` is True in Python; an axis still is not.
        with self.assertRaises(TypeError):
            check_icon_axes(weight=True)


class TestAxisRanges(unittest.TestCase):
    """The font declares a range per axis; outside it, clamp to the edge."""

    def test_ranges_match_the_font(self):
        self.assertEqual({"weight": (100, 700), "grade": (-50, 200),
                          "optical": (20, 48)}, ICON_AXES)

    def test_out_of_range_values_clamp(self):
        for axis, (low, high, outside) in AXES.items():
            with self.subTest(axis=axis, edge="low"):
                self.assertEqual(low, check_icon_axes(**{axis: -9999})[axis])
            with self.subTest(axis=axis, edge="high"):
                self.assertEqual(high, check_icon_axes(**{axis: 99999})[axis])
            with self.subTest(axis=axis, outside=outside):
                clamped = check_icon_axes(**{axis: outside})[axis]
                self.assertTrue(low <= clamped <= high, clamped)

    def test_an_unset_axis_is_not_a_value(self):
        self.assertEqual({"weight": None, "grade": None, "optical": None},
                         check_icon_axes())


class TestStylesheetAxes(unittest.TestCase):
    """``.icon { icon-weight: 600 }`` reaches the glyph."""

    def test_the_four_keys_are_registered(self):
        for key in ("iconWeight", "iconGrade", "iconOptical", "iconFill"):
            with self.subTest(key=key):
                self.assertIn(key, VALID_STYLE_KEYS)
                self.assertIn(key, KEY_KIND)

    def test_kebab_spellings_resolve_to_the_canonical_key(self):
        expected = {"icon-weight": "iconWeight", "icon-grade": "iconGrade",
                    "icon-optical": "iconOptical", "icon-fill": "iconFill"}
        for kebab, canonical in expected.items():
            with self.subTest(key=kebab):
                self.assertEqual(canonical, _KEBAB_CANONICAL[kebab])

    def test_a_stylesheet_can_set_them(self):
        sheet = parse_pss("Icon { icon-weight: 700; icon-fill: true; }")
        resolved, _ = resolve_styles(sheet, [Icon("star")])
        body = next(iter(resolved.values()))
        self.assertEqual(700, body["iconWeight"])
        self.assertIs(True, body["iconFill"])

    def test_a_class_rule_reaches_the_icons_that_carry_the_class(self):
        sheet = parse_pss(".nav-icon { icon-weight: 600; }")
        plain = Icon("home")
        nav = Icon("home", class_=["nav-icon"])
        resolved, _ = resolve_styles(sheet, [plain, nav])
        self.assertEqual(1, len(resolved), resolved)
        self.assertEqual(600, next(iter(resolved.values()))["iconWeight"])

    def test_an_out_of_range_stylesheet_value_still_reaches_the_renderer(self):
        # The renderer clamps; the parser must not reject the declaration.
        sheet = parse_pss("Icon { icon-optical: 96; }")
        resolved, _ = resolve_styles(sheet, [Icon("star")])
        self.assertEqual(96, next(iter(resolved.values()))["iconOptical"])


class TestJavaRenderer(unittest.TestCase):
    """The generated renderer reads the axes and applies them."""

    def setUp(self):
        self.icons = _read("PydrudIcons.java.j2")
        self.builtins = _read("BuiltinViews.java.j2")

    def test_the_drawable_carries_all_four_axes(self):
        for declaration in ("private final int weight;",
                            "private final boolean filled;",
                            "private final int grade;",
                            "private final float optical;"):
            with self.subTest(field=declaration):
                self.assertIn(declaration, self.icons)

    def test_the_stroke_model_names_its_constants(self):
        for constant in ("OUTLINE_STROKE", "WEIGHT_STROKE",
                         "GRADE_AS_WEIGHT", "OPTICAL_REFERENCE"):
            with self.subTest(constant=constant):
                self.assertIn(constant, self.icons)

    def test_outline_is_a_stroke_and_fill_is_a_fill(self):
        self.assertRegex(self.icons, r"filled \? 0f : OUTLINE_STROKE")

    def test_grade_folds_into_weight(self):
        # The spec's equivalence: one grade step is 1.5 weight steps.
        self.assertRegex(self.icons, r"grade\s*\*\s*GRADE_AS_WEIGHT")

    def test_the_factory_resolves_axes_with_the_stylesheet_winning(self):
        self.assertIn("static JSONObject iconAxes(", self.builtins)
        for prop in ("weight", "grade", "optical", "fill"):
            with self.subTest(prop=prop):
                self.assertRegex(self.builtins, rf'props\.has\("{prop}"\)')
        for key in ("iconWeight", "iconGrade", "iconOptical", "iconFill"):
            with self.subTest(key=key):
                self.assertRegex(self.builtins, rf'style\.has\("{key}"\)')
        # A style key overwrites the prop value it shadows.
        self.assertRegex(
            self.builtins,
            r'axes\.has\("iconWeight"\)\)\s*axes\.put\("weight"')

    def test_both_icon_kinds_route_through_the_axes(self):
        self.assertIn("PydrudIcons.drawable(name, tint, px, axes)",
                      self.builtins)
        self.assertIn("PydrudIcons.drawablePath(path, tint, px, axes)",
                      self.builtins)

    def test_optical_reference_is_the_size_the_paths_were_drawn_at(self):
        # The bundled outlines are the 24px designs, so 24 is the reference.
        self.assertRegex(self.icons, r"OPTICAL_REFERENCE\s*=\s*24f")
        self.assertRegex(self.icons, r"OPTICAL_REFERENCE\s*\n?\s*/\s*Math\.max")


if __name__ == "__main__":
    unittest.main()
