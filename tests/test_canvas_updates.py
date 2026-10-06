"""PB-004 — a Canvas painted from shared state must actually update.

The 2.0.2 diff re-ran each widget's ``_serialise_props()`` for both the old
and the new tree. For a ``Canvas`` that means re-running ``on_draw``; when
the painter reads shared mutable state (the normal game-loop pattern) the
*old* widget was re-serialised against the *current* state, so old and new
produced identical ops and the diff emitted zero patches — the canvas froze
silently.

The fix freezes each widget's props at build time and diffs the frozen
values. These tests pin both the app-level behaviour and the lower-level
contract.
"""

from __future__ import annotations

import pytest

from pydrud import Canvas, Column
from pydrud.core.diff import TreeDiff
from pydrud.testing import AppTester


def test_frozen_canvas_diff_emits_update():
    """A build-time frozen Canvas diffs correctly against the live state."""
    scene = {"x": 0.10}

    def painter(canvas, width, height):
        canvas.circle(scene["x"], 0.5, 0.05)

    old = Canvas(on_draw=painter, key="cv", height=100)
    old.to_dict()                       # freeze at x=0.10

    scene["x"] = 0.90                   # "the engine advanced"
    new = Canvas(on_draw=painter, key="cv", height=100)
    new.to_dict()                       # freeze at x=0.90

    patches = TreeDiff.diff(old, new)
    assert [p.op for p in patches] == ["update"]
    assert patches[0].props["ops"][0]["x"] == pytest.approx(0.90)


def test_canvas_over_shared_state_repaints_on_device():
    """End to end: the native view receives the new ops after a state change."""
    scene = {"x": 0.10}

    def painter(canvas, width, height):
        canvas.circle(scene["x"], 0.5, 0.05)

    def main(page):
        page.add(Column(key="col", children=[
            Canvas(on_draw=painter, key="cv", height=100),
        ]))

    with AppTester(main) as tester:
        first = tester.node("cv")
        assert first is not None, "the canvas must render"
        assert first.props["ops"][0]["x"] == pytest.approx(0.10)

        scene["x"] = 0.90
        tester.app.run_on_ui(tester.app.update)
        tester.settle(timeout=2.0)

        second = tester.node("cv")
        assert second.props["ops"][0]["x"] == pytest.approx(0.90), (
            "the canvas ops must follow the shared state"
        )
