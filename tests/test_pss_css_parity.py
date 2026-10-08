"""CSS parity: the reference prototype stylesheet, resolved by PSS.

``docs/examples/heartbeat-css-parity.pss`` is the design's web ``<style>``
block translated to PSS. This module parses it and resolves a synthetic widget
tree at three real phone viewports, asserting the numbers a browser would
compute. It is the end-to-end proof that PSS now speaks the CSS authoring
surface: custom properties, the universal selector, pseudo-classes, ``@media``,
``@keyframes``, ``transition`` and the ``clamp()``/``calc()``/``env()`` value
language.
"""

from __future__ import annotations

import os
import unittest

from pydrud.core.styles.parser import parse_pss
from pydrud.core.styles.resolver import resolve_styles
from pydrud.core.styles.values import ValueContext
from pydrud.widgets import Canvas, Column, Container, Row, Stack, Text

_EXAMPLE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs", "examples", "heartbeat-css-parity.pss")


def _stylesheet():
    with open(_EXAMPLE, "r", encoding="utf-8") as handle:
        return parse_pss(handle.read(), filename="heartbeat-css-parity.pss")


def _tree():
    """A widget tree carrying the prototype's classes."""
    return Container(key="app", class_="app running", children=[
        Row(key="topbar", class_="topbar", children=[
            Text("Heartbeat", key="app_name", class_="app-name"),
            Row(key="session", class_="session", children=[
                Container(key="dot", class_="session-dot"),
            ]),
        ]),
        Column(key="stage", class_="stage", children=[
            Stack(key="visual", class_="visual", children=[
                Container(key="glow", class_="glow"),
                Container(key="ring_one", class_="ring one"),
                Container(key="ring_two", class_="ring two"),
                Container(key="heart", class_="heart"),
            ]),
            Text("72", key="number", class_="number"),
            Text("BPM", key="unit", class_="unit"),
            Text("message", key="message", class_="message"),
            Canvas(key="ecg", class_="ecg-wrap"),
        ]),
        Container(key="fab", class_="fab"),
        Row(key="bottom", class_="bottom", children=[
            Text("Visual rhythms", key="footnote", class_="footnote"),
        ]),
        Container(key="flash", class_="flash"),
    ])


class TestParityStylesheetParses(unittest.TestCase):
    def test_no_errors_and_only_the_web_only_warning(self):
        sheet = _stylesheet()
        self.assertEqual([d for d in sheet.diagnostics if d.kind == "error"], [])
        self.assertEqual([d for d in sheet.diagnostics if d.kind == "warning"], [])
        self.assertEqual(sorted(sheet.keyframes),
                         ["beat", "ecgMove", "flash", "glow", "ring"])
        self.assertEqual(sheet.variables["--heart"], "#E85D68")

    def test_resolving_the_whole_tree_reports_no_value_warnings(self):
        _, warnings = resolve_styles(
            _stylesheet(), _tree(), context=ValueContext(width=360, height=640))
        # The only warning is the aggregated web-only note; no schema or
        # token warnings.
        self.assertEqual(len(warnings), 1, warnings)
        self.assertIn("web-only", warnings[0])


