"""Fold CSS long-hands and shorthands into Pydrud composite style keys.

A stylesheet copied from the web writes ``font-size``, ``padding-top``,
``border-color``, ``transform``, ``transition`` and ``animation``. The
renderer, however, speaks Pydrud's canonical composites (``font``, ``padding``,
``margin``, ``border``) plus a few flat transform/animation keys.

This module is the single place that bridges the two: it runs *after* tokens,
custom properties and the numeric value language have been resolved, and turns
the CSS spellings into exactly the shapes the renderer already reads. It also
drops the declarations Pydrud has no native meaning for
(:data:`~pydrud.core.styles.schema.WEB_ONLY_STYLE_KEYS`).
"""

from __future__ import annotations

import re
from typing import Any, Optional

from pydrud.core.styles.parser import (
    parse_animation_shorthand,
    parse_transition_shorthand,
)
from pydrud.core.styles.schema import KEY_KIND, WEB_ONLY_STYLE_KEYS
from pydrud.core.styles.values import ValueContext, decompose_transform, to_dp

#: CSS font long-hands → the ``font`` sub-key they write.
_FONT_LONGHANDS = {
    "fontSize": "size",
    "fontWeight": "weight",
    "fontFamily": "family",
    "letterSpacing": "letterSpacing",
    "lineHeight": "lineHeight",
}

#: Widget types that paint text through ``font`` (so ``color`` folds in).
_TEXT_WIDGETS = frozenset({
    "Text", "Button", "TextField", "RichText", "Markdown", "Heading",
    "Title", "FormField", "Chip", "Snackbar", "Badge", "Tooltip", "Label",
    "Dialog", "ListTile",
})

_BOX_LONGHANDS = {
    "paddingTop": ("padding", "top"),
    "paddingRight": ("padding", "right"),
    "paddingBottom": ("padding", "bottom"),
    "paddingLeft": ("padding", "left"),
    "marginTop": ("margin", "top"),
    "marginRight": ("margin", "right"),
    "marginBottom": ("margin", "bottom"),
    "marginLeft": ("margin", "left"),
}

_BORDER_LONGHANDS = {"borderColor": "color", "borderWidth": "width"}

_RADIUS_KEYS = (
    "borderRadius", "borderTopLeftRadius", "borderTopRightRadius",
    "borderBottomLeftRadius", "borderBottomRightRadius",
)

_NOOP_VALUES = frozenset({"inherit", "initial", "unset", "revert", "revert-layer"})

#: Absolute offsets; an unresolvable (percentage) value is dropped.
_POSITION_KEYS = frozenset({"top", "left", "right", "bottom"})

_FILTER_BLUR = re.compile(r"blur\(\s*([0-9.]+)\s*(?:px|dp|dip)?\s*\)", re.IGNORECASE)


def finalize_style(
    style: dict,
    context: ValueContext,
    keyframes: Optional[dict] = None,
    widget_type: str = "",
) -> tuple[dict, list[str]]:
    """Fold *style* into the renderer's canonical shape.

    Returns ``(style, dropped_web_only_keys)`` so the resolver can report the
    declarations that had no native meaning.
    """
    keyframes = keyframes or {}
    result: dict[str, Any] = {}
    dropped: list[str] = []

    for key, value in style.items():
        if key in WEB_ONLY_STYLE_KEYS:
            dropped.append(key)
            continue
        if isinstance(value, str) and value.strip().lower() in _NOOP_VALUES:
            continue
        result[key] = value

    _fold_radii(result)
    _fold_font(result, context, widget_type)
    _fold_box(result, context)
    _fold_border(result, context)
    _fold_overflow(result)
    _fold_filter(result)
    _fold_transform(result, context)
    _fold_animation(result, context, keyframes)
    _fold_transition(result)
    _coerce_number_keys(result, context)
    return result, dropped


def _coerce_number_keys(style: dict, context: ValueContext) -> None:
    """Collapse ``"16px"``-style strings for number-kind keys to dp numbers.

    The renderer reads these with ``optInt``/``optDouble``, so a string would
    be dropped. ``to_dp`` leaves keywords (``"match"``), percentages and
    colours untouched.
    """
    for key, value in list(style.items()):
        if not isinstance(value, str) or KEY_KIND.get(key) != "number":
            continue
        coerced = to_dp(value, context)
        if isinstance(coerced, str) and key in _POSITION_KEYS:
            # An offset Pydrud cannot resolve (a percentage of an unknown
            # parent) is dropped rather than sent as a dead string — the
            # widget's Stack alignment does the centring instead.
            del style[key]
            continue
        style[key] = coerced


