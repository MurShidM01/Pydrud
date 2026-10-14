"""Every published design token must actually do something.

`Tokens` is the single source of truth for how an app looks, and the whole
class ships to the device on every theme push. A token that nothing reads is
worse than useless: a user retunes it, sees no change, and has no way to find
out that the framework ignored them. That is what the Material 3 audit found —
`tonal_elevation_*`, the `state_*` alphas, the component sizes and the motion
tokens were all published, loaded into the renderer, and then never used.

This module keeps the vocabulary honest. Every token must fall into one of
three buckets, and a new token that belongs to none of them fails the build:

``RENDERED``
    Something reads it — a Java factory, the theme, or a Python widget — so
    changing the value changes the screen.
``VOCABULARY``
    A scale an author picks from rather than a value the framework applies on
    its own: the corner scale, the motion ladder, the colour roles. These must
    be reachable as PSS ``$tokens`` and as ``Tokens`` constants, which is
    exactly what they are for.
``PLATFORM_CHROME``
    Destined for a surface Android draws itself, where the framework owns the
    pixels (a popup-menu radius, a tooltip's corner). Published so a renderer
    that owns those surfaces can honour them; listed here with the reason.

The audit is deliberately two-sided: it reads the rendered Java templates the
way the device would, and the Python sources the way the app does. Grep-level
claims are not enough — an earlier version of this check passed the
`state_*` alphas because the *assignment* lines mentioned them.
"""

from __future__ import annotations

import pathlib
import re
import unittest

import jinja2

from pydrud.core.styles.resolver import _theme_tokens
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

#: Tokens whose Java field is not the camelCase of the token name.
FIELD_ALIASES = {
    "touch_target": "touchTargetDp",
    "font_family": "fontFamily",
    "line_height": "lineHeight",
    "letter_spacing": "letterSpacing",
    "press_scale": "pressScale",
}

#: A scale an author picks from; reachable as a ``$token``, not auto-applied.
VOCABULARY = frozenset({
    # The corner scale: a component names the step it wants.
    "corner_none", "corner_extra_small", "corner_small", "corner_medium",
    "corner_large", "corner_large_increased", "corner_extra_large",
    "corner_extra_large_increased", "corner_extra_extra_large", "corner_full",
    # The motion ladder: a transition names its step.
    "duration_short_1", "duration_short_2", "duration_short_3", "duration_short_4",
    "duration_medium_1", "duration_medium_2", "duration_medium_3", "duration_medium_4",
    "duration_long_1", "duration_long_2", "duration_long_3", "duration_long_4",
    "duration_extra_long_1", "duration_extra_long_2", "duration_extra_long_3",
    "duration_extra_long_4",
    "duration_fast", "duration_normal", "duration_slow",
    # Easing curves: named by `transition` / `animation`.
    "easing_standard", "easing_standard_decelerate", "easing_standard_accelerate",
    "easing_emphasized", "easing_emphasized_decelerate",
    "easing_emphasized_accelerate", "easing_linear",
})

#: Android paints these surfaces itself, so the framework owns the geometry.
PLATFORM_CHROME = {
    "radius_menu": "a popup menu is framework chrome; Android draws it",
    "radius_tooltip": "the platform tooltip window is framework chrome",
    "elevation_menu": "the popup window's elevation is set by the platform",
}


def _java_files() -> dict:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES)), keep_trailing_newline=True
    )
    return {
        path.name: env.get_template(path.name).render(**RENDER_CONTEXT)
        for path in sorted(TEMPLATES.glob("*.java.j2"))
    }


