"""Every Material 3 component must render something real.

GAP #7 from the Material 3 audit.  Seven of the components added in 2.1.5
were placeholders: the pickers painted a ``TextView`` reading "Date Picker"
in a 200dp box, ``ButtonGroup`` / ``SplitButton`` / ``Toolbar`` returned an
empty ``FrameLayout``, and ``StandardBottomSheet`` / ``SideSheet`` /
``FullScreenDialog`` were routed to ``buildAlertDialog`` — so asking for a
side sheet got you an alert dialog.

Those factories are now real. These tests hold the line: they drive the
templates the way the build does, render every Java file, and assert each
component has a factory that draws something, that no factory is a
placeholder, and that the dispatch table has no holes.
"""

from __future__ import annotations

import pathlib
import re
import unittest

import jinja2

TEMPLATE_DIR = (
    pathlib.Path(__file__).resolve().parent.parent
    / "pydrud" / "android" / "templates" / "android"
)

#: Context sufficient to render every template in the android directory.
RENDER_CONTEXT = {
    "package": "com.example.app",
    "android_package": "com.example.app",
    "app_id": "com.example.app",
    "app_name": "Demo",
    "project_name": "Demo",
    "label": "Demo",
    "min_sdk": 24,
    "target_sdk": 34,
    "version_name": "2.1.5",
    "version_code": 21,
    "runtime": "chaquopy",
    "bridge_port": 8765,
    "python_version": "3.11",
    "pydrud_import": "pydrud",
    "deep_link_scheme": "demo",
    "theme_mode": "light",
    "permissions": [],
    "uses_cleartext": False,
    "splash": False,
    "icon": None,
    "entry_point": "app.py",
    "include_icons": True,
    "has_camera": False,
    "has_firebase": False,
}

#: The seven components that used to be placeholders, with the factory each
#: one must now have. A tuple means the factory returns a Dialog.
REAL_FACTORIES = {
    "DatePicker": "createDatePicker",
    "DateRangePicker": "createDateRangePicker",
    "TimePicker": "createTimePicker",
    "StandardBottomSheet": "createStandardBottomSheet",
    "SideSheet": "createSideSheet",
    "FullScreenDialog": "createFullScreenDialog",
    "ButtonGroup": "createButtonGroup",
    "SplitButton": "createSplitButton",
    "Toolbar": "createToolbar",
}


def _render(name: str) -> str:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)), keep_trailing_newline=True
    )
    return env.get_template(name).render(**RENDER_CONTEXT)


