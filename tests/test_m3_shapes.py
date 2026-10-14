"""
Material 3 shape morphing and springs (GAP #5).

Material's shapes are a parametric family, and a shape morph is the motion
between two members of it. Material's motion system has a second vocabulary
for exactly that job: springs, written as a damping ratio and a stiffness
rather than a curve and a duration.

These tests pin both halves — the Python evaluator and the generated Java —
plus the stylesheet keys that let a class retune a morph.
"""

from __future__ import annotations

import math
import unittest
from pathlib import Path

from pydrud import ShapeMorph, Shapes
from pydrud.core.controllers import CURVES, M3_SPRINGS, Spring, curve
from pydrud.core.styles.manager import parse_pss
from pydrud.core.styles.resolver import resolve_styles
from pydrud.core.styles.schema import KEY_KIND, VALID_STYLE_KEYS, _KEBAB_CANONICAL
from pydrud.widgets.shapes import DEFAULT_SPRING, SHAPES, SPRINGS
from pydrud.widgets.tokens import Tokens

TEMPLATES = (Path(__file__).resolve().parent.parent / "pydrud" / "android"
             / "templates" / "android")

#: The six springs Google publishes, as Microsoft's own attrs carry them:
#: damping, stiffness, and the shape of the step response.
SPEC_SPRINGS = {
    "spring_fast_spatial": (0.9, 1400, "under"),
    "spring_default_spatial": (0.9, 700, "under"),
    "spring_slow_spatial": (0.9, 300, "under"),
    "spring_fast_effects": (1.0, 3800, "critical"),
    "spring_default_effects": (1.0, 1600, "critical"),
    "spring_slow_effects": (1.0, 800, "critical"),
}


