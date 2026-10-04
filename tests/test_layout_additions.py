"""Regression tests for the layout and icon compatibility additions."""

import pytest

from pydrud import FittedBox, FractionallySizedBox, Icons, Text


def test_fractionally_sized_box_is_exported_and_serializes_factors():
    widget = FractionallySizedBox(Text("arena"), width_factor=.5,
                                   height_factor=1)
    data = widget.to_dict()
    assert data["type"] == "Container"
    assert data["style"]["widthFactor"] == .5
    assert data["style"]["heightFactor"] == 1.0


def test_fractionally_sized_box_rejects_invalid_factors():
    with pytest.raises(ValueError):
        FractionallySizedBox(width_factor=1.1)


def test_fitted_box_serializes_renderer_fit_mode():
    widget = FittedBox(Text("arena"), fit="cover")
    assert widget.to_dict()["style"]["fit"] == "cover"


def test_material_icon_compatibility_aliases_are_renderer_backed():
    assert Icons.PLAY_ARROW == Icons.PLAY
    assert Icons.EMOJI_EVENTS == Icons.TROPHY
    assert Icons.SKULL == Icons.WARNING
    assert Icons.LEADERBOARD == Icons.ANALYTICS
    assert Icons.STORAGE == Icons.DATABASE
