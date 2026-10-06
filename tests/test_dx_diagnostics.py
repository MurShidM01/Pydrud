"""Developer-diagnostics fixes: DX-002, DX-004 and DX-006.

- DX-002: the analyzer no longer flags a widget nested inside a keyed parent.
- DX-004: Python output goes to logcat under the single `Pydrud` tag.
- DX-006: the renderer warns (once per key) about style keys it ignores.
"""

from __future__ import annotations

import io
import re
import sys
import unittest
from pathlib import Path

from pydrud.commands.analyzer import _analyze_file
from pydrud.core import logcat

TEMPLATES = (Path(__file__).resolve().parent.parent / "pydrud" / "android"
             / "templates" / "android")


def _messages(source: str) -> list:
    return [i["message"] for i in _analyze_file(source, "x.py")]


class TestLoopKeyFalsePositive(unittest.TestCase):
    """DX-002 — a keyed parent already gives its children identity."""

    def test_nested_child_of_keyed_parent_is_clean(self):
        src = ("from pydrud import Column, Row, Icon\n"
               "def f(page, rows):\n"
               "    for i, r in enumerate(rows):\n"
               "        page.add(Row(key=f'row-{i}', children=[Icon('star')]))\n")
        self.assertEqual(_messages(src), [])

    def test_unkeyed_outer_widget_still_warns(self):
        src = ("from pydrud import Row, Icon\n"
               "def f(page, rows):\n"
               "    for r in rows:\n"
               "        page.add(Row(children=[Icon('star')]))\n")
        found = _messages(src)
        self.assertEqual(len(found), 1, found)
        self.assertIn("Row() built in a loop", found[0])

    def test_two_unkeyed_siblings_each_warn(self):
        src = ("from pydrud import Row, Text, Icon\n"
               "def f(page, rows):\n"
               "    for r in rows:\n"
               "        page.add(Text(r), Icon('star'))\n")
        self.assertEqual(len(_messages(src)), 2)


class TestLogcatTag(unittest.TestCase):
    """DX-004 — one documented tag for framework and app output."""

    def test_tag_is_stable(self):
        self.assertEqual(logcat.TAG, "Pydrud")

    def test_install_is_a_noop_off_device(self):
        before = sys.stdout
        self.assertFalse(logcat.install())
        self.assertIs(sys.stdout, before)

    def test_log_writes_to_stdout_on_host(self):
        buffer = io.StringIO()
        original = sys.stdout
        sys.stdout = buffer
        try:
            logcat.log("hello")
            logcat.log("boom", error=True)
        finally:
            sys.stdout = original
        self.assertIn("hello", buffer.getvalue())

    def test_log_exception_includes_the_traceback(self):
        buffer = io.StringIO()
        original = sys.stderr
        sys.stderr = buffer
        try:
            try:
                raise ValueError("kaboom")
            except ValueError as exc:
                import traceback
                logcat.log_exception(exc, traceback.format_exc())
        finally:
            sys.stderr = original
        text = buffer.getvalue()
        self.assertIn("Error: kaboom", text)
        self.assertIn("ValueError", text)


class TestUnknownStyleKeys(unittest.TestCase):
    """DX-006 — the renderer reports style keys no branch consumes."""

    def setUp(self):
        from tests import all_java_templates
        self.view_factory = all_java_templates()

    def test_applystyle_warns_about_unknown_keys(self):
        self.assertIn("warnUnknownStyleKeys(s)", self.view_factory)
        self.assertIn("unhandled style key", self.view_factory)

    def test_warning_is_once_per_key(self):
        body = re.search(r"void warnUnknownStyleKeys"
                         r"\(.*?\n    \}", self.view_factory, re.S).group(0)
        self.assertIn("WARNED_STYLE_KEYS.add(k)", body)

    def test_known_keys_cover_every_key_the_templates_read(self):
        keys: set = set()
        for path in TEMPLATES.glob("*.j2"):
            text = path.read_text(encoding="utf-8")
            keys.update(re.findall(
                r'\.(?:has|optString|optInt|optDouble|optBoolean'
                r'|optJSONObject|optJSONArray|isNull|opt)\(\s*"([^"]+)"', text))
        block = re.search(r"KNOWN_KEYS =.*?\.split\(\" \"\)\)\);",
                          self.view_factory, re.S).group(0)
        known = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", block))
        # The declaration itself mentions the identifiers we ignore.
        known -= {"KNOWN_KEYS", "new", "java", "util", "HashSet", "Arrays",
                  "asList", "Set", "String", "split", "trim", "private",
                  "static", "final"}
        missing = sorted(k for k in keys if not k.startswith("_")
                         and k not in known)
        self.assertEqual([], missing,
                         "renderer reads keys missing from KNOWN_KEYS: "
                         + ", ".join(missing))


if __name__ == "__main__":
    unittest.main()
