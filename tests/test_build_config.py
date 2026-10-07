"""Tests for pydrud.yaml parsing and NDK detection used by the builder."""

import os
import shutil
import tempfile
import unittest
from unittest import mock

from pydrud.commands.builder import Builder
from pydrud.commands.project import _detect_ndk, _version_key, create_project
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


class TestBuildVariants(unittest.TestCase):
    """``pydrud build`` speaks both variants explicitly: ``--debug`` (the
    default) and ``--release``."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pydrud-variant-")
        self.cwd = os.getcwd()
        os.chdir(self.tmp)
        create_project("variant", org="com.example", runtime="chaquopy")
        os.chdir(os.path.join(self.tmp, "variant"))

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _invoke(self, *args):
        from click.testing import CliRunner
        from pydrud.commands.cli import main

        with mock.patch.object(Builder, "build",
                               return_value="/tmp/app.apk") as build:
            result = CliRunner().invoke(main, list(args))
        return result, build

    def test_debug_is_the_default_variant(self):
        _result, build = self._invoke("build")
        build.assert_called_once_with(release=False, debug=False)

    def test_debug_flag_builds_the_debug_variant(self):
        result, build = self._invoke("build", "--debug")
        self.assertEqual(result.exit_code, 0, result.output)
        build.assert_called_once_with(release=False, debug=True)

    def test_release_flag_still_builds_release(self):
        result, build = self._invoke("build", "--release")
        self.assertEqual(result.exit_code, 0, result.output)
        build.assert_called_once_with(release=True, debug=False)

    def test_debug_and_release_are_mutually_exclusive(self):
        result, build = self._invoke("build", "--debug", "--release")
        self.assertEqual(result.exit_code, 2)
        self.assertIn("either --debug or --release", result.output)
        build.assert_not_called()

    def test_run_accepts_the_same_flag(self):
        from click.testing import CliRunner
        from pydrud.commands.cli import main

        with mock.patch.object(Builder, "run", return_value=0) as run:
            result = CliRunner().invoke(main, ["run", "--debug"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertFalse(run.call_args.kwargs["release"])
        self.assertTrue(run.call_args.kwargs["debug"])


if __name__ == "__main__":
    unittest.main()
