"""The ``NativeView`` escape hatch (PYDRUD §15.3).

An app team must be able to drop in any Android ``View`` subclass without
forking Pydrud or regenerating the Java. The Java side cannot run here, so
these tests pin the three things that make the escape hatch usable: the
serialised payload, the diff path (props change in place), and the exact
contract the generated Java implements.
"""

from __future__ import annotations

import os
import unittest

from pydrud import NativeView, Text
from pydrud.core.diff import TreeDiff
from pydrud.testing import AppTester

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEW_FACTORY = os.path.join(ROOT, "pydrud", "android", "templates",
                            "android", "ViewFactory.java.j2")


def _java() -> str:
    with open(VIEW_FACTORY, encoding="utf-8") as handle:
        return handle.read()


class TestSerialisation(unittest.TestCase):

    def test_the_class_name_and_props_are_sent(self):
        node = NativeView("com.example.MyGauge",
                          props={"value": 0.42, "unit": "%"},
                          key="g").to_dict()
        self.assertEqual(node["type"], "NativeView")
        self.assertEqual(node["props"]["viewClass"], "com.example.MyGauge")
        self.assertEqual(node["props"]["value"], 0.42)
        self.assertEqual(node["props"]["unit"], "%")

    def test_explicit_props_win_over_stray_kwargs(self):
        node = NativeView("com.example.V", props={"value": 2},
                          value=1).to_dict()
        self.assertEqual(node["props"]["value"], 2)

    def test_it_can_host_children(self):
        node = NativeView("com.example.V",
                          children=[Text("inner", key="t")]).to_dict()
        self.assertEqual(node["children"][0]["props"]["value"], "inner")

    def test_style_is_applied(self):
        node = NativeView("com.example.V",
                          style={"width": 240, "height": 240}).to_dict()
        self.assertEqual(node["style"]["width"], 240)

    def test_a_blank_class_name_is_rejected(self):
        for bad in ("", "   ", None):
            with self.subTest(value=bad):
                with self.assertRaises(ValueError):
                    NativeView(bad)

    def test_an_unqualified_class_name_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            NativeView("MyGauge")
        self.assertIn("fully-qualified", str(caught.exception))

    def test_repr_names_the_class(self):
        self.assertIn("com.example.V", repr(NativeView("com.example.V")))


class TestDiffing(unittest.TestCase):

    def test_a_prop_change_is_an_in_place_update(self):
        patches = TreeDiff.diff(
            NativeView("com.example.V", props={"value": 1}, key="g"),
            NativeView("com.example.V", props={"value": 2}, key="g"))
        self.assertEqual([p.op for p in patches], ["update"], patches)
        self.assertEqual(patches[0].props["value"], 2)
        self.assertNotIn("viewClass", patches[0].props,
                         "an unchanged class must not be re-sent")

    def test_a_class_change_is_sent_as_a_prop_update(self):
        patches = TreeDiff.diff(NativeView("com.example.A", key="g"),
                                NativeView("com.example.B", key="g"))
        self.assertEqual([p.op for p in patches], ["update"], patches)
        self.assertEqual(patches[0].props["viewClass"], "com.example.B")

    def test_a_custom_view_renders_in_the_harness(self):
        with AppTester(lambda page: page.add(
                NativeView("com.example.V", props={"value": 7},
                           key="g"))) as app:
            self.assertEqual(app.prop("g", "viewClass"), "com.example.V")
            self.assertEqual(app.prop("g", "value"), 7)


class TestGeneratedJava(unittest.TestCase):
    """The renderer must implement the documented contract."""

    def setUp(self):
        self.source = _java()

    def test_the_type_is_dispatched(self):
        self.assertIn('case "NativeView":', self.source)

    def test_it_loads_the_class_from_the_app_loader(self):
        self.assertIn("Class.forName(className, true, activity.getClassLoader())",
                      self.source)

    def test_it_requires_the_class_to_be_a_view(self):
        self.assertIn("View.class.isAssignableFrom(cls)", self.source)

    def test_it_constructs_from_context(self):
        self.assertIn("getConstructor(android.content.Context.class)",
                      self.source)

    def test_applyprops_is_preferred(self):
        self.assertIn('getMethod("applyProps", JSONObject.class)',
                      self.source)

    def test_props_fall_back_to_setters(self):
        self.assertIn('"set" + Character.toUpperCase', self.source)
        self.assertIn("findSetter(view.getClass(), setter, value)",
                      self.source)

    def test_json_numbers_are_coerced_to_the_parameter_type(self):
        for target in ("int.class", "float.class", "double.class",
                       "long.class", "String.class"):
            with self.subTest(target=target):
                self.assertIn(target, self.source)

    def test_a_missing_setter_is_logged(self):
        self.assertIn("has no \" + setter", self.source)

    def test_failures_fall_back_to_an_empty_box(self):
        self.assertIn("return new FrameLayout(activity);", self.source)
        self.assertIn("failed to mount", self.source)

    def test_the_view_is_reused_across_updates(self):
        # isReusableType must list NativeView, or every render would rebuild
        # the custom view and throw away its state.
        self.assertIn('case "NativeView":', self.source)
        self.assertIn("case \"NativeView\":\n                return true;",
                      self.source)

    def test_a_changed_class_recreates_the_view(self):
        self.assertIn("return false;   // updateProps() -> recreateInPlace()",
                      self.source)

    def test_updates_receive_the_whole_prop_set(self):
        self.assertIn("mergeProps(node.optJSONObject(\"props\"), p)",
                      self.source)

    def test_children_are_attached_for_a_viewgroup(self):
        self.assertIn("if (view instanceof ViewGroup) attachChildren(view, json);",
                      self.source)


if __name__ == "__main__":
    unittest.main()
