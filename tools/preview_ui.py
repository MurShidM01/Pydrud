#!/usr/bin/env python3
"""
Render a Pydrud widget tree to a PNG, without a device.

This is a *design review* tool, not a second renderer: it consumes the
exact JSON the bridge sends to Android and lays it out with the same
rules ``ViewFactory``/``MaterialViews`` use (match/wrap sizing, padding,
spacing, weights, radii, elevation, the type scale). It is close enough
to catch spacing, hierarchy and colour mistakes in seconds instead of
waiting three minutes for a Gradle build.

Usage::

    pip install pillow qtawesome fonttools
    python tools/preview_ui.py                      # the starter app
    python tools/preview_ui.py --width 800          # tablet layout
    python tools/preview_ui.py --dark

Output goes to ``build/preview/<screen>.png``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:  # pragma: no cover - developer tool
    sys.exit("pip install pillow first")

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

SCALE = 2                       # render at 2x for crisp text
FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
MDI_FONT = (Path(sys.prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}"
            / "site-packages" / "qtawesome" / "fonts"
            / "materialdesignicons6-webfont-6.9.96.ttf")
MDI_MAP = MDI_FONT.with_name("materialdesignicons6-webfont-charmap-6.9.96.json")


# ── resources ────────────────────────────────────────────────────────────


def _font(size: float, weight: int = 400):
    name = "DejaVuSans-Bold.ttf" if weight >= 600 else "DejaVuSans.ttf"
    return ImageFont.truetype(str(FONT_DIR / name), max(1, int(size * SCALE)))


def _icon_font(size: float):
    return ImageFont.truetype(str(MDI_FONT), max(1, int(size * SCALE)))


def _icon_char(name: str) -> str | None:
    """Map a Pydrud icon name to its Material Design Icons glyph."""
    if not _icon_char.table:
        try:
            from generate_icons import ALIASES, ICONS
        except Exception:
            return None
        charmap = json.loads(MDI_MAP.read_text())
        resolved = {}
        for pydrud_name, mdi_name in ICONS.items():
            code = charmap.get(mdi_name)
            if code:
                resolved[pydrud_name] = chr(int(code, 16))
        for alias, target in ALIASES.items():
            if target in resolved:
                resolved[alias] = resolved[target]
        _icon_char.table = resolved
    return _icon_char.table.get(name)


_icon_char.table = {}


def _rgba(color: str | None, fallback=(0, 0, 0, 0)):
    if not color:
        return fallback
    c = color.lstrip("#")
    if len(c) == 6:
        c = "FF" + c
    if len(c) != 8:
        return fallback
    a, r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4, 6))
    return (r, g, b, a)


# ── layout + paint ───────────────────────────────────────────────────────


class Preview:
    """A tiny box-model renderer for Pydrud JSON trees."""

    def __init__(self, width: int, height: int, background: str):
        self.w, self.h = width, height
        self.img = Image.new("RGBA", (width * SCALE, height * SCALE),
                             _rgba(background, (255, 255, 255, 255)))
        self.draw = ImageDraw.Draw(self.img)

    # -- helpers ----------------------------------------------------------

    def px(self, v: float) -> int:
        return int(round(v * SCALE))

    def rect(self, box, fill=None, radius=0, outline=None, width=1,
             shadow=0.0):
        x0, y0, x1, y1 = (self.px(v) for v in box)
        if x1 <= x0 or y1 <= y0:
            return
        r = self.px(radius)
        if shadow:
            blur = max(2, self.px(shadow * 1.6))
            layer = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
            ImageDraw.Draw(layer).rounded_rectangle(
                [x0 + blur // 3, y0 + blur // 2, x1 + blur // 3, y1 + blur // 2],
                radius=r, fill=(16, 24, 40, 40))
            self.img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur / 2)))
        if fill or outline:
            translucent = ((fill and len(fill) > 3 and fill[3] < 255)
                           or (outline and len(outline) > 3 and outline[3] < 255))
            if translucent:
                layer = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
                ImageDraw.Draw(layer).rounded_rectangle(
                    [x0, y0, x1, y1], radius=r, fill=fill, outline=outline,
                    width=max(1, self.px(width)) if outline else 0)
                self.img.alpha_composite(layer)
            else:
                self.draw.rounded_rectangle(
                    [x0, y0, x1, y1], radius=r, fill=fill, outline=outline,
                    width=max(1, self.px(width)) if outline else 0)

    def text(self, x, y, value, size, weight, color, max_width=None,
             align="left", max_lines=None):
        font = _font(size, weight)
        lines = self._wrap(value, font, max_width) if max_width else [value]
        if max_lines:
            if len(lines) > max_lines:
                lines = lines[:max_lines]
                lines[-1] = lines[-1][:-1] + "…"
        line_h = size * 1.32
        for i, line in enumerate(lines):
            tx = self.px(x)
            if align in ("center", "right") and max_width:
                tw = self.draw.textlength(line, font=font) / SCALE
                tx = self.px(x + (max_width - tw) / (2 if align == "center" else 1))
            self._text_at(tx, self.px(y + i * line_h), line, font, color)
        return len(lines) * line_h

    def _text_at(self, x, y, line, font, color):
        if color and len(color) > 3 and color[3] < 255:
            layer = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
            ImageDraw.Draw(layer).text((x, y), line, font=font, fill=color)
            self.img.alpha_composite(layer)
        else:
            self.draw.text((x, y), line, font=font, fill=color)

    def _wrap(self, value, font, max_width):
        words, lines, current = str(value).split(), [], ""
        for word in words:
            trial = f"{current} {word}".strip()
            if self.draw.textlength(trial, font=font) / SCALE <= max_width or not current:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines or [""]

    def icon(self, name, x, y, size, color):
        char = _icon_char(name)
        if char is None:
            self.rect((x, y, x + size, y + size), fill=color, radius=size / 4)
            return
        self._text_at(self.px(x), self.px(y), char, _icon_font(size), color)

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.img.convert("RGB").save(path)
        return path


# ── the tree walker ──────────────────────────────────────────────────────


class Renderer:
    """Draws a tree using the same design tokens the device gets."""

    def __init__(self, preview: Preview, theme, tokens):
        self.p = preview
        self.theme = theme
        self.t = tokens

    # -- measuring --------------------------------------------------------

    def measure(self, node, width) -> float:
        if node is None or not node.get("visible", True):
            return 0
        style = node.get("style") or {}
        kind = node.get("type")
        props = node.get("props") or {}
        pad = style.get("padding") or {}
        pt, pb = pad.get("top", 0), pad.get("bottom", 0)
        inner = max(1, width - pad.get("left", 0) - pad.get("right", 0))

        if style.get("height") not in (None, "match", "wrap", 0):
            return float(style["height"])

        if kind == "Text":
            size = (style.get("font") or {}).get("size", 15)
            lines = self.p._wrap(props.get("value", ""), _font(size, 400), inner)
            cap = style.get("maxLines") or (style.get("font") or {}).get("maxLines")
            if cap:
                lines = lines[:int(cap)]
            return pt + pb + len(lines) * size * 1.34

        if kind in ("Button",):
            return {"sm": self.t.button_height_sm,
                    "lg": self.t.button_height_lg}.get(
                        style.get("buttonSize", "md"), self.t.button_height_md)
        if kind == "TextField":
            return self.t.input_height
        if kind == "Divider":
            return max(1, style.get("thickness") or self.t.divider_thickness) + 1
        if kind == "Icon":
            return (style.get("font") or {}).get("size", props.get("size", 24)) + 2
        if kind == "SizedBox":
            return float(style.get("height", 0))
        if kind == "ListTile":
            return (self.t.list_tile_height_two_line if props.get("subtitle")
                    else self.t.list_tile_height)
        if kind == "BottomNavigationBar":
            return self.t.nav_height
        if kind == "ProgressBar":
            return 8
        if kind == "Rating":
            return props.get("size", 24) + 4
        if kind == "SearchBar":
            return self.t.input_height
        if kind in ("Avatar", "Badge"):
            return self.t.avatar_size
        if kind == "Chip":
            return 36
        if kind == "SegmentedButton":
            return 44
        if kind == "Chart":
            return 160
        if kind == "Tabs":
            body = (node.get("children") or [None])[0]
            return 48 + (self.measure(body, width) if body else 0)

        children = node.get("children") or []
        if kind == "Row":
            tallest = max((self.measure(c, inner) for c in children), default=0)
            return pt + pb + tallest
        # Column, Container, Card, Stack, Center…
        spacing = style.get("spacing", 0) if kind in ("Column", "ListView") else 0
        total = 0
        visible = [c for c in children if c.get("visible", True)]
        for child in visible:
            total += self.measure(child, inner - (child.get("style") or {}).get("margin", {}).get("left", 0))
        total += spacing * max(0, len(visible) - 1)
        return pt + pb + total

    # -- drawing ----------------------------------------------------------

    def draw(self, node, x, y, width, height=None):
        if node is None or not node.get("visible", True):
            return 0
        kind = node.get("type")
        style = node.get("style") or {}
        props = node.get("props") or {}
        margin = style.get("margin") or {}
        x += margin.get("left", 0)
        width -= margin.get("left", 0) + margin.get("right", 0)
        y += margin.get("top", 0)

        h = height if height is not None else self.measure(node, width)
        handler = getattr(self, f"_draw_{kind.lower()}", None)

        # Widgets that paint their own surface (so a `bg` that means
        # "accent" is not mistaken for a fill, exactly like ViewFactory).
        self_painting = {
            "Text", "Icon", "Divider", "SizedBox", "Button", "TextField",
            "Chip", "Avatar", "Switch", "SearchBar", "SegmentedButton",
            "ProgressBar", "Rating", "BottomNavigationBar", "Badge", "Tabs",
        }
        if kind not in self_painting:
            self._paint_box(style, x, y, width, h)

        if handler:
            handler(node, x, y, width, h, style, props)
        else:
            self._draw_container(node, x, y, width, h, style, props)
        return h + margin.get("bottom", 0)

    def _paint_box(self, style, x, y, w, h):
        bg = style.get("bg")
        gradient = style.get("gradient")
        radius = style.get("borderRadius", 0)
        border = style.get("border")
        outline = None
        if border:
            side = border.get("all") or border.get("left") or {}
            if side.get("width"):
                outline = _rgba(side.get("color"))
        if gradient:
            self._paint_gradient(gradient, x, y, w, h, radius)
        elif bg or outline:
            self.p.rect((x, y, x + w, y + h), fill=_rgba(bg) if bg else None,
                        radius=radius, outline=outline,
                        width=(border or {}).get("left", {}).get("width", 1),
                        shadow=style.get("elevation", 0))
        # A bottom-only hairline (app bars).
        if border and not outline:
            bottom = border.get("bottom") or {}
            if bottom.get("width"):
                self.p.rect((x, y + h - bottom["width"], x + w, y + h),
                            fill=_rgba(bottom.get("color")))

    def _paint_gradient(self, gradient, x, y, w, h, radius):
        colors = [_rgba(c) for c in gradient.get("colors", []) or []]
        if len(colors) < 2:
            colors = colors * 2 or [(99, 102, 241, 255)] * 2
        box = Image.new("RGBA", (self.p.px(w), self.p.px(h)))
        px = box.load()
        horizontal = gradient.get("direction") in ("horizontal",)
        diagonal = str(gradient.get("direction", "")).startswith("diagonal")
        for j in range(box.height):
            for i in range(box.width):
                if horizontal:
                    t = i / max(1, box.width - 1)
                elif diagonal:
                    t = (i / max(1, box.width - 1) + j / max(1, box.height - 1)) / 2
                else:
                    t = j / max(1, box.height - 1)
                px[i, j] = tuple(
                    int(colors[0][k] + (colors[-1][k] - colors[0][k]) * t)
                    for k in range(4))
        mask = Image.new("L", box.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, box.size[0] - 1, box.size[1] - 1],
            radius=self.p.px(radius), fill=255)
        self.p.img.paste(box, (self.p.px(x), self.p.px(y)), mask)

    # -- per-widget -------------------------------------------------------

    def _children_box(self, style, x, y, w, h):
        pad = style.get("padding") or {}
        return (x + pad.get("left", 0), y + pad.get("top", 0),
                w - pad.get("left", 0) - pad.get("right", 0),
                h - pad.get("top", 0) - pad.get("bottom", 0))

    def _draw_container(self, node, x, y, w, h, style, props):
        cx, cy, cw, ch = self._children_box(style, x, y, w, h)
        centered = style.get("alignment") in ("center", "centre")
        for child in node.get("children") or []:
            child_w = self._intrinsic_width(child, cw)
            if centered:
                child_h = self.measure(child, child_w)
                self.draw(child, cx + (cw - child_w) / 2,
                          cy + max(0, (ch - child_h) / 2), child_w)
            else:
                self.draw(child, cx, cy, cw)

    def _draw_column(self, node, x, y, w, h, style, props):
        cx, cy, cw, ch = self._children_box(style, x, y, w, h)
        spacing = style.get("spacing", 0)
        align = style.get("crossAxisAlignment")
        children = [c for c in (node.get("children") or [])
                    if c.get("visible", True)]

        # Weighted children (expand=1) share whatever is left over, the
        # same way LinearLayout weights do on device.
        weights = [c.get("expand") or 0 for c in children]
        heights = [0 if weight else self.measure(c, cw)
                   for c, weight in zip(children, weights)]
        if any(weights):
            used = sum(heights) + spacing * max(0, len(children) - 1)
            free = max(0, ch - used)
            total = sum(weights)
            heights = [h_ if not weight else free * weight / total
                       for h_, weight in zip(heights, weights)]

        for child, child_h, weight in zip(children, heights, weights):
            child_w = self._intrinsic_width(child, cw)
            offset = (cw - child_w) / 2 if align == "center" else 0
            drawn = self.draw(child, cx + offset, cy, child_w,
                              child_h if weight else None)
            cy += (child_h if weight else drawn) + spacing

    _draw_listview = _draw_column

    def _draw_row(self, node, x, y, w, h, style, props):
        cx, cy, cw, ch = self._children_box(style, x, y, w, h)
        spacing = style.get("spacing", 0)
        children = [c for c in (node.get("children") or []) if c.get("visible", True)]
        fixed, weights = [], []
        for child in children:
            expand = child.get("expand") or 0
            weights.append(expand)
            fixed.append(0 if expand else self._intrinsic_width(child, cw))
        free = cw - sum(fixed) - spacing * max(0, len(children) - 1)
        total_weight = sum(weights) or 1
        for child, base, weight in zip(children, fixed, weights):
            child_w = base if not weight else max(0, free * weight / total_weight)
            fills = (child.get("style") or {}).get("height") in ("match", 0) \
                or child.get("type") in ("NavigationRail", "Column", "ListView")
            if fills:
                self.draw(child, cx, cy, child_w, ch)
            else:
                child_h = self.measure(child, child_w)
                self.draw(child, cx, cy + max(0, (ch - child_h) / 2), child_w)
            cx += child_w + spacing

    #: Widgets the native layer lays out full-width by default.
    FILL_BY_DEFAULT = {
        "Divider", "TextField", "SearchBar", "ListTile", "ListView", "Tabs",
        "BottomNavigationBar", "ProgressBar", "SegmentedButton", "Chart",
        "Stack", "RefreshIndicator", "Form", "Slider",
    }

    #: Fixed-width widgets the native layer sizes for us.
    INTRINSIC = {"NavigationRail": 80}

    def _intrinsic_width(self, child, available):
        """Width the child would take on device (wrap_content by default)."""
        style = child.get("style") or {}
        props = child.get("props") or {}
        kind = child.get("type")
        width = style.get("width")
        if isinstance(width, (int, float)):
            return float(width)
        if width == "match" or child.get("expand"):
            return available
        if kind in self.INTRINSIC:
            return self.INTRINSIC[kind]
        if kind in self.FILL_BY_DEFAULT:
            return available

        if kind == "Text":
            font = style.get("font") or {}
            return min(available, self.p.draw.textlength(
                str(props.get("value", "")),
                font=_font(font.get("size", 15), font.get("weight", 400))) / SCALE + 2)
        if kind == "Button":
            size = {"sm": 13.5, "lg": 16}.get(style.get("buttonSize", "md"), 15)
            label = self.p.draw.textlength(str(props.get("text", "")),
                                           font=_font(size, 600)) / SCALE
            pad = {"sm": 28, "lg": 52}.get(style.get("buttonSize", "md"), 40)
            return min(available, label + pad + (size + 8 if style.get("icon") else 0))
        if kind == "Icon":
            return (style.get("font") or {}).get("size", props.get("size", 24)) + 2
        if kind == "Avatar":
            return props.get("size", 40)
        if kind == "Chip":
            return self.p.draw.textlength(str(props.get("label", "")),
                                          font=_font(13.5, 500)) / SCALE + 28
        if kind == "Rating":
            return (props.get("size", 24) + 4) * int(props.get("count", 5))
        if kind == "Switch":
            return 52

        # Containers hug their content unless told otherwise.
        pad = style.get("padding") or {}
        frame = pad.get("left", 0) + pad.get("right", 0)
        children = [c for c in (child.get("children") or [])
                    if c.get("visible", True)]
        inner = max(0, available - frame)
        if not children:
            return min(available, frame or 0)
        if kind == "Row":
            spacing = style.get("spacing", 0) * max(0, len(children) - 1)
            total = sum(self._intrinsic_width(c, inner) for c in children)
            return min(available, total + spacing + frame)
        widest = max(self._intrinsic_width(c, inner) for c in children)
        return min(available, widest + frame)

    def _draw_stack(self, node, x, y, w, h, style, props):
        h = min(h, self.p.h - y)       # a Stack cannot exceed the screen
        for child in node.get("children") or []:
            cstyle = child.get("style") or {}
            if cstyle.get("position") == "absolute":
                cw = cstyle.get("width", 56)
                ch = cstyle.get("height", 56)
                fx = x + w - cw - cstyle.get("right", 24) if "right" in cstyle \
                    else x + cstyle.get("left", 0)
                fy = y + h - ch - cstyle.get("bottom", 24) if "bottom" in cstyle \
                    else y + cstyle.get("top", 0)
                self.draw(child, fx, fy, cw, ch)
            else:
                self.draw(child, x, y, w, h)

    def _draw_center(self, node, x, y, w, h, style, props):
        for child in node.get("children") or []:
            cw = self._intrinsic_width(child, w)
            fills = (child.get("style") or {}).get("height") == "match"
            ch = h if fills else self.measure(child, cw)
            offset = 0 if fills else max(0, (h - ch) / 2)
            self.draw(child, x + (w - cw) / 2, y + offset, cw, ch if fills else None)

    def _draw_navigationrail(self, node, x, y, w, h, style, props):
        self.p.rect((x, y, x + w, y + h), fill=_rgba(self.theme.surface))
        self.p.rect((x + w - 1, y, x + w, y + h), fill=_rgba(self.theme.outline))
        items = props.get("items") or []
        top = y + 24
        for i, item in enumerate(items):
            selected = i == props.get("selected", 0)
            color = (_rgba(self.theme.primary) if selected
                     else _rgba(self.theme.text_secondary))
            cx = x + w / 2
            if selected:
                self.p.rect((cx - 28, top, cx + 28, top + 32),
                            fill=_alpha(_rgba(self.theme.primary), 0.14),
                            radius=16)
            self.p.icon(item.get("icon", "help"), cx - 11, top + 5, 22, color)
            label = item.get("label", "")
            tw = self.p.draw.textlength(label, font=_font(11.5, 600 if selected
                                                          else 500)) / SCALE
            self.p.text(cx - tw / 2, top + 36, label, 11.5,
                        600 if selected else 500, color)
            top += 72

    def _draw_text(self, node, x, y, w, h, style, props):
        font = style.get("font") or {}
        size = font.get("size", 15)
        self.p.text(x, y + 1, props.get("value", ""), size,
                    font.get("weight", 400),
                    _rgba(font.get("color"), _rgba(self.theme.text)),
                    max_width=w, align=style.get("textAlign", "left"),
                    max_lines=style.get("maxLines"))

    def _draw_icon(self, node, x, y, w, h, style, props):
        font = style.get("font") or {}
        size = font.get("size", props.get("size", 24))
        color = _rgba(props.get("color") or font.get("color"),
                      _rgba(self.theme.text))
        self.p.icon(props.get("name", "help"), x, y, size, color)

    def _draw_button(self, node, x, y, w, h, style, props):
        variant = style.get("variant", "filled")
        accent = _rgba(style.get("bg"), _rgba(self.theme.primary))
        radius = style.get("borderRadius",
                           h / 2 if style.get("pill") else self.t.radius_button)
        label_color = _rgba((style.get("font") or {}).get("color"))
        if variant == "filled":
            self.p.rect((x, y, x + w, y + h), fill=accent, radius=radius,
                        shadow=1.5)
            label = label_color if label_color[3] else _on(accent)
        elif variant == "tonal":
            tint = _blend(accent, (255, 255, 255, 255), 0.86)
            self.p.rect((x, y, x + w, y + h), fill=tint, radius=radius)
            label = label_color if label_color[3] else _blend(accent, (0, 0, 0, 255), 0.35)
        elif variant == "outlined":
            self.p.rect((x, y, x + w, y + h), radius=radius,
                        outline=_alpha(accent, 0.45), width=1.4)
            label = label_color if label_color[3] else accent
        else:
            label = label_color if label_color[3] else accent
        size = {"sm": 13.5, "lg": 16}.get(style.get("buttonSize", "md"), 15)
        text = str(props.get("text", ""))
        tw = self.p.draw.textlength(text, font=_font(size, 600)) / SCALE
        icon = style.get("icon")
        iw = (size + 8) if icon else 0
        start = x + (w - tw - iw) / 2
        if icon:
            self.p.icon(icon, start, y + (h - size) / 2 - 1, size + 2, label)
        self.p.text(start + iw, y + (h - size * 1.34) / 2, text, size, 600, label)

    def _draw_textfield(self, node, x, y, w, h, style, props):
        outlined = style.get("variant") == "outlined"
        fill = _rgba(self.theme.surface_variant) if not outlined else _rgba(self.theme.surface)
        self.p.rect((x, y, x + w, y + h), fill=fill, radius=self.t.radius_input,
                    outline=_rgba(self.theme.outline) if outlined else None, width=1.2)
        text = props.get("value") or props.get("hint") or props.get("label") or ""
        color = _rgba(self.theme.text) if props.get("value") else \
            _alpha(_rgba(self.theme.text_secondary), 0.8)
        tx = x + 16
        if style.get("icon"):
            self.p.icon(style["icon"], tx, y + (h - 20) / 2, 20,
                        _rgba(self.theme.text_secondary))
            tx += 30
        self.p.text(tx, y + (h - 15.5 * 1.34) / 2, text, 15.5, 400, color,
                    max_width=w - (tx - x) - 12, max_lines=1)

    def _draw_divider(self, node, x, y, w, h, style, props):
        self.p.rect((x, y, x + w,
                     y + max(1, style.get("thickness") or self.t.divider_thickness)),
                    fill=_rgba(style.get("color"), _rgba(self.theme.outline)))

    def _draw_sizedbox(self, node, x, y, w, h, style, props):
        return

    def _draw_listtile(self, node, x, y, w, h, style, props):
        text_x = x + 16
        if props.get("leadingIcon"):
            self.p.icon(props["leadingIcon"], text_x, y + (h - 24) / 2, 24,
                        _rgba(self.theme.text_secondary))
            text_x += 40
        title_y = y + (h - (40 if props.get("subtitle") else 20)) / 2
        self.p.text(text_x, title_y, props.get("title", ""), 15.5, 500,
                    _rgba(self.theme.text), max_width=w - 80, max_lines=1)
        if props.get("subtitle"):
            self.p.text(text_x, title_y + 22, props["subtitle"], 13.5, 400,
                        _rgba(self.theme.text_secondary), max_width=w - 80,
                        max_lines=1)
        if props.get("trailingIcon"):
            self.p.icon(props["trailingIcon"], x + w - 36, y + (h - 22) / 2, 22,
                        _rgba(self.theme.text_secondary))
        for child in node.get("children") or []:
            cw = self._intrinsic_width(child, 80)
            self.draw(child, x + w - cw - 16, y + (h - self.measure(child, cw)) / 2, cw)

    def _draw_bottomnavigationbar(self, node, x, y, w, h, style, props):
        self.p.rect((x, y, x + w, y + h), fill=_rgba(self.theme.surface))
        self.p.rect((x, y, x + w, y + 1), fill=_rgba(self.theme.outline))
        items = props.get("items") or []
        if not items:
            return
        slot = w / len(items)
        for i, item in enumerate(items):
            selected = i == props.get("selected", 0)
            color = _rgba(self.theme.primary) if selected else \
                _rgba(self.theme.text_secondary)
            cx = x + slot * i + slot / 2
            if selected:
                self.p.rect((cx - 32, y + 10, cx + 32, y + 42),
                            fill=_alpha(_rgba(self.theme.primary), 0.14),
                            radius=16)
            self.p.icon(item.get("icon", "help"), cx - 11, y + 16, 22, color)
            label = item.get("label", "")
            tw = self.p.draw.textlength(label, font=_font(11.5, 600 if selected else 500)) / SCALE
            self.p.text(cx - tw / 2, y + 44, label, 11.5,
                        600 if selected else 500, color)

    def _draw_badge(self, node, x, y, w, h, style, props):
        for child in node.get("children") or []:
            self.draw(child, x, y, w)
        label = str(props.get("count") or props.get("label") or "")
        if label and label != "0":
            self.p.rect((x + 18, y - 2, x + 18 + 9 + 7 * len(label), y + 14),
                        fill=_rgba(self.theme.error), radius=9)
            self.p.text(x + 22, y - 1, label, 10.5, 700, (255, 255, 255, 255))

    def _draw_avatar(self, node, x, y, w, h, style, props):
        size = props.get("size", 40)
        bg = _rgba(props.get("bg"), _rgba(self.theme.primary))
        self.p.rect((x, y, x + size, y + size), fill=bg, radius=size / 2)
        if props.get("icon"):
            self.p.icon(props["icon"], x + size * 0.25, y + size * 0.25,
                        size * 0.5, _on(bg))
        else:
            initials = props.get("initials", "")
            tw = self.p.draw.textlength(initials, font=_font(15, 600)) / SCALE
            self.p.text(x + (size - tw) / 2, y + size / 2 - 10, initials, 15,
                        600, _on(bg))

    def _draw_chip(self, node, x, y, w, h, style, props):
        selected = props.get("selected")
        accent = _rgba(self.theme.primary)
        fill = _alpha(accent, 0.14) if selected else _rgba(self.theme.surface)
        self.p.rect((x, y, x + w, y + h), fill=fill, radius=h / 2,
                    outline=None if selected else _rgba(self.theme.outline))
        label = props.get("label", "")
        tw = self.p.draw.textlength(label, font=_font(13.5, 600 if selected else 500)) / SCALE
        self.p.text(x + (w - tw) / 2, y + (h - 18) / 2, label, 13.5,
                    600 if selected else 500,
                    accent if selected else _rgba(self.theme.text))

    def _draw_rating(self, node, x, y, w, h, style, props):
        size = props.get("size", 24)
        value = props.get("value", 0)
        color = _rgba(props.get("color"), (245, 158, 11, 255))
        for i in range(int(props.get("count", 5))):
            name = "star" if i < round(value) else "star_border"
            self.p.icon(name, x + i * (size + 4), y, size,
                        color if i < round(value) else _rgba(self.theme.outline))

    def _draw_progressbar(self, node, x, y, w, h, style, props):
        value = float(props.get("value", 0) or 0)
        self.p.rect((x, y, x + w, y + 8), fill=_rgba(self.theme.surface_variant),
                    radius=4)
        self.p.rect((x, y, x + w * min(1, value), y + 8),
                    fill=_rgba(self.theme.primary), radius=4)

    def _draw_searchbar(self, node, x, y, w, h, style, props):
        self.p.rect((x, y, x + w, y + h), fill=_rgba(self.theme.surface),
                    radius=h / 2, outline=_rgba(self.theme.outline))
        self.p.icon("search", x + 16, y + (h - 20) / 2, 20,
                    _rgba(self.theme.text_secondary))
        text = props.get("value") or props.get("hint", "")
        self.p.text(x + 46, y + (h - 20) / 2, text, 15, 400,
                    _rgba(self.theme.text) if props.get("value")
                    else _rgba(self.theme.text_secondary), max_lines=1)

    def _draw_switch(self, node, x, y, w, h, style, props):
        on = props.get("active") or props.get("value")
        track = _rgba(self.theme.primary) if on else _rgba(self.theme.outline)
        self.p.rect((x + w - 52, y + 2, x + w - 52 + 46, y + 28),
                    fill=track, radius=14)
        knob = x + w - 52 + (24 if on else 3)
        self.p.rect((knob, y + 5, knob + 22, y + 25), fill=(255, 255, 255, 255),
                    radius=11, shadow=1)

    def _draw_tabs(self, node, x, y, w, h, style, props):
        tabs = props.get("tabs") or []
        selected = props.get("selected", 0)
        self.p.rect((x, y, x + w, y + 48), fill=_rgba(self.theme.surface))
        if tabs:
            slot = w / len(tabs)
            for i, tab in enumerate(tabs):
                active = i == selected
                color = _rgba(self.theme.primary) if active else \
                    _rgba(self.theme.text_secondary)
                label = tab.get("label", "")
                tw = self.p.draw.textlength(label, font=_font(14, 600 if active else 500)) / SCALE
                self.p.text(x + slot * i + (slot - tw) / 2, y + 14, label, 14,
                            600 if active else 500, color)
                if active:
                    self.p.rect((x + slot * i + slot * 0.2, y + 44,
                                 x + slot * i + slot * 0.8, y + 47),
                                fill=_rgba(self.theme.primary), radius=2)
        for child in node.get("children") or []:
            self.draw(child, x, y + 48, w)

    def _draw_chart(self, node, x, y, w, h, style, props):
        values = props.get("values") or []
        if not values:
            return
        top = max(values) or 1
        bar_w = w / (len(values) * 1.6)
        for i, value in enumerate(values):
            bar_h = (h - 20) * (value / top)
            cx = x + (i + 0.5) * (w / len(values))
            self.p.rect((cx - bar_w / 2, y + h - 10 - bar_h, cx + bar_w / 2,
                         y + h - 10), fill=_rgba(self.theme.primary), radius=6)

    def _draw_segmentedbutton(self, node, x, y, w, h, style, props):
        options = props.get("options") or []
        self.p.rect((x, y, x + w, y + h), fill=_rgba(self.theme.surface_variant),
                    radius=h / 2)
        if not options:
            return
        slot = w / len(options)
        for i, option in enumerate(options):
            active = i == props.get("selected", 0)
            if active:
                self.p.rect((x + slot * i + 3, y + 3, x + slot * (i + 1) - 3,
                             y + h - 3), fill=_rgba(self.theme.surface),
                            radius=(h - 6) / 2, shadow=1)
            label = option if isinstance(option, str) else option.get("label", "")
            tw = self.p.draw.textlength(label, font=_font(14, 600 if active else 500)) / SCALE
            self.p.text(x + slot * i + (slot - tw) / 2, y + (h - 19) / 2, label,
                        14, 600 if active else 500,
                        _rgba(self.theme.text) if active
                        else _rgba(self.theme.text_secondary))


def _alpha(color, a):
    return (color[0], color[1], color[2], int(255 * a))


def _blend(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(4))


def _on(color):
    luminance = (0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]) / 255
    return (31, 41, 55, 255) if luminance > 0.62 else (255, 255, 255, 255)


# ── entry point ──────────────────────────────────────────────────────────


def render_starter(width: int, height: int, dark: bool, out_dir: Path,
                   seed: str | None = None, tokens: dict | None = None):
    """Render every screen of the generated starter app.

    ``seed`` is the brand colour and ``tokens`` any design-token
    overrides, so a preview shows exactly what ``Theme.configure(...)``
    would produce on the device.
    """
    from jinja2 import Environment, PackageLoader

    from pydrud import App, Theme, Tokens
    from pydrud.core.responsive import MediaQuery, Responsive

    env = Environment(loader=PackageLoader("pydrud", "android/templates"),
                      keep_trailing_newline=True)
    source = env.get_template("python/main.py.j2").render(
        project_name="My App", scheme="myapp",
        seed_color=seed or "#FF6366F1")
    module_path = out_dir / "_starter_app.py"
    module_path.parent.mkdir(parents=True, exist_ok=True)
    module_path.write_text(source)
    sys.path.insert(0, str(out_dir))
    import importlib

    starter = importlib.import_module("_starter_app")

    Responsive.init(width, height, 2.0)
    MediaQuery.init(width, height, 2.0)
    if tokens:
        Theme.configure(**tokens)
    Theme.seed(seed or "#FF6366F1")
    if dark:
        Theme.dark()
    else:
        Theme.light()

    written = []
    for route in ("home", "showcase", "settings"):
        starter.router.reset(route)
        app = App(target=starter.router.build_root(), title="My App")
        starter.app = app
        tree = app.build().to_dict()

        preview = Preview(width, height, Theme.background)
        renderer = Renderer(preview, Theme, Tokens)
        # Status bar / gesture bar, so the safe areas are visible.
        renderer.draw(tree, 0, 0, width, height)
        preview.rect((0, 0, width, 1), fill=_alpha(_rgba(Theme.outline), 0.6))
        suffix = "-dark" if dark else ""
        written.append(preview.save(out_dir / f"{route}{suffix}.png"))
    return written


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, default=411, help="screen width in dp")
    parser.add_argument("--height", type=int, default=890, help="screen height in dp")
    parser.add_argument("--dark", action="store_true", help="render the dark theme")
    parser.add_argument("--accent", default=None,
                        help="brand colour, e.g. '#FF0EA5E9'")
    parser.add_argument("--token", action="append", default=[],
                        metavar="NAME=VALUE",
                        help="design-token override, e.g. --token radius_card=28")
    parser.add_argument("--out", default=str(REPO / "build" / "preview"))
    args = parser.parse_args()

    tokens = {}
    for pair in args.token:
        name, _, value = pair.partition("=")
        try:
            tokens[name.strip()] = float(value)
        except ValueError:
            tokens[name.strip()] = value.strip()

    files = render_starter(args.width, args.height, args.dark, Path(args.out),
                           seed=args.accent, tokens=tokens)
    for path in files:
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
