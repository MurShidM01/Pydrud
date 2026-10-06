"""The icon catalogue: fail-loud resolution, aliases and custom SVG icons.

PB-005: unknown icon names used to render a silent "?" on device and the
vocabulary diverged from Material Symbols. These tests pin the public
``pydrud.icons`` API, the shipped alias table, and the analyzer rule that
surfaces the mistake at build time instead of on screen.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from pydrud import Icon, icons
from pydrud.commands.analyzer import _analyze_file

TEMPLATE = (Path(__file__).resolve().parent.parent / "pydrud" / "android"
            / "templates" / "android" / "PydrudIcons.java.j2")

#: The Material Symbols names from the PYDRUD report that used to render "?".
REPORT_NAMES = [
    "rocket_launch", "play_arrow", "emoji_events", "sports_esports", "bolt",
    "flash_on", "speed", "replay", "restart_alt", "account_tree", "shuffle",
    "content_paste", "notifications_active", "circle", "diamond",
    "hourglass_bottom",
]


def _template_paths() -> set:
    return set(re.findall(r'PATHS\.put\(\s*"([^"]+)"',
                          TEMPLATE.read_text(encoding="utf-8")))


def _template_aliases() -> dict:
    return dict(re.findall(r'ALIASES\.put\(\s*"([^"]+)"\s*,\s*"([^"]+)"',
                           TEMPLATE.read_text(encoding="utf-8")))


class TestCatalogue(unittest.TestCase):

    def test_has_accepts_shipped_names_and_aliases(self):
        for name in ("star", "home", "rocket", "play"):
            with self.subTest(name=name):
                self.assertTrue(icons.has(name))
        for alias in REPORT_NAMES:
            with self.subTest(alias=alias):
                self.assertTrue(icons.has(alias), alias)

    def test_has_rejects_unknown_and_blank(self):
        for name in ("", "   ", "not_a_real_icon", "definitely:missing"):
            with self.subTest(name=name):
                self.assertFalse(icons.has(name))

    def test_available_is_the_shipped_set_plus_packs(self):
        available = icons.available()
        self.assertGreater(len(available), 300)
        self.assertTrue(set(icons.shipped()) <= available)
        self.assertIn("star", available)
        self.assertNotIn("not_a_real_icon", available)

    def test_canonical_resolves_aliases_to_real_paths(self):
        self.assertEqual(icons.canonical("rocket_launch"), "rocket")
        self.assertEqual(icons.canonical("play_arrow"), "play")
        self.assertEqual(icons.canonical("star"), "star")
        self.assertIsNone(icons.canonical("not_a_real_icon"))
        # Every advertised name must resolve to a real path — an alias that
        # points at another alias would silently fall back to "help".
        for name in icons.shipped():
            with self.subTest(name=name):
                target = icons.canonical(name)
                self.assertIsNotNone(target)
                self.assertIn(target, _template_paths())

    def test_suggest_finds_the_closest_match(self):
        self.assertIn("rocket", icons.suggest("rocket_lunch"))
        self.assertIn("rocket_launch", icons.suggest("rocket_lunch"))
        self.assertEqual(icons.suggest(""), [])

    def test_every_alias_target_is_a_shipped_path(self):
        paths = _template_paths()
        broken = {a: t for a, t in _template_aliases().items()
                  if t not in paths}
        self.assertEqual(broken, {})


class TestVendoredData(unittest.TestCase):
    """The catalogue must work inside the APK, where the template is absent.

    ``pydrud/android`` is build-time only (it is excluded from the bundle),
    so ``pydrud.icons`` reads ``pydrud.core.icon_data`` instead. These tests
    keep the two generated artefacts — the Java template and the Python
    data — from drifting apart.
    """

    def setUp(self):
        from pydrud.core import icon_data

        self.data = icon_data

    def test_vendored_paths_match_the_template(self):
        self.assertEqual(set(self.data.PATHS), _template_paths())

    def test_vendored_aliases_match_the_template(self):
        self.assertEqual(self.data.ALIASES, _template_aliases())

    def test_shipped_is_the_union_of_the_vendored_data(self):
        self.assertEqual(
            icons.shipped(),
            frozenset(self.data.PATHS | set(self.data.ALIASES)))

    def test_the_catalogue_does_not_read_the_template_file(self):
        # A regression guard: re-introducing a file read would make every
        # lookup wrong (not fatal) on a device, where android/ is absent.
        self.assertFalse(hasattr(icons, "_TEMPLATE"))
        self.assertTrue(icons.shipped())


class TestAnalyzerRule(unittest.TestCase):

    def _messages(self, source: str) -> list:
        return [i["message"] for i in _analyze_file(source, "x.py")]

    def test_unknown_icon_string_is_reported(self):
        found = self._messages('from pydrud import Icon\nIcon("not_a_real_icon")\n')
        self.assertEqual(len(found), 1, found)
        self.assertIn("Unknown icon", found[0])
        self.assertIn("Did you mean", found[0])

    def test_shipped_names_are_clean(self):
        source = (
            "from pydrud import Icon, Button\n"
            "Icon('rocket_launch')\n"
            "Icon('star')\n"
            "Button('Go', icon='play_arrow')\n"
        )
        self.assertEqual(self._messages(source), [])

    def test_keyword_icon_names_are_checked(self):
        found = self._messages('from pydrud import Button\nButton("x", icon="bogus")\n')
        self.assertEqual(len(found), 1, found)

    def test_custom_svg_icons_are_not_flagged(self):
        source = ('from pydrud import Icon\n'
                  'Icon.svg("M12,2 L22,12 L12,22 L2,12 Z")\n')
        self.assertEqual(self._messages(source), [])


class TestIconSvg(unittest.TestCase):

    def test_svg_icon_serialises_path_not_name(self):
        icon = Icon.svg("M12,2 L22,12 L12,22 L2,12 Z", size=32)
        props = icon.to_dict()["props"]
        self.assertEqual(props, {"path": "M12,2 L22,12 L12,22 L2,12 Z"})
        self.assertEqual(icon.style["font"]["size"], 32)

    def test_named_icon_still_serialises_name(self):
        self.assertEqual(Icon("star").to_dict()["props"], {"name": "star"})

    def test_svg_icon_survives_clone(self):
        icon = Icon.svg("M12,2 L22,12 L12,22 L2,12 Z")
        self.assertEqual(icon.clone().to_dict()["props"], icon.to_dict()["props"])

    def test_empty_svg_path_is_rejected(self):
        for bad in ("", "   ", None):
            with self.subTest(value=bad):
                with self.assertRaises(ValueError):
                    Icon.svg(bad)


class TestJavaFailLoud(unittest.TestCase):
    """The native layer must warn instead of silently rendering "?"."""

    def setUp(self):
        self.source = TEMPLATE.read_text(encoding="utf-8")

    def test_drawable_warns_once_per_unknown_name(self):
        self.assertIn("warnUnknown(name)", self.source)
        self.assertIn("Log.w(TAG", self.source)
        self.assertIn('TAG = "Pydrud"', self.source)

    def test_public_helpers_exist(self):
        for symbol in ("public static boolean has(",
                       "public static Set<String> available()",
                       "public static Drawable drawablePath("):
            with self.subTest(symbol=symbol):
                self.assertIn(symbol, self.source)


class TestGeneratorSync(unittest.TestCase):
    """The committed Java and the generator must agree (no drift)."""

    def test_generator_reproduces_the_committed_aliases(self):
        try:
            import importlib.util

            import fontTools  # noqa: F401
        except ImportError:
            self.skipTest("fonttools not installed")

        spec = importlib.util.spec_from_file_location(
            "_gen_icons",
            Path(__file__).resolve().parent.parent / "tools" / "generate_icons.py")
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)

        paths = {name: data for name, data
                 in re.findall(r'PATHS\.put\(\s*"([^"]+)"\s*,\s*"([^"]*)"',
                               self.source)
                 if name not in gen.EXTRA_PATHS}
        rendered = gen.render(paths)
        self.assertEqual(
            dict(re.findall(r'ALIASES\.put\(\s*"([^"]+)"\s*,\s*"([^"]+)"',
                            rendered)),
            _template_aliases(),
        )
        self.assertEqual(set(re.findall(r'PATHS\.put\(\s*"([^"]+)"', rendered)),
                         _template_paths())

    @property
    def source(self) -> str:
        return TEMPLATE.read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
