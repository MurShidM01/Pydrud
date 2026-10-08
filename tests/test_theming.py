"""Theming parity with Flutter: scoped overrides, text roles, extensions.

PYDRUD §10: Pydrud resolved every theme value at build time, so the only
way to restyle a subtree was to mutate the globals and remember to undo
them. These tests pin the three ergonomic additions that close the gap —
``Theme.scope`` (Flutter's ``Theme(data: …)``), ``TextTheme`` (the
Material 3 type scale) and ``ThemeExtension`` (named custom tokens) — plus
the runtime light/dark switch that was already wired through
``page.set_theme_mode``.
"""

from __future__ import annotations

import unittest

from pydrud import (
    Text,
    TextTheme,
    Theme,
    ThemeExtension,
    Tokens,
)
from pydrud.testing import AppTester

#: Captured once so a failed test can always put the globals back.
_DEFAULT_PRIMARY = Theme.primary
_DEFAULT_RADIUS_CARD = Tokens.radius_card
_DEFAULT_DARK = Theme.dark_mode


class _RestoresTheme(unittest.TestCase):
    """Every test starts and ends on the shipped palette."""

    def setUp(self):
        Theme.light()
        Theme._extensions.clear()

    def tearDown(self):
        Theme.light() if not _DEFAULT_DARK else Theme.dark()
        Theme._extensions.clear()
        Theme.configure_reset()


class TestThemeScope(_RestoresTheme):

    def test_scope_overrides_a_colour_role(self):
        with Theme.scope(primary="#FFEC4899"):
            self.assertEqual(Theme.primary, "#FFEC4899")
        self.assertEqual(Theme.primary, _DEFAULT_PRIMARY)

    def test_scope_overrides_a_design_token(self):
        with Theme.scope(radius_card=4):
            self.assertEqual(Tokens.radius_card, 4)
        self.assertEqual(Tokens.radius_card, _DEFAULT_RADIUS_CARD)

    def test_scope_accepts_roles_and_tokens_together(self):
        with Theme.scope(primary="#FF22D3EE", radius_card=2):
            self.assertEqual(Theme.primary, "#FF22D3EE")
            self.assertEqual(Tokens.radius_card, 2)
        self.assertEqual(Theme.primary, _DEFAULT_PRIMARY)
        self.assertEqual(Tokens.radius_card, _DEFAULT_RADIUS_CARD)

    def test_scope_yields_the_theme_class(self):
        with Theme.scope(primary="#FF000000") as theme:
            self.assertIs(theme, Theme)

    def test_scope_restores_after_an_exception(self):
        with self.assertRaises(RuntimeError):
            with Theme.scope(primary="#FF111111"):
                raise RuntimeError("boom")
        self.assertEqual(Theme.primary, _DEFAULT_PRIMARY)

    def test_nested_scopes_restore_in_order(self):
        with Theme.scope(primary="#FF111111"):
            self.assertEqual(Theme.primary, "#FF111111")
            with Theme.scope(primary="#FF222222"):
                self.assertEqual(Theme.primary, "#FF222222")
            self.assertEqual(Theme.primary, "#FF111111")
        self.assertEqual(Theme.primary, _DEFAULT_PRIMARY)

    def test_nested_scope_restores_tokens_it_did_not_touch(self):
        with Theme.scope(radius_card=2):
            with Theme.scope(primary="#FF333333"):
                self.assertEqual(Tokens.radius_card, 2)
            self.assertEqual(Tokens.radius_card, 2)
        self.assertEqual(Tokens.radius_card, _DEFAULT_RADIUS_CARD)

    def test_a_widget_built_inside_the_scope_captures_the_value(self):
        with Theme.scope(primary="#FFEC4899"):
            inside = Text("x", color=Theme.primary).to_dict()
        after = Text("x", color=Theme.primary).to_dict()
        self.assertEqual(inside["style"]["font"]["color"], "#FFEC4899")
        self.assertEqual(after["style"]["font"]["color"], _DEFAULT_PRIMARY)


