"""Tests for the Responsive scaling system."""

from pydrud.core.responsive import Responsive


def reset():
    """Reset Responsive to defaults before each test."""
    Responsive.init(360, 640, 2.0)


def test_default_scale_factor():
    """Without calling init(), Responsive.text(16) returns 16 (factor=1)."""
    val = Responsive.text(16)
    assert val == 16, f"Expected 16, got {val}"


def test_init_sets_dimensions():
    """After init(720, 1280, 2.0), screen_width() returns 720."""
    Responsive.init(720, 1280, 2.0)
    assert Responsive.screen_width() == 720
    assert Responsive.screen_height() == 1280
    assert Responsive.density() == 2.0
    reset()


def test_scaling_half_width():
    """On a 180dp screen, everything should be half size."""
    Responsive.init(180, 320, 1.5)
    assert Responsive.text(16) == 8
    assert Responsive.w(48) == 24
    assert Responsive.h(48) == 24
    assert Responsive.padding(16) == 8
    assert Responsive.spacing(8) == 4
    assert Responsive.radius(12) == 6
    assert Responsive.icon(24) == 12
    reset()


def test_scaling_double_width():
    """On a 720dp screen, everything should be double size."""
    Responsive.init(720, 1280, 2.0)
    assert Responsive.text(16) == 32
    assert Responsive.w(48) == 96
    assert Responsive.h(48) == 96
    assert Responsive.padding(16) == 32
    assert Responsive.spacing(8) == 16
    assert Responsive.radius(12) == 24
    assert Responsive.icon(24) == 48
    reset()


def test_all_methods_consistent():
    """All methods produce the same output for the same input value."""
    Responsive.init(540, 960, 2.0)
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
    """init(0, 0, 1.0) should not crash and use width=1 minimum."""
    Responsive.init(0, 0, 1.0)
    assert Responsive.screen_width() == 1
    assert Responsive.text(16) == 0  # 16 / 360 * 1 = 0.044 → round(0) = 0
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
