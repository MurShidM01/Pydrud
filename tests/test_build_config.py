"""Tests for pydrud.yaml parsing and NDK detection used by the builder."""

import os
import tempfile
import unittest

from pydrud.commands.builder import Builder
from pydrud.commands.project import _detect_ndk, _version_key
from pydrud.compatibility import COMPATIBILITY

YAML = """\
# Pydrud project configuration
app_name: "demo"
ndk: 28.2.13676358  # detected
empty:
python_version: "3.11"
permissions:
  - CAMERA
  ndk: 1.0.0
"""


class TestLoadConfig(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        with open(os.path.join(self.root, "pydrud.yaml"), "w",
                  encoding="utf-8") as handle:
            handle.write(YAML)
        self.config = Builder._load_config(self.root)

    def test_reads_top_level_values(self):
        self.assertEqual(self.config["app_name"], "demo")
        self.assertEqual(self.config["python_version"], "3.11")

    def test_strips_inline_comments(self):
        self.assertEqual(self.config["ndk"], "28.2.13676358")

    def test_ignores_nested_keys_and_list_items(self):
        """An indented ``ndk:`` belongs to another block, not the project."""
        self.assertEqual(self.config["ndk"], "28.2.13676358")
        self.assertEqual(self.config["permissions"], "")

    def test_empty_value_is_empty_string(self):
        self.assertEqual(self.config["empty"], "")

    def test_missing_file_is_empty_dict(self):
        self.assertEqual(Builder._load_config(tempfile.mkdtemp()), {})


class TestDetectNdk(unittest.TestCase):
    def test_newest_version_wins_numerically(self):
        sdk = tempfile.mkdtemp()
        for version in ("9.0.9519653", "26.1.1", "28.2.13676358"):
            os.makedirs(os.path.join(sdk, "ndk", version))
        self.assertEqual(_detect_ndk(sdk), "28.2.13676358")

    def test_falls_back_to_the_pinned_version(self):
        self.assertEqual(_detect_ndk(tempfile.mkdtemp()),
                         COMPATIBILITY.ndk_version)
        self.assertEqual(_detect_ndk(""), COMPATIBILITY.ndk_version)

    def test_version_key_orders_numerically(self):
        self.assertLess(_version_key("9.0.1"), _version_key("28.2.3"))


if __name__ == "__main__":
    unittest.main()