class TestTextTheme(_RestoresTheme):

    #: The full Material 3 type scale, in role order.
    ROLES = (
        "display_large", "display_medium", "display_small",
        "headline_large", "headline_medium", "headline_small",
        "title_large", "title_medium", "title_small",
        "body_large", "body_medium", "body_small",
        "label_large", "label_medium", "label_small",
    )

    def test_every_role_resolves_in_all_three_spellings(self):
        for role in self.ROLES:
            with self.subTest(role=role):
                snake = getattr(TextTheme, role)
                upper = getattr(TextTheme, role.upper())
                camel = getattr(TextTheme, _camel(role))
                self.assertEqual(snake, upper)
                self.assertEqual(snake, camel)

    def test_every_role_carries_a_font_size_and_weight(self):
        for role in self.ROLES:
            with self.subTest(role=role):
                style = getattr(TextTheme, role)
                self.assertIn("size", style["font"])
                self.assertIn("weight", style["font"])

    def test_display_large_is_the_largest_and_label_small_the_smallest(self):
        self.assertGreater(TextTheme.display_large["font"]["size"],
                           TextTheme.label_small["font"]["size"])

    def test_a_text_accepts_a_role_directly(self):
        style = Text("Hi", style=TextTheme.title_large).to_dict()["style"]
        self.assertEqual(style["font"]["size"], 22)
        self.assertEqual(style["font"]["weight"], 500)

    def test_with_refines_a_role_without_mutating_it(self):
        base = TextTheme.body_medium
        tinted = base.with_(color="#FF0000")
        self.assertEqual(tinted["font"]["color"], "#FF0000")
        self.assertNotIn("color", base["font"])
        self.assertEqual(tinted["font"]["size"], base["font"]["size"])

    def test_size_and_weight_are_readable_as_attributes(self):
        self.assertEqual(TextTheme.headline_medium.size, 28)
        self.assertEqual(TextTheme.headline_medium.weight, 500)

    def test_unknown_role_names_the_available_ones(self):
        with self.assertRaises(AttributeError) as caught:
            TextTheme.title_huge  # noqa: B018
        self.assertIn("title_large", str(caught.exception))

    def test_dunder_lookups_do_not_explode(self):
        self.assertFalse(hasattr(TextTheme, "__not_a_role__"))


class TestThemeExtension(_RestoresTheme):

    def test_values_are_readable_as_attributes(self):
        brand = ThemeExtension("brand", accent="#FF22D3EE", hero_radius=28)
        self.assertEqual(brand.accent, "#FF22D3EE")
        self.assertEqual(brand.hero_radius, 28)

    def test_get_supplies_a_default(self):
        brand = ThemeExtension("brand", accent="#FF22D3EE")
        self.assertEqual(brand.get("accent"), "#FF22D3EE")
        self.assertIsNone(brand.get("missing"))
        self.assertEqual(brand.get("missing", 5), 5)

    def test_unknown_value_raises_with_the_available_names(self):
        brand = ThemeExtension("brand", accent="#FF22D3EE")
        with self.assertRaises(AttributeError) as caught:
            brand.hue  # noqa: B018
        self.assertIn("accent", str(caught.exception))

    def test_replace_copies_without_mutating_the_original(self):
        brand = ThemeExtension("brand", hero_radius=28)
        tighter = brand.replace(hero_radius=8)
        self.assertEqual(tighter.hero_radius, 8)
        self.assertEqual(brand.hero_radius, 28)
        self.assertEqual(tighter.name, "brand")

    def test_as_dict_is_a_copy(self):
        brand = ThemeExtension("brand", accent="#FF22D3EE")
        snapshot = brand.as_dict()
        snapshot["accent"] = "#FF000000"
        self.assertEqual(brand.accent, "#FF22D3EE")

    def test_repr_shows_the_name(self):
        self.assertIn("brand", repr(ThemeExtension("brand", accent="#FF22D3EE")))

    def test_a_name_must_be_an_identifier(self):
        with self.assertRaises(ValueError):
            ThemeExtension("bad name", x=1)
        with self.assertRaises(ValueError):
            ThemeExtension("1brand", x=1)

    def test_extend_registers_and_returns_the_extension(self):
        brand = ThemeExtension("brand", accent="#FF22D3EE")
        self.assertIs(Theme.extend(brand), brand)
        self.assertIs(Theme.extension("brand"), brand)

    def test_extensions_lists_everything_registered(self):
        Theme.extend(ThemeExtension("brand", accent="#FF22D3EE"))
        Theme.extend(ThemeExtension("layout", hero_radius=28))
        self.assertEqual(set(Theme.extensions()), {"brand", "layout"})

    def test_unknown_extension_raises_with_the_registered_names(self):
        Theme.extend(ThemeExtension("brand", accent="#FF22D3EE"))
        with self.assertRaises(KeyError) as caught:
            Theme.extension("nope")
        self.assertIn("brand", str(caught.exception))

    def test_an_extension_can_drive_a_widget(self):
        Theme.extend(ThemeExtension("brand", accent="#FF22D3EE"))
        brand = Theme.extension("brand")
        color = Text("x", color=brand.accent).to_dict()["style"]["font"]["color"]
        self.assertEqual(color, "#FF22D3EE")


