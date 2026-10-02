"""Shared terminal UI used by one-shot commands and Hot Reload."""

from __future__ import annotations

import unittest

from click.testing import CliRunner

from pydrud.commands.analyzer import format_report
from pydrud.commands.cli import main
from pydrud.utils import tui


class TestSharedTui(unittest.TestCase):

    def test_command_header_contains_brand_context_and_details(self):
        rendered = tui.strip_ansi(tui.render_command_header(
            "sync",
            "Syncing Taskflow",
            subtitle="Applying Android configuration",
            details=(("Package", "com.example.taskflow"),),
        ))
        self.assertIn("PYDRUD · SYNC", rendered)
        self.assertIn("Syncing Taskflow", rendered)
        self.assertIn("com.example.taskflow", rendered)
        self.assertIn("╭", rendered)
        self.assertIn("╯", rendered)

    def test_table_is_responsive_and_keeps_headers(self):
        rendered = tui.strip_ansi(tui.render_table(
            ("PACKAGE", "VERSION", "DESCRIPTION"),
            (("requests", ">=2", "A" * 200),),
            max_width=60,
        ))
        self.assertIn("PACKAGE", rendered)
        self.assertIn("requests", rendered)
        self.assertIn("…", rendered)
        self.assertLessEqual(max(map(len, rendered.splitlines())), 62)

    def test_summary_and_next_steps_have_consistent_status_language(self):
        summary = tui.strip_ansi(tui.render_summary(
            "Project synchronized", (("Java classes", 18),)
        ))
        steps = tui.strip_ansi(tui.render_next_steps((
            ("pydrud run", "rebuild and launch"),
        )))
        self.assertIn("✓ Project synchronized", summary)
        self.assertIn("Java classes", summary)
        self.assertIn("Next steps", steps)
        self.assertIn("$ pydrud run", steps)

    def test_analysis_uses_shared_tui_but_json_stays_machine_readable(self):
        human = tui.strip_ansi(format_report([]))
        machine = format_report([], json_output=True)
        self.assertIn("PYDRUD · ANALYZE", human)
        self.assertIn("No issues found", human)
        self.assertEqual(machine, "[]")


class TestCliHelpTui(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()

    def test_root_help_has_brand_banner(self):
        result = self.runner.invoke(main, ["--help"], color=False)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("PYDRUD 2.0.0", result.output)
        self.assertIn("Native Android. Python powered.", result.output)
        self.assertIn("Commands:", result.output)

    def test_command_help_has_command_banner_and_short_help_flag(self):
        result = self.runner.invoke(main, ["build", "--help"], color=False)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("PYDRUD · BUILD", result.output)
        self.assertIn("Command reference", result.output)
        self.assertIn("-h, --help", result.output)


if __name__ == "__main__":
    unittest.main()
