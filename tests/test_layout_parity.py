"""Layout-model parity: main/cross axis sizes and the collapse guard.

PB-007: ``Row``/``Column`` fill the width by default, so two unweighted
fill-width siblings collapse. These tests pin the Flutter-style
``main_axis_size``/``cross_axis_size`` opt-outs, the documented default,
and the analyzer rule that makes the remaining footgun loud.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from pydrud import Column, Row
from pydrud.commands.analyzer import _analyze_file

VIEW_FACTORY = (Path(__file__).resolve().parent.parent / "pydrud" / "android"
                / "templates" / "android" / "ViewFactory.java.j2")


def _style(widget) -> dict:
    return widget.to_dict()["style"]


class TestAxisSizes(unittest.TestCase):

    def test_row_main_axis_min_wraps_the_width(self):
        self.assertEqual(_style(Row(main_axis_size="min"))["width"], "wrap")

    def test_row_main_axis_max_matches_the_width(self):
        self.assertEqual(_style(Row(main_axis_size="max"))["width"], "match")

    def test_column_main_axis_min_wraps_the_height(self):
        self.assertEqual(_style(Column(main_axis_size="min"))["height"], "wrap")

    def test_column_main_axis_max_matches_the_height(self):
        self.assertEqual(_style(Column(main_axis_size="max"))["height"], "match")

    def test_cross_axis_size_maps_to_the_other_axis(self):
        row = _style(Row(cross_axis_size="min"))
        self.assertEqual(row.get("height"), "wrap")
        self.assertNotIn("width", row)
        col = _style(Column(cross_axis_size="min"))
        self.assertEqual(col.get("width"), "wrap")
        self.assertNotIn("height", col)

    def test_flutter_and_pydrud_spellings_agree(self):
        self.assertEqual(_style(Row(main_axis_size="min"))["width"],
                         _style(Row(main_axis_size="wrap"))["width"])
        self.assertEqual(_style(Row(main_axis_size="max"))["width"],
                         _style(Row(main_axis_size="match"))["width"])

    def test_numeric_axis_size_passes_through(self):
        self.assertEqual(_style(Row(main_axis_size=240))["width"], 240)

    def test_invalid_axis_size_is_rejected(self):
        with self.assertRaises(ValueError):
            Row(main_axis_size="huge")

    def test_default_still_fills_the_width(self):
        # The documented default: a Row/Column is MATCH_PARENT unless told
        # otherwise (the native layer downgrades it inside a horizontal row).
        self.assertNotIn("width", _style(Row()))
        self.assertNotIn("height", _style(Column()))


class TestCollapseAnalyzerRule(unittest.TestCase):

    def _messages(self, source: str) -> list:
        return [i["message"] for i in _analyze_file(source, "x.py")]

    def test_two_explicit_fill_children_warn(self):
        src = ('from pydrud import Row, Column\n'
               'Row(children=[Column(style={"width": "match"}),\n'
               '              Column(style={"width": "match"})])\n')
        found = self._messages(src)
        self.assertEqual(len(found), 1, found)
        self.assertIn("collapse", found[0])

    def test_width_keyword_is_checked(self):
        src = ('from pydrud import Row, Card\n'
               'Row(children=[Card(width="match"), Card(width="match")])\n')
        self.assertEqual(len(self._messages(src)), 1)

    def test_weighted_children_are_clean(self):
        src = ('from pydrud import Row, Column\n'
               'Row(children=[Column(style={"width": "match"}, expand=1),\n'
               '              Column(style={"width": "match"}, expand=1)])\n')
        self.assertEqual(self._messages(src), [])

    def test_content_sized_children_are_clean(self):
        src = ('from pydrud import Row, Column\n'
               'Row(children=[Column(main_axis_size="min"),\n'
               '              Column(main_axis_size="min")])\n')
        self.assertEqual(self._messages(src), [])

    def test_column_collapse_is_detected_on_the_height(self):
        src = ('from pydrud import Column, Container\n'
               'Column(children=[Container(style={"height": "match"}),\n'
               '                 Container(style={"height": "match"})])\n')
        self.assertEqual(len(self._messages(src)), 1)


class TestNativeMitigation(unittest.TestCase):
    """The renderer hugs content instead of collapsing inside a Row."""

    def setUp(self):
        from tests import all_java_templates
        self.source = all_java_templates()

    def test_horizontal_row_downgrades_unweighted_fill_children(self):
        body = re.search(r"LinearLayout\.LayoutParams linearParams"
                         r"\(.*?\n    \}", self.source, re.S).group(0)
        self.assertIn("orientation == LinearLayout.HORIZONTAL", body)
        self.assertIn("base.width = ViewGroup.LayoutParams.WRAP_CONTENT", body)
        self.assertIn("declaresWidth(json)", body)

    def test_row_and_column_still_fill_by_default(self):
        body = re.search(r"static boolean fillsWidthByDefault"
                         r"\(.*?\n    \}", self.source, re.S).group(0)
        self.assertIn('case "Column": case "Row"', body)


if __name__ == "__main__":
    unittest.main()
