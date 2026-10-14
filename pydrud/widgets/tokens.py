"""
Design tokens — the single Python source of truth for how an app looks.

Every metric the renderer draws with: M3 elevation levels (L0–L5),
tonal elevation, motion durations, the shape scale, spacing and an
uncapped font scale.
"""

from __future__ import annotations

from typing import Any, Dict


class Tokens:
    """Mutable design constants shared by the Python widgets and Android.

    Every metric the renderer draws with lives here.
    The whole set is serialised into the ``theme`` bridge command and applied
    by ``PydrudTheme`` on the device.
    """

    # ── shape ────────────────────────────────────────────────────────────
    radius_button: float = 20       # M3: rounded rectangle
    radius_card: float = 12         # M3: medium
    radius_input: float = 4         # M3: extra-small (top corners for filled)
    radius_chip: float = 8          # M3: small (NOT pill)
    radius_sheet: float = 28        # M3: extra-large
    radius_dialog: float = 28       # M3: extra-large
    radius_fab: float = 16          # M3: large
    radius_image: float = 12        # M3: medium
    radius_menu: float = 4          # M3: extra-small
    radius_snackbar: float = 4      # M3: extra-small
    radius_tooltip: float = 4       # M3: extra-small
    radius_toolbar: float = 32      # M3: docked toolbar is a full pill

    # M3 corner-radius scale — the named steps a designer works from, as
    # opposed to the per-component radii above.
    corner_none: float = 0
    corner_extra_small: float = 4
    corner_small: float = 8
    corner_medium: float = 12
    corner_large: float = 16
    corner_large_increased: float = 20
    corner_extra_large: float = 28
    corner_extra_large_increased: float = 32
    corner_extra_extra_large: float = 48
    corner_full: float = 999        # rendered as height / 2 (a pill)

    # ── size ─────────────────────────────────────────────────────────────
    app_bar_height: float = 64      # M3: 64dp (was 56)
    app_bar_height_medium: float = 112  # M3: medium top app bar
    app_bar_height_large: float = 152   # M3: large top app bar
    nav_height: float = 80          # M3: navigation bar is 80dp
    rail_width: float = 80
    fab_size: float = 56
    toolbar_height: float = 64      # M3: docked toolbar
    side_sheet_width: float = 360   # M3: side sheet default width
    input_height: float = 56        # M3: 56dp (was 52)
    button_height_sm: float = 40    # M3: small button
    button_height_md: float = 40    # M3: default button height
    button_height_lg: float = 40    # M3: large button
    touch_target: float = 48        # M3: minimum 48dp
    icon_size: float = 24
    avatar_size: float = 40
    divider_thickness: float = 1
    border_width: float = 1
    list_tile_height: float = 56
    list_tile_height_two_line: float = 72
    list_tile_height_three_line: float = 88
    chip_height: float = 32         # M3: 32dp
    switch_width: float = 52        # M3: 52×32 track
    switch_height: float = 32
    checkbox_size: float = 18       # M3: 18dp box in 40dp state layer
    radio_size: float = 20          # M3: 20dp radio in 40dp state layer

    # ── spacing ──────────────────────────────────────────────────────────
    gutter: float = 16              # M3: 16dp compact, 24dp medium+
    section: float = 24
    card_padding: float = 16
    content_max_width: float = 0

    # ── depth — M3 elevation levels L0–L5 ────────────────────────────────
    elevation_level_0: float = 0    # L0: no shadow
    elevation_level_1: float = 1    # L1: 1dp
    elevation_level_2: float = 3    # L2: 3dp (M3 correct, was 2)
    elevation_level_3: float = 6    # L3: 6dp
    elevation_level_4: float = 8    # L4: 8dp (was missing)
    elevation_level_5: float = 12   # L5: 12dp

    # Component-specific elevations (mapped to M3 levels)
    elevation_card: float = 1       # L1 (was 0 — M3 cards are elevated by default)
    elevation_button: float = 1     # L1 (was 1.5 — not an M3 level)
    elevation_fab: float = 3        # L3 (was 6)
    elevation_app_bar: float = 0    # L0
    elevation_sheet: float = 1      # L1 (bottom sheet)
    elevation_dialog: float = 3     # L3 (was 16 — not an M3 level)
    elevation_nav_bar: float = 0    # L0 (M3 nav bar has no shadow)
    elevation_menu: float = 2       # L2

    # Tonal elevation: primary tint percentage per level (M3 dark mode)
    tonal_elevation_0: float = 0.0
    tonal_elevation_1: float = 0.05
    tonal_elevation_2: float = 0.08
    tonal_elevation_3: float = 0.11
    tonal_elevation_4: float = 0.12
    tonal_elevation_5: float = 0.14

    # Shadow
    shadow_color: str = ""
    shadow_offset_x: float = 0
    shadow_offset_y: float = 2
    shadow_blur: float = 8
    shadow_spread: float = 0

    # ── motion — M3 durations and curves ─────────────────────────────────
    duration_short_1: int = 50
    duration_short_2: int = 100
    duration_short_3: int = 150
    duration_short_4: int = 200
    duration_medium_1: int = 250
    duration_medium_2: int = 300
    duration_medium_3: int = 350
    duration_medium_4: int = 400
    duration_long_1: int = 450
    duration_long_2: int = 500
    duration_long_3: int = 550
    duration_long_4: int = 600
    duration_extra_long_1: int = 700
    duration_extra_long_2: int = 800
    duration_extra_long_3: int = 900
    duration_extra_long_4: int = 1000

    # Legacy aliases
    duration_fast: int = 150
    duration_normal: int = 250
    duration_slow: int = 400

    # Easing curves — the Material 3 motion spec's cubic-béziers, written the
    # way CSS writes them so a stylesheet, a widget and the renderer all read
    # the same string.
    #
    # These used to hold the names of platform interpolators (`ease_in_out`,
    # `overshoot`), which are approximations of these curves rather than the
    # curves themselves: the M3 standard curve starts fast and eases out
    # steeply, and nothing resembling that can be said with a keyword. The
    # keyword names still work everywhere a curve can be named — they are
    # resolved as the platform curves they always were.
    easing_standard: str = "cubic-bezier(0.2, 0, 0, 1)"
    easing_standard_decelerate: str = "cubic-bezier(0, 0, 0, 1)"
    easing_standard_accelerate: str = "cubic-bezier(0.3, 0, 1, 1)"
    easing_emphasized: str = "cubic-bezier(0.2, 0, 0, 1)"
    easing_emphasized_decelerate: str = "cubic-bezier(0.05, 0.7, 0.1, 1)"
    easing_emphasized_accelerate: str = "cubic-bezier(0.3, 0, 0.8, 0.15)"
    easing_linear: str = "cubic-bezier(0, 0, 1, 1)"

    press_scale: float = 0.97
    ripple_opacity: float = 0.12
    state_hover: float = 0.08       # M3: 8%
    state_focus: float = 0.10       # M3: 10%
    state_pressed: float = 0.10     # M3: 10% (was 0.12)
    state_dragged: float = 0.16     # M3: 16%
    state_disabled_content: float = 0.38  # M3: 38%
    state_disabled_container: float = 0.12  # M3: 12%
    animate_layout: bool = True

    # ── type ─────────────────────────────────────────────────────────────
    font_family: str = ""
    font_scale: float = 1.0
    # font_scale_max REMOVED — text scales freely per user preference
    # Clamp layout density instead if needed
    text_display: float = 57        # M3 display-large
    text_headline: float = 32       # M3 headline-large
    text_title: float = 22          # M3 title-large
    text_subtitle: float = 16       # M3 title-medium
    text_body: float = 16           # M3 body-large
    text_label: float = 14          # M3 label-large
    text_caption: float = 12        # M3 body-small
    weight_regular: int = 400
    weight_medium: int = 500
    weight_bold: int = 700
    letter_spacing: float = 0.0
    line_height: float = 1.32

    # ── behaviour ────────────────────────────────────────────────────────
    haptics: bool = True
    overscroll_glow: bool = False

    #: Snapshot of the shipped defaults, filled in below.
    _DEFAULTS: Dict[str, Any] = {}

    # ── api ──────────────────────────────────────────────────────────────

    @classmethod
    def names(cls) -> tuple:
        return tuple(sorted(cls._DEFAULTS))

    @classmethod
    def as_dict(cls) -> Dict[str, Any]:
        return {name: getattr(cls, name) for name in cls._DEFAULTS}

    @classmethod
    def changed(cls) -> Dict[str, Any]:
        return {name: getattr(cls, name) for name, default
                in cls._DEFAULTS.items() if getattr(cls, name) != default}

    @classmethod
    def update(cls, **values: Any) -> None:
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
            elif expected in (int, float) and not isinstance(value, (int, float)):
                raise ValueError(
                    f"Design token '{name}' expects a number, got {value!r}")
            setattr(cls, name, value)

    @classmethod
    def reset(cls) -> None:
        for name, default in cls._DEFAULTS.items():
            setattr(cls, name, default)

    @classmethod
    def button_height(cls, size: str = "md") -> float:
        return {
            "sm": cls.button_height_sm,
            "lg": cls.button_height_lg,
        }.get(size, cls.button_height_md)


Tokens._DEFAULTS = {
    name: value for name, value in vars(Tokens).items()
    if not name.startswith("_") and isinstance(value, (int, float, str, bool))
}


def _closest(name: str, options) -> str:
    import difflib
    matches = difflib.get_close_matches(name, list(options), n=1, cutoff=0.6)
    return matches[0] if matches else ""


__all__ = ["Tokens"]