"""The package layout is part of the public contract.

Pydrud 2.0 names its top-level directories after layers — runtime,
widgets, services, data, commands — instead of leaving a 1 600-line
``main.py`` at the root. Old import paths keep working through shims, and
these tests pin both halves of that promise.
"""

from __future__ import annotations

import importlib
import os
import pkgutil
import unittest
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = os.path.join(ROOT, "pydrud")

LAYERS = ("runtime", "core", "widgets", "services", "data", "commands",
          "android", "utils")


class TestLayout(unittest.TestCase):

    def test_every_layer_is_a_package(self):
        for layer in LAYERS:
            with self.subTest(layer=layer):
                self.assertTrue(
                    os.path.isfile(os.path.join(PACKAGE, layer, "__init__.py")),
                    f"pydrud/{layer} is not a package")

    def test_runtime_holds_the_app_and_the_router(self):
        for module in ("pydrud.runtime.app", "pydrud.runtime.navigation"):
            with self.subTest(module=module):
                self.assertTrue(importlib.import_module(module))

    def test_no_stray_modules_at_the_top_level(self):
        """Only the public surface and the deprecation shims live at the root."""
        allowed = {"__init__", "compatibility", "testing",
                   "main", "navigation", "packages"}
        found = {name for _, name, ispkg
                 in pkgutil.iter_modules([PACKAGE]) if not ispkg}
        self.assertEqual(found - allowed, set())

    def test_public_namespace_exposes_the_runtime(self):
        import pydrud
        from pydrud.runtime.app import App
        from pydrud.runtime.navigation import Router

        self.assertIs(pydrud.App, App)
        self.assertIs(pydrud.Router, Router)


class TestDeprecationShims(unittest.TestCase):
    """2.0 moved modules; it did not break anybody's imports."""

    def _reimport(self, name: str):
        import sys

        sys.modules.pop(name, None)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            module = importlib.import_module(name)
        return module, caught

    def test_pydrud_main_still_exports_app(self):
        module, caught = self._reimport("pydrud.main")
        from pydrud.runtime.app import App

        self.assertIs(module.App, App)
        self.assertTrue(any(issubclass(w.category, DeprecationWarning)
                            for w in caught))

    def test_pydrud_navigation_still_exports_router(self):
        module, caught = self._reimport("pydrud.navigation")
        from pydrud.runtime.navigation import Route, Router

        self.assertIs(module.Router, Router)
        self.assertIs(module.Route, Route)
        self.assertTrue(module.TRANSITIONS)
        self.assertTrue(any(issubclass(w.category, DeprecationWarning)
                            for w in caught))

    def test_pydrud_packages_still_exports_requirements(self):
        module, caught = self._reimport("pydrud.packages")
        from pydrud.commands.packages import PackageError, Requirements

        self.assertIs(module.Requirements, Requirements)
        self.assertIs(module.PackageError, PackageError)
        self.assertTrue(any(issubclass(w.category, DeprecationWarning)
                            for w in caught))

    def test_shims_name_their_replacement(self):
        for name, replacement in (
                ("main", "pydrud.runtime.app"),
                ("navigation", "pydrud.runtime.navigation"),
                ("packages", "pydrud.commands.packages")):
            with self.subTest(module=name):
                with open(os.path.join(PACKAGE, f"{name}.py"),
                          encoding="utf-8") as fh:
                    source = fh.read()
                self.assertIn(replacement, source)
                self.assertIn("3.0", source, "say when the shim goes away")


if __name__ == "__main__":
    unittest.main()
