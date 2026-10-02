"""Static analyzer: findings, de-duplication and registry drift."""

import inspect
import unittest

import pydrud
from pydrud.commands.analyzer import _WIDGET_CLASSES, _analyze_file
from pydrud.widgets.base import Widget

NESTED = """
from pydrud import Text
def f(page, rows):
    for r in rows:
        for c in r:
            page.add(Text(c))
            page.update()
"""

CLEAN = """
from pydrud import Text
def f(page, rows):
    for r in rows:
        page.add(Text(r, key=f"row-{r}"))
    page.update()
"""


def messages(source):
    return [(i["line"], i["message"]) for i in _analyze_file(source, "x.py")]


class TestAnalyzer(unittest.TestCase):
    def test_nested_loops_report_once(self):
        found = messages(NESTED)
        self.assertEqual(len(found), 2, found)
        self.assertIn("without an explicit key=", found[0][1])
        self.assertIn("page.update() inside a loop", found[1][1])

    def test_keyed_widgets_are_clean(self):
        self.assertEqual(messages(CLEAN), [])

    def test_issues_are_sorted_by_line(self):
        lines = [line for line, _ in messages(NESTED)]
        self.assertEqual(lines, sorted(lines))

    def test_syntax_errors_are_reported(self):
        issues = _analyze_file("def (:\n", "bad.py")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["severity"], "error")

    def test_unknown_style_key(self):
        source = 'from pydrud import Text\nText("hi", style={"nope": 1})\n'
        self.assertTrue(any("Unknown style key" in m for _, m in
                            messages(source)))


class TestWidgetRegistryDrift(unittest.TestCase):
    def test_analyzer_knows_every_exported_widget(self):
        """A new widget must be added to ``_WIDGET_CLASSES`` as well."""
        exported = {
            name for name in dir(pydrud)
            if inspect.isclass(getattr(pydrud, name))
            and issubclass(getattr(pydrud, name), Widget)
            and getattr(pydrud, name) is not Widget
        }
        self.assertEqual(exported - _WIDGET_CLASSES, set())
        self.assertEqual(_WIDGET_CLASSES - exported, set())


if __name__ == "__main__":
    unittest.main()
