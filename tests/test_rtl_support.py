"""RTL support — logical insets have to survive to the device.

``AndroidManifest.xml`` declares ``supportsRtl="true"`` and the Python side has
offered ``EdgeInsets.only(start=…, end=…)`` since 2.1.0, documented as
"resolve relative to the current text direction". The renderer, though, read
only ``left``/``top``/``right``/``bottom`` from a padding or margin dict — so a
logical inset arrived as

    {"left": 0, "top": 0, "right": 0, "bottom": 0, "start": 16, "end": 8}

and was applied as *zero* padding. The inset did not fail to mirror; it
vanished, in silence.

These tests pin the three things that make RTL work: the logical pair reaches
the renderer, the renderer resolves it against the layout direction, and the
box shorthands a stylesheet may use all collapse into something the renderer
reads.
"""

from __future__ import annotations

import pathlib
import re
import unittest

import jinja2

import pydrud as pd
from pydrud.core.styles import parse_pss, resolve_styles
from pydrud.widgets.styling import EdgeInsets

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


def _render(name: str) -> str:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES)), keep_trailing_newline=True
    )
    return env.get_template(name).render(**RENDER_CONTEXT)


class TestLogicalInsetsReachTheRenderer(unittest.TestCase):
    def test_start_end_insets_survive_serialisation(self):
        app = pd.App(target=lambda page: page.add(pd.Column(key="col", children=[
            pd.Text("a", key="a",
                    style={"padding": EdgeInsets.only(start=16, end=8).to_dict()}),
            pd.Text("b", key="b",
                    style={"margin": EdgeInsets.only(start=12).to_dict()}),
        ])), dev_server=False)
        self.addCleanup(app.stop)
        tree = app.build().to_dict()

        def find(node, key):
            stack = [node]
            while stack:
                current = stack.pop()
                if current.get("key") == key:
                    return current
                stack.extend(current.get("children") or [])
            raise AssertionError(key)

        self.assertEqual(find(tree, "a")["style"]["padding"]["start"], 16)
        self.assertEqual(find(tree, "a")["style"]["padding"]["end"], 8)
        self.assertEqual(find(tree, "b")["style"]["margin"]["start"], 12)

    def test_renderer_resolves_logical_insets_against_layout_direction(self):
        styler = _render("ViewStyler.java.j2")
        self.assertIn("void applyPadding(View view, JSONObject p)", styler)
        self.assertIn("setPaddingRelative(", styler)
        self.assertIn("isLogical(", styler)
        # The fallback direction: start falls back to left, end to right.
        self.assertIn('p.optInt("start", p.optInt("left", 0))', styler)
        self.assertIn('p.optInt("end", p.optInt("right", 0))', styler)

    def test_renderer_resolves_logical_margins(self):
        styler = _render("ViewStyler.java.j2")
        self.assertIn("void applyMargin(ViewGroup.MarginLayoutParams lp, JSONObject m)",
                      styler)
        self.assertIn("setMarginStart(", styler)
        self.assertIn("setMarginEnd(", styler)

    def test_physical_insets_stay_physical(self):
        """``left``/``right`` are documented as absolute, and stay so."""
        styler = _render("ViewStyler.java.j2")
        padding = styler[styler.index("void applyPadding(View view, JSONObject p)"):]
        padding = padding[:padding.index("\n    void applyMargin")]
        self.assertIn("view.setPadding(dp(p.optInt(\"left\", 0)), top,", padding)
        self.assertIn('else {\n            view.setPadding(', padding)

    def test_explicit_sides_win_over_the_logical_fallback(self):
        """``start`` is used when given; ``left`` only fills in when it is not."""
        styler = _render("ViewStyler.java.j2")
        self.assertIn('p.optInt("start", p.optInt("left", 0))', styler)
        self.assertIn('m.optInt("start", m.optInt("left", 0))', styler)


