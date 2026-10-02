"""
``pydrud run`` must fail fast, not two minutes into Gradle.

Two guards run before the build:

* a staleness warning when the project's generated Java came from another
  Pydrud release (``pydrud sync`` fixes it);
* a cross-class symbol check over the project's own ``*.java`` files, so a
  ``cannot find symbol`` is reported in under a second.
"""

from __future__ import annotations

import io
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout

from pydrud import __version__
from pydrud.commands.builder import Builder
from pydrud.commands.project import create_project, sync_project

try:
    import javalang  # noqa: F401
    HAS_JAVALANG = True
except ImportError:  # pragma: no cover - optional dev dependency
    HAS_JAVALANG = False


class TestPreflight(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="pydrud-preflight-")
        cls.cwd = os.getcwd()
        os.chdir(cls.tmp)
        create_project("demo_app", org="com.example")
        cls.project = os.path.join(cls.tmp, "demo_app")

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls.cwd)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def factory_path(self) -> str:
        return os.path.join(self.project, "android", "app", "src", "main",
                            "java", "com", "example", "demo_app",
                            "ViewFactory.java")

    def test_project_records_the_generator_version(self):
        with open(os.path.join(self.project, "pydrud.yaml"),
                  encoding="utf-8") as handle:
            config = handle.read()
        self.assertIn(f'pydrud_version: "{__version__}"', config)

    def test_fresh_project_passes_preflight(self):
        builder = Builder(self.project)
        output = io.StringIO()
        with redirect_stdout(output):
            passed = builder._preflight_java()
        self.assertTrue(passed, output.getvalue())

    @unittest.skipUnless(HAS_JAVALANG, "javalang not installed")
    def test_broken_generated_java_is_caught(self):
        path = self.factory_path()
        with open(path, encoding="utf-8") as handle:
            original = handle.read()
        broken = original.replace("advanced.setEventDispatcher(d);",
                                  "advanced.noSuchMethod(d);")
        self.assertNotEqual(original, broken, "anchor line moved")
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(broken)
            output = io.StringIO()
            with redirect_stdout(output):
                passed = Builder(self.project)._preflight_java()
            self.assertFalse(passed)
            self.assertIn("noSuchMethod", output.getvalue())
        finally:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(original)

    def test_stale_project_warns_and_sync_restamps(self):
        config_path = os.path.join(self.project, "pydrud.yaml")
        original = open(config_path, encoding="utf-8").read()
        try:
            with open(config_path, "w", encoding="utf-8") as handle:
                handle.write(original.replace(
                    f'pydrud_version: "{__version__}"',
                    'pydrud_version: "0.0.1"'))
            output = io.StringIO()
            with redirect_stdout(output):
                Builder(self.project)._warn_if_stale()
            self.assertIn("0.0.1", output.getvalue())
            self.assertIn("pydrud sync", output.getvalue())

            with redirect_stdout(io.StringIO()):
                sync_project(self.project, update_runtime=False)
            with open(config_path, encoding="utf-8") as handle:
                refreshed = handle.read()
            self.assertIn(f'pydrud_version: "{__version__}"', refreshed)

            output = io.StringIO()
            with redirect_stdout(output):
                Builder(self.project)._warn_if_stale()
            self.assertEqual("", output.getvalue())
        finally:
            with open(config_path, "w", encoding="utf-8") as handle:
                handle.write(original)

    def test_preflight_is_skipped_when_there_is_no_java(self):
        empty = tempfile.mkdtemp(prefix="pydrud-empty-")
        try:
            self.assertTrue(Builder(empty)._preflight_java())
        finally:
            shutil.rmtree(empty, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
