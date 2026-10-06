"""The native update path: Canvas ops and Positioned offsets.

PB-003 and PB-006 were both "the Python side emits a correct update patch,
the Android side silently ignores it". These tests pin the patch the diff
produces *and* the Java branches that apply it, so neither half can regress.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from pydrud import Canvas, Container, Positioned, Stack
from pydrud.core.diff import TreeDiff

VIEW_FACTORY = (Path(__file__).resolve().parent.parent / "pydrud" / "android"
                / "templates" / "android" / "ViewFactory.java.j2")


def _method_body(name_pattern: str) -> str:
    text = VIEW_FACTORY.read_text(encoding="utf-8")
    match = re.search(name_pattern + r".*?\n    \}", text, re.S)
    assert match, name_pattern
    return match.group(0)


def _updates(patches):
    return [p for p in patches if p.op == "update"]


class TestPositionedPatch(unittest.TestCase):

    def _stack(self, left: float, top: float) -> Stack:
        return Stack(key="field", children=[
            Positioned(left=left, top=top, key="ship", child=Container())])

    def test_diff_emits_the_new_offsets(self):
        patches = TreeDiff.diff(self._stack(10, 10), self._stack(210, 340))
        updates = _updates(patches)
        self.assertEqual(len(updates), 1, patches)
        style = updates[0].to_dict()["style"]
        self.assertEqual(style["left"], 210)
        self.assertEqual(style["top"], 340)

    def test_applystyle_reapplies_absolute_offsets(self):
        body = _method_body(r"private void applyStyle\(")
        self.assertIn('"absolute".equals(s.optString("position", ""))', body)
        for offset in ("leftMargin", "topMargin", "rightMargin", "bottomMargin"):
            with self.subTest(offset=offset):
                self.assertIn(offset, body)
        self.assertIn("view.setLayoutParams(flp)", body)


class TestCanvasPatch(unittest.TestCase):

    def _canvas(self, value: float) -> Canvas:
        return Canvas(key="board",
                      on_draw=lambda c, w, h: c.rect(0, 0, value, 10))

    def test_diff_emits_changed_ops(self):
        patches = TreeDiff.diff(self._canvas(5), self._canvas(50))
        updates = _updates(patches)
        self.assertEqual(len(updates), 1, patches)
        props = updates[0].to_dict()["props"]
        self.assertIn("ops", props)
        self.assertNotEqual(props["ops"], [])

    def test_updateprops_reapplies_canvas_ops(self):
        body = _method_body(r"private boolean updateProps\(")
        self.assertIn("instanceof AdvancedViews.PydrudCanvas", body)
        self.assertIn("advanced.updateCanvas(view, p)", body)


if __name__ == "__main__":
    unittest.main()
