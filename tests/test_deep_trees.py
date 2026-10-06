"""PB-001 — deep widget trees must not raise ``RecursionError``.

In 2.0.2 every tree traversal was recursive: ``clone`` (called on every
render) blew the C stack near depth 200, ``to_dict``/``walk``/``diff`` near
depth 1000. The algorithms are now iterative, and an over-deep tree raises a
structured :class:`MaxDepthError` (a ``RecursionError`` subclass) instead of
a bare stack overflow.
"""

from __future__ import annotations

import pytest

from pydrud import Column, MaxDepthError, Text
from pydrud.core.diff import TreeDiff
from pydrud.widgets.base import MAX_TREE_DEPTH, assign_stable_keys


def _deep(depth: int):
    node = Text("leaf", key="leaf")
    for i in range(depth):
        node = Column(children=[node], key=f"c{i}")
    return node


@pytest.mark.parametrize("depth", [150, 200, 500, 800])
def test_deep_tree_algorithms_are_iterative(depth):
    tree = _deep(depth)

    # to_dict — used to fail near depth 1000.
    serialised = tree.to_dict()
    assert serialised["type"] == "Column"
    assert serialised["children"], "the nesting must be preserved"

    # clone — used to fail near depth 200, on every render.
    clone = tree.clone()
    assert clone.key == tree.key
    assert clone.children[0].children, "clone must keep the full subtree"

    # walk / find_by_key.
    assert sum(1 for _ in tree.walk()) == depth + 1
    assert tree.find_by_key("leaf") is not None
    assert tree.find_by_key("missing") is None

    # assign_stable_keys.
    assign_stable_keys(tree, prefix="_page")

    # diff two identical deep trees — used to fail near depth 1000.
    assert TreeDiff.diff(_deep(depth), _deep(depth)) == []


def test_over_deep_tree_raises_structured_error():
    tree = _deep(MAX_TREE_DEPTH + 5)
    with pytest.raises(MaxDepthError) as excinfo:
        tree.to_dict()
    assert isinstance(excinfo.value, RecursionError)
    assert "maximum depth" in str(excinfo.value)


def test_clone_shares_event_handlers_but_copies_style():
    calls = []

    def handler():
        calls.append(1)

    tree = Column(
        children=[Text("hi", key="t")],
        key="root",
        style={"bg": "#FFFFFFFF"},
        on_click=handler,
    )
    clone = tree.clone()
    clone.style["bg"] = "#FF000000"
    assert tree.style["bg"] == "#FFFFFFFF", "style must be deep-copied"
    assert clone.event_handlers["click"] is handler, "handlers are shared"
