"""v1.5 — the responsive engine, live metrics and responsive widgets."""

import unittest

from pydrud import (
    AdaptiveLayout, Breakpoints, Column, MediaQuery, ResponsiveBuilder,
    ResponsiveGrid, Responsive, Row, SafeArea, ShowWhen, Text,
)


PHONE = dict(width=360, height=800, density=3.0)
TABLET = dict(width=800, height=1280, density=2.0)
LANDSCAPE_PHONE = dict(width=800, height=360, density=3.0)
DESKTOP = dict(width=1440, height=900, density=2.0)


class ResponsiveTestCase(unittest.TestCase):
    def setUp(self):
        MediaQuery.reset()
        MediaQuery.clear_listeners()
        Breakpoints.reset()
        Responsive.configure_reset()

    tearDown = setUp


class TestMetrics(ResponsiveTestCase):
    def test_defaults_describe_a_baseline_phone(self):
        info = MediaQuery.info()
        self.assertEqual((info.width, info.height), (360, 640))
        self.assertEqual(info.breakpoint, "compact")
        self.assertEqual(info.device_type, "phone")
        self.assertEqual(info.orientation, "portrait")

    def test_update_derives_everything(self):
        MediaQuery.update(**TABLET)
        info = MediaQuery.info()
        self.assertEqual(info.device_type, "tablet")
        self.assertEqual(info.breakpoint, "medium")
        self.assertEqual(info.shortest_side, 800)
        self.assertEqual(MediaQuery.resolution(), (1600, 2560))
        self.assertTrue(MediaQuery.is_tablet())

    def test_pixels_are_used_when_reported(self):
        MediaQuery.update(width=360, height=800, density=3.0,
                          width_px=1080, height_px=2400)
        self.assertEqual(MediaQuery.resolution(), (1080, 2400))

    def test_landscape_phone_is_not_a_tablet(self):
        MediaQuery.update(**LANDSCAPE_PHONE)
        self.assertTrue(MediaQuery.is_landscape())
        self.assertEqual(MediaQuery.info().device_type, "phone")
        # ... even though its *width* is in the medium size class.
        self.assertEqual(MediaQuery.breakpoint(), "medium")

    def test_desktop_width_class(self):
        MediaQuery.update(**DESKTOP)
        self.assertEqual(MediaQuery.breakpoint(), "large")
        self.assertTrue(MediaQuery.is_desktop())

    def test_update_returns_whether_anything_changed(self):
        self.assertTrue(MediaQuery.update(**PHONE))
        self.assertFalse(MediaQuery.update(**PHONE))

    def test_listeners_fire_once_per_change(self):
        seen = []
        stop = MediaQuery.listen(lambda info: seen.append(info.breakpoint))
        MediaQuery.update(**TABLET)
        MediaQuery.update(**TABLET)      # no change → no callback
        stop()
        MediaQuery.update(**PHONE)
        self.assertEqual(seen, ["medium"])

    def test_broken_listener_cannot_break_rendering(self):
        MediaQuery.listen(lambda info: 1 / 0)
        MediaQuery.update(**TABLET)      # must not raise
        self.assertEqual(MediaQuery.breakpoint(), "medium")

    def test_safe_area_and_viewport(self):
        MediaQuery.update(width=360, height=800, density=3.0,
                          padding_top=48, padding_bottom=24,
                          keyboard_height=300)
        self.assertEqual(MediaQuery.safe_area()["top"], 48)
        self.assertTrue(MediaQuery.keyboard_visible())
        self.assertEqual(MediaQuery.viewport(), (360, 800 - 48 - 24 - 300))

    def test_matches_query(self):
        MediaQuery.update(**TABLET)
        self.assertTrue(MediaQuery.matches(min_width=600, orientation="portrait"))
        self.assertFalse(MediaQuery.matches(min_width=600, orientation="landscape"))
        self.assertFalse(MediaQuery.matches(max_width=500))

    def test_at_least_at_most(self):
        MediaQuery.update(**TABLET)
        self.assertTrue(MediaQuery.at_least("medium"))
        self.assertFalse(MediaQuery.at_least("expanded"))
        self.assertTrue(MediaQuery.at_most("large"))


