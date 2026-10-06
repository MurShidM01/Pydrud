"""
PSS (Pydrud Style Sheet) resolver and renderer profiles.

Resolver
--------
Given a :class:`~pydrud.core.styles.parser.StyleSheet` and a widget tree,
the resolver computes the effective style dict for every widget by:
* Indexing rules by selector type (type, class, id)
* Matching each widget against applicable rules
* Computing specificity as a tuple ``(is_inline, id_count, class_count, type_count)``
* Merging declarations in specificity order (higher wins; ties broken by order)

The resolver is pure and side-effect-free: calling it twice with the same
inputs yields the same output.

RendererProfile
---------------
Platform-specific quirks are modelled as data rather than hardcoded rules.
An :class:`AndroidRendererProfile` warns about known problematic patterns:
* Background-owning widgets (e.g. ``Container``, ``Card``) that have a
  child also setting ``bg`` — the inner ``bg`` is usually ignored.
* Simultaneous ``textAlign`` and ``alignment`` declarations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from pydrud.widgets.base import Widget
from pydrud.core.styles.parser import (
    StyleSheet, Rule, Selector, CompoundSelector, DeclarationBlock,
)


@dataclass(frozen=True)
class RendererProfile:
    """Platform rendering quirks as data."""
    #: Widget types that own their background (children's bg is ignored).
    background_owners: tuple[str, ...] = ()
    #: Known conflicting property pairs.
    conflict_pairs: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class AndroidRendererProfile(RendererProfile):
    background_owners = ("Container", "Card", "Stack")
    conflict_pairs = (("textAlign", "alignment"),)


def _specificity(selector: Selector) -> tuple[int, int, int, int, int]:
    """Compute specificity as a comparable tuple.

    ``(is_inline, id_count, class_count, type_count)`` compared lexicographically.
    Inline styles always win (highest is_inline).
    """
    id_count = sum(
        1 for c in selector.compounds if c.id is not None
    )
    class_count = sum(len(c.classes) for c in selector.compounds)
    type_count = sum(
        1 for c in selector.compounds if c.widget_type is not None
    )
    return (0, id_count, class_count, type_count)


def _match_selector(selector: Selector, widget: Widget) -> bool:
    """Check whether *selector* matches *widget*."""
    if not selector.compounds:
        return False
    # For simplicity we match the last compound against the widget.
    # Full descendant/child matching would require walking parent chains.
    comp = selector.compounds[-1]
    if comp.widget_type and widget._widget_type != comp.widget_type:
        return False
    if comp.id and widget.key != comp.id:
        return False
    # class matching: widget.style keys starting with "class_"
    widget_classes = {
        k[len("class_"):]
        for k in widget.style
        if k.startswith("class_")
    }
    for cls in comp.classes:
        if cls not in widget_classes:
            return False
    return True


def resolve_styles(
    stylesheet: StyleSheet,
    widgets: Iterable[Widget],
    profile: Optional[RendererProfile] = None,
) -> dict[str, dict]:
    """Return a mapping ``widget_key -> merged style dict``.

    Only explicitly-keyed widgets (``_auto_key == False``) are resolved;
    auto-generated keys do not participate in ``#id`` matching.
    """
    profile = profile or RendererProfile()
    result: dict[str, dict] = {}
    warnings: list[str] = []

    # Index rules for fast lookup
    type_rules: dict[str, list[tuple[Selector, DeclarationBlock]]] = {}
    class_rules: dict[str, list[tuple[Selector, DeclarationBlock]]] = {}
    id_rules: dict[str, list[tuple[Selector, DeclarationBlock]]] = {}

    for rule in stylesheet.rules:
        sel = rule.selector
        body = rule.body
        spec = _specificity(sel)
        for comp in sel.compounds:
            if comp.widget_type:
                type_rules.setdefault(comp.widget_type, []).append((sel, body))
            if comp.id:
                id_rules.setdefault(comp.id, []).append((sel, body))
            for cls in comp.classes:
                class_rules.setdefault(cls, []).append((sel, body))

    for w in widgets:
        key = w.key
        # Extract class names from the widget's style dict.
        widget_classes = {
            k[len("class_"):]
            for k in w.style
            if k.startswith("class_")
        }
        if getattr(w, "_auto_key", True):
            # Id selectors only match explicitly-supplied keys.
            # Auto-keyed widgets still match type and class selectors.
            matched_rules: list[tuple[tuple[int, int, int, int], DeclarationBlock]] = []
            for sel, body in type_rules.get(w._widget_type, []):
                matched_rules.append((_specificity(sel), body))
            for cls in widget_classes:
                for sel, body in class_rules.get(cls, []):
                    matched_rules.append((_specificity(sel), body))
        else:
            matched_rules = []
            for sel, body in type_rules.get(w._widget_type, []):
                matched_rules.append((_specificity(sel), body))
            for cls in widget_classes:
                for sel, body in class_rules.get(cls, []):
                    matched_rules.append((_specificity(sel), body))
            for sel, body in id_rules.get(key, []):
                matched_rules.append((_specificity(sel), body))

        # Sort by specificity ascending; later entries override earlier ones.
        matched_rules.sort(key=lambda x: x[0])
        merged: dict[str, str] = {}
        for _, body in matched_rules:
            for k, v in body.declarations:
                merged[k] = v

        # Only include widgets that actually matched rules.
        if matched_rules:
            result[key] = merged

            # Warn about known conflicts
            for p1, p2 in profile.conflict_pairs:
                if p1 in merged and p2 in merged:
                    warnings.append(
                        f"Conflicting properties '{p1}' and '{p2}' on widget {key!r}"
                    )

            # Warn about background nesting on Android
            if isinstance(profile, AndroidRendererProfile):
                if "bg" in merged and w._widget_type in profile.background_owners:
                    for child in w.children:
                        if "bg" in child.style:
                            warnings.append(
                                f"Child {child._widget_type} sets 'bg' inside "
                                f"{w._widget_type} which owns its own background."
                            )
                            break

    return result, warnings
