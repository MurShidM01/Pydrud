"""Regression tests for the layout and icon compatibility additions."""

import pytest

from pydrud import DataTable, FittedBox, FractionallySizedBox, Icons, MetricCard, Text, Timeline


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


def test_optional_icon_packs_can_be_loaded_without_a_hard_dependency():
    # Pack registration is process-global state; snapshot and restore it so
    # this test cannot leak pack icons into other suites (e.g. the generated
    # vector-set checks in test_v14_ui).
    saved = dict(Icons._external)
    try:
        count = Icons.load_pack({"BRAND_GITHUB": "github", "BRAND_PYTHON": "python"})
        assert count == 2
        assert Icons.BRAND_GITHUB == "github"
        assert Icons.normalize("brandGithub") == "github"
    finally:
        Icons._external.clear()
        Icons._external.update(saved)


def test_premium_compositions_use_native_widget_trees():
    metric = MetricCard("Revenue", "$12k", trend="+8%")
    table = DataTable(["Name", "Status"], [["Ada", "Active"]], striped=True)
    timeline = Timeline([{"title": "Created", "time": "Today"}])
    assert metric.to_dict()["type"] == "Card"
    assert table.to_dict()["type"] == "Card"
    assert timeline.to_dict()["type"] == "Column"


def test_data_table_rejects_mismatched_rows():
    with pytest.raises(ValueError):
        DataTable(["Only"], [["one", "too many"]])