class TestBreakpoints(ResponsiveTestCase):
    def test_custom_breakpoints(self):
        Breakpoints.configure(medium=700)
        MediaQuery.update(width=650, height=1000, density=2.0)
        self.assertEqual(MediaQuery.breakpoint(), "compact")
        Breakpoints.reset()
        MediaQuery.update(width=650, height=1000, density=2.0)
        self.assertEqual(MediaQuery.breakpoint(), "medium")

    def test_breakpoints_must_increase(self):
        with self.assertRaises(ValueError):
            Breakpoints.configure(medium=900, expanded=800)

    def test_unknown_breakpoint_rejected(self):
        with self.assertRaises(ValueError):
            Breakpoints.configure(gigantic=4000)


class TestScaling(ResponsiveTestCase):
    def test_percent_units(self):
        MediaQuery.update(**PHONE)
        self.assertEqual(Responsive.wp(50), 180)
        self.assertEqual(Responsive.hp(25), 200)
        self.assertEqual(Responsive.sw(100), 360)

    def test_viewport_units_exclude_insets(self):
        MediaQuery.update(width=360, height=800, density=3.0,
                          padding_top=40, padding_bottom=40)
        self.assertEqual(Responsive.vh(50), 360)

    def test_px_conversions(self):
        MediaQuery.update(**PHONE)
        self.assertEqual(Responsive.to_px(16), 48)
        self.assertEqual(Responsive.px(48), 16)

    def test_font_scale_is_capped(self):
        MediaQuery.update(width=360, height=800, density=3.0, text_scale=2.0)
        self.assertEqual(Responsive.sp(16, max_scale=1.3), 21)

    def test_scaling_is_clamped_and_configurable(self):
        MediaQuery.update(**TABLET)
        self.assertEqual(Responsive.text(16), 19)       # 1.2x clamp
        Responsive.configure(max_factor=2.0)
        self.assertEqual(Responsive.text(16), 32)       # 800/360 = 2.22 → 2.0

    def test_shortest_side_basis_survives_rotation(self):
        MediaQuery.update(**PHONE)
        portrait = Responsive.text(16)
        MediaQuery.update(**LANDSCAPE_PHONE)
        self.assertEqual(Responsive.text(16), portrait)

    def test_value_picker_falls_back_upwards(self):
        MediaQuery.update(**PHONE)
        self.assertEqual(Responsive.value(compact=1, expanded=3), 1)
        MediaQuery.update(**TABLET)
        self.assertEqual(Responsive.value(compact=1, expanded=3), 1)
        self.assertEqual(Responsive.value(compact=1, medium=2, expanded=3), 2)
        MediaQuery.update(**DESKTOP)
        self.assertEqual(Responsive.value(compact=1, medium=2, expanded=3), 3)
        self.assertEqual(Responsive.value(phone=8, desktop=32), 32)

    def test_orientation_override_wins(self):
        MediaQuery.update(**LANDSCAPE_PHONE)
        self.assertEqual(Responsive.value(compact=8, landscape=24), 24)

    def test_select_and_default(self):
        MediaQuery.update(**PHONE)
        self.assertEqual(Responsive.select({"expanded": 3}, default=1), 1)

    def test_grid_maths(self):
        MediaQuery.update(**TABLET)
        cols, width = Responsive.grid(min_width=180, gutter=16)
        self.assertEqual(cols, 4)
        self.assertGreater(width, 150)
        self.assertEqual(Responsive.content_width(560), 560)

    def test_gutter_grows_with_the_window(self):
        MediaQuery.update(**PHONE)
        phone_gutter = Responsive.gutter()
        MediaQuery.update(**DESKTOP)
        self.assertGreater(Responsive.gutter(), phone_gutter)


