"""
Tests for the 1.4 UI layer: design tokens, theming, responsive layout and
the generated native renderer.

These cover the pieces that decide whether an app *looks* right — the
palette that reaches the device, the spacing scale, adaptive layout — and
the structural guarantees the Java side depends on.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import unittest

from pydrud import (
    AppBar, Border, BottomNavigationBar, Button, Card, Colors, Divider, Icons,
    ListTile, MediaQuery, NavItem, Radius, Responsive, Scaffold, Spacing,
    Switch, Text, TextField, Theme,
)
from pydrud import FloatingActionButton, Tokens
from pydrud.widgets.theme import ColorScheme

TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "pydrud", "android", "templates", "android",
)


def _brightness(color: str) -> int:
    """Sum of the RGB channels — enough to compare two shades."""
    return sum(int(color[i:i + 2], 16) for i in (3, 5, 7))


def template(name: str) -> str:
    with open(os.path.join(TEMPLATE_DIR, name), encoding="utf-8") as fh:
        return fh.read()


class TestDesignTokens(unittest.TestCase):

    def test_spacing_scale_is_a_4dp_grid(self):
        values = [Spacing.XS, Spacing.SM, Spacing.MD, Spacing.LG,
                  Spacing.XL, Spacing.XXL, Spacing.HUGE]
        self.assertEqual(values, sorted(values))
        for value in values:
            self.assertEqual(value % 4, 0, f"{value} is off the 4dp grid")
        self.assertEqual(Spacing.scale(3), 12)

    def test_radius_scale_increases(self):
        values = [Radius.XS, Radius.SM, Radius.MD, Radius.LG, Radius.XL]
        self.assertEqual(values, sorted(values))
        self.assertGreater(Radius.PILL, Radius.XXL)

    def test_colour_maths(self):
        self.assertEqual(Colors.mix("#FF000000", "#FFFFFFFF", 0.5), "#FF808080")
        self.assertEqual(Colors.mix("#FF123456", "#FFFFFFFF", 0.0), "#FF123456")
        # Readable foreground selection.
        self.assertEqual(Colors.on("#FFFFFFFF"), Colors.TEXT)
        self.assertEqual(Colors.on("#FF111827"), Colors.WHITE)
        self.assertTrue(Colors.is_light(Colors.BACKGROUND))
        self.assertFalse(Colors.is_light("#FF0F1420"))
        # lighten/darken move in the right direction.
        self.assertTrue(Colors.is_light(Colors.lighten(Colors.PRIMARY, 0.9)))
        self.assertFalse(Colors.is_light(Colors.darken(Colors.PRIMARY, 0.9)))

    def test_with_opacity_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            Colors.with_opacity(Colors.PRIMARY, 1.5)


class TestTheming(unittest.TestCase):

    def tearDown(self):
        Theme.seed(Colors.PRIMARY)
        Theme.light()

    def test_seed_rebuilds_the_whole_palette(self):
        Theme.seed(Colors.SECONDARY)
        self.assertEqual(Theme.primary, Colors.SECONDARY)
        self.assertEqual(Theme.text, Theme.scheme.on_surface)
        self.assertEqual(Theme.outline, Theme.scheme.outline)

    def test_dark_mode_lifts_the_primary_and_keeps_the_seed(self):
        Theme.seed(Colors.PRIMARY)
        light_primary = Theme.primary
        Theme.dark()
        self.assertTrue(Theme.dark_mode)
        self.assertNotEqual(Theme.primary, light_primary)
        self.assertGreater(_brightness(Theme.primary), _brightness(light_primary),
                           "a dark theme needs a lighter primary for contrast")
        self.assertFalse(Colors.is_light(Theme.background))
        Theme.light()
        self.assertEqual(Theme.primary, light_primary)

    def test_derived_secondary_is_a_hue_rotation_not_a_channel_swap(self):
        scheme = ColorScheme.from_seed("#FF14B8A6")
        # A channel swap used to produce magenta from teal; a 38-degree
        # rotation keeps the family (teal -> blue).
        r, g, b = (int(scheme.secondary[i:i + 2], 16) for i in (3, 5, 7))
        self.assertGreater(b, r, "secondary drifted away from the seed hue")

    def test_payload_carries_the_roles_the_renderer_needs(self):
        Theme.seed(Colors.PRIMARY)
        payload = Theme.payload()
        for role in ("primary", "background", "surface", "on_surface", "dark",
                     "secondary", "surface_variant", "outline", "error"):
            self.assertIn(role, payload)
        self.assertFalse(payload["dark"])
        Theme.dark()
        self.assertTrue(Theme.payload()["dark"])


class TestResponsiveLayout(unittest.TestCase):

    def tearDown(self):
        Responsive.reset()
        MediaQuery.reset()

    def test_tablets_do_not_get_a_zoomed_in_phone_ui(self):
        Responsive.init(360, 800, 2.0)
        phone = Responsive.text(16)
        Responsive.init(1024, 768, 2.0)
        tablet = Responsive.text(16)
        self.assertGreater(tablet, phone)
        self.assertLess(tablet, phone * 1.5,
                        "text should grow gently, not with screen width")

    def test_breakpoints_match_material_window_classes(self):
        for width, expected in ((360, "compact"), (599, "compact"),
                                (600, "medium"), (839, "medium"),
                                (840, "expanded")):
            Responsive.init(width, 900, 2.0)
            self.assertEqual(Responsive.breakpoint(), expected, width)

    def test_media_query_agrees_with_responsive(self):
        Responsive.init(700, 1000, 2.0)
        MediaQuery.init(700, 1000, 2.0)
        self.assertEqual(MediaQuery.breakpoint(), Responsive.breakpoint())
        self.assertEqual(MediaQuery.is_tablet(), Responsive.is_tablet())

    def test_safe_area_is_reported(self):
        MediaQuery.init(360, 800, 2.0, padding_top=48, padding_bottom=24)
        self.assertEqual(MediaQuery.safe_area()["top"], 48)
        self.assertEqual(MediaQuery.safe_area()["bottom"], 24)


class TestWidgetDefaults(unittest.TestCase):

    def test_app_bar_follows_the_theme_and_the_touch_grid(self):
        bar = AppBar(title="Home", key="bar").to_dict()
        style = bar["style"]
        self.assertEqual(style["bg"], Theme.surface)
        self.assertEqual(style["minHeight"], 56)
        self.assertEqual(style["elevation"], 0)
        # Flat bar => hairline separator on the bottom edge only.
        self.assertEqual(style["border"]["bottom"]["width"], 1)
        self.assertEqual(style["border"]["top"]["width"], 0)

    def test_app_bar_honours_explicit_colours(self):
        bar = AppBar(title="Home", key="bar", bg_color=Colors.PRIMARY,
                     elevation=4).to_dict()
        self.assertEqual(bar["style"]["bg"], Colors.PRIMARY)
        self.assertNotIn("border", bar["style"])   # raised bars cast a shadow

    def test_button_variants_are_validated(self):
        for variant in Button.VARIANTS:
            self.assertEqual(
                Button("x", variant=variant).style["variant"], variant)
        with self.assertRaises(ValueError):
            Button("x", variant="ghost")

    def test_button_modifiers(self):
        style = Button("Save", pill=True, full_width=True, size="lg").style
        self.assertTrue(style["pill"])
        self.assertEqual(style["width"], "match")
        self.assertEqual(style["buttonSize"], "lg")

    def test_card_is_flat_and_outlined_by_default(self):
        style = Card(key="c").style
        self.assertEqual(style["elevation"], 0)
        self.assertEqual(style["bg"], Theme.surface)
        self.assertEqual(style["border"]["left"]["color"], Theme.outline)

    def test_text_field_variants(self):
        self.assertNotIn("variant", TextField().style)       # filled default
        field = TextField(variant="outlined", icon=Icons.SEARCH,
                          accent=Colors.SECONDARY)
        self.assertEqual(field.style["variant"], "outlined")
        self.assertEqual(field.style["icon"], Icons.SEARCH)
        self.assertEqual(field.style["accent"], Colors.SECONDARY)

    def test_divider_uses_theme_colour_and_indent(self):
        self.assertEqual(Divider().style["color"], Theme.outline)
        self.assertEqual(Divider(indent=56).style["margin"]["left"], 56)

    def test_border_only_marks_a_single_edge(self):
        border = Border.only(bottom=True, color=Colors.OUTLINE).to_dict()
        self.assertEqual(border["bottom"]["width"], 1)
        self.assertEqual([border[side]["width"]
                          for side in ("left", "top", "right")], [0, 0, 0])

    def test_list_tile_keeps_explicit_child_keys(self):
        """Events are addressed by key — a child key must survive."""
        tile = ListTile("Dark mode", key="tile",
                        trailing=Switch("", key="dark_switch"))
        keys = [child.key for child in tile.children]
        self.assertIn("dark_switch", keys)
        # Auto-keyed children still get a stable, derived key.
        auto = ListTile("Wi-Fi", key="wifi", trailing=Switch(""))
        self.assertEqual(auto.children[0].key, "wifi_trailing")


class TestEdgeToEdgeLayout(unittest.TestCase):
    """The widgets at the screen edges absorb the system-bar insets."""

    @staticmethod
    def slots(scaffold):
        column = scaffold.to_dict()["children"][0]
        return {child["key"]: child["style"] for child in column["children"]}

    def test_app_bar_and_bottom_nav_take_the_insets(self):
        scaffold = Scaffold(
            key="s",
            app_bar=AppBar(title="T", key="bar"),
            body=Text("x"),
            bottom_navigation=BottomNavigationBar(
                [NavItem("Home", icon=Icons.HOME)], key="nav"),
        )
        slots = self.slots(scaffold)
        self.assertTrue(slots["bar._bar"]["safeAreaTop"])
        # The bottom bar draws its own gesture inset, so it opts out of the
        # generic safe-area padding (otherwise the inset is counted twice).
        self.assertFalse(slots["nav"]["safeAreaBottom"])
        self.assertNotIn("safeAreaTop", slots["nav"])
        column = scaffold.to_dict()["children"][0]["children"]
        nav = [c for c in column if c["key"] == "nav"][0]
        self.assertTrue(nav["props"]["safeArea"])

    def test_bare_body_takes_both_insets(self):
        slots = self.slots(Scaffold(key="s", body=Text("x")))
        self.assertTrue(slots["s._body"]["safeAreaTop"])
        self.assertTrue(slots["s._body"]["safeAreaBottom"])

    def test_safe_area_can_be_switched_off(self):
        slots = self.slots(Scaffold(key="s", body=Text("x"), safe_area=False))
        self.assertNotIn("safeAreaTop", slots["s._body"])

    def test_native_layer_reapplies_insets(self):
        from tests import all_java_templates
        factory = all_java_templates()
        self.assertIn("refreshInsets", factory)
        self.assertIn("safeAreaTop", factory)
        activity = template("MainActivity.java.j2")
        self.assertIn("PydrudTheme.setInsets", activity)
        self.assertIn("viewFactory.refreshInsets()", activity)


class TestGeneratedNativeLayer(unittest.TestCase):
    """Guarantees about the Java the scaffolder writes."""

    def test_every_icon_constant_resolves_in_the_vector_set(self):
        icons = template("PydrudIcons.java.j2")
        known = set(re.findall(r'PATHS\.put\("([a-z0-9_]+)"', icons))
        known |= set(re.findall(r'ALIASES\.put\("([a-z0-9_]+)"', icons))
        # Only the constants Pydrud ships must resolve here: icons registered
        # at runtime from optional packs (Icons.load_pack) deliberately have
        # no vector in the generated template.
        missing = [name for name in Icons.builtins() if name not in known]
        self.assertEqual(missing, [], "Icons constants without vector paths")

    def test_renderers_use_theme_roles_not_hardcoded_colours(self):
        """A stray hex literal is a widget that ignores dark mode."""
        pattern = re.compile(r'"#[0-9A-Fa-f]{6,8}"|0xFF[0-9A-Fa-f]{6}')
        allowed = {
            "0xFFFFFFFF", "0xFF000000", "0xFF111827",   # neutral extremes
            "0xFFF59E0B",                               # rating star accent
            "0xFF9BA6B8", "0xFFB91C1C",                 # dark hint, fatal red
        }
        for name in ("ViewFactory.java.j2", "MaterialViews.java.j2",
                     "AdvancedViews.java.j2", "BuiltinViews.java.j2",
                     "ViewStyler.java.j2", "LayoutEngine.java.j2",
                     "TreePatcher.java.j2", "EventBinder.java.j2",
                     "NativeViewFactory.java.j2", "ViewAnimator.java.j2",
                     "ImageLoader.java.j2"):
            found = {m for m in pattern.findall(template(name))} - allowed
            self.assertEqual(found, set(), f"{name} hardcodes colours")

    def test_theme_command_is_handled_by_the_bridge(self):
        bridge = template("BridgeService.java.j2")
        self.assertIn('case "theme":', bridge)
        self.assertIn("applyTheme", bridge)

    def test_activity_initialises_the_design_system_first(self):
        activity = template("MainActivity.java.j2")
        self.assertIn("PydrudTheme.init(this)", activity)
        self.assertIn("applySystemBarAppearance", activity)

    def test_themes_xml_ships_a_night_variant(self):
        themes = template("themes.xml.j2")
        self.assertIn("Theme.Material3.Dark.NoActionBar", themes)
        self.assertIn("Theme.Material3.Light.NoActionBar", themes)
        self.assertIn("android:windowLightStatusBar", themes)


class TestProjectSync(unittest.TestCase):
    """``pydrud sync`` upgrades an existing project in place."""

    @classmethod
    def setUpClass(cls):
        from pydrud.commands.project import create_project

        cls.tmp = tempfile.mkdtemp(prefix="pydrud-sync-")
        cls.cwd = os.getcwd()
        os.chdir(cls.tmp)
        create_project("sync_app", org="com.example", runtime="chaquopy")
        cls.project = os.path.join(cls.tmp, "sync_app")

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls.cwd)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def java(self, name: str) -> str:
        return os.path.join(self.project, "android", "app", "src", "main",
                            "java", "com", "example", "sync_app", name)

    def test_scaffold_includes_the_design_system(self):
        for name in ("PydrudTheme.java", "PydrudIcons.java"):
            self.assertTrue(os.path.isfile(self.java(name)), name)
        night = os.path.join(self.project, "android", "app", "src", "main",
                             "res", "values-night", "themes.xml")
        self.assertTrue(os.path.isfile(night))

    def test_sync_restores_and_rewrites_the_native_layer(self):
        from pydrud.commands.project import sync_project

        theme = self.java("PydrudTheme.java")
        os.remove(theme)
        activity = self.java("SyncAppActivity.java")
        with open(activity, "w", encoding="utf-8") as fh:
            fh.write("// stale\n")

        self.assertTrue(sync_project(self.project, update_runtime=False))
        self.assertTrue(os.path.isfile(theme))
        with open(activity, encoding="utf-8") as fh:
            self.assertIn("PydrudTheme.init(this)", fh.read())

    def test_sync_leaves_app_code_alone(self):
        from pydrud.commands.project import sync_project

        main = os.path.join(self.project, "src", "app", "main.py")
        with open(main, "a", encoding="utf-8") as fh:
            fh.write("\n# my own code\n")
        sync_project(self.project, update_runtime=False)
        with open(main, encoding="utf-8") as fh:
            self.assertIn("# my own code", fh.read())


class TestPythonControlledTokens(unittest.TestCase):
    """Every visual constant is owned by Python, not by Java or XML."""

    def tearDown(self):
        Tokens.reset()
        Theme.seed(Colors.PRIMARY)
        Theme.light()

    def test_configure_updates_tokens_and_rejects_typos(self):
        Theme.configure(radius_card=28, app_bar_height=64)
        self.assertEqual(Tokens.radius_card, 28)
        self.assertEqual(Tokens.app_bar_height, 64)
        with self.assertRaises(ValueError) as caught:
            Theme.configure(radius_crd=4)
        self.assertIn("radius_card", str(caught.exception))   # suggestion

    def test_configure_accepts_colours_too(self):
        Theme.configure(primary="#FF0EA5E9", radius_button=20)
        self.assertEqual(Theme.primary, "#FF0EA5E9")
        self.assertEqual(Tokens.radius_button, 20)

    def test_widgets_follow_the_tokens(self):
        Theme.configure(radius_card=30, card_padding=24,
                        divider_thickness=2, fab_size=72)
        self.assertEqual(Card(child=None).style["borderRadius"], 30)
        self.assertEqual(Card(child=None).style["padding"]["left"], 24)
        self.assertEqual(Divider().style["thickness"], 2)
        self.assertEqual(
            FloatingActionButton(icon=Icons.ADD).style["width"], 72)
        self.assertEqual(
            AppBar(title="T").to_dict()["style"]["minHeight"], 56)
        Theme.configure(app_bar_height=72)
        self.assertEqual(
            AppBar(title="T").to_dict()["style"]["minHeight"], 72)

    def test_tokens_travel_in_the_theme_payload(self):
        Theme.configure(radius_card=18, font_family="serif", font_scale=1.1)
        tokens = Theme.payload()["tokens"]
        self.assertEqual(tokens["radius_card"], 18)
        self.assertEqual(tokens["font_family"], "serif")
        self.assertEqual(tokens["font_scale"], 1.1)
        # The payload is JSON — no Python objects may leak into it.
        json.dumps(Theme.payload())

    def test_every_python_token_is_read_by_the_native_layer(self):
        """A token Java ignores is a token the user cannot actually set."""
        theme = template("PydrudTheme.java.j2")
        missing = [name for name in Tokens.names()
                   if f'"{name}"' not in theme]
        self.assertEqual(missing, [], f"not applied on device: {missing}")

    def test_renderers_read_metrics_from_the_theme(self):
        from tests import all_java_templates
        factory = all_java_templates()
        for field in ("PydrudTheme.radiusCard", "PydrudTheme.radiusButton",
                      "PydrudTheme.radiusInput", "PydrudTheme.inputHeight",
                      "PydrudTheme.buttonHeightMd", "PydrudTheme.elevationFab",
                      "PydrudTheme.rippleOpacity", "PydrudTheme.pressScale"):
            self.assertIn(field, factory)
        material = (template("MaterialViews.java.j2")
                    + template("MaterialNavigationViews.java.j2"))
        for field in ("PydrudTheme.listTileHeight", "PydrudTheme.avatarSize",
                      "PydrudTheme.iconSize"):
            self.assertIn(field, material)

    def test_theme_apply_parses_the_token_object(self):
        theme = template("PydrudTheme.java.j2")
        self.assertIn('applyTokens(scheme.optJSONObject("tokens"))', theme)
        self.assertIn("public static void applyTokens(JSONObject t)", theme)

    def test_reset_restores_the_shipped_defaults(self):
        original = Tokens.radius_card
        Theme.configure(radius_card=original + 10)
        Theme.configure_reset()
        self.assertEqual(Tokens.radius_card, original)
        self.assertEqual(Tokens.changed(), {})


class TestGeneratedThemeResources(unittest.TestCase):
    """themes.xml is generated from the Python palette, not hand-written."""

    def test_xml_palette_comes_from_the_colour_scheme(self):
        from pydrud.commands.project import _theme_colors

        colors = _theme_colors("#FF0EA5E9")
        self.assertEqual(colors["light"]["primary"], "#FF0EA5E9")
        # Dark lifts the brand colour instead of repeating it.
        self.assertNotEqual(colors["dark"]["primary"], colors["light"]["primary"])
        self.assertGreater(_brightness(colors["dark"]["primary"]),
                           _brightness(colors["light"]["primary"]))
        for variant in ("light", "dark"):
            for role in ("primary", "surface", "on_surface", "outline",
                         "background", "error", "hint"):
                self.assertRegex(colors[variant][role], r"^#[0-9A-F]{8}$")

    def test_theme_template_has_no_hardcoded_colours(self):
        xml = template("themes.xml.j2")
        self.assertNotRegex(xml, r"<item[^>]*>#[0-9A-Fa-f]{6,8}<")
        self.assertIn("{{ colors.primary }}", xml)

    def test_accent_flag_is_normalised(self):
        from pydrud.commands.project import _normalise_color

        self.assertEqual(_normalise_color("#0EA5E9"), "#FF0EA5E9")
        self.assertEqual(_normalise_color("0ea5e9"), "#FF0EA5E9")
        self.assertEqual(_normalise_color("#FF0EA5E9"), "#FF0EA5E9")
        self.assertIsNone(_normalise_color(None))
        with self.assertRaises(ValueError):
            _normalise_color("salmon")


class TestFloatingActionButtonPlacement(unittest.TestCase):
    """Floating action button placement within Scaffold."""

    def setUp(self):
        # Reset any global state that might leak from other test files
        from pydrud.core.responsive import MediaQuery, Breakpoints, Responsive
        MediaQuery.reset()
        MediaQuery.clear_listeners()
        Breakpoints.reset()
        Responsive.configure_reset()

    def test_fab_clears_a_bottom_navigation_bar(self):
        from pydrud import BottomNavigationBar, NavItem, Scaffold, Text

        scaffold = Scaffold(
            key="s", body=Text("x"),
            bottom_navigation=BottomNavigationBar(
                [NavItem("Home", icon=Icons.HOME)], key="nav"),
            floating_action_button=FloatingActionButton(
                icon=Icons.ADD, key="fab"),
        )
        fab = [c for c in scaffold.to_dict()["children"]
               if c["key"] == "fab"][0]
        self.assertEqual(fab["style"]["bottom"], 24 + Tokens.nav_height)
        # FAB sits above the bar and clears the bottom navigation area
        self.assertTrue(fab["style"].get("safeAreaBottom", True))

    def test_fab_positions_start_and_center(self):
        from pydrud import BottomNavigationBar, NavItem, Scaffold, Text

        scaffold_start = Scaffold(
            key="s1", body=Text("x"),
            fab_position="bottom_start",
            bottom_navigation=BottomNavigationBar(
                [NavItem("Home", icon=Icons.HOME)], key="nav"),
            floating_action_button=FloatingActionButton(
                icon=Icons.ADD, key="fab"),
        )
        fab_start = [c for c in scaffold_start.to_dict()["children"] if c["key"] == "fab"][0]
        self.assertEqual(fab_start["style"].get("left"), 24)
        self.assertNotIn("right", fab_start["style"])

        scaffold_center = Scaffold(
            key="s2", body=Text("x"),
            fab_position="bottom_center",
            bottom_navigation=BottomNavigationBar(
                [NavItem("Home", icon=Icons.HOME)], key="nav"),
            floating_action_button=FloatingActionButton(
                icon=Icons.ADD, key="fab"),
        )
        fab_center = [c for c in scaffold_center.to_dict()["children"] if c["key"] == "fab"][0]
        self.assertEqual(fab_center["style"].get("alignment"), "bottomCenter")
        self.assertNotIn("right", fab_center["style"])
        self.assertNotIn("left", fab_center["style"])

    def test_tabs_effective_height(self):
        from pydrud import Tab, Tabs, Text
        tabs = Tabs([Tab("Tab 1", content=Text("1")), Tab("Tab 2", content=Text("2"))], tab_height=48)
        self.assertEqual(tabs.effective_height, 48)

    def test_container_border_property(self):
        from pydrud import Border, Container, Text
        c1 = Container(child=Text("a"), border=Border("#FF0000", 2))
        self.assertEqual(c1.style["border"]["left"]["color"], "#FF0000")
        self.assertEqual(c1.style["border"]["left"]["width"], 2)

        c2 = Container(child=Text("b"), border={"color": "#00FF00", "width": 1})
        self.assertEqual(c2.style["border"]["color"], "#00FF00")

    def test_fab_keeps_its_offset_without_a_bar(self):
        from pydrud import Scaffold, Text

        scaffold = Scaffold(key="s", body=Text("x"),
                            floating_action_button=FloatingActionButton(
                                icon=Icons.ADD, key="fab"))
        fab = [c for c in scaffold.to_dict()["children"]
               if c["key"] == "fab"][0]
        self.assertEqual(fab["style"]["bottom"], 24)


if __name__ == "__main__":
    unittest.main()