class TestNoPlaceholderFactories(unittest.TestCase):
    """The audit's specific complaints must not come back."""

    @classmethod
    def setUpClass(cls):
        cls.material = _render("MaterialViews.java.j2")

    def test_picker_placeholder_text_is_gone(self):
        """No component may render its own name as a label."""
        for gone in ('"Date Picker"', '"Time Picker"', 'pickerType + " Picker"'):
            self.assertNotIn(
                gone, self.material, f"placeholder label {gone} is back"
            )

    def test_every_new_component_has_a_dedicated_factory(self):
        for widget, factory in REAL_FACTORIES.items():
            self.assertRegex(
                self.material,
                r"(View|Dialog)\s+" + factory + r"\s*\(",
                f"{widget} needs a real {factory}()",
            )

    def test_every_new_component_is_in_the_dispatch_table(self):
        for widget in REAL_FACTORIES:
            self.assertRegex(
                self.material,
                r'case\s+"' + widget + r'"',
                f"{widget} is missing from the dispatch switch",
            )

    def test_sheets_are_not_routed_to_alert_dialog(self):
        """Sheets must not fall through to the dialog builder."""
        switch = self.material[self.material.index("public View create("):]
        switch = switch[: switch.index("private View createListTile")]
        for widget in ("StandardBottomSheet", "SideSheet", "FullScreenDialog"):
            line = re.search(
                r'case\s+"' + widget + r'":\s*(.+)', switch
            )
            self.assertIsNotNone(line, f"{widget} has no dispatch case")
            target = line.group(1)
            self.assertNotIn(
                "createOverlay",
                target,
                f"{widget} must not be routed through createOverlay",
            )
            self.assertNotIn(
                "buildAlertDialog",
                target,
                f"{widget} must not be an alert dialog",
            )

    #: Factories that legitimately delegate to a shared builder.
    DELEGATES = {
        "createDatePicker": "pickerHost",
        "createTimePicker": "pickerHost",
        "createDateRangePicker": "pickerHost",
    }

    def test_no_factory_returns_a_bare_empty_frame(self):
        """The old stubs were literally ``new FrameLayout(activity)``."""
        for widget, factory in REAL_FACTORIES.items():
            body = self._method_body(factory)
            delegate = self.DELEGATES.get(factory)
            if delegate:
                # A thin delegation is fine as long as the shared builder it
                # delegates to is itself substantial.
                self.assertIn(delegate, body, f"{factory} must call {delegate}")
                for builder in ("buildMaterialDatePicker",
                                "buildMaterialTimePicker"):
                    self.assertGreater(
                        len(self._method_body(builder).splitlines()), 12,
                        f"{builder} looks like a stub")
                continue
            self.assertGreater(
                len(body.splitlines()),
                6,
                f"{factory} looks like a stub ({len(body.splitlines())} lines)",
            )

    def test_wrapper_fallback_logs_unknown_types(self):
        """An unknown type must not silently render nothing."""
        self.assertIn("lastUnhandledType", self.material)
        self.assertIn("no factory for widget type", self.material)
        self.assertIn("KNOWN_WRAPPERS", self.material)

    def _method_body(self, name: str) -> str:
        """Extract a method body by brace matching."""
        match = re.search(
            r"(?:private|public|static|\s)*[A-Za-z_][\w.]*(?:<[^>]*>)?\s+"
            + name
            + r"\s*\([^)]*\)\s*\{",
            self.material,
        )
        self.assertIsNotNone(match, f"{name} not found")
        start = match.end()
        depth, index = 1, start
        while index < len(self.material) and depth:
            if self.material[index] == "{":
                depth += 1
            elif self.material[index] == "}":
                depth -= 1
            index += 1
        return self.material[start:index]


class TestMaterialComponentsAreReal(unittest.TestCase):
    """The implementations must use the M3 building blocks, not hand-rolled ones."""

    @classmethod
    def setUpClass(cls):
        cls.material = _render("MaterialViews.java.j2")
        cls.theme = _render("PydrudTheme.java.j2")

    def test_date_picker_uses_material_date_picker(self):
        self.assertIn("MaterialDatePicker", self.material)
        self.assertIn("datePicker()", self.material)
        self.assertIn("dateRangePicker()", self.material)

    def test_time_picker_uses_material_time_picker(self):
        self.assertIn("MaterialTimePicker", self.material)
        self.assertIn("TimeFormat.CLOCK_24H", self.material)

    def test_pickers_have_a_fallback_when_material_is_missing(self):
        """A missing Material class must not take the app down."""
        self.assertIn("buildFallbackDateDialog", self.material)
        self.assertIn("buildFallbackTimeDialog", self.material)
        self.assertIn("DatePickerDialog", self.material)
        self.assertIn("TimePickerDialog", self.material)

    def test_pickers_report_their_selection(self):
        for event in ('"change"', '"cancel"'):
            self.assertIn(event, self.material)

    def test_pickers_are_modally_hosted_and_torn_down(self):
        """Attaching opens the dialog; detaching dismisses it."""
        self.assertIn("onViewAttachedToWindow", self.material)
        self.assertIn("onViewDetachedFromWindow", self.material)

    def test_side_sheet_is_single_sided_rounding(self):
        self.assertIn("sideRoundedShape", self.theme)
        self.assertIn("sideRoundedShape", self.material)

    def test_bottom_sheet_is_top_rounded(self):
        self.assertIn("topRoundedShape", self.theme)
        self.assertIn("topRoundedShape", self.material)

    def test_full_screen_dialog_is_full_screen(self):
        body = self.material[
            self.material.index("private android.app.Dialog buildFullScreenDialog"):
        ]
        body = body[: body.index("\n    /**", 10)]
        self.assertIn("MATCH_PARENT", body)

    def test_button_group_shares_one_silhouette(self):
        """Segments must be restyled as they arrive, not left as plain buttons."""
        self.assertIn("setCornerRadii", self.material)
        self.assertIn("applySegmentShapes", self.material)
        self.assertIn("pydrud-divider", self.material)

    def test_split_button_builds_a_menu_from_menu_items(self):
        self.assertIn("menuItems", self.material)
        self.assertIn("PopupMenu", self.material)

    def test_toolbar_uses_the_toolbar_tokens(self):
        self.assertIn("radiusToolbar", self.theme)
        self.assertIn("toolbarHeight", self.theme)
        self.assertIn("radiusToolbar", self.material)
        self.assertIn("toolbarHeight", self.material)

    def test_full_m3_role_set_is_loaded_from_the_scheme(self):
        """Components reach for the role the spec names."""
        for role in (
            "surfaceContainerLow", "surfaceContainerHigh", "surfaceContainerHighest",
            "surfaceDim", "surfaceBright", "secondaryContainer",
            "onSecondaryContainer", "tertiaryContainer", "onTertiaryContainer",
            "errorContainer", "onErrorContainer", "outlineVariant",
            "inverseSurface", "inverseOnSurface", "inversePrimary", "surfaceTint",
        ):
            self.assertIn(role, self.theme, f"{role} missing from PydrudTheme")
        for role in (
            "surface_container_low", "surface_container_high",
            "surface_container_highest", "surface_dim", "secondary_container",
            "on_secondary_container", "outline_variant", "inverse_surface",
        ):
            self.assertIn(role, self.theme, f"{role} not read from the payload")


