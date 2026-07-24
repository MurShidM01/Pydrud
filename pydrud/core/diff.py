"""
Virtual-tree diff engine.

Produces a list of ``Patch`` operations that the Android renderer applies
to update the native view tree efficiently.
"""

from __future__ import annotations
from typing import Any, Optional

from pydrud.widgets.base import Widget


# ── Diff result types ────────────────────────────────────────────────────────


class Patch:
    """A single mutation to apply to the native view tree."""

    def __init__(self, op: str, key: str, **data: Any):
        # op: "create" | "update" | "delete" | "move" | "replace"
        self.op = op
        self.key = key
        self.data = data

    def to_dict(self) -> dict:
        return {"op": self.op, "key": self.key, **self.data}

    def __repr__(self) -> str:
        return f"Patch({self.op}, {self.key})"


# ── Public API ───────────────────────────────────────────────────────────────


class TreeDiff:
    """Compares two widget trees and produces a minimal patch list."""

    @staticmethod
    def diff(old: Widget, new: Widget) -> list[Patch]:
        """Return patches to transform *old* into *new*."""
        patches: list[Patch] = []
        _diff_node(old, new, patches)
        return patches

    @staticmethod
    def patches_to_json(patches: list[Patch]) -> str:
        """Serialise patches to JSON for the Android bridge."""
        import json
        return json.dumps([p.to_dict() for p in patches], default=str)


# ── Internal helpers ─────────────────────────────────────────────────────────


def _diff_node(old: Optional[Widget], new: Widget, patches: list[Patch]):
    """Compute patches for a single node."""
    if old is None:
        # Entirely new subtree — include the full JSON tree.
        patches.append(Patch("create", new.key, tree=new.to_dict()))
        return

    if old._widget_type != new._widget_type:
        # Different widget types — replace the whole subtree.
        patches.append(Patch("replace", new.key, tree=new.to_dict()))
        return

    # Same type: check for property changes.
    changed_props = _changed_props(old, new)
    changed_style = _changed_dict(old.style, new.style)

    if changed_props or changed_style:
        patch_data: dict = {}
        if changed_props:
            patch_data["props"] = changed_props
        if changed_style:
            patch_data["style"] = changed_style
        patches.append(Patch("update", new.key, **patch_data))

    # Walk children.
    _diff_children(old.children, new.children, patches)


def _diff_children(old_list: list[Widget], new_list: list[Widget], patches: list[Patch]):
    """Simple index-based children diff.

    For V1 we use a straightforward approach: match by index.
    A future version can implement a keyed diff (longest-common-subsequence)
    for better performance with reordered children.
    """
    old_by_idx = {i: w for i, w in enumerate(old_list)}
    max_len = max(len(old_list), len(new_list))

    for i in range(max_len):
        old_w = old_by_idx.get(i)
        if i >= len(new_list):
            # Child was removed.
            if old_w is not None:
                patches.append(Patch("delete", old_w.key))
            continue

        new_w = new_list[i]

        # If both exist and have different keys, treat as replace.
        if old_w is not None and old_w.key != new_w.key:
            patches.append(Patch("delete", old_w.key))
            patches.append(Patch("create", new_w.key, tree=new_w.to_dict()))
            continue

        if old_w is not None:
            _diff_node(old_w, new_w, patches)
        else:
            # Brand-new child.
            patches.append(Patch("create", new_w.key, tree=new_w.to_dict()))


def _changed_props(old: Widget, new: Widget) -> dict:
    """Return a dict of changed properties, or empty dict if none."""
    changed: dict = {}
    old_p = old._serialise_props()
    new_p = new._serialise_props()

    all_keys = set(old_p.keys()) | set(new_p.keys())
    for k in all_keys:
        if old_p.get(k) != new_p.get(k):
            changed[k] = new_p.get(k)

    # Event handler presence.
    if bool(old.event_handlers) != bool(new.event_handlers):
        changed["_has_events"] = new.event_handlers.keys()

    if old.expand != new.expand:
        changed["_expand"] = new.expand

    if old.visible != new.visible:
        changed["_visible"] = new.visible

    if old.tooltip != new.tooltip:
        changed["_tooltip"] = new.tooltip

    return changed


def _changed_dict(old: dict, new: dict) -> dict:
    """Return entries in *new* that differ from *old*."""
    changed: dict = {}
    all_keys = set(old.keys()) | set(new.keys())
    for k in all_keys:
        if old.get(k) != new.get(k):
            changed[k] = new.get(k) if k in new else None
    return changed