class TestRuntimeThemeMode(_RestoresTheme):

    def test_set_theme_mode_flips_the_palette_at_runtime(self):
        def main(page):
            page.add(Text("hi", key="t"))

        with AppTester(main) as app:
            app.app.page.set_theme_mode("dark")
            app.settle()
            self.assertTrue(Theme.dark_mode)
            self.assertEqual(app.app.page.theme_mode, "dark")
            self.assertEqual(Theme.background, "#FF111827")

    def test_set_theme_mode_rejects_an_unknown_mode(self):
        def main(page):
            page.add(Text("hi", key="t"))

        with AppTester(main) as app:
            with self.assertRaises(ValueError):
                app.app.page.set_theme_mode("neon")

    def test_system_mode_is_the_default(self):
        def main(page):
            page.add(Text("hi", key="t"))

        with AppTester(main) as app:
            self.assertEqual(app.app.page.theme_mode, "system")

    def test_system_mode_adopts_a_dark_device(self):
        def main(page):
            page.add(Text("hi", key="t"))

        with AppTester(main, dark=True) as app:
            self.assertEqual(app.app.page.theme_mode, "system")
            self.assertTrue(Theme.dark_mode)
            self.assertEqual(Theme.background, "#FF111827")

    def test_system_mode_stays_light_on_a_light_device(self):
        def main(page):
            page.add(Text("hi", key="t"))

        with AppTester(main, dark=False):
            self.assertFalse(Theme.dark_mode)

    def test_a_light_page_ignores_a_dark_device(self):
        def main(page):
            page.theme_mode = "light"
            page.add(Text("hi", key="t"))

        with AppTester(main, dark=True):
            self.assertFalse(Theme.dark_mode)

    def test_toggling_the_system_setting_recolours_a_system_page(self):
        def main(page):
            page.add(Text("hi", key="t"))

        with AppTester(main, dark=False) as app:
            self.assertFalse(Theme.dark_mode)
            app.set_dark(True)
            self.assertTrue(Theme.dark_mode)
            self.assertEqual(Theme.background, "#FF111827")
            app.set_dark(False)
            self.assertFalse(Theme.dark_mode)

    def test_switching_to_system_adopts_the_device_immediately(self):
        def main(page):
            page.theme_mode = "light"
            page.add(Text("hi", key="t"))

        with AppTester(main, dark=True) as app:
            self.assertFalse(Theme.dark_mode)
            app.app.page.set_theme_mode("system")
            app.settle()
            self.assertTrue(Theme.dark_mode)


