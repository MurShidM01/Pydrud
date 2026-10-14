"""GAP #2 — the motion tokens are the spec's curves, and something moves.

Material 3 motion is a duration *step* plus an easing *curve*, and both sets
are published as tokens. Two things were wrong with them:

* the easing tokens held the names of platform interpolators (`ease_in_out`,
  `overshoot`) rather than the spec's cubic-béziers, so the standard curve —
  which starts fast and eases out steeply — could not be expressed at all;
* nothing read any of them beyond `duration_normal`. A stylesheet could write
  ``transition: background $duration_medium_2`` and the shorthand parser would
  split the substituted curve on its spaces and hand the renderer
  ``cubic-bezier(0.2,`` — a curve it ignored — while the duration went
  missing entirely.

The contract now: a curve is a CSS cubic-bézier wherever it can be named, the
M3 names (`standard`, `emphasized_decelerate`, …) resolve through the tokens
on both the Python and the renderer side, and the framework's own animations
read the same tokens instead of carrying millisecond literals.
"""

from __future__ import annotations

import pathlib
import unittest

import jinja2

from pydrud.core.controllers import CURVES as PY_CURVES, CubicBezier, curve
from pydrud.core.styles.manager import parse_pss
from pydrud.core.styles.resolver import resolve_styles
from pydrud.widgets import Container
from pydrud.widgets.animation import CURVES, Animation
from pydrud.widgets.theme import Theme
from pydrud.widgets.tokens import Tokens

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "pydrud" / "android" / "templates" / "android"

RENDER_CONTEXT = {
    "package": "com.example.app", "android_package": "com.example.app",
    "app_id": "com.example.app", "app_name": "Demo", "project_name": "Demo",
    "label": "Demo", "min_sdk": 24, "target_sdk": 34, "version_name": "2.1.5",
    "version_code": 21, "runtime": "chaquopy", "bridge_port": 8765,
    "python_version": "3.11", "pydrud_import": "pydrud",
    "deep_link_scheme": "demo", "theme_mode": "light", "permissions": [],
    "uses_cleartext": False, "splash": False, "icon": None, "entry_point": "app.py",
    "include_icons": True, "has_camera": False, "has_firebase": False,
}

#: The Material 3 motion spec, easing table.
SPEC_EASINGS = {
    "easing_standard": (0.2, 0.0, 0.0, 1.0),
    "easing_standard_decelerate": (0.0, 0.0, 0.0, 1.0),
    "easing_standard_accelerate": (0.3, 0.0, 1.0, 1.0),
    "easing_emphasized": (0.2, 0.0, 0.0, 1.0),
    "easing_emphasized_decelerate": (0.05, 0.7, 0.1, 1.0),
    "easing_emphasized_accelerate": (0.3, 0.0, 0.8, 0.15),
    "easing_linear": (0.0, 0.0, 1.0, 1.0),
}

#: ...and its duration ladder, in milliseconds.
SPEC_DURATIONS = {
    "short": (50, 100, 150, 200),
    "medium": (250, 300, 350, 400),
    "long": (450, 500, 550, 600),
    "extra_long": (700, 800, 900, 1000),
}


def _curve_text(points) -> str:
    """How the spec prints a curve: `0.2, 0, 0, 1`."""
    return ", ".join(f"{point:g}" for point in points)


def _render(name: str) -> str:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES)), keep_trailing_newline=True
    )
    return env.get_template(name).render(**RENDER_CONTEXT)


def _body(text: str, signature: str) -> str:
    start = text.index(signature)
    depth, index = 0, text.index("{", start)
    end = index
    while end < len(text):
        if text[end] == "{":
            depth += 1
        elif text[end] == "}":
            depth -= 1
            if depth == 0:
                break
        end += 1
    return text[start:end]


