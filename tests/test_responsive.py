"""Tests for the Responsive scaling system."""

from pydrud.core.responsive import MediaQuery, Responsive


def reset():
    """Reset Responsive to defaults before each test."""
    Responsive.init(360, 640, 2.0)


def test_default_scale_factor():
    """Without calling init(), Responsive.text(16) returns 16 (factor=1)."""
    Responsive.reset()
    val = Responsive.text(16)
    assert val == 16, f"Expected 16, got {val}"


def test_init_sets_dimensions():
    """After init(720, 1280, 2.0), screen_width() returns 720."""
    Responsive.init(720, 1280, 2.0)
    assert Responsive.screen_width() == 720
    assert Responsive.screen_height() == 1280
    assert Responsive.density() == 2.0
    reset()


def test_scaling_is_clamped_on_narrow_screens():
    """A tiny screen shrinks sizes, but never below 0.9x (readability)."""
    Responsive.init(180, 320, 1.5)
    assert Responsive.text(16) == 14
    assert Responsive.w(48) == 43
    assert Responsive.h(48) == 43
    assert Responsive.padding(16) == 14
    assert Responsive.icon(24) == 22
    reset()


def test_scaling_is_clamped_on_wide_screens():
    """A tablet grows sizes gently (1.2x cap), not linearly with width."""
    Responsive.init(720, 1280, 2.0)
    assert Responsive.text(16) == 19
    assert Responsive.w(48) == 58
    assert Responsive.icon(24) == 29
    # Linear scaling is still available when it is really wanted.
    assert Responsive.raw(16) == 32
    reset()


def test_breakpoints():
    """Window size classes follow the Material 3 thresholds."""
    Responsive.init(360, 800, 2.0)
    assert Responsive.breakpoint() == "compact"
    assert Responsive.is_phone() and not Responsive.is_tablet()
    Responsive.init(700, 1000, 2.0)
    assert Responsive.breakpoint() == "medium"
    assert Responsive.is_tablet()
    Responsive.init(1000, 800, 2.0)
    assert Responsive.breakpoint() == "expanded"
    assert Responsive.is_landscape()
    reset()


def test_value_picks_per_breakpoint():
    """value() resolves per size class and falls back to smaller ones."""
    Responsive.init(360, 800, 2.0)
    assert Responsive.value(compact=1, medium=2, expanded=3) == 1
    assert Responsive.value(phone=16, tablet=32) == 16
    Responsive.init(900, 800, 2.0)
    assert Responsive.value(compact=1, medium=2, expanded=3) == 3
    assert Responsive.value(compact=8) == 8          # falls back
    assert Responsive.value(phone=16, tablet=32) == 32
    reset()


def test_columns_fit_screen_width():
    """columns() answers how many cards of a minimum width fit."""
    Responsive.init(360, 800, 2.0)
    assert Responsive.columns(min_width=160) == 2   # two cards fit
    assert Responsive.columns(min_width=300) == 1
    Responsive.init(800, 1200, 2.0)
    assert Responsive.columns(min_width=160) >= 3
    assert Responsive.columns(min_width=160, max_columns=2) == 2
    reset()


def test_content_width_caps_on_tablets():
    """Long lines are capped so text stays readable on big screens."""
    Responsive.init(1200, 800, 2.0)
    assert Responsive.content_width(560) == 560
    Responsive.init(360, 800, 2.0)
    assert Responsive.content_width(560) == 360
    reset()


def test_all_methods_consistent():
    """All methods produce the same output for the same input value."""
    Responsive.init(400, 960, 2.0)
    v = 20
    results = {
        Responsive.text(v),
        Responsive.w(v),
        Responsive.h(v),
        Responsive.padding(v),
        Responsive.spacing(v),
        Responsive.radius(v),
        Responsive.icon(v),
    }
    assert len(results) == 1, f"Methods disagree: {results}"
    reset()


def test_zero_width_handling():
    """init(0, 0, 1.0) should not crash, and sizes stay usable."""
    Responsive.init(0, 0, 1.0)
    assert Responsive.screen_width() == 1
    # Clamping keeps a degenerate screen size from collapsing the UI.
    assert Responsive.text(16) == 14
    reset()


def test_factor_property():
    """factor() should return screen_width / 360."""
    Responsive.init(480, 800, 1.0)
    assert abs(Responsive.factor() - 480 / 360) < 0.0001
    reset()


def test_density_property():
    """density() returns the value passed to init()."""
    Responsive.init(360, 640, 2.625)
    assert Responsive.density() == 2.625
    reset()


def test_platform_version_is_neutral_with_legacy_sdk_alias():
    MediaQuery.reset()
    assert MediaQuery.platform_version == ""
    MediaQuery.update(platform_version="34")
    assert MediaQuery.platform_version == "34"
    assert MediaQuery.sdk == 34
    assert MediaQuery.of()["sdk"] == 34
    MediaQuery.reset()
