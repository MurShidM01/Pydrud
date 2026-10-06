"""PB-002 — an oversized render frame must never wedge the UI.

The 2.0.2 bug: ``_send_desired_tree`` registered the in-flight transaction
*before* encoding it, so when the frame exceeded ``MAX_FRAME_BYTES`` the
encode raised and left a phantom transaction behind. Every later render then
hit ``if self._inflight: return`` and was deferred forever — a silent,
permanent freeze.

These tests shrink the frame limit so the failure is cheap to reproduce, and
assert that a large tree is streamed (chunked) and that rendering recovers.
"""

from __future__ import annotations

import pytest

from pydrud import App, Column, State, Text
from pydrud.testing import AppTester


def _rows(count: int):
    return [
        Text("Item %03d " % i + "x" * 60, key=f"row-{i}")
        for i in range(count)
    ]


def test_plan_snapshot_frames_splits_a_large_tree():
    from pydrud.runtime.app import App

    tree = {
        "type": "Column", "key": "root", "style": {}, "props": {},
        "children": [
            {"type": "Text", "key": f"c{i}", "style": {}, "props": {"value": "y" * 400},
             "children": []}
            for i in range(200)
        ],
    }
    frames = App._plan_snapshot_frames(tree)
    assert frames, "a tree larger than the frame must be split"
    assert frames[0][1] == "snapshot"
    # Every node is either in the snapshot or created by exactly one patch.
    created = set()
    for payload, kind in frames[1:]:
        assert kind == "patch"
        for patch in payload["patches"]:
            assert patch["op"] == "create"
            created.add(patch["key"])
    snapshot_children = {c["key"] for c in frames[0][0]["tree"]["children"]}
    assert snapshot_children | created == {f"c{i}" for i in range(200)}
    assert not (snapshot_children & created)


def test_oversized_snapshot_streams_and_does_not_wedge(monkeypatch):
    import pydrud.core.protocol as protocol
    import pydrud.runtime.app as app_module

    monkeypatch.setattr(protocol, "MAX_FRAME_BYTES", 8192)
    monkeypatch.setattr(app_module, "MAX_FRAME_BYTES", 8192)

    count = State(3)

    def main(page):
        page.add(Column(key="list", children=_rows(count.value)))

    app = App(target=main, title="Recovery")
    app.bind(count)

    with AppTester(app=app) as tester:
        assert tester.count("Text") >= 3

        # Grow well past the (tiny) frame limit. 2.0.2 froze here forever.
        count.value = 250
        tester.app.update()
        tester.settle(timeout=5.0)

        assert tester.count("Text") == 250, "the whole tree must reach the device"
        assert not tester.app._inflight, "no phantom in-flight transaction"

        # Shrink again: rendering must still work after the big frame.
        count.value = 4
        tester.app.update()
        tester.settle(timeout=5.0)

        assert tester.count("Text") == 4
        assert not tester.app._inflight
        assert tester.device.full_renders >= 1
