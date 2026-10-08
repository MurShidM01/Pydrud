"""
Shared helpers for the theme package.

Colour maths and the forgiving constant-lookup metaclass that powers
``Colors``, ``Icons`` and the token scales live here, so the sibling
modules stay focused on their own constants.
"""

from __future__ import annotations

import re


def _argb(hex_rgb: str, alpha: str = "FF") -> str:
    return f"#{alpha}{hex_rgb.upper()}"


# deepOrange / deep_orange / amber -> DEEP_ORANGE
def _token_name(name: str) -> str:
    return re.sub(r"(?<!^)([A-Z])", r"_\1", name).replace("-", "_").upper()


class _ConstantsMeta(type):
    """Forgiving lookups and teaching errors for the token classes.

    ``Colors.amber``, ``Colors.deepOrange`` and ``Colors.DEEP_ORANGE`` all
    resolve to the same constant (exactly as :class:`Icons` already does),
    and a name that genuinely does not exist reports the closest matches
    instead of leaving the developer to guess from ``dir()``.
    """

    def __getattr__(cls, name: str):
        if name.startswith("__"):
            raise AttributeError(name)
        token = _token_name(name)
        for klass in cls.__mro__:
            value = vars(klass).get(token)
            if value is not None and _is_constant(token, value):
                return value
        raise AttributeError(cls._unknown_message(name))

    # ── introspection ────────────────────────────────────────────────────

    def names(cls) -> list:
        """Every constant this class defines, sorted."""
        found: set = set()
        for klass in cls.__mro__:
            found.update(key for key, value in vars(klass).items()
                         if _is_constant(key, value))
        return sorted(found)

    def _unknown_message(cls, name: str) -> str:
        import difflib

        options = cls.names()
        close = difflib.get_close_matches(_token_name(name), options, n=3,
                                          cutoff=0.5)
        hint = f" Did you mean {' or '.join(repr(c) for c in close)}?" if close \
            else ""
        preview = ", ".join(options[:12])
        if len(options) > 12:
            preview += ", …"
        return (f"type object {cls.__name__!r} has no attribute {name!r}."
                f"{hint} Available: {preview} "
                f"(see {cls.__name__}.names()).")


def _is_constant(name: str, value) -> bool:
    return (name.isupper() and not name.startswith("_")
            and isinstance(value, (str, int, float, tuple)))


def _rgb(color: str) -> tuple[int, int, int]:
    c = color.lstrip("#")
    if len(c) == 8:
        c = c[2:]
    if len(c) != 6:
        raise ValueError(f"Unsupported colour format: {color!r}")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _tone(r: int, g: int, b: int, factor: float) -> str:
    """Lighten (>1) or darken (<1) a colour, clamped to the 8-bit range."""
    def _clamp(v: float) -> int:
        return max(0, min(255, int(round(v))))

    if factor >= 1:
        # Blend towards white so highlights do not clip to a flat colour.
        t = min(1.0, factor - 1.0)
        return _argb("%02X%02X%02X" % (_clamp(r + (255 - r) * t),
                                       _clamp(g + (255 - g) * t),
                                       _clamp(b + (255 - b) * t)))
    return _argb("%02X%02X%02X" % (_clamp(r * factor), _clamp(g * factor),
                                   _clamp(b * factor)))


def _mix(color_a: str, color_b: str, t: float) -> str:
    """Linear blend between two colours (``t`` 0 → *color_a*, 1 → *color_b*).

    Used to tween a whole palette: every role moves through the same fraction
    so the intermediate frames stay a coherent scheme, not a patchwork.
    """
    k = max(0.0, min(1.0, float(t)))
    a = color_a.lstrip("#")
    b = color_b.lstrip("#")
    if len(a) == 6:
        a = "FF" + a
    if len(b) == 6:
        b = "FF" + b
    if len(a) != 8 or len(b) != 8:
        return color_b if k >= 0.5 else color_a
    out = []
    for index in range(0, 8, 2):
        va = int(a[index:index + 2], 16)
        vb = int(b[index:index + 2], 16)
        out.append("%02X" % max(0, min(255, int(round(va + (vb - va) * k)))))
    return "#" + "".join(out)


def _rotate_hue(color: str, degrees: float, *, saturation: float = 1.0) -> str:
    """Rotate a colour around the hue wheel, keeping its lightness."""
    import colorsys

    r, g, b = (c / 255.0 for c in _rgb(color))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    h = (h + degrees / 360.0) % 1.0
    s = max(0.0, min(1.0, s * saturation))
    nr, ng, nb = colorsys.hls_to_rgb(h, l, s)
    return _argb("%02X%02X%02X" % (round(nr * 255), round(ng * 255), round(nb * 255)))


def _lighten_hsl(color: str, amount: float) -> str:
    """Raise a colour's lightness without washing out its hue."""
    import colorsys

    r, g, b = (c / 255.0 for c in _rgb(color))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = max(0.0, min(1.0, l + amount))
    nr, ng, nb = colorsys.hls_to_rgb(h, l, s)
    return _argb("%02X%02X%02X" % (round(nr * 255), round(ng * 255), round(nb * 255)))
