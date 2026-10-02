"""
The diff must be correct *against the applier that runs on the device*.

``ViewFactory.applyPatch`` executes patches in order:

* ``create`` inserts the new view at ``index``;
* ``move``   removes the view and re-inserts it at ``index``;
* ``replace`` swaps the view **in place** (it keeps the current position);
* ``delete`` removes it.

So every insertion and deletion shifts the children after it. This module
models that applier exactly and fuzzes it against random trees: if the diff
and the renderer ever disagree about ordering, a test fails here instead of
a list silently rendering in the wrong order on a phone.
"""

from __future__ import annotations

import random
import unittest

from pydrud.core.diff import TreeDiff
from pydrud.widgets.basic import Text
from pydrud.widgets.layout import Column


# ── A faithful model of the native applier ──────────────────────────────────

def node_of(tree: dict) -> list:
    """``{"key", "props", "children"}`` → ``[key, value, children]``."""
    return [tree.get("key"),
            (tree.get("props") or {}).get("value"),
            [node_of(child) for child in (tree.get("children") or [])]]


def widget_node(widget) -> list:
    widget = widget.unwrap()
    return [widget.key,
            widget._serialise_props().get("value"),
            [widget_node(child) for child in widget.children]]


def find(node: list, key: str):
    if node[0] == key:
        return node
    for child in node[2]:
        hit = find(child, key)
        if hit is not None:
            return hit
    return None


def apply_patches(state: list, patches) -> list:
    """Apply patches the way ``ViewFactory`` does."""
    for patch in patches:
        data = patch.to_dict()
        op, key = data["op"], data["key"]
        parent = find(state, data.get("parent_key", "")) \
            if data.get("parent_key") else None
        siblings = parent[2] if parent is not None else None

        if op == "delete":
            if siblings is not None:
                siblings[:] = [c for c in siblings if c[0] != key]
        elif op == "create":
            if siblings is None:
                continue
            index = data.get("index", -1)
            at = len(siblings) if index < 0 or index > len(siblings) else index
            siblings.insert(at, node_of(data["tree"]))
        elif op == "replace":
            fresh = node_of(data["tree"])
            if siblings is None:          # root replacement
                state[:] = fresh
                continue
            for position, child in enumerate(siblings):
                if child[0] == key:
                    siblings[position] = fresh   # keeps the current position
                    break
        elif op == "move":
            if siblings is None:
                continue
            moving = next(c for c in siblings if c[0] == key)
            siblings.remove(moving)
            index = min(data["index"], len(siblings))
            siblings.insert(index, moving)
        elif op == "update":
            target = find(state, key)
            if target is not None and "value" in data.get("props", {}):
                target[1] = data["props"]["value"]
    return state


# ── Tree generation ─────────────────────────────────────────────────────────

def build(spec: list) -> list:
    children = []
    for key, value, sub in spec:
        if sub is None:
            children.append(Text(value, key=key))
        else:
            children.append(Column(children=build(sub), key=key))
    return children


def tree(spec: list):
    return Column(children=build(spec), key="root")


def random_spec(rng: random.Random, depth: int = 0,
                pool: list | None = None) -> list:
    """Random children with keys unique across the whole tree.

    Pydrud requires globally unique keys (the native renderer keeps one
    key → View map), so the generator must honour that too.
    """
    if pool is None:
        pool = [f"k{n}" for n in range(8)]
        rng.shuffle(pool)
    spec: list = []
    for _ in range(rng.randint(0, 4)):
        if not pool:
            break
        key = pool.pop()
        if depth < 1 and rng.random() < 0.4:
            spec.append((key, None, random_spec(rng, depth + 1, pool)))
        else:
            spec.append((key, f"v{rng.randint(0, 3)}", None))
    return spec


class TestDiffMatchesApplier(unittest.TestCase):

    def check(self, old_spec: list, new_spec: list) -> None:
        old, new = tree(old_spec), tree(new_spec)
        state = widget_node(old)
        apply_patches(state, TreeDiff.diff(old, new))
        self.assertEqual(widget_node(new), state,
                         f"{old_spec} -> {new_spec}")

    # ── the regressions this suite was written for ──────────────────────

    def test_insert_while_reordering(self):
        """Two inserts around a survivor that keeps its old index.

        ``b`` sits at index 1 before and after, so the old algorithm never
        moved it — but the two creations pushed it to index 3 on the
        device, and the row rendered as ``new1, a, new2, b``.
        """
        self.check([("a", None, [("x", "1", None)]), ("b", None, [])],
                   [("new1", "n", None), ("b", "flat", None),
                    ("new2", "m", None), ("a", "flat2", None)])

    def test_insert_before_a_replaced_sibling(self):
        """A prepend shifts the sibling the diff replaces in place."""
        self.check(
            [("a", None, [("x", "1", None)]), ("b", None, [])],
            [("new", "n", None), ("a", "flat", None), ("b", "flat2", None)],
        )

    def test_insert_shifts_an_unmoved_survivor(self):
        self.check([("a", "1", None), ("b", "2", None)],
                   [("new", "0", None), ("a", "1", None), ("b", "2", None)])

    def test_delete_shifts_a_later_survivor(self):
        self.check([("a", "1", None), ("b", "2", None), ("c", "3", None)],
                   [("b", "2", None), ("c", "3", None)])

    def test_reverse_order(self):
        self.check([("a", "1", None), ("b", "2", None), ("c", "3", None)],
                   [("c", "3", None), ("b", "2", None), ("a", "1", None)])

    def test_swap_middle_pair_with_an_insert(self):
        self.check([("a", "1", None), ("b", "2", None), ("c", "3", None)],
                   [("a", "1", None), ("c", "3", None), ("new", "x", None),
                    ("b", "2", None)])

    def test_nested_children_follow_their_parent(self):
        self.check(
            [("p", None, [("x", "1", None), ("y", "2", None)])],
            [("q", "new", None),
             ("p", None, [("y", "2", None), ("z", "3", None)])],
        )

    # ── fuzz ────────────────────────────────────────────────────────────

    def test_fuzz_against_the_native_applier(self):
        rng = random.Random(20240917)
        for _ in range(2000):
            old_spec = random_spec(rng)
            new_spec = random_spec(rng)
            with self.subTest(old=old_spec, new=new_spec):
                self.check(old_spec, new_spec)


if __name__ == "__main__":
    unittest.main()
