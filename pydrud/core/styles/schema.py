"""
Cross-platform neutral style vocabulary for Pydrud.

This module owns every known style key and its value kind so that both the
static analyser and the .pss stylesheet engine share one source of truth —
write a property inline or in a .pss file and it means exactly the same thing.

Value kinds
-----------
* ``number``  — integer or float (may also accept the string ``"match"`` for
                width/height).
* ``color``   — ARGB hex string, e.g. ``"#FF6366F1"``.
* ``keyword`` — one of a finite set of symbolic values (e.g. ``"start"`` /
                ``"end"``).
* ``composite`` — a nested structure such as an edge-inset dict or a font
                  sub-dict; the analyser accepts any mapping when this is set.

Kebab-case aliases
------------------
Every canonical Python key also accepts a kebab-case spelling (e.g.
``text-align`` → ``text_align``) so .pss authors can write CSS-style keys.
Both normalise to the canonical name here; the renderer sees only the
canonical form.
"""

from __future__ import annotations
from typing import Literal

#: A known style key together with the kind of value it accepts.
_StyleEntry = tuple[str, str]  # (canonical_name, kind)

# ── Canonical vocabulary ────────────────────────────────────────────────────

VALID_STYLE_KEYS: frozenset[str] = frozenset({
    "bg", "opacity", "width", "height", "minWidth", "maxWidth",
    "minHeight", "maxHeight", "padding", "margin", "border", "borderRadius",
    "font", "textAlign", "alignment", "expand", "visible", "tooltip",
    "rotate", "fit", "bgImage", "elevation", "position", "bottom", "right",
    "top", "left", "spacing", "mainAxis", "crossAxisAlignment", "scroll",
    "variant", "icon", "buttonSize", "disabled", "multiline", "password",
    "readOnly", "keyboard", "activeColor", "color", "thickness",
    "textScale", "status_bar_color", "icon_brightness",
    "borderLeft", "borderRight", "borderTop", "borderBottom",
    "columns", "circular", "divisions", "maxLines", "overflow", "selectable",
    "tristate", "crossAxis", "mainAxisAlignment",
    # v1.2
    "animation", "scale", "rotation", "drawerSide", "fabPosition",
    "safeArea", "resizeForKeyboard", "shadow", "aspectRatio", "zIndex",
    # v1.5 — responsive
    "safeAreaTop", "safeAreaBottom", "breakpoint",
    # read by the native renderer (ViewFactory / MaterialViews)
    "gradient", "feedback", "role", "pill", "accent", "size",
    "minItemWidth", "maxColumns", "tabletColumns",
    # v2.0 — FractionallySizedBox factors
    "widthFactor", "heightFactor",
})

#: Mapping from canonical key → (kind, description). Used by the parser and
#: the analyser to validate values without duplicating knowledge.
KEY_KIND: dict[str, str] = {
    "bg": "color",
    "opacity": "number",
    "width": "number",
    "height": "number",
    "minWidth": "number",
    "maxWidth": "number",
    "minHeight": "number",
    "maxHeight": "number",
    "padding": "composite",
    "margin": "composite",
    "border": "composite",
    "borderRadius": "number",
    "font": "composite",
    "textAlign": "keyword",
    "alignment": "keyword",
    "expand": "number",
    "visible": "keyword",
    "tooltip": "keyword",
    "rotate": "number",
    "fit": "keyword",
    "bgImage": "keyword",
    "elevation": "number",
    "position": "keyword",
    "bottom": "number",
    "right": "number",
    "top": "number",
    "left": "number",
    "spacing": "number",
    "mainAxis": "keyword",
    "crossAxisAlignment": "keyword",
    "scroll": "keyword",
    "variant": "keyword",
    "icon": "keyword",
    "buttonSize": "number",
    "disabled": "keyword",
    "multiline": "keyword",
    "password": "keyword",
    "readOnly": "keyword",
    "keyboard": "keyword",
    "activeColor": "color",
    "color": "color",
    "thickness": "number",
    "textScale": "number",
    "status_bar_color": "color",
    "icon_brightness": "keyword",
    "borderLeft": "number",
    "borderRight": "number",
    "borderTop": "number",
    "borderBottom": "number",
    "columns": "number",
    "circular": "keyword",
    "divisions": "number",
    "maxLines": "number",
    "overflow": "keyword",
    "selectable": "keyword",
    "tristate": "keyword",
    "crossAxis": "number",
    "mainAxisAlignment": "keyword",
    "animation": "keyword",
    "scale": "number",
    "rotation": "number",
    "drawerSide": "keyword",
    "fabPosition": "keyword",
    "safeArea": "keyword",
    "resizeForKeyboard": "keyword",
    "shadow": "number",
    "aspectRatio": "number",
    "zIndex": "number",
    "safeAreaTop": "number",
    "safeAreaBottom": "number",
    "breakpoint": "number",
    "gradient": "composite",
    "feedback": "number",
    "role": "keyword",
    "pill": "keyword",
    "accent": "color",
    "size": "number",
    "minItemWidth": "number",
    "maxColumns": "number",
    "tabletColumns": "number",
    "widthFactor": "number",
    "heightFactor": "number",
}

#: Kebab-case spellings accepted in .pss files; normalised to the canonical
#: Python key before any validation.
_KEBAB_CANONICAL: dict[str, str] = {
    "text-align": "textAlign",
    "min-width": "minWidth",
    "max-width": "maxWidth",
    "min-height": "minHeight",
    "max-height": "maxHeight",
    "border-radius": "borderRadius",
    "text-scale": "textScale",
    "status-bar-color": "status_bar_color",
    "icon-brightness": "icon_brightness",
    "border-left": "borderLeft",
    "border-right": "borderRight",
    "border-top": "borderTop",
    "border-bottom": "borderBottom",
    "cross-axis": "crossAxis",
    "main-axis": "mainAxis",
    "main-axis-align": "mainAxisAlignment",
    "cross-axis-align": "crossAxisAlignment",
    "safe-area-top": "safeAreaTop",
    "safe-area-bottom": "safeAreaBottom",
    "width-factor": "widthFactor",
    "height-factor": "heightFactor",
    "min-item-width": "minItemWidth",
    "max-columns": "maxColumns",
    "tablet-columns": "tabletColumns",
}


def normalize_key(key: str) -> str | None:
    """Normalise a style key to its canonical Python form, or ``None`` if unknown."""
    if key in VALID_STYLE_KEYS:
        return key
    return _KEBAB_CANONICAL.get(key)