class TestTokensAreTheSpecsCurves(unittest.TestCase):
    def test_every_easing_token_is_its_spec_cubic_bezier(self):
        for token, points in SPEC_EASINGS.items():
            with self.subTest(token=token):
                raw = getattr(Tokens, token)
                self.assertIn("cubic-bezier(", raw)
                parsed = CubicBezier.parse(raw)
                self.assertEqual(
                    (parsed.x1, parsed.y1, parsed.x2, parsed.y2), points)

    def test_the_duration_ladder_is_the_spec_table(self):
        for name, values in SPEC_DURATIONS.items():
            for step, expected in enumerate(values, start=1):
                token = f"duration_{name}_{step}"
                with self.subTest(token=token):
                    self.assertEqual(getattr(Tokens, token), expected)

    def test_a_curve_can_still_be_named_the_old_way(self):
        """The platform names are approximations, not the spec's curves."""
        names = ("linear", "ease_in", "ease_out", "ease_in_out", "overshoot",
                 "accelerate", "decelerate")
        for name in names:
            with self.subTest(curve=name):
                self.assertIn(name, CURVES)
                self.assertAlmostEqual(curve(name)(0.0), 0.0, places=6)
                self.assertAlmostEqual(curve(name)(1.0), 1.0, places=6)

    def test_the_spec_curves_differ_from_the_platform_keywords(self):
        """Otherwise naming the spec curve would be pointless."""
        self.assertGreater(abs(curve("standard")(0.25) - curve("ease_in_out")(0.25)),
                           0.2)


class TestCubicBezierEvaluatesLikeTheDevice(unittest.TestCase):
    def test_endpoints_are_exact(self):
        ease = CubicBezier.parse(Tokens.easing_standard)
        self.assertEqual(ease(0.0), 0.0)
        self.assertEqual(ease(1.0), 1.0)

    def test_the_standard_curve_matches_the_solved_value(self):
        # cubic-bezier(0.2, 0, 0, 1) at x = 0.5 is 0.878 to three places —
        # the value the platform's PathInterpolator lands on.
        ease = curve("cubic-bezier(0.2, 0, 0, 1)")
        self.assertAlmostEqual(ease(0.5), 0.878, places=3)

    def test_linear_is_the_identity(self):
        ease = curve("cubic-bezier(0, 0, 1, 1)")
        for t in (0.0, 0.1, 0.37, 0.5, 0.9, 1.0):
            with self.subTest(t=t):
                self.assertAlmostEqual(ease(t), t, places=5)

    def test_a_control_point_outside_the_unit_square_is_rejected(self):
        with self.assertRaises(ValueError):
            CubicBezier.parse("cubic-bezier(1.4, 0, 0, 1)")

    def test_the_spec_names_evaluate_through_the_tokens(self):
        """Retuning the token must move the curve, not just its string."""
        self.addCleanup(Tokens.reset)
        before = curve("standard")(0.5)
        Tokens.update(easing_standard="cubic-bezier(0, 0, 1, 1)")
        self.assertNotAlmostEqual(curve("standard")(0.5), before, places=3)
        self.assertAlmostEqual(curve("standard")(0.5), 0.5, places=5)

    def test_the_m3_names_are_in_both_tables(self):
        for name in ("standard", "standard_decelerate", "standard_accelerate",
                     "emphasized", "emphasized_decelerate",
                     "emphasized_accelerate"):
            with self.subTest(name=name):
                self.assertIn(name, PY_CURVES)
                self.assertIn(name, CURVES)


class TestWidgetAnimationsUseTheTokens(unittest.TestCase):
    def test_the_default_duration_is_the_token(self):
        self.addCleanup(Tokens.reset)
        self.assertEqual(Animation().duration, int(Tokens.duration_normal))
        Tokens.update(duration_normal=444)
        self.assertEqual(Animation().duration, 444)

    def test_the_default_curve_is_the_spec_standard(self):
        self.assertEqual(Animation().curve, "standard")
        self.assertAlmostEqual(curve(Animation().curve)(0.25),
                               curve(Tokens.easing_standard)(0.25))

    def test_presets_are_named_curves(self):
        self.assertEqual(Animation.fast().curve, "standard_decelerate")
        self.assertEqual(Animation.slow().curve, "emphasized_decelerate")

    def test_an_unknown_curve_is_still_rejected(self):
        with self.assertRaises(ValueError):
            Animation(curve="wobble")