def _is_a_use(line: str, column: int, token: str) -> bool:
    """True when ``column`` is a read of ``token``, not a load or a declaration.

    Three things look like a read but are not: a comment, the theme loader
    (which always quotes the snake_case name next to the field it fills), and
    a declaration or assignment whose target *is* the field.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith(("//", "*", "/*")):
        return False
    # A theme loader reads the snake_case token name out of the `tokens`
    # object; a name in any other position (`case "spring_fast_spatial":`
    # in the resolver, say) is the token being *used*.
    if re.search(r'\.(?:opt\w*|has|isNull|get\w*)\(\s*"' + re.escape(token) + r'"',
                 line):
        return False
    assign = re.search(r"(?<![=!<>+\-*/%&|^])=(?!=)", line)
    if assign and column < assign.start():
        target = line[: assign.start()]
        if re.fullmatch(r"[\w\s.\[\]<>]+", target):
            return False
    return True


class TestNoTokenIsDead(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = _java_files()
        cls.theme = cls.files["PydrudTheme.java.j2"]
        cls.fields = set(re.findall(
            r"public static (?:\w+|String)\s+(\w+)\s*=", cls.theme))
        cls.python = {
            path: path.read_text(encoding="utf-8")
            for path in (ROOT / "pydrud").rglob("*.py")
            if "templates" not in str(path) and path.name != "tokens.py"
        }

    def _read_by_java(self, field: str, token: str) -> bool:
        for text in self.files.values():
            for match in re.finditer(r"\b" + re.escape(field) + r"\b", text):
                line_start = text.rfind("\n", 0, match.start()) + 1
                line = text[line_start: text.find("\n", match.start())]
                if _is_a_use(line, match.start() - line_start, token):
                    return True
        return False

    def _read_by_python(self, name: str) -> bool:
        for text in self.python.values():
            for match in re.finditer(r"\b" + re.escape(name) + r"\b", text):
                line_start = text.rfind("\n", 0, match.start()) + 1
                line = text[line_start: text.find("\n", match.start())]
                if _is_a_use(line, match.start() - line_start, name):
                    return True
        return False

    def test_every_token_is_rendered_or_declared_vocabulary(self):
        dead = []
        for token in sorted(Tokens.names()):
            if token in VOCABULARY or token in PLATFORM_CHROME:
                continue
            field = FIELD_ALIASES.get(token) or _camel(token)
            if self._read_by_java(field, token) or self._read_by_python(token):
                continue
            dead.append(token)
        self.assertEqual(
            [], dead,
            "these tokens nothing reads, so setting them changes nothing on "
            "screen — either wire them up or add them to VOCABULARY / "
            "PLATFORM_CHROME with a reason: " + ", ".join(dead),
        )

    def test_vocabulary_tokens_are_reachable_as_pss_references(self):
        """A scale is only useful if a stylesheet can name a step of it."""
        tokens = _theme_tokens()
        missing = [name for name in sorted(VOCABULARY) if name not in tokens]
        self.assertEqual([], missing, f"not resolvable as $token: {missing}")

    def test_platform_chrome_entries_carry_a_reason(self):
        for name, reason in PLATFORM_CHROME.items():
            with self.subTest(token=name):
                self.assertIn(name, Tokens.names())
                self.assertTrue(reason and len(reason) > 20, "needs a real reason")


class TestRenderedTokensAreHonoured(unittest.TestCase):
    """The tokens the audit named must be consumed, not just loaded."""

    @classmethod
    def setUpClass(cls):
        cls.theme = _java_files()["PydrudTheme.java.j2"]
        cls.styler = _java_files()["ViewStyler.java.j2"]

    def _body(self, text: str, signature: str) -> str:
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

    def test_tonal_elevation_is_applied(self):
        """GAP #10 — the tonal ladder was published and never drawn."""
        self.assertIn("tonalSurface(", self.theme)
        # ...and the ladder drives it, so retuning the steps moves the tints.
        body = self._body(self.theme, "float tonalTintFor(")
        for level in ("elevationLevel1", "elevationLevel3", "elevationLevel5"):
            self.assertIn(level, body)
        self.assertIn("PydrudTheme.tonalSurface(", self.styler)

    def test_disabled_state_layers_are_applied(self):
        """GAP #10 — state_disabled_content / _container had no consumer."""
        self.assertIn("applyDisabledTreatment(", self.theme)
        body = self._body(self.theme, "void applyDisabledTreatment(")
        self.assertIn("stateDisabledContainer", body)
        self.assertIn("stateDisabledContent", body)
        # ...and the `disabled` style key reaches it.
        self.assertIn("applyDisabled(", self.styler)
        self.assertIn('s.has("disabled")', self.styler)

    def test_pressed_and_dragged_states_have_consumers(self):
        self.assertIn("PydrudTheme.statePressed", self.styler)
        self.assertIn("draggedLayer()", self.theme)
        self.assertIn("PydrudTheme.draggedLayer()", _java_files()["AdvancedViews.java.j2"])
        self.assertIn("stateDragged", self._body(self.theme, "int draggedLayer("))

    def test_component_sizes_drive_their_components(self):
        files = _java_files()
        pairs = [
            ("checkboxSize", "BuiltinViews.java.j2"),
            ("radioSize", "BuiltinViews.java.j2"),
            ("switchWidth", "BuiltinViews.java.j2"),
            ("switchHeight", "BuiltinViews.java.j2"),
            ("chipHeight", "MaterialViews.java.j2"),
            ("dividerThickness", "BuiltinViews.java.j2"),
            ("railWidth", "MaterialNavigationViews.java.j2"),
            ("listTileHeightThreeLine", "MaterialViews.java.j2"),
            ("radiusImage", "BuiltinViews.java.j2"),
        ]
        for field, template in pairs:
            with self.subTest(field=field, template=template):
                text = files[template]
                self.assertRegex(
                    text, r"PydrudTheme\." + field + r"\b",
                    f"{field} is published but {template} never reads it",
                )

    def test_component_elevations_drive_their_surfaces(self):
        files = _java_files()
        for field, template in (
            ("elevationDialog", "MaterialViews.java.j2"),
            ("elevationSheet", "MaterialViews.java.j2"),
            ("elevationNavBar", "MaterialNavigationViews.java.j2"),
            ("elevationAppBar", "MaterialViews.java.j2"),
        ):
            with self.subTest(field=field):
                self.assertIn(f"PydrudTheme.{field}", files[template])

    def test_motion_tokens_reach_the_animator(self):
        animator = _java_files()["ViewAnimator.java.j2"]
        # Every duration an animation uses resolves through the token table.
        self.assertIn("PydrudTheme.durationMs(", animator)
        self.assertNotIn('optDouble("duration", 1000)', animator)
        self.assertNotIn('duration\", 250', animator)
        body = self._body(self.theme, "long defaultDurationMs(")
        self.assertIn("durationNormal", body)
        resolver = self._body(self.theme, "public static long durationMs(Object value)")
        self.assertIn("durationNormal", resolver)

    def test_no_animation_duration_is_a_bare_millisecond_literal(self):
        # The loading waveform's sweep used to be `setDuration(1150)`.
        views = _java_files()["MaterialViews.java.j2"]
        self.assertIn('sweep.setDuration(PydrudTheme.durationMs(', views)
        self.assertNotIn("sweep.setDuration(1150)", views)

    def test_text_scale_endpoints_are_honoured(self):
        body = self._body(self.theme, "float snapTextSize(")
        self.assertIn("textBody", body)
        self.assertIn("textCaption", body)
        self.assertIn("textDisplay", body)

    def test_overscroll_token_reaches_the_scroll_containers(self):
        engine = _java_files()["LayoutEngine.java.j2"]
        self.assertIn("PydrudTheme.overScrollMode()", engine)
        self.assertNotIn("setOverScrollMode(View.OVER_SCROLL_IF_CONTENT_SCROLLS)", engine)
        self.assertIn("overscrollGlow", self._body(self.theme, "int overScrollMode("))


class TestThemeTuningChangesTheRender(unittest.TestCase):
    """End to end: retune a token from Python and the wire changes."""

    def test_a_retuned_size_reaches_the_payload(self):
        from pydrud.widgets.theme import Theme

        before = Theme.payload()["tokens"]["checkbox_size"]
        self.addCleanup(Tokens.reset)
        Tokens.update(checkbox_size=24)
        after = Theme.payload()["tokens"]["checkbox_size"]
        self.assertEqual(after, 24)
        self.assertNotEqual(before, after)

    def test_a_retuned_state_layer_reaches_the_payload(self):
        from pydrud.widgets.theme import Theme

        self.addCleanup(Tokens.reset)
        Tokens.update(state_pressed=0.2, tonal_elevation_3=0.2)
        tokens = Theme.payload()["tokens"]
        self.assertEqual(tokens["state_pressed"], 0.2)
        self.assertEqual(tokens["tonal_elevation_3"], 0.2)


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.capitalize() for part in rest)


if __name__ == "__main__":
    unittest.main()