class TestBoxShorthandsCollapse(unittest.TestCase):
    """Every spelling a stylesheet may use must reach the four sides."""

    @classmethod
    def setUpClass(cls):
        cls.root = pd.Column(key="root", children=[pd.Text("x", key="w")])

    def _resolve(self, declaration: str, key: str):
        resolved, _ = resolve_styles(parse_pss(f"#w {{ {declaration} }}"), self.root)
        return resolved["w"].get(key)

    def test_a_lone_all_is_left_for_the_renderer(self):
        """The renderer reads ``all`` directly, so the compact form stays."""
        self.assertEqual(self._resolve("padding: { all: 8 };", "padding"), {"all": 8})

    def test_all_expands_when_it_would_shadow_a_specific_edge(self):
        """The renderer tests ``all`` first, so the edge would be dropped."""
        self.assertEqual(
            self._resolve("padding: { all: 8, left: 4 };", "padding"),
            {"left": 4, "top": 8, "right": 8, "bottom": 8},
        )

    def test_horizontal_and_vertical_expand(self):
        """The documented example used to reach the renderer as-is and be ignored."""
        self.assertEqual(
            self._resolve("padding: { horizontal: 16, vertical: 10 };", "padding"),
            {"left": 16, "right": 16, "top": 10, "bottom": 10},
        )
        self.assertEqual(
            self._resolve("margin: { horizontal: 6 };", "margin"),
            {"left": 6, "right": 6},
        )

    def test_a_longhand_still_overrides_a_shorthand(self):
        box = self._resolve("padding: { horizontal: 16 };", "padding")
        self.assertEqual(box, {"left": 16, "right": 16})

    def test_logical_insets_are_left_alone(self):
        """``start``/``end`` cannot be folded — only the device knows the direction."""
        self.assertEqual(
            self._resolve("padding: { start: 16, end: 4 };", "padding"),
            {"start": 16, "end": 4},
        )


class TestComponentChromeIsRtlAware(unittest.TestCase):
    """Asymmetric component padding must use the relative API."""

    #: Padding that differs on the leading and trailing edges, per template.
    ASYMMETRIC = {
        "MaterialViews.java.j2": [
            "button.setPaddingRelative(dp(12), 0, 0, 0);",
            "box.setPaddingRelative(dp(16), dp(6), dp(12), dp(6));",
            "btn.setPaddingRelative(PydrudTheme.dp(8), 0, 0, 0);",
            "primary.setPaddingRelative(PydrudTheme.dp(20), 0, PydrudTheme.dp(12), 0);",
            "tv.setPaddingRelative(PydrudTheme.dp(12), 0, PydrudTheme.dp(8), 0);",
        ],
        "AdvancedViews.java.j2": [
            "text.setPaddingRelative(dp(12), dp(4), dp(4), dp(4));",
        ],
    }

    def test_asymmetric_component_padding_is_relative(self):
        for name, snippets in self.ASYMMETRIC.items():
            rendered = _render(name)
            for snippet in snippets:
                with self.subTest(template=name, snippet=snippet[:40]):
                    self.assertIn(snippet, rendered)

    #: Asymmetric padding that is deliberately physical. A screen cutout sits
    #: on a literal edge, and the physical branch of the inset helper is what
    #: makes ``left``/``right`` absolute in the first place.
    PHYSICAL_BY_DESIGN = (
        "bars.left",             # window insets describe physical screen edges
        'dp(p.optInt("left", 0)), top',   # applyPadding's physical branch
    )

    def test_no_unjustified_asymmetric_setpadding_remains(self):
        """A left/right pair that differs must use the relative API.

        Absolute padding does not mirror, so any component chrome with a
        leading/trailing asymmetry — an icon gutter, a sheet handle, a
        blockquote rule — would sit on the wrong edge in an RTL locale.
        """
        offenders = []
        for path in sorted(TEMPLATES.glob("*.java.j2")):
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(
                r"setPadding\(\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^)]+)\)", text
            ):
                left, _top, right, _bottom = (g.strip() for g in match.groups())
                if left == right:
                    continue
                snippet = match.group(0)
                if any(excuse in snippet for excuse in self.PHYSICAL_BY_DESIGN):
                    continue
                line = text[: match.start()].count("\n") + 1
                offenders.append(f"{path.name}:{line}: {snippet[:70]}")
        self.assertEqual(
            [], offenders,
            "asymmetric padding must use setPaddingRelative so it mirrors in "
            "RTL:\n  " + "\n  ".join(offenders),
        )

    def test_safe_area_insets_preserve_relative_padding(self):
        engine = _render("LayoutEngine.java.j2")
        self.assertIn("view.getPaddingStart()", engine)
        self.assertIn("view.getPaddingEnd()", engine)
        self.assertNotIn("view.setPadding(view.getPaddingLeft()", engine)

    def test_manifest_still_declares_rtl_support(self):
        manifest = _render("AndroidManifest.xml.j2")
        self.assertIn('android:supportsRtl="true"', manifest)

    def test_drawables_and_gravity_are_relative(self):
        """The other half of RTL: icon slots and alignment."""
        for name in ("BuiltinViews.java.j2", "MaterialViews.java.j2",
                     "ViewStyler.java.j2"):
            with self.subTest(template=name):
                text = _render(name)
                self.assertNotIn("Gravity.LEFT", text)
                self.assertNotIn("Gravity.RIGHT", text)
                self.assertIn("setCompoundDrawablesRelativeWithIntrinsicBounds", text)


if __name__ == "__main__":
    unittest.main()
