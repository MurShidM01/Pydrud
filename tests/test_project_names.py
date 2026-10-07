"""
Project names become Java class names, package segments, directories and a
Python module — all with different rules.  ``pydrud create 2cool`` used to
generate ``public class 2coolActivity``, which does not compile.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import unittest

from pydrud.commands.project import (
    _camel, _sanitize_package, _slugify, create_project,
)

JAVA_IDENT = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")
PY_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

AWKWARD = ["my_app", "my-app", "My App", "2cool", "class", "ünïcode",
           "___", "app.name", "99", "a"]


class TestNameSanitising(unittest.TestCase):

    def test_class_prefix_is_always_a_java_identifier(self):
        for name in AWKWARD:
            with self.subTest(name=name):
                camel = _camel(name)
                self.assertRegex(camel, JAVA_IDENT)
                self.assertTrue(JAVA_IDENT.match(camel + "Activity"))

    def test_module_slug_is_always_a_python_identifier(self):
        for name in AWKWARD:
            with self.subTest(name=name):
                slug = _slugify(name)
                self.assertRegex(slug, PY_IDENT)
                self.assertTrue(slug.isidentifier())

    def test_package_segments_are_valid(self):
        for name in AWKWARD:
            with self.subTest(name=name):
                package = _sanitize_package("com.example", _slugify(name))
                for segment in package.split("."):
                    self.assertRegex(segment, PY_IDENT)
                    self.assertFalse(segment[0].isdigit())

    def test_familiar_names_are_unchanged(self):
        self.assertEqual("MyApp", _camel("my_app"))
        self.assertEqual("MyApp", _camel("my-app"))
        self.assertEqual("my_app", _slugify("My App"))


class TestAwkwardProjectGenerates(unittest.TestCase):
    """A digit-leading name must still produce compilable sources."""

    def test_digit_leading_name(self):
        tmp = tempfile.mkdtemp(prefix="pydrud-names-")
        cwd = os.getcwd()
        try:
            os.chdir(tmp)
            create_project("2cool", org="com.example", runtime="chaquopy")
            root = os.path.join(tmp, "app_2cool")
            activity = os.path.join(
                root, "android", "app", "src", "main", "java", "com",
                "example", "app_2cool", "App2coolActivity.java")
            self.assertTrue(os.path.isfile(activity), os.listdir(root))
            source = open(activity, encoding="utf-8").read()
            self.assertIn("public class App2coolActivity", source)
            manifest = open(os.path.join(
                root, "android", "app", "src", "main",
                "AndroidManifest.xml"), encoding="utf-8").read()
            self.assertIn('android:name=".App2coolActivity"', manifest)
        finally:
            os.chdir(cwd)
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
