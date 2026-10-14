"""GAP #11 — the shadow and scrim roles are the spec's black, and are used.

Material 3 defines both roles as ``#000000``. The framework had drifted to a
tinted grey (``#33101828`` / ``#99101828``) in two places, and — more
important than the value — the renderer never read either role from the
payload at all. So a scheme could say "my scrim is this" and the device would
keep drawing whatever was compiled into it, which is the same class of bug as
the dead tokens GAP #10 closed.

The scrim's *opacity* is not part of the role. M3 components composite the
role at 32 %, so the framework does the same: the role stays black and
``scrimOverlay()`` applies the component's share. That distinction is what
made the old values impossible to reason about — dimming was baked into the
colour, so there was no scrim to retune.

A scrim that nothing draws is still a dead role, so the modal drawer — which
previously slid over the content with no dim layer at all — now composites it.
"""

from __future__ import annotations

import pathlib
import re
import unittest

import jinja2

from pydrud.widgets.material import Drawer
from pydrud.widgets.theme import Theme
from pydrud.widgets.theme.colors import Colors
from pydrud.widgets.theme.hct import DynamicScheme

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

SPEC_BLACK = "#FF000000"


def _render(name: str) -> str:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES)), keep_trailing_newline=True
    )
    return env.get_template(name).render(**RENDER_CONTEXT)


def _body(text: str, signature: str) -> str:
    """The source of the method that starts at ``signature``."""
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


def _composite(color: str, alpha: float) -> str:
    """The ARGB string Android's ``PydrudTheme.alpha()`` would produce."""
    value = int(color[1:], 16)
    a = round(255 * alpha)
    return "#%02X%02X%02X%02X" % (a, (value >> 16) & 0xFF,
                                  (value >> 8) & 0xFF, value & 0xFF)


class TestRolesAreSpecBlack(unittest.TestCase):
    def test_constants_are_the_spec_value(self):
        self.assertEqual(Colors.SHADOW, SPEC_BLACK)
        self.assertEqual(Colors.SCRIM, SPEC_BLACK)

    def test_no_tinted_grey_survives_anywhere(self):
        """The drift is not allowed to creep back in as a literal."""
        offenders = []
        for path in list((ROOT / "pydrud").rglob("*.py")) + \
                    list((ROOT / "pydrud").rglob("*.j2")):
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(r"0x33[0-9A-Fa-f]{6}|#33[0-9A-Fa-f]{6}", text):
                offenders.append(f"{path.relative_to(ROOT)}: {match.group(0)}")
        self.assertEqual([], offenders)

    def test_both_scheme_paths_agree(self):
        payload = Theme.payload()
        for role in ("shadow", "scrim"):
            with self.subTest(role=role):
                self.assertEqual(payload[role], SPEC_BLACK)

        for dark in (False, True):
            scheme = DynamicScheme.from_seed(0xFF6750A4, dark=dark)
            for role in ("shadow", "scrim"):
                with self.subTest(role=role, dark=dark):
                    # ARGB int: opaque black, not a tinted grey.
                    self.assertEqual(scheme.to_dict()[role] & 0x00FFFFFF, 0)
                    self.assertEqual(scheme.to_dict()[role] >> 24 & 0xFF, 0xFF)

    def test_the_renderer_reads_both_roles(self):
        theme = _render("PydrudTheme.java.j2")
        self.assertIn('shadow                 = color(scheme, "shadow", shadow);', theme)
        self.assertIn('scrim                  = color(scheme, "scrim", scrim);', theme)
        # ...and its compiled-in defaults agree with the spec, so a device
        # that renders before the first theme push still looks right.
        self.assertIn("public static int shadow             = 0xFF000000;", theme)
        self.assertIn("public static int scrim              = 0xFF000000;", theme)
        self.assertNotIn("0x33101828", theme)
        self.assertNotIn("0x99101828", theme)


class TestScrimOpacityIsTheComponents(unittest.TestCase):
    def test_the_overlay_composites_the_role_at_thirty_two_percent(self):
        theme = _render("PydrudTheme.java.j2")
        self.assertIn("public static final float SCRIM_ALPHA = 0.32f;", theme)
        body = _body(theme, "public static int scrimOverlay()")
        self.assertIn("alpha(scrim, SCRIM_ALPHA)", body)
        # The role itself stays opaque; only the overlay is dimmed.
        self.assertEqual(_composite(SPEC_BLACK, 0.32), "#52000000")

    def test_a_retuned_scrim_role_changes_the_overlay(self):
        """The point of a role: retune it and the dim layer follows."""
        self.assertEqual(_composite("#FF102030", 0.32), "#52102030")
        self.assertNotEqual(_composite(SPEC_BLACK, 0.32),
                            _composite("#FF102030", 0.32))


class TestTheModalDrawerCompositesTheScrim(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.activity = _render("MainActivity.java.j2")

    def test_the_drawer_has_a_dim_layer(self):
        self.assertIn("private void showDrawerScrim(", self.activity)
        self.assertIn("private void hideDrawerScrim(", self.activity)
        self.assertIn("PydrudTheme.scrimOverlay()", self.activity)
        # The scrim is drawn under the drawer, over everything else.
        self.assertIn("drawerScrim.bringToFront();", self.activity)
        self.assertIn("drawer.bringToFront();", self.activity)

    def test_open_and_close_manage_the_layer(self):
        body = _body(self.activity, "public void setDrawerOpen(")
        self.assertIn("if (modal) showDrawerScrim(drawer, side);", body)
        self.assertIn("hideDrawerScrim();", body)

    def test_tapping_the_scrim_closes_the_drawer(self):
        self.assertIn("drawerScrim.setOnClickListener(v -> setDrawerOpen(false, side));",
                      self.activity)

    def test_a_standard_drawer_can_opt_out(self):
        self.assertIn('props.optBoolean("scrim", true)', self.activity)
        self.assertTrue(Drawer().to_dict()["props"]["scrim"])
        self.assertFalse(Drawer(scrim=False).to_dict()["props"]["scrim"])

    def test_the_scrim_layer_is_a_sibling_that_can_actually_be_added(self):
        """A raw ViewGroup.LayoutParams in a LinearLayout throws at measure."""
        body = _body(self.activity,
                     "private android.view.ViewGroup.LayoutParams drawerScrimParams(")
        self.assertIn("android.widget.FrameLayout.LayoutParams", body)
        self.assertIn("android.widget.LinearLayout.LayoutParams", body)


class TestElevationUsesTheShadowRole(unittest.TestCase):
    def test_elevation_tints_its_shadow_with_the_role(self):
        theme = _render("PydrudTheme.java.j2")
        body = _body(theme, "public static void elevate(View view")
        self.assertIn("setOutlineSpotShadowColor(shadow)", body)
        self.assertIn("alpha(shadow, 0.10f)", body)
        # The role reaches the platform as a colour, not a pre-dimmed overlay.
        self.assertNotIn("alpha(shadow, SCRIM_ALPHA)", body)


if __name__ == "__main__":
    unittest.main()