try:  # pragma: no cover - optional dev dependency
    import javalang  # noqa: F401

    HAS_JAVALANG = True
except ImportError:  # pragma: no cover
    HAS_JAVALANG = False


class TestJavaScriptFreeJava(unittest.TestCase):
    """Every template still renders to parseable Java after the change."""

    def test_all_java_templates_render(self):
        for path in sorted(TEMPLATE_DIR.glob("*.java.j2")):
            with self.subTest(template=path.name):
                rendered = _render(path.name)
                self.assertTrue(rendered.strip(), f"{path.name} rendered empty")
                self.assertEqual(
                    rendered.count("{"),
                    rendered.count("}"),
                    f"{path.name} has unbalanced braces",
                )

    @unittest.skipUnless(HAS_JAVALANG, "javalang not installed")
    def test_all_java_templates_parse(self):
        """A real parser catches what brace counting cannot.

        Counting parentheses is not enough: strings and comments legitimately
        contain unbalanced ones (``KNOWN_KEYS`` holds a literal ``"("``).
        """
        for path in sorted(TEMPLATE_DIR.glob("*.java.j2")):
            with self.subTest(template=path.name):
                javalang.parse.parse(_render(path.name))


class TestTokenPayloadCarriesTheNewValues(unittest.TestCase):
    """Python must actually ship the tokens the new components read."""

    def test_toolbar_and_sheet_tokens_are_published(self):
        from pydrud.widgets.tokens import Tokens

        payload = Tokens.as_dict()
        self.assertEqual(payload["radius_toolbar"], 32)
        self.assertEqual(payload["toolbar_height"], 64)
        self.assertEqual(payload["side_sheet_width"], 360)

    def test_m3_corner_scale_is_published(self):
        """GAP #8 — the ten named steps of M3's corner scale."""
        from pydrud.widgets.tokens import Tokens

        payload = Tokens.as_dict()
        expected = {
            "corner_none": 0,
            "corner_extra_small": 4,
            "corner_small": 8,
            "corner_medium": 12,
            "corner_large": 16,
            "corner_large_increased": 20,
            "corner_extra_large": 28,
            "corner_extra_large_increased": 32,
            "corner_extra_extra_large": 48,
            "corner_full": 999,
        }
        for name, value in expected.items():
            self.assertIn(name, payload, f"{name} missing from the token payload")
            self.assertEqual(payload[name], value, name)

    def test_theme_payload_pushes_the_full_scheme(self):
        from pydrud.widgets.theme import Theme

        payload = Theme.payload()
        for role in (
            "surface_container", "surface_container_low", "surface_container_high",
            "surface_container_highest", "surface_container_lowest", "surface_dim",
            "surface_bright", "secondary_container", "on_secondary_container",
            "tertiary_container", "on_tertiary_container", "error_container",
            "on_error_container", "outline_variant", "inverse_surface",
            "inverse_on_surface", "inverse_primary",
        ):
            self.assertIn(role, payload, f"{role} missing from Theme.payload()")


if __name__ == "__main__":
    unittest.main()