def _read(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


class TestSpringTokens(unittest.TestCase):
    """The six springs live in the token table, as ``damping, stiffness``."""

    def tearDown(self):
        Tokens.reset()

    def test_the_six_springs_are_published(self):
        self.assertEqual(set(SPEC_SPRINGS), set(M3_SPRINGS))

    def test_each_token_carries_the_spec_pair(self):
        for name, (damping, stiffness, _) in SPEC_SPRINGS.items():
            with self.subTest(spring=name):
                raw = getattr(Tokens, name)
                self.assertEqual([damping, stiffness],
                                 [float(p) for p in raw.split(",")])

    def test_spatial_springs_may_overshoot_and_effects_springs_may_not(self):
        for name in SPEC_SPRINGS:
            spring = Spring.parse(getattr(Tokens, name))
            peak = max(spring.at(ms) for ms in range(0, 2000, 5))
            with self.subTest(spring=name):
                if name.endswith("_spatial"):
                    self.assertGreater(peak, 1.0)     # it overshoots…
                    self.assertLess(peak, 1.1)        # …but stays material
                else:
                    self.assertLessEqual(peak, 1.0 + 1e-9)

    def test_a_retuned_token_reaches_the_curve(self):
        Tokens.update(spring_fast_spatial="1.0, 400")
        self.assertGreater(curve("spring_fast_spatial")(0.5), 0.9)
        # Critically damped now: no overshoot at all.
        spring = Spring.parse(Tokens.spring_fast_spatial)
        self.assertLessEqual(max(spring.at(ms) for ms in range(0, 2000, 5)), 1.0)


class TestSpringEvaluation(unittest.TestCase):
    """The analytic step response, matching a native ``TimeInterpolator``."""

    def test_it_starts_at_zero_and_ends_at_one(self):
        spring = Spring.parse(getattr(Tokens, "spring_default_spatial"))
        self.assertEqual(0.0, spring.at(0))
        # "Settled" is the tolerance the spring itself settles at: 0.1 %.
        self.assertAlmostEqual(1.0, spring.at(spring.settle_ms), delta=1e-3)

    def test_it_approaches_one_monotonically_after_the_overshoot(self):
        spring = Spring.parse(getattr(Tokens, "spring_default_spatial"))
        samples = [spring.at(ms) for ms in range(0, int(spring.settle_ms) + 1, 5)]
        self.assertAlmostEqual(1.0, samples[-1], delta=2e-3)
        self.assertLess(abs(samples[-1] - 1.0), abs(samples[0] - 1.0))

    def test_settle_time_is_where_it_comes_to_rest(self):
        spring = Spring.parse(getattr(Tokens, "spring_fast_spatial"))
        # 0.1 % of the travel — the tolerance Google's springs settle at.
        for ms in range(int(spring.settle_ms), int(spring.settle_ms) + 60, 5):
            with self.subTest(ms=ms):
                self.assertLess(abs(spring.at(ms) - 1.0), 0.001)

    def test_stiffer_springs_settle_sooner(self):
        slow = Spring.parse(getattr(Tokens, "spring_slow_spatial"))
        fast = Spring.parse(getattr(Tokens, "spring_fast_spatial"))
        self.assertLess(fast.settle_ms, slow.settle_ms)

    def test_the_call_form_is_progress_over_the_settle_time(self):
        spring = Spring.parse(getattr(Tokens, "spring_fast_spatial"))
        self.assertEqual(0.0, spring(0.0))
        self.assertEqual(1.0, spring(1.0))
        self.assertAlmostEqual(spring.at(spring.settle_ms / 2), spring(0.5),
                               places=9)

    def test_it_rejects_nonsense(self):
        with self.assertRaises(ValueError):
            Spring.parse("0.9")                     # one number is not a spring
        with self.assertRaises(ValueError):
            Spring.parse("0.9, not-a-number")
        with self.assertRaises(ValueError):
            Spring(0.9, 0)                          # zero stiffness cannot move
        with self.assertRaises(ValueError):
            Spring(-0.5, 700)                       # negative damping diverges
        with self.assertRaises(ValueError):
            Spring(0.0, 700)                        # no damping never settles

    def test_an_overdamped_spring_is_real_and_boring(self):
        spring = Spring(2.5, 700)
        peak = max(spring.at(ms) for ms in range(0, 2000, 5))
        self.assertLessEqual(peak, 1.0 + 1e-9)
        self.assertAlmostEqual(1.0, spring.at(spring.settle_ms), delta=1e-3)

    def test_every_spring_name_resolves_through_curve(self):
        for name in SPRINGS:
            with self.subTest(spring=name):
                self.assertIn(name, CURVES)
                self.assertIsInstance(curve(name)(0.5), float)
                for t in (0.0, 0.25, 0.5, 1.0):
                    with self.subTest(t=t):
                        self.assertAlmostEqual(
                            curve(name)(t), curve(name.replace("_", "-"))(t),
                            places=9)


class TestShapeFamily(unittest.TestCase):
    """The catalogue the renderer draws and the morph interpolates."""

    def test_the_family_is_the_one_the_renderer_draws(self):
        java = _read("PydrudShapes.java.j2")
        for shape in SHAPES:
            with self.subTest(shape=shape):
                self.assertIn(f'"{shape}"', java)

    def test_names_are_forgiving(self):
        for spelling in ("COOKIE_9", "cookie-9", "cookie_9", " Cookie_9 "):
            with self.subTest(spelling=spelling):
                self.assertEqual("cookie_9", Shapes.normalize(spelling))

    def test_an_unknown_shape_is_an_error(self):
        with self.assertRaises(ValueError):
            Shapes.normalize("hexadecagon")

    def test_shapes_constant_matches_the_family(self):
        for name in SHAPES:
            with self.subTest(shape=name):
                self.assertEqual(name, getattr(Shapes, name.upper()))


class TestShapeMorphWidget(unittest.TestCase):
    """``ShapeMorph`` carries the pair, the progress and the spring."""

    def test_it_serialises_the_whole_morph(self):
        morph = ShapeMorph(Shapes.COOKIE_9, "circle", progress=0.4,
                           rotation=90, spring="spring-slow-spatial")
        self.assertEqual({"from": "cookie_9", "to": "circle", "progress": 0.4,
                          "rotation": 90.0, "spring": "spring_slow_spatial"},
                         morph._serialise_props())

    def test_the_widget_type_is_the_renderer_door(self):
        self.assertEqual("ShapeMorph", ShapeMorph()._widget_type)

    def test_progress_is_a_fraction_and_is_clamped(self):
        self.assertEqual(0.0, ShapeMorph(progress=-2)._serialise_props()["progress"])
        self.assertEqual(1.0, ShapeMorph(progress=7)._serialise_props()["progress"])

    def test_a_shape_is_a_default_for_both_ends(self):
        props = ShapeMorph(Shapes.CLOVER_8)._serialise_props()
        self.assertEqual(("clover_8", "clover_8"), (props["from"], props["to"]))

    def test_the_default_spring_is_the_quick_spatial_one(self):
        self.assertEqual(DEFAULT_SPRING, ShapeMorph()._serialise_props()["spring"])
        self.assertEqual("spring_fast_spatial", DEFAULT_SPRING)

    def test_an_unknown_spring_is_an_error(self):
        with self.assertRaises(ValueError):
            ShapeMorph(spring="spring_wobbly")

    def test_a_size_becomes_a_box(self):
        style = ShapeMorph(size=96, bg="#FFFF0000").style
        self.assertEqual(96, style["width"])
        self.assertEqual(96, style["height"])
        self.assertEqual("#FFFF0000", style["bg"])

    def test_children_sit_inside_the_shape(self):
        from pydrud import Icon

        morph = ShapeMorph(child=Icon("star"))
        self.assertEqual(1, len(morph.children))


class TestMorphStylesheet(unittest.TestCase):
    """A class can retune the whole morph, progress included."""

    def test_the_five_keys_are_registered(self):
        for key in ("shapeFrom", "shapeTo", "shapeProgress", "shapeRotation",
                    "shapeSpring"):
            with self.subTest(key=key):
                self.assertIn(key, VALID_STYLE_KEYS)
                self.assertIn(key, KEY_KIND)

    def test_kebab_spellings_canonicalise(self):
        expected = {"shape-from": "shapeFrom", "shape-to": "shapeTo",
                    "shape-progress": "shapeProgress",
                    "shape-rotation": "shapeRotation",
                    "shape-spring": "shapeSpring"}
        for kebab, canonical in expected.items():
            with self.subTest(key=kebab):
                self.assertEqual(canonical, _KEBAB_CANONICAL[kebab])

    def test_a_stylesheet_retunes_a_morph(self):
        sheet = parse_pss(
            "ShapeMorph.chip { shape-to: cookie_9; shape-progress: 0.5; "
            "shape-spring: spring-slow-spatial; shape-rotation: 90; }")
        resolved, warnings = resolve_styles(
            sheet, [ShapeMorph(class_=["chip"])])
        self.assertEqual([], warnings)
        body = next(iter(resolved.values()))
        self.assertEqual("cookie_9", body["shapeTo"])
        self.assertEqual(0.5, body["shapeProgress"])
        self.assertEqual("spring-slow-spatial", body["shapeSpring"])
        self.assertEqual(90, body["shapeRotation"])


class TestJavaShapeRenderer(unittest.TestCase):
    """The generated renderer does the morph."""

    def setUp(self):
        self.shapes = _read("PydrudShapes.java.j2")
        self.styler = _read("ViewStyler.java.j2")
        self.builtins = _read("BuiltinViews.java.j2")
        self.patcher = _read("TreePatcher.java.j2")
        self.theme = _read("PydrudTheme.java.j2")

    def test_the_three_radius_functions_are_there(self):
        for function in ("squircle", "polygon", "wave"):
            with self.subTest(function=function):
                self.assertIn(f"float {function}(", self.shapes)

    def test_every_shape_is_sampled_at_the_same_angles(self):
        # Vertex matching is what makes a morph a morph.
        self.assertRegex(self.shapes, r"SAMPLES\s*=\s*\d+")

    def test_the_morph_interpolates_between_the_two_samples(self):
        self.assertRegex(self.shapes, r"start\[i\] \+ \(end\[i\] - start\[i\]\) \* t")

    def test_the_spring_drives_the_progress(self):
        self.assertIn("PydrudTheme.springEasing(spring)", self.shapes)
        self.assertIn("PydrudTheme.springDurationMs(spring)", self.shapes)
        self.assertRegex(self.shapes, r"ValueAnimator\.ofFloat\(progress, to\)")

    def test_java_resolves_the_same_six_springs(self):
        self.assertIn('case "spring_default_spatial":', self.theme)
        for name in SPEC_SPRINGS:
            if name == "spring_default_spatial":
                continue                     # named, and also the fallback
            with self.subTest(spring=name):
                self.assertIn(f'case "{name}"', self.theme)
        for token in SPEC_SPRINGS:
            with self.subTest(token=token):
                self.assertIn(f'optString("{token}"', self.theme)

    def test_the_interpolator_is_analytic(self):
        for branch in ("Math.exp", "Math.cos", "Math.sinh"):
            with self.subTest(branch=branch):
                self.assertIn(branch, self.theme)
        self.assertIn("implements android.view.animation.Interpolator", self.theme)

    def test_effects_springs_are_critically_damped_in_the_defaults(self):
        for name in ("spring_fast_effects", "spring_default_effects",
                     "spring_slow_effects"):
            with self.subTest(spring=name):
                self.assertIn(f'optString("{name}", ', self.theme)
        self.assertIn('springFastEffects = "1.0, 3800"', self.theme)

    def test_the_styler_reads_the_morph_and_owns_the_background(self):
        self.assertIn("static PydrudShapes.MorphDrawable shapeMorphDrawable(",
                      self.styler)
        self.assertIn("view.setBackground(morph)", self.styler)
        # A live morph keeps its drawable, so progress springs from where it is.
        self.assertIn("live.animateTo(progress)", self.styler)

    def test_the_factory_creates_a_morph_view(self):
        self.assertIn('case "ShapeMorph":', self.builtins)
        self.assertIn("new PydrudShapes.MorphView(", self.builtins)

    def test_updates_spring_the_live_progress(self):
        self.assertIn("morph.animateTo(", self.patcher)
        self.assertIn("PydrudShapes.MorphDrawable) view.getBackground()",
                      self.patcher)

    def test_the_rotation_is_applied(self):
        self.assertIn("Math.toRadians(rotationDeg)", self.shapes)


class TestMorphGeometry(unittest.TestCase):
    """The shapes are the family they claim to be, not blobs."""

    @staticmethod
    def _shape_call(shape: str):
        """The Java switch arm for a shape: ``(function, positional args)``."""
        import re as _re

        java = _read("PydrudShapes.java.j2")
        for match in _re.finditer(
                r'case "([a-z0-9_]+)":\s*return (\w+)\(([^;]+)\);', java):
            if match.group(1) == shape:
                function = match.group(2)
                args = [a.strip().rstrip("f") for a in match.group(3).split(",")]
                # The angle is always the first argument.
                return function, [a for a in args if a != "theta"]
        return None, []

    @staticmethod
    def _amplitude(function: str, args, steps: int = 720):
        """Sample a radius function over a full turn, in Python."""
        n = int(float(args[0]))
        extra = float(args[1]) if len(args) > 1 else 0.0
        out = []
        for i in range(steps):
            theta = 2 * math.pi * i / steps
            if function == "wave":
                out.append(1 + extra * math.cos(n * theta))
            elif function == "squircle":
                p = float(args[0])
                out.append((abs(math.cos(theta)) ** p
                            + abs(math.sin(theta)) ** p) ** (-1 / p))
            elif function == "polygon":
                step = 2 * math.pi / n
                wrapped = ((theta + step / 2) % step + step) % step - step / 2
                sharp = math.cos(math.pi / n) / math.cos(wrapped)
                out.append(sharp * (1 - extra) + extra)
        return out

    def _radii(self, shape: str):
        function, args = self._shape_call(shape)
        self.assertIsNotNone(function, f"{shape} is not drawn by the renderer")
        return self._amplitude(function, args)

    def test_a_cookie_wobbles_around_a_circle(self):
        radii = self._radii("cookie_9")
        # cosine waves are symmetric about 1: amplitude 0.04 either way.
        self.assertAlmostEqual(1.04, max(radii), places=6)
        self.assertAlmostEqual(0.96, min(radii), places=6)

    def test_a_square_reaches_further_into_its_corners_than_a_circle(self):
        radii = self._radii("square")
        self.assertGreater(max(radii), min(radii))          # not a circle
        self.assertAlmostEqual(1.0, min(radii), places=6)   # flat edges
        # The corner reach is the superellipse's: it approaches √2 as p grows
        # and stops at 1.26 for the p = 6 design.
        self.assertAlmostEqual(1.26, max(radii), places=2)
        self.assertGreater(max(self._radii("square")),
                           max(self._radii("puffy_square")))
        self.assertGreater(max(self._radii("puffy_square")), 1.0)   # > circle

    def test_a_clover_bites_deeper_than_a_cookie(self):
        self.assertLess(min(self._radii("clover_4")),
                        min(self._radii("cookie_4")))

    def test_a_wave_has_as_many_lobes_as_it_is_told(self):
        def lobes(radii):
            peaks = sum(1 for i in range(len(radii))
                        if radii[i] > radii[i - 1] and radii[i] >= radii[(i + 1) % len(radii)])
            return peaks

        for shape, expected in (("cookie_4", 4), ("cookie_9", 9),
                                ("clover_6", 6), ("burst", 12), ("sunny", 16)):
            with self.subTest(shape=shape):
                self.assertEqual(expected, lobes(self._radii(shape)))

    def test_a_flower_is_deeper_than_a_burst_which_is_deeper_than_a_cookie(self):
        depth = lambda shape: max(self._radii(shape)) - min(self._radii(shape))
        self.assertGreater(depth("flower"), depth("burst"))
        self.assertGreater(depth("burst"), depth("cookie_12"))


if __name__ == "__main__":
    unittest.main()
