"""
Design tokens — the single Python source of truth for how an app looks.

Everything the native renderer draws (corner radii, control heights, bar
heights, depth, motion, the type ramp, even the typeface) is a value in
this class.  The whole set is serialised into the ``theme`` bridge command
and applied by ``PydrudTheme`` on the device, so Java never decides what
the UI looks like — it only draws what Python sends::

    from pydrud import Theme, Tokens

    Theme.configure(radius_card=24, app_bar_height=64, font_family="serif")
    Theme.configure(button_height_md=52, ripple_opacity=0.18)

    Tokens.radius_card          # 24 — widgets read the same values
    Theme.configure_reset()     # back to the Pydrud defaults

Changing a token re-themes the running app the next time a frame is sent
(``app.apply_theme()`` pushes it immediately).
"""

from __future__ import annotations

from typing import Any, Dict


class Tokens:
    """Mutable design constants shared by the Python widgets and Android.

    Every attribute is a plain number, string or bool so the whole class
    can travel over the bridge as JSON.  Set them directly or, preferably,
    through :meth:`Theme.configure`, which validates names.
    """

    # ── shape ────────────────────────────────────────────────────────────
    radius_button: float = 14
    radius_card: float = 16
    radius_input: float = 14
    radius_chip: float = 999          # pill
    radius_sheet: float = 24
    radius_dialog: float = 24
    radius_fab: float = 28
    radius_image: float = 12

    # ── size ─────────────────────────────────────────────────────────────
    app_bar_height: float = 56
    nav_height: float = 64
    rail_width: float = 80
    fab_size: float = 56
    input_height: float = 52
    button_height_sm: float = 38
    button_height_md: float = 48
    button_height_lg: float = 56
    touch_target: float = 48
    icon_size: float = 24
    avatar_size: float = 40
    divider_thickness: float = 1
    border_width: float = 1
    list_tile_height: float = 56
    list_tile_height_two_line: float = 72

    # ── spacing ──────────────────────────────────────────────────────────
    gutter: float = 20                # page side padding
    section: float = 24               # gap between sections
    card_padding: float = 16
    content_max_width: float = 0      # 0 = unconstrained

    # ── depth ────────────────────────────────────────────────────────────
    elevation_card: float = 0
    elevation_button: float = 1.5
    elevation_fab: float = 6
    elevation_app_bar: float = 0
    elevation_sheet: float = 12
    elevation_dialog: float = 16

    # ── motion ───────────────────────────────────────────────────────────
    duration_fast: int = 140
    duration_normal: int = 220
    duration_slow: int = 320
    press_scale: float = 0.97
    ripple_opacity: float = 0.12
    state_hover: float = 0.08
    state_pressed: float = 0.12
    state_disabled: float = 0.38
    animate_layout: bool = True

    # ── type ─────────────────────────────────────────────────────────────
    font_family: str = ""             # "" = platform default (Roboto)
    font_scale: float = 1.0
    text_display: float = 34
    text_headline: float = 24
    text_title: float = 18
    text_subtitle: float = 16
    text_body: float = 15
    text_label: float = 14
    text_caption: float = 12
    weight_regular: int = 400
    weight_medium: int = 500
    weight_bold: int = 700
    letter_spacing: float = 0.0
    line_height: float = 1.32

    # ── behaviour ────────────────────────────────────────────────────────
    haptics: bool = True              # tap feedback on buttons/list rows
    overscroll_glow: bool = False     # Material 3 drops the blue glow

    #: Snapshot of the shipped defaults, filled in below.
    _DEFAULTS: Dict[str, Any] = {}

    # ── api ──────────────────────────────────────────────────────────────

    @classmethod
    def names(cls) -> tuple:
        """Every configurable token name."""
        return tuple(sorted(cls._DEFAULTS))

    @classmethod
    def as_dict(cls) -> Dict[str, Any]:
        """The full token set, ready to be sent to the device."""
        return {name: getattr(cls, name) for name in cls._DEFAULTS}

    @classmethod
    def changed(cls) -> Dict[str, Any]:
        """Only the tokens that differ from the shipped defaults."""
        return {name: getattr(cls, name) for name, default
                in cls._DEFAULTS.items() if getattr(cls, name) != default}

    @classmethod
    def update(cls, **values: Any) -> None:
        """Set tokens by name, rejecting typos instead of ignoring them."""
        for name, value in values.items():
            if name not in cls._DEFAULTS:
                suggestion = _closest(name, cls._DEFAULTS)
                hint = f" Did you mean '{suggestion}'?" if suggestion else ""
                raise ValueError(f"Unknown design token '{name}'.{hint}")
            expected = type(cls._DEFAULTS[name])
            if expected is bool:
                value = bool(value)
            elif expected is str:
                value = str(value)
            elif expected is int and isinstance(value, float):
                value = int(value)
            elif expected in (int, float) and not isinstance(value, (int, float)):
                raise ValueError(
                    f"Design token '{name}' expects a number, got {value!r}")
            setattr(cls, name, value)

    @classmethod
    def reset(cls) -> None:
        """Restore every token to the Pydrud default."""
        for name, default in cls._DEFAULTS.items():
            setattr(cls, name, default)

    @classmethod
    def button_height(cls, size: str = "md") -> float:
        """Height for a ``sm`` / ``md`` / ``lg`` button."""
        return {
            "sm": cls.button_height_sm,
            "lg": cls.button_height_lg,
        }.get(size, cls.button_height_md)


Tokens._DEFAULTS = {
    name: value for name, value in vars(Tokens).items()
    if not name.startswith("_") and isinstance(value, (int, float, str, bool))
}


def _closest(name: str, options) -> str:
    """Cheap suggestion for a mistyped token name."""
    import difflib

    matches = difflib.get_close_matches(name, list(options), n=1, cutoff=0.6)
    return matches[0] if matches else ""


__all__ = ["Tokens"]
