"""``RangeSlider`` — the two-thumb range control (PYDRUD §15.2).

The Python side clamps and orders the pair; the native side is Material's
``RangeSlider``. The Java cannot run here, so the last section pins the
contract the generated ``ViewFactory`` implements — including the two
failure modes that would otherwise crash a frame: values off the step grid
and values outside ``[min, max]``.
"""

from __future__ import annotations

import os
import re
import unittest

from pydrud import RangeSlider
from pydrud.core.diff import TreeDiff
from pydrud.testing import AppTester

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEW_FACTORY = os.path.join(ROOT, "pydrud", "android", "templates",
                            "android", "ViewFactory.java.j2")


def _java() -> str:
    with open(VIEW_FACTORY, encoding="utf-8") as handle:
        return handle.read()


class TestSerialisation(unittest.TestCase):

    def test_the_pair_and_bounds_are_sent(self):
        node = RangeSlider(20, 80, min=0, max=100).to_dict()
        self.assertEqual(node["type"], "RangeSlider")
        self.assertEqual(node["props"]["values"], [20.0, 80.0])
        self.assertEqual(node["props"]["min"], 0.0)
        self.assertEqual(node["props"]["max"], 100.0)

    def test_a_reversed_pair_is_ordered(self):
        self.assertEqual(RangeSlider(80, 20).values, (20.0, 80.0))

    def test_values_outside_the_bounds_are_clamped(self):
        widget = RangeSlider(values=(-50, 250), min=0, max=100)
        self.assertEqual(widget.values, (0.0, 100.0))

    def test_the_values_keyword_works(self):
        self.assertEqual(RangeSlider(values=(30, 60)).values, (30.0, 60.0))

    def test_it_fills_the_width_by_default(self):
        self.assertEqual(RangeSlider().to_dict()["style"]["width"], "match")

    def test_divisions_and_step_size_go_into_style(self):
        node = RangeSlider(0, 100, divisions=4, step_size=25).to_dict()
        self.assertEqual(node["style"]["divisions"], 4)
        self.assertEqual(node["style"]["stepSize"], 25.0)

    def test_colour_goes_into_style(self):
        node = RangeSlider(0, 100, color="#FFEF4444").to_dict()
        self.assertEqual(node["style"]["color"], "#FFEF4444")

    def test_the_values_setter_orders_and_clamps(self):
        widget = RangeSlider(0, 100, min=0, max=50)
        widget.values = (90, -10)
        self.assertEqual(widget.values, (0.0, 50.0))

    def test_start_and_end_are_readable(self):
        widget = RangeSlider(15, 45)
        self.assertEqual(widget.start, 15.0)
        self.assertEqual(widget.end, 45.0)


class TestValidation(unittest.TestCase):

    def test_max_must_exceed_min(self):
        with self.assertRaises(ValueError):
            RangeSlider(0, 10, min=10, max=10)

    def test_step_size_must_be_positive(self):
        with self.assertRaises(ValueError):
            RangeSlider(0, 10, step_size=0)
        with self.assertRaises(ValueError):
            RangeSlider(0, 10, step_size=-5)

    def test_values_must_be_a_pair(self):
        with self.assertRaises(ValueError) as caught:
            RangeSlider(values=(1, 2, 3))
        self.assertIn("pair", str(caught.exception))


class TestEvents(unittest.TestCase):

    def test_on_change_registers_a_change_handler(self):
        widget = RangeSlider(0, 50, on_change=lambda e: None)
        self.assertIn("change", widget.event_handlers)

    def test_a_change_event_reports_the_pair(self):
        seen: list = []

        def main(page):
            page.add(RangeSlider(20, 80, key="r", on_change=seen.append))

        with AppTester(main) as app:
            app.device.send_event("change", "r", {"values": [10, 30]})
            app.settle()

        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["values"], [10, 30])

    def test_the_rendered_props_carry_the_pair(self):
        with AppTester(lambda page: page.add(
                RangeSlider(25, 75, key="r"))) as app:
            self.assertEqual(app.prop("r", "values"), [25.0, 75.0])


class TestDiffing(unittest.TestCase):

    def test_a_value_change_is_an_in_place_update(self):
        patches = TreeDiff.diff(RangeSlider(20, 80, key="r"),
                                RangeSlider(30, 70, key="r"))
        self.assertEqual([p.op for p in patches], ["update"], patches)
        self.assertEqual(patches[0].props["values"], [30.0, 70.0])
        self.assertNotIn("min", patches[0].props,
                         "unchanged bounds must not be re-sent")

    def test_an_unchanged_slider_is_not_re_sent(self):
        patches = TreeDiff.diff(RangeSlider(20, 80, key="r"),
                                RangeSlider(20, 80, key="r"))
        self.assertEqual(patches, [])


class TestGeneratedJava(unittest.TestCase):

    def setUp(self):
        self.source = _java()

    def test_the_type_is_dispatched(self):
        self.assertIn('case "RangeSlider":', self.source)

    def test_it_uses_the_material_range_slider(self):
        self.assertIn("com.google.android.material.slider.RangeSlider", self.source)

    def test_the_view_is_reused_across_updates(self):
        body = re.search(r"private static boolean isReusableType"
                         r"\(String type\) \{(.*?)\n    \}", self.source, re.S)
        self.assertIn('case "RangeSlider":', body.group(1))

    def test_the_update_path_handles_the_pair(self):
        # The update branch reads the patch's props (p.has) — not the node.
        self.assertIn('if (p.has("values"))', self.source)
        self.assertIn("applyRangeValues(rs, min, max, step,", self.source)

    def test_change_events_ignore_the_programmatic_echo(self):
        self.assertIn("if (!fromUser) return;", self.source)

    def test_it_reports_the_pair_from_the_change_listener(self):
        self.assertIn('d.put("values", arr);', self.source)

    def test_off_grid_values_are_snapped_and_guarded(self):
        body = re.search(r"private void applyRangeValues"
                         r"\(.*?\n    \}", self.source, re.S).group(0)
        self.assertIn("Math.round((lo - min) / step)", body)
        self.assertIn("catch (RuntimeException e)", body)
        self.assertIn("rs.setValues(min, max);", body)

    def test_it_fills_the_width_by_default(self):
        body = re.search(r"fillsWidthByDefault\(String type\) \{(.*?)\n    \}",
                         self.source, re.S).group(0)
        self.assertIn('case "RangeSlider":', body)

    def test_stepping_and_values_are_known_renderer_keys(self):
        block = re.search(r"KNOWN_KEYS =.*?\.split\(\" \"\)\)\);",
                          self.source, re.S).group(0)
        known = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", block))
        for key in ("stepSize", "values"):
            self.assertIn(key, known)


if __name__ == "__main__":
    unittest.main()