class TestParityResolvesLikeCSS(unittest.TestCase):
    def _resolve(self, width, height):
        result, _ = resolve_styles(
            _stylesheet(), _tree(),
            context=ValueContext(width=width, height=height))
        return result

    def test_phone_360x640(self):
        # width ≤ 699, ≤ 360 and height ≤ 700 all apply, in source order.
        result = self._resolve(360, 640)
        self.assertAlmostEqual(result["app"]["padding"]["top"], 12.0)
        self.assertAlmostEqual(result["app"]["padding"]["left"], 18.0)
        self.assertAlmostEqual(result["app"]["maxWidth"], 430.0)
        self.assertAlmostEqual(result["visual"]["width"], 150.0)
        self.assertAlmostEqual(result["glow"]["width"], 90.0)
        self.assertAlmostEqual(result["ring_one"]["width"], 136.8)
        self.assertAlmostEqual(result["heart"]["width"], 57.6)
        self.assertAlmostEqual(result["number"]["font"]["size"], 78.0)
        self.assertAlmostEqual(result["number"]["margin"]["top"], -6.0)
        self.assertAlmostEqual(result["ecg"]["width"], 151.2)
        self.assertAlmostEqual(result["ecg"]["height"], 20.0)
        self.assertAlmostEqual(result["fab"]["width"], 52.0)
        self.assertAlmostEqual(result["fab"]["right"], 14.0)

    def test_large_phone_412x915(self):
        # width 412 is not ≤ 360, and height 915 is not ≤ 700.
        result = self._resolve(412, 915)
        self.assertAlmostEqual(result["app"]["padding"]["top"], 18.0)
        self.assertAlmostEqual(result["app"]["padding"]["left"], 20.6)
        self.assertAlmostEqual(result["visual"]["width"], 206.0)
        self.assertAlmostEqual(result["glow"]["width"], 103.0)
        self.assertAlmostEqual(result["ring_one"]["width"], 156.0)
        self.assertAlmostEqual(result["heart"]["width"], 62.0)
        self.assertAlmostEqual(result["number"]["font"]["size"], 98.88)
        self.assertAlmostEqual(result["number"]["margin"]["top"], -12.0)
        self.assertAlmostEqual(result["fab"]["width"], 56.0)
        self.assertAlmostEqual(result["fab"]["right"], 20.0)

    def test_small_phone_320x480(self):
        result = self._resolve(320, 480)
        self.assertAlmostEqual(result["app"]["padding"]["left"], 14.0)
        self.assertAlmostEqual(result["number"]["font"]["size"], 78.0)
        self.assertAlmostEqual(result["ecg"]["width"], 134.4)
        self.assertAlmostEqual(result["fab"]["width"], 52.0)

    def test_variables_and_keyframes_reach_the_widgets(self):
        result = self._resolve(360, 640)
        # `background: var(--heart-soft)` on the pulse field.
        self.assertEqual(result["glow"]["bg"], "rgba(232, 93, 104, .08)")
        # `.running .glow { animation: glow 1.12s ease-out infinite }`
        spec = result["glow"]["animation"]
        self.assertEqual(spec["duration"], 1120.0)
        self.assertEqual(spec["iterations"], "infinite")
        self.assertEqual(spec["curve"], "ease_out")
        self.assertEqual(spec["keyframes"][0], [0.0, {"opacity": 0.18,
                                                     "scale": 0.78}])
        # The delayed trailing ring keeps its .37s delay.
        self.assertEqual(result["ring_two"]["animation"]["delay"], 370.0)
        # `.running .heart { animation: beat .84s infinite }` — sorted offsets.
        offsets = [frame[0] for frame in result["heart"]["animation"]["keyframes"]]
        self.assertEqual(offsets, sorted(offsets))

    def test_pseudo_class_and_transition_reach_the_widgets(self):
        result = self._resolve(360, 640)
        # `.fab:active { transform: scale(.92) }` becomes a press spec.
        self.assertEqual(result["fab"]["press"], {"scale": 0.92})
        # `.session-dot { transition: background .2s ease }`
        self.assertEqual(
            result["dot"]["transition"],
            [{"property": "background", "curve": "ease_in_out",
              "duration": 200.0}])

    def test_border_and_radius_longhands_fold(self):
        result = self._resolve(360, 640)
        self.assertEqual(result["ring_one"]["border"],
                         {"width": 1.0, "color": "rgba(232, 93, 104, .18)"})
        # `border-radius: 50%` is the CSS circle idiom.
        self.assertEqual(result["dot"]["borderRadius"], 999)


if __name__ == "__main__":
    unittest.main()
