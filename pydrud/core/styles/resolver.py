"""Platform-neutral PSS selector matching and style resolution.

Renderer-specific facts are supplied as optional :class:`RendererProfile`
data. The core resolver never imports a platform adapter or assumes a native
renderer; it only applies selector semantics and returns style dictionaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Number
import re
from typing import Iterable, Optional

from pydrud.core.styles.parser import DeclarationBlock, Selector, StyleSheet
from pydrud.core.styles.schema import KEY_KIND
from pydrud.widgets.base import Widget


@dataclass(frozen=True)
class RendererProfile:
    """Data-only description of optional renderer style behavior."""

    #: Widget types whose renderer-owned background may override ``bg``.
    background_owners: tuple[str, ...] = ()
    #: Property pairs with renderer-specific collisions.
    conflict_pairs: tuple[tuple[str, str], ...] = ()
    #: Style keys understood by this renderer, or ``None`` when unspecified.
    style_keys: frozenset[str] | None = None
    #: Widget types understood by this renderer, or ``None`` when unknown.
    widget_types: frozenset[str] | None = None


def _specificity(selector: Selector) -> tuple[int, int, int, int]:
    """Return CSS-like specificity (inline, ids, classes, widget types).

    Inline declarations are applied by :class:`App` after these rules, so the
    first component stays zero here and remains reserved for API symmetry.
    """
    ids = sum(comp.id is not None for comp in selector.compounds)
    classes = sum(len(comp.classes) for comp in selector.compounds)
    types = sum(comp.widget_type is not None for comp in selector.compounds)
    return (0, ids, classes, types)


def _widget_classes(widget: Widget) -> set[str]:
    """Get classes from the Python-only ``class_`` API.

    Read historical ``class_<name>`` markers too, so code that used the early
    PSS prototype still matches. Those markers are never serialized.
    """
    names = set(getattr(widget, "class_", ()) or ())
    names.update(
        key[len("class_"):]
        for key in widget.style
        if isinstance(key, str) and key.startswith("class_")
    )
    return names


def _matches_compound(
    compound,
    widget: Widget,
    *,
    allow_id: bool = True,
) -> bool:
    if compound.widget_type and widget._widget_type != compound.widget_type:
        return False
    if compound.id and (
            not allow_id
            or getattr(widget, "_auto_key", True)
            or widget.key != compound.id):
        return False
    classes = _widget_classes(widget)
    return all(name in classes for name in compound.classes)


def _match_selector(
    selector: Selector,
    widget: Widget,
    parents: dict[int, Optional[Widget]] | None = None,
) -> bool:
    """Match a selector right-to-left against *widget* and its ancestors."""
    if not selector.compounds:
        return False
    parents = parents or {}

    def match_at(index: int, current: Widget) -> bool:
        if not _matches_compound(selector.compounds[index], current):
            return False
        if index == 0:
            return True
        parent = parents.get(id(current))
        combinator = selector.combinators[index - 1]
        if combinator == ">":
            return parent is not None and match_at(index - 1, parent)
        if combinator == " ":
            while parent is not None:
                if match_at(index - 1, parent):
                    return True
                parent = parents.get(id(parent))
            return False
        return False

    return match_at(len(selector.compounds) - 1, widget)


def _flatten_widgets(
    widgets: Iterable[Widget] | Widget,
) -> tuple[list[Widget], dict[int, Optional[Widget]]]:
    roots = [widgets] if isinstance(widgets, Widget) else list(widgets)
    ordered: list[Widget] = []
    parents: dict[int, Optional[Widget]] = {}
    seen: set[int] = set()
    stack = [(root, None) for root in reversed(roots) if isinstance(root, Widget)]
    while stack:
        widget, parent = stack.pop()
        identity = id(widget)
        if identity in seen:
            continue
        seen.add(identity)
        ordered.append(widget)
        parents[identity] = parent
        stack.extend((child, widget) for child in reversed(widget.children))
    return ordered, parents


_DIMENSION_KEYS = frozenset({
    "width", "height", "minWidth", "maxWidth", "minHeight", "maxHeight",
})
_DIMENSION_VALUE = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:dp|px|%|vw|vh|%[whs])$",
    re.IGNORECASE,
)
_DIMENSION_KEYWORDS = frozenset({
    "match", "match_parent", "fill", "100%", "expand",
    "wrap", "wrap_content", "auto",
})


def _value_kind_warning(key: str, value, widget: Widget) -> str | None:
    kind = KEY_KIND.get(key)
    if kind is None:
        return None
    valid = True
    if kind == "number":
        valid = isinstance(value, Number) and not isinstance(value, bool)
        if isinstance(value, str) and key in _DIMENSION_KEYS:
            normalized = value.strip().lower()
            valid = (
                normalized in _DIMENSION_KEYWORDS
                or bool(_DIMENSION_VALUE.fullmatch(normalized))
            )
    elif kind == "color":
        valid = isinstance(value, str) and bool(value.strip())
    elif kind == "keyword":
        valid = isinstance(value, (str, bool))
    elif kind == "composite":
        valid = isinstance(value, (dict, list, tuple))
    if valid:
        return None
    return (
        f"Style property {key!r} has a value incompatible with its "
        f"{kind} schema on widget {widget.key!r}"
    )


def resolve_styles(
    stylesheet: StyleSheet,
    widgets: Iterable[Widget] | Widget,
    profile: Optional[RendererProfile] = None,
) -> tuple[dict[str, dict], list[str]]:
    """Resolve matching rules to ``(widget_key -> style, warnings)``.

    ``widgets`` can be a root widget (for full descendant/child matching) or
    an iterable of roots. Explicit keys alone participate in ``#id`` rules;
    generated structural keys remain implementation details.
    """
    profile = profile or RendererProfile()
    ordered_widgets, parents = _flatten_widgets(widgets)
    result: dict[str, dict] = {}
    warnings: list[str] = []

    for widget in ordered_widgets:
        matched: list[tuple[tuple[int, int, int, int], int, DeclarationBlock]] = []
        for source_order, rule in enumerate(stylesheet.rules):
            if _match_selector(rule.selector, widget, parents):
                matched.append((_specificity(rule.selector), source_order, rule.body))
        if not matched:
            continue

        # CSS specificity wins first; source order breaks ties. Stable order
        # also preserves declaration order within each block.
        matched.sort(key=lambda item: (item[0], item[1]))
        merged: dict = {}
        for _, _, body in matched:
            for key, value in body.declarations:
                merged[key] = value
        result[widget.key] = merged

        for property_name, value in merged.items():
            value_warning = _value_kind_warning(property_name, value, widget)
            if value_warning:
                warnings.append(value_warning)
            if (profile.style_keys is not None
                    and property_name not in profile.style_keys):
                warnings.append(
                    f"Renderer profile does not declare style key "
                    f"{property_name!r} on widget {widget.key!r}"
                )

        if (profile.widget_types is not None
                and widget._widget_type not in profile.widget_types):
            warnings.append(
                f"Renderer profile does not declare widget type "
                f"{widget._widget_type!r} (key {widget.key!r})"
            )
        for first, second in profile.conflict_pairs:
            if first in merged and second in merged:
                warnings.append(
                    f"Conflicting properties {first!r} and {second!r} "
                    f"on widget {widget.key!r}"
                )
        if "bg" in merged and widget._widget_type in profile.background_owners:
            warnings.append(
                f"Renderer profile reports that {widget._widget_type} owns its "
                f"background; the 'bg' style may be ignored."
            )

    # Parser warnings are useful to callers that use the resolver directly;
    # errors are retained on StyleSheet.diagnostics and handled by loaders.
    warnings.extend(
        f"{diagnostic.filename}:{diagnostic.line}:{diagnostic.col}: "
        f"{diagnostic.message}"
        for diagnostic in stylesheet.diagnostics
        if diagnostic.kind == "warning"
    )
    return result, warnings
