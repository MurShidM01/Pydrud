"""
Virtual-tree diff engine.

Produces a list of ``Patch`` operations that the Android renderer applies
to update the native view tree efficiently.

The children diff is *keyed*: widgets are matched by key rather than by
index, so inserting or removing an item in the middle of a list only
patches that item instead of re-creating everything after it.
"""

from __future__ import annotations
import hashlib
import json
from typing import Any, Optional

from pydrud.widgets.base import Widget, validate_tree_keys


# ── Diff result types ────────────────────────────────────────────────────────


class Patch:
    """A single mutation to apply to the native view tree."""

    #: Valid operations.
    OPS = ("create", "update", "delete", "move", "replace")

    def __init__(self, op: str, key: str, *, parent_key: str = "", **data: Any):
        if op not in self.OPS:
            raise ValueError(f"Unknown patch op: {op!r}")
        self.op = op
        self.key = key
        self.parent_key = parent_key
        self.data = data

    @property
    def props(self) -> dict:
        """Changed widget properties (empty for non-update patches)."""
        return self.data.get("props", {})

    @property
    def style(self) -> dict:
        """Changed style entries (empty for non-update patches)."""
        return self.data.get("style", {})

    @property
    def index(self) -> int:
        """Target child index for create/move/replace patches (-1 if n/a)."""
        return self.data.get("index", -1)

    @property
    def tree(self) -> dict:
        """The serialised subtree for create/replace patches."""
        return self.data.get("tree", {})

    def to_dict(self) -> dict:
        d = {"op": self.op, "key": self.key, "parent_key": self.parent_key}
        d.update(self.data)
        return d

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Patch) and self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return f"Patch({self.op}, {self.key})"


# ── Public API ───────────────────────────────────────────────────────────────


class TreeDiff:
    """Compares two widget trees and produces a minimal patch list."""

    @staticmethod
    def diff(old: Optional[Widget], new: Optional[Widget]) -> list[Patch]:
        """Return patches that transform *old* into *new*."""
        patches: list[Patch] = []
        if old is not None:
            validate_tree_keys(old)
        if new is not None:
            validate_tree_keys(new)
        if new is None:
            if old is not None:
                patches.append(Patch("delete", old.unwrap().key))
            return patches
        _diff_node(old, new, patches, parent_key="", index=0)
        return patches

    @staticmethod
    def patches_to_json(patches: list[Patch]) -> str:
        """Serialise patches to JSON for the Android bridge."""
        return json.dumps([p.to_dict() for p in patches], default=str)


# ── Internal helpers ─────────────────────────────────────────────────────────


def _diff_node(
    old: Optional[Widget],
    new: Widget,
    patches: list[Patch],
    *,
    parent_key: str = "",
    index: int = 0,
):
    """Compute patches for a single node."""
    new = new.unwrap()
    if old is not None:
        old = old.unwrap()
    if old is None:
        # Entirely new subtree — include the full JSON tree.
        patches.append(
            Patch("create", new.key, parent_key=parent_key, index=index, tree=new.to_dict())
        )
        return

    if old._widget_type != new._widget_type or old.key != new.key:
        # Different widget identity — replace the whole subtree.
        patches.append(
            Patch("replace", old.key, parent_key=parent_key, index=index,
                  new_key=new.key, tree=new.to_dict())
        )
        return

    # Same type and key: check for property changes.
    changed_props = _changed_props(old, new)
    changed_style = _changed_dict(old.style, new.style)

    if changed_props or changed_style:
        patch_data: dict = {}
        if changed_props:
            patch_data["props"] = changed_props
        if changed_style:
            patch_data["style"] = changed_style
        patches.append(Patch("update", new.key, parent_key=parent_key, **patch_data))

    # Walk children.
    _diff_children(old.children, new.children, patches, parent_key=new.key)


def _diff_children(
    old_list: list[Widget],
    new_list: list[Widget],
    patches: list[Patch],
    *,
    parent_key: str = "",
):
    """Keyed children diff.

    Children are matched by key: survivors are diffed in place, children
    only in the old tree are deleted and children only in the new tree are
    created at their target index.

    Positions are tracked against an *evolving* list rather than the
    original one. The native applier executes patches in order — ``create``
    inserts at ``index`` and ``move`` removes then re-inserts at ``index``
    — so every insertion and deletion shifts the children after it. Using
    the original indices meant a child that kept its old index but was
    pushed along by an earlier insert was never moved, and the row ended up
    in the wrong order on the device (e.g. prepending one item while
    replacing another).
    """
    old_list = [w.unwrap() for w in old_list]
    new_list = [w.unwrap() for w in new_list]
    _preserve_keyless_identities(old_list, new_list, parent_key)
    old_by_key = _index_unique(old_list, parent_key)
    new_by_key = _index_unique(new_list, parent_key)

    # 1. Deletions (old children that disappeared).
    for widget in old_list:
        if widget.key not in new_by_key:
            patches.append(Patch("delete", widget.key, parent_key=parent_key))

    # The order the native side is left in once the deletions are applied.
    order = [w.key for w in old_list if w.key in new_by_key]

    # 2. Creations / moves / updates, left to right.
    for index, new_w in enumerate(new_list):
        old_w = old_by_key.get(new_w.key)
        if old_w is None:
            patches.append(
                Patch("create", new_w.key, parent_key=parent_key,
                      index=index, tree=new_w.to_dict())
            )
            order.insert(index, new_w.key)
            continue

        current = order.index(new_w.key)
        if current != index:
            patches.append(
                Patch("move", new_w.key, parent_key=parent_key, index=index)
            )
            order.pop(current)
            order.insert(index, new_w.key)
        # ``replace`` keeps the view at its current position, so the move
        # above must happen first — hence diffing the node last.
        _diff_node(old_w, new_w, patches, parent_key=parent_key, index=index)


