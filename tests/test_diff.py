"""
Unit tests for the virtual-tree diff engine.
"""

import unittest
from pydrud.widgets import Text, Container, Column, Button
from pydrud.core.diff import TreeDiff, Patch


class TestTreeDiff(unittest.TestCase):
    def test_no_changes(self):
        old = Text("Hello", key="t1")
        new = Text("Hello", key="t1")
        patches = TreeDiff.diff(old, new)
        self.assertEqual(len(patches), 0)

    def test_prop_change(self):
        old = Text("Hello", key="t1")
        new = Text("World", key="t1")
        patches = TreeDiff.diff(old, new)
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0].op, "update")
        self.assertEqual(patches[0].key, "t1")
        self.assertIn("props", patches[0].data)

    def test_style_change(self):
        old = Text("Hi", key="t1")
        new = Text("Hi", key="t1")
        new.style = {"color": "red"}
        patches = TreeDiff.diff(old, new)
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0].op, "update")
        self.assertIn("style", patches[0].data)

    def test_type_change_triggers_replace(self):
        old = Text("Hi", key="k1")
        new = Button("Hi", key="k1")
        patches = TreeDiff.diff(old, new)
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0].op, "replace")

    def test_child_added(self):
        old = Column(key="col", children=[Text("A", key="a")])
        new = Column(key="col", children=[Text("A", key="a"), Text("B", key="b")])
        patches = TreeDiff.diff(old, new)
        creates = [p for p in patches if p.op == "create"]
        self.assertEqual(len(creates), 1)
        self.assertEqual(creates[0].key, "b")

    def test_child_removed(self):
        old = Column(key="col", children=[Text("A", key="a"), Text("B", key="b")])
        new = Column(key="col", children=[Text("A", key="a")])
        patches = TreeDiff.diff(old, new)
        deletes = [p for p in patches if p.op == "delete"]
        self.assertEqual(len(deletes), 1)
        self.assertEqual(deletes[0].key, "b")

    def test_child_replaced_when_key_differs(self):
        old = Column(key="col", children=[Text("A", key="a")])
        new = Column(key="col", children=[Text("C", key="c")])
        patches = TreeDiff.diff(old, new)
        ops = [(p.op, p.key) for p in patches]
        self.assertIn(("delete", "a"), ops)
        self.assertIn(("create", "c"), ops)

    def test_nested_diff(self):
        old = Container(
            key="root",
            child=Column(key="col", children=[Text("A", key="a")]),
        )
        new = Container(
            key="root",
            child=Column(key="col", children=[Text("B", key="a")]),
        )
        patches = TreeDiff.diff(old, new)
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0].op, "update")

    def test_serialize_patches(self):
        old = Text("A", key="t1")
        new = Text("B", key="t1")
        patches = TreeDiff.diff(old, new)
        json_str = TreeDiff.patches_to_json(patches)
        self.assertIn("op", json_str)
        self.assertIn("update", json_str)


class TestPatch(unittest.TestCase):
    def test_patch_creation(self):
        p = Patch("create", "key1", tree={"type": "Text"})
        self.assertEqual(p.op, "create")
        self.assertEqual(p.key, "key1")
        self.assertEqual(p.data["tree"]["type"], "Text")

    def test_patch_to_dict(self):
        p = Patch("update", "k1", props={"value": "X"})
        d = p.to_dict()
        self.assertEqual(d["op"], "update")
        self.assertEqual(d["key"], "k1")
        self.assertEqual(d["props"]["value"], "X")


if __name__ == "__main__":
    unittest.main()