class TestResponsiveWidgets(ResponsiveTestCase):
    def test_builder_sees_live_metrics(self):
        widget = ResponsiveBuilder(lambda s: Text(f"{s.width}"), key="rb")
        MediaQuery.update(**PHONE)
        self.assertEqual(widget.to_dict()["props"]["value"], "360")
        MediaQuery.update(**TABLET)
        self.assertEqual(widget.to_dict()["props"]["value"], "800")

    def test_builder_accepts_zero_argument_callables(self):
        widget = ResponsiveBuilder(lambda: Text("hi"), key="rb")
        self.assertEqual(widget.to_dict()["props"]["value"], "hi")

    def test_builder_rejects_non_widgets(self):
        with self.assertRaises(TypeError):
            ResponsiveBuilder(lambda s: "nope").to_dict()

    def test_adaptive_layout_switches_on_breakpoint(self):
        layout = AdaptiveLayout(
            compact=Column(children=[Text("a")]),
            expanded=Row(children=[Text("a")]),
            key="al",
        )
        MediaQuery.update(**PHONE)
        self.assertEqual(layout.to_dict()["type"], "Column")
        MediaQuery.update(**DESKTOP)
        self.assertEqual(layout.to_dict()["type"], "Row")

    def test_adaptive_layout_builds_lazily(self):
        built = []

        def heavy():
            built.append(1)
            return Text("tablet")

        layout = AdaptiveLayout(compact=Text("phone"), medium=heavy, key="al")
        MediaQuery.update(**PHONE)
        layout.to_dict()
        self.assertEqual(built, [])
        MediaQuery.update(**TABLET)
        layout.to_dict()
        self.assertEqual(built, [1])

    def test_responsive_grid_columns_follow_the_screen(self):
        grid = ResponsiveGrid(children=[Text(str(i)) for i in range(6)],
                              min_item_width=160, spacing=16, key="g")
        MediaQuery.update(**PHONE)
        self.assertEqual(grid.to_dict()["style"]["columns"], 2)
        MediaQuery.update(**TABLET)
        self.assertEqual(grid.to_dict()["style"]["columns"], 4)

    def test_show_when_matches(self):
        widget = ShowWhen(Text("sidebar"), min_width=600,
                          otherwise=Text("compact"), key="sw")
        MediaQuery.update(**PHONE)
        self.assertEqual(widget.to_dict()["props"]["value"], "compact")
        MediaQuery.update(**TABLET)
        self.assertEqual(widget.to_dict()["props"]["value"], "sidebar")

    def test_show_when_renders_a_placeholder(self):
        widget = ShowWhen(Text("x"), at_least="expanded", key="sw")
        MediaQuery.update(**PHONE)
        data = widget.to_dict()
        self.assertEqual(data["type"], "Container")
        self.assertEqual(data["style"]["width"], 0)

    def test_safe_area_uses_device_insets(self):
        MediaQuery.update(width=360, height=800, density=3.0,
                          padding_top=48, padding_bottom=24)
        data = SafeArea(child=Text("x"), key="sa").to_dict()
        self.assertEqual(data["style"]["padding"]["top"], 48)
        self.assertEqual(data["style"]["padding"]["bottom"], 24)

    def test_safe_area_edges_can_be_disabled(self):
        MediaQuery.update(width=360, height=800, density=3.0,
                          padding_top=48, padding_bottom=24)
        data = SafeArea(child=Text("x"), top=False, key="sa").to_dict()
        self.assertEqual(data["style"]["padding"]["top"], 0)


class TestAppMetricsEvents(ResponsiveTestCase):
    """The ``metrics`` bridge event must refresh MediaQuery and re-render."""

    def test_metrics_event_updates_and_rerenders(self):
        from pydrud.main import App

        app = App(title="t")
        renders = []
        app.render = lambda *a, **k: renders.append(1)   # type: ignore
        seen = []
        app.on_metrics_change(lambda info: seen.append(info.orientation))

        app._handle_raw_event(
            '{"type": "metrics", "data": {"width": 800, "height": 360,'
            ' "density": 3.0, "padding_bottom": 24}}')

        self.assertEqual(MediaQuery.width, 800)
        self.assertEqual(MediaQuery.safe_area()["bottom"], 24)
        self.assertEqual(seen, ["landscape"])
        self.assertEqual(len(renders), 1)

    def test_identical_metrics_do_not_rerender(self):
        from pydrud.main import App

        app = App(title="t")
        renders = []
        app.render = lambda *a, **k: renders.append(1)   # type: ignore
        event = ('{"type": "metrics", "data": {"width": 420, "height": 900,'
                 ' "density": 2.0}}')
        app._handle_raw_event(event)
        app._handle_raw_event(event)
        self.assertEqual(len(renders), 1)

    def test_ready_event_still_initialises_metrics(self):
        from pydrud.main import App

        app = App(title="t")
        app.render = lambda *a, **k: None                # type: ignore
        app._handle_raw_event(
            '{"type": "ready", "data": {"width": 600, "height": 960,'
            ' "density": 2.0, "text_scale": 1.15}}')
        self.assertEqual(MediaQuery.width, 600)
        self.assertEqual(Responsive.text_scale(), 1.15)


if __name__ == "__main__":
    unittest.main()