class TestTheShorthandsCarryTheTokens(unittest.TestCase):
    def _style(self, css: str, *widgets):
        sheet = parse_pss(css)
        styles, warnings = resolve_styles(sheet, list(widgets))
        self.assertEqual([], warnings, warnings)
        return styles

    def test_a_token_reference_resolves_to_a_whole_curve(self):
        """The curve contains spaces; the shorthand must not split it."""
        style = self._style(
            "#a { transition: background $duration_medium_2 $easing_emphasized; }",
            Container(key="a"))
        entry = style["a"]["transition"][0]
        self.assertEqual(entry["duration"], 300.0)
        self.assertEqual(entry["curve"], "cubic-bezier(0.2, 0, 0, 1)")

    def test_a_duration_token_arrives_with_its_unit(self):
        style = self._style(
            "#a { transition: background $duration_short_4 linear; }",
            Container(key="a"))
        self.assertEqual(style["a"]["transition"][0]["duration"], 200.0)

    def test_an_animation_takes_a_token_duration_and_curve(self):
        style = self._style(
            "#a { animation: pulse $duration_long_1 $easing_emphasized_decelerate infinite; }",
            Container(key="a"))
        spec = style["a"]["animation"]
        self.assertEqual(spec["duration"], 450.0)
        self.assertEqual(spec["curve"], "cubic-bezier(0.05, 0.7, 0.1, 1)")
        self.assertEqual(spec["iterations"], "infinite")

    def test_the_m3_names_can_be_written_directly(self):
        style = self._style(
            "#a { transition: border-radius medium-2 emphasized-decelerate; }",
            Container(key="a"))
        entry = style["a"]["transition"][0]
        self.assertEqual(entry["duration"], "medium_2")
        self.assertEqual(entry["curve"], "emphasized_decelerate")

    def test_a_css_time_and_keyword_still_work(self):
        style = self._style(
            "#a { transition: opacity 180ms ease-out; }", Container(key="a"))
        entry = style["a"]["transition"][0]
        self.assertEqual(entry["duration"], 180.0)
        self.assertEqual(entry["curve"], "ease_out")

    def test_the_theme_payload_carries_the_curves(self):
        tokens = Theme.payload()["tokens"]
        self.assertEqual(tokens["easing_standard"], "cubic-bezier(0.2, 0, 0, 1)")
        self.assertEqual(tokens["duration_medium_2"], 300)