def _copy_auto_keys(fresh_node: Widget, prev_node: Widget) -> None:
    """Recursively synchronize auto-generated keys for matched subtrees."""
    fresh_node.key = prev_node.key
    for fc, pc in zip(fresh_node.children, prev_node.children):
        if getattr(fc, "_auto_key", False) and getattr(pc, "_auto_key", False):
            _copy_auto_keys(fc, pc)


def _preserve_keyless_identities(
    old_list: list[Widget], new_list: list[Widget], parent_key: str,
) -> None:
    """Give recognisable keyless survivors their previous native identity.

    ``assign_stable_keys`` correctly makes a static keyless layout stable, but
    its structural keys cannot tell that ``Text("B")`` moved from position 1
    to position 0.  On a reorder that used to turn a focused field or a
    scrolled native widget into a replacement.  Explicit user keys always win;
    only auto-generated siblings with a unique rendered fingerprint are
    remapped. Ambiguous duplicates deliberately keep positional semantics.
    """
    old_candidates: dict[str, list[Widget]] = {}
    new_candidates: dict[str, list[Widget]] = {}
    for widget in old_list:
        if getattr(widget, "_auto_key", False):
            old_candidates.setdefault(_keyless_fingerprint(widget), []).append(widget)
    for widget in new_list:
        if getattr(widget, "_auto_key", False):
            new_candidates.setdefault(_keyless_fingerprint(widget), []).append(widget)

    used: set[str] = set()
    matched: set[int] = set()
    for fingerprint, fresh in new_candidates.items():
        previous = old_candidates.get(fingerprint, [])
        # A 1:1 signature is safe. With duplicate cards/rows there is no
        # reliable identity without an explicit key, so positional matching is
        # less surprising than moving an arbitrary duplicate.
        if len(previous) == len(fresh) == 1:
            _copy_auto_keys(fresh[0], previous[0])
            used.add(previous[0].key)
            matched.add(id(fresh[0]))

    occupied = {w.key for w in new_list if not getattr(w, "_auto_key", False)} | used
    for ordinal, widget in enumerate(new_list):
        if (not getattr(widget, "_auto_key", False)
                or id(widget) in matched
                or widget.key not in occupied):
            occupied.add(widget.key)
            continue
        # An inserted keyless child can retain a structural key already given
        # to a matched survivor. Allocate a deterministic temporary identity;
        # on a later rebuild its fingerprint will match and recover this key.
        digest = hashlib.sha1(
            f"{parent_key}|{_keyless_fingerprint(widget)}|{ordinal}".encode("utf-8")
        ).hexdigest()[:10]
        base = f"{parent_key or 'root'}._auto_{digest}_{widget._widget_type}"
        key, suffix = base, 2
        while key in occupied:
            key = f"{base}_{suffix}"
            suffix += 1
        widget.key = key
        occupied.add(key)


def _keyless_fingerprint(widget: Widget) -> str:
    """A conservative content signature used only for keyless matching."""
    try:
        payload = {
            "type": widget._widget_type,
            "props": widget._serialise_props(),
            "style": widget.style,
            "expand": widget.expand,
            "visible": widget.visible,
            "tooltip": widget.tooltip,
            "children": [_keyless_fingerprint(c) for c in widget.children],
        }
        return json.dumps(payload, sort_keys=True, default=str,
                          separators=(",", ":"))
    except Exception:
        # Never let an exotic custom prop make reconciliation fail. A unique
        # value means it simply falls back to the existing structural key.
        return f"{widget._widget_type}:{id(widget)}"


def _changed_props(old: Widget, new: Widget) -> dict:
    """Return a dict of changed properties, or empty dict if none."""
    changed: dict = {}
    old_p = old._serialise_props()
    new_p = new._serialise_props()

    all_keys = set(old_p.keys()) | set(new_p.keys())
    for k in all_keys:
        if old_p.get(k) != new_p.get(k):
            changed[k] = new_p.get(k)

    # Event handler presence (names only — callables are not serialisable).
    old_events = sorted(old.event_handlers.keys())
    new_events = sorted(new.event_handlers.keys())
    if old_events != new_events:
        changed["_events"] = new_events
        changed["_has_events"] = bool(new_events)

    if old.expand != new.expand:
        changed["_expand"] = new.expand

    if old.visible != new.visible:
        changed["_visible"] = new.visible

    if old.tooltip != new.tooltip:
        changed["_tooltip"] = new.tooltip

    return changed


def _changed_dict(old: dict, new: dict) -> dict:
    """Return entries in *new* that differ from *old* (removals become None)."""
    changed: dict = {}
    all_keys = set(old.keys()) | set(new.keys())
    for k in all_keys:
        if old.get(k) != new.get(k):
            changed[k] = new.get(k) if k in new else None
    return changed


def _index_unique(items: list[Widget], parent_key: str) -> dict[str, Widget]:
    """Build a keyed index while producing an actionable duplicate error."""
    result: dict[str, Widget] = {}
    for index, widget in enumerate(items):
        if widget.key in result:
            raise ValueError(
                f"Duplicate widget key {widget.key!r} under parent "
                f"{parent_key or '<root>'}; child indexes include "
                f"{index} and an earlier position"
            )
        result[widget.key] = widget
    return result