class TestColorSchemeLerp(unittest.TestCase):
    """`ColorScheme.lerp` is the frame between two palettes."""

    def _schemes(self):
        from pydrud.widgets.theme.colors import ColorScheme

        light = ColorScheme.from_seed("#FF6366F1", dark=False)
        dark = ColorScheme.from_seed("#FF6366F1", dark=True)
        return ColorScheme, light, dark

    def test_endpoints_are_exact(self):
        Scheme, light, dark = self._schemes()
        self.assertEqual(Scheme.lerp(light, dark, 0.0).surface, light.surface)
        self.assertEqual(Scheme.lerp(light, dark, 1.0).surface, dark.surface)

    def test_midpoint_is_between_the_endpoints(self):
        Scheme, light, dark = self._schemes()
        mid = Scheme.lerp(light, dark, 0.5)
        for channel in ("surface", "primary", "background"):
            self.assertNotEqual(getattr(mid, channel),
                                getattr(light, channel))
            self.assertNotEqual(getattr(mid, channel),
                                getattr(dark, channel))

    def test_fraction_is_clamped(self):
        Scheme, light, dark = self._schemes()
        self.assertEqual(Scheme.lerp(light, dark, -3.0).surface, light.surface)
        self.assertEqual(Scheme.lerp(light, dark, 9.0).surface, dark.surface)

    def test_dark_flag_flips_past_the_midpoint(self):
        Scheme, light, dark = self._schemes()
        self.assertFalse(Scheme.lerp(light, dark, 0.2).dark)
        self.assertTrue(Scheme.lerp(light, dark, 0.8).dark)


class TestAnimatedTheme(_RestoresTheme):

    def _await(self, predicate, timeout: float = 3.0) -> bool:
        import time

        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return True
            time.sleep(0.01)
        return False

    def _await_theme_settled(self, app, before: int,
                             timeout: float = 3.0) -> int:
        """Wait until the palette stream stops growing; return how many."""
        import time

        deadline = time.time() + timeout
        last, stable = -1, 0
        while time.time() < deadline:
            count = len(app.device.commands_named("theme")) - before
            if count == last and count > 0:
                stable += 1
                if stable >= 4:
                    return count
            else:
                stable = 0
            last = count
            time.sleep(0.02)
        return max(last, 0)

    def test_animated_mode_change_lands_on_the_target(self):
        def main(page):
            page.add(Text("hi", key="t"))

        with AppTester(main) as app:
            before = len(app.device.commands_named("theme"))
            app.app.page.set_theme_mode("dark", animate=True, duration=120)
            self._await_theme_settled(app, before)
            self.assertTrue(Theme.dark_mode)
            self.assertEqual(Theme.background, "#FF111827")

    def test_animation_sends_intermediate_palettes(self):
        def main(page):
            page.add(Text("hi", key="t"))

        with AppTester(main) as app:
            before = len(app.device.commands_named("theme"))
            app.app.page.set_theme_mode("dark", animate=True, duration=200)
            # Wait until more than the single final push has arrived.
            self.assertTrue(self._await(
                lambda: len(app.device.commands_named("theme")) - before > 1),
                "an animated change should push >1 palette")

    def test_a_non_animated_change_sends_a_single_palette(self):
        def main(page):
            page.add(Text("hi", key="t"))

        with AppTester(main) as app:
            before = len(app.device.commands_named("theme"))
            app.app.page.set_theme_mode("dark")
            app.settle()
            self.assertEqual(len(app.device.commands_named("theme")) - before, 1)

    def test_animated_seed_change_glides_to_the_new_brand(self):
        def main(page):
            page.add(Text("hi", key="t"))

        with AppTester(main) as app:
            from pydrud import Colors
            from pydrud.widgets.theme.colors import ColorScheme

            expected = ColorScheme.from_seed(Colors.TEAL, dark=False).primary
            before = len(app.device.commands_named("theme"))
            app.app.page.set_theme(Colors.TEAL, animate=True, duration=120)
            self._await_theme_settled(app, before)
            self.assertEqual(Theme.primary, expected)


def _camel(role: str) -> str:
    head, _, tail = role.partition("_")
    return head + tail.title()


if __name__ == "__main__":
    unittest.main()