class TestTheRendererResolvesTheTokens(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.theme = _render("PydrudTheme.java.j2")
        cls.styler = _render("ViewStyler.java.j2")
        cls.animator = _render("ViewAnimator.java.j2")

    def test_the_curve_defaults_are_the_spec_curves(self):
        for token, points in SPEC_EASINGS.items():
            field = "".join(part.capitalize() for part in token.split("_"))
            field = field[0].lower() + field[1:]
            with self.subTest(token=token):
                self.assertIn(
                    f'public static String {field} = '
                    f'"cubic-bezier({_curve_text(points)})";',
                    self.theme)

    def test_the_m3_names_resolve_through_the_tokens(self):
        body = _body(self.theme, "public static android.view.animation.Interpolator easing(")
        for field in ("easingStandard", "easingEmphasized",
                      "easingStandardDecelerate", "easingStandardAccelerate",
                      "easingEmphasizedDecelerate", "easingEmphasizedAccelerate"):
            with self.subTest(field=field):
                self.assertIn(field, body)
        # A raw CSS timing function is accepted too, which is what a
        # `$easing_*` reference substitutes to.
        self.assertIn('startsWith("cubic-bezier(")', self.theme)
        self.assertIn('startsWith("steps(")', self.theme)

    def test_durations_resolve_by_step_name_number_or_css_time(self):
        body = _body(self.theme, "public static long durationMs(Object value)")
        for case in ("short1", "medium2", "long4", "extralong4", "fast",
                     "normal", "slow"):
            with self.subTest(case=case):
                self.assertIn(f'case "{case}"', body)
        self.assertIn('key.endsWith("ms")', body)
        self.assertIn('key.endsWith("s")', body)
        self.assertIn("Double.parseDouble(key)", body)

    def test_the_styler_and_the_animator_go_through_the_resolver(self):
        self.assertIn("PydrudTheme.easing(curve)", self.styler)
        self.assertIn('optString("curve", "standard")', self.styler)
        self.assertEqual(3, self.animator.count("PydrudTheme.durationMs("))

    def test_the_framework_animates_with_the_tokens(self):
        """No millisecond literals left in the animations the theme drives."""
        press = _body(self.theme, "public static void pressFeedback(")
        self.assertIn('durationMs("short_2")', press)
        self.assertIn('durationMs("short_4")', press)
        self.assertIn('easing("standard_accelerate")', press)
        self.assertIn('easing("standard_decelerate")', press)

        layout = _body(self.theme, "public static void animateLayout(")
        self.assertIn('durationMs("short_4")', layout)
        self.assertNotIn("setDuration(180)", layout)

        enter = _body(self.theme, "public static void enter(")
        self.assertIn('durationMs("medium_2")', enter)
        self.assertIn('easing("emphasized_decelerate")', enter)
        self.assertNotIn("DecelerateInterpolator", enter)

        activity = _render("MainActivity.java.j2")
        drawer = _body(activity, "public void setDrawerOpen(")
        self.assertIn('durationMs("medium_2")', drawer)
        self.assertIn('easing("emphasized_accelerate")', drawer)

        for template in ("ImageLoader.java.j2", "GestureBinder.java.j2"):
            with self.subTest(template=template):
                text = _render(template)
                self.assertIn("PydrudTheme.durationMs(", text)

    def test_no_hardcoded_interpolator_classes_are_left_in_the_animator(self):
        for name in ("AccelerateDecelerateInterpolator", "OvershootInterpolator"):
            with self.subTest(interpolator=name):
                self.assertNotIn(name, self.animator)


class TestTheMotionTokensAreWired(unittest.TestCase):
    """The token-liveness rule, applied to motion specifically."""

    @classmethod
    def setUpClass(cls):
        cls.files = {path.name: path.read_text(encoding="utf-8")
                     for path in TEMPLATES.glob("*.java.j2")}

    def test_every_duration_field_is_read_by_the_resolver(self):
        body = _body(_render("PydrudTheme.java.j2"),
                     "public static long durationMs(Object value)")
        for name in ("Short1", "Short2", "Short3", "Short4", "Medium1",
                     "Medium2", "Medium3", "Medium4", "Long1", "Long2",
                     "Long3", "Long4", "ExtraLong1", "ExtraLong2",
                     "ExtraLong3", "ExtraLong4"):
            with self.subTest(field=name):
                self.assertIn(f"duration{name}", body)

    def test_the_easing_fields_are_null_checked_before_use(self):
        """A theme that sends no curve must not blank the animation."""
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(TEMPLATES)), keep_trailing_newline=True
        )
        theme = env.get_template("PydrudTheme.java.j2").render(**RENDER_CONTEXT)
        self.assertIn('easingStandard = t.optString("easing_standard", easingStandard);',
                      theme)
        # A null name means "the theme's default", never a crash.
        self.assertIn('name == null ? "" : name.trim()', theme)

    def test_no_motion_literal_is_left_in_the_drawer_path(self):
        activity = self.files["MainActivity.java.j2"]
        for literal in ("setDuration(220)", "setDuration(200)",
                        "setDuration(180)", "setDuration(250)"):
            with self.subTest(literal=literal):
                self.assertNotIn(literal, activity)


if __name__ == "__main__":
    unittest.main()
