"""DOC-001 — `pydrud permissions list` mirrors `capabilities list`."""

from __future__ import annotations

import unittest

from click.testing import CliRunner

from pydrud.commands.cli import main


class TestPermissionsListCommand(unittest.TestCase):

    def _help(self, *args) -> str:
        result = CliRunner().invoke(main, [*args, "--help"])
        self.assertEqual(result.exit_code, 0, result.output)
        return result.output

    def test_permissions_list_exists(self):
        self.assertIn("list", self._help("permissions").lower())

    def test_capabilities_list_exists(self):
        self.assertIn("list", self._help("capabilities").lower())

    def test_permissions_list_has_an_all_flag(self):
        self.assertIn("--all", self._help("permissions", "list"))


if __name__ == "__main__":
    unittest.main()