def _expand_all(box: dict) -> dict:
    """Turn ``{all: n}`` into explicit sides so a long-hand can override one."""
    if "all" not in box:
        return box
    value = box.pop("all")
    for side in ("left", "top", "right", "bottom"):
        box.setdefault(side, value)
    return box


def _coerce_box(box: dict, context: ValueContext) -> dict:
    return {key: to_dp(value, context) for key, value in box.items()}


def _fold_font(style: dict, context: ValueContext, widget_type: str) -> None:
    longhands = {key: style.pop(key) for key in list(style)
                 if key in _FONT_LONGHANDS}
    color = style.get("color") if widget_type in _TEXT_WIDGETS else None
    font = style.get("font")
    if not longhands and color is None:
        return
    if isinstance(font, dict):
        merged = dict(font)
    elif isinstance(font, str):
        merged = {"family": font}
    elif isinstance(font, (int, float)) and not isinstance(font, bool):
        merged = {"size": font}
    else:
        merged = {}
    for key, value in longhands.items():
        merged[_FONT_LONGHANDS[key]] = to_dp(value, context)
    if color is not None:
        merged.setdefault("color", color)
    style["font"] = merged


def _fold_box(style: dict, context: ValueContext) -> None:
    for key, (composite, side) in _BOX_LONGHANDS.items():
        if key not in style:
            continue
        value = to_dp(style.pop(key), context)
        box = style.get(composite)
        if not isinstance(box, dict):
            box = {}
        else:
            box = _expand_all(dict(box))
        box[side] = value
        style[composite] = _coerce_box(box, context)
    # Normalise a box that arrived whole.
    for composite in ("padding", "margin"):
        box = style.get(composite)
        if isinstance(box, dict):
            style[composite] = _coerce_box(box, context)


def _fold_border(style: dict, context: ValueContext) -> None:
    if not any(key in style for key in _BORDER_LONGHANDS):
        return
    border = style.get("border")
    if isinstance(border, dict):
        box = dict(border)
    elif isinstance(border, (int, float)) and not isinstance(border, bool):
        box = {"width": border}
    else:
        box = {}
    for key, field in _BORDER_LONGHANDS.items():
        if key in style:
            box[field] = style.pop(key)
    if "width" in box:
        box["width"] = to_dp(box["width"], context)
    style["border"] = box


def _fold_overflow(style: dict) -> None:
    for key in ("overflowX", "overflowY"):
        if key in style:
            style.setdefault("overflow", style.pop(key))


def _fold_filter(style: dict) -> None:
    if "filter" not in style:
        return
    text = str(style.pop("filter"))
    match = _FILTER_BLUR.search(text)
    if match is not None:
        style["blur"] = float(match.group(1))


def _fold_radii(style: dict) -> None:
    # A percentage radius is the CSS circle idiom; Pydrud draws a circle with a
    # radius larger than the view. `border-radius: 50%` → 999.
    for key in _RADIUS_KEYS:
        value = style.get(key)
        if isinstance(value, str) and "%" in value:
            style[key] = 999


def _fold_transform(style: dict, context: ValueContext) -> None:
    if "transform" not in style:
        return
    text = str(style.pop("transform")).strip()
    if not text or text.lower() == "none":
        return
    style.update(decompose_transform(text, context))


def _normalize_keyframe(declarations: list, context: ValueContext) -> dict:
    frame: dict[str, Any] = {}
    for key, value in declarations:
        frame[key] = value
    if "transform" in frame:
        _fold_transform(frame, context)
    return {key: to_dp(value, context) for key, value in frame.items()}


def _fold_animation(style: dict, context: ValueContext,
                    keyframes: dict) -> None:
    if "animation" not in style:
        return
    value = style["animation"]
    if isinstance(value, dict):
        return  # already a renderer spec
    text = str(value).strip()
    if not text or text.lower() == "none":
        style.pop("animation", None)
        return
    spec = parse_animation_shorthand(text)
    name = spec.get("name")
    timeline = keyframes.get(name) if name else None
    if timeline is not None:
        # CSS `0%, 100% { … }` lists offsets out of order; the renderer
        # samples a sorted timeline.
        ordered = sorted(timeline.frames, key=lambda frame: frame.offset)
        spec["keyframes"] = [
            [frame.offset, _normalize_keyframe(frame.declarations, context)]
            for frame in ordered
        ]
    style["animation"] = spec


def _fold_transition(style: dict) -> None:
    if "transition" not in style:
        return
    value = style["transition"]
    if isinstance(value, (dict, list)):
        return
    text = str(value).strip()
    if not text or text.lower() == "none":
        style.pop("transition", None)
        return
    style["transition"] = parse_transition_shorthand(text)


__all__ = ["finalize_style"]
