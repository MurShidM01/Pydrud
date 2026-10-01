"""Unit tests for the Pydrud 1.2 widget library (Material, gestures, animation)."""

import json
import unittest

from pydrud import (
    AnimatedContainer, AnimatedOpacity, AnimatedRotation, AnimatedScale,
    AnimatedSwitcher, Animation, Avatar, Badge, Banner, BottomNavigationBar,
    Chart, Chip, CircularProgress, Colors, ColorScheme, Dismissible,
    Draggable, Drawer, ExpansionTile, FadeIn, GestureDetector, Hero, Icons,
    InkWell, ListTile, NavItem, NavigationRail, Rating, RefreshIndicator,
    ScaleIn, Scaffold, SearchBar, SegmentedButton, Skeleton, SlideIn, Stepper,
    Switch, Tab, Tabs, Text, Theme, Tooltip, Typography, VideoPlayer, WebView,
    animate,
)
from pydrud.widgets.base import assign_stable_keys


def tree(widget):
    """Serialise and round-trip through JSON — the bridge does exactly this."""
    return json.loads(json.dumps(widget.to_dict()))


class TestListWidgets(unittest.TestCase):

    def test_list_tile_props(self):
        tile = ListTile("Wi-Fi", subtitle="PyNet 5G", leading=Icons.SETTINGS,
                        key="wifi")
        data = tree(tile)
        self.assertEqual(data["props"]["title"], "Wi-Fi")
        self.assertEqual(data["props"]["subtitle"], "PyNet 5G")
        self.assertEqual(data["props"]["leadingIcon"], "settings")
        self.assertNotIn("dense", data["props"])  # defaults stay native

    def test_list_tile_widget_trailing_becomes_child(self):
        tile = ListTile("Dark mode", trailing=Switch(value=True), key="dm")
        self.assertEqual(len(tile.children), 1)
        self.assertEqual(tile.children[0].key, "dm_trailing")

    def test_list_tile_click(self):
        seen = []
        tile = ListTile("Tap me", on_click=lambda e: seen.append(e))
        tile.event_handlers["click"]({"key": "x"})
        self.assertEqual(len(seen), 1)

    def test_expansion_tile_children_and_event(self):
        tile = ExpansionTile("FAQ", children=[Text("answer")], expanded=True,
                             on_expand=lambda e: None, key="faq")
        data = tree(tile)
        self.assertTrue(data["props"]["expanded"])
        self.assertIn("expand", data["events"])
        self.assertEqual(len(data["children"]), 1)


class TestSmallComponents(unittest.TestCase):

    def test_chip_variants_validated(self):
        with self.assertRaises(ValueError):
            Chip("x", variant="nope")

    def test_filter_chip_change(self):
        chip = Chip("Python", variant="filter", selected=True,
                    on_change=lambda e: None, key="c")
        data = tree(chip)
        self.assertTrue(data["props"]["selected"])
        self.assertIn("change", data["events"])

    def test_badge_counts_and_overflow(self):
        self.assertEqual(Badge(5).label, "5")
        self.assertEqual(Badge(150).label, "99+")
        self.assertEqual(Badge(150, max_count=9).label, "9+")
        self.assertFalse(Badge(0).show)       # zero hides the bubble
        self.assertTrue(Badge("NEW").show)

    def test_avatar_initials_are_two_upper_chars(self):
        self.assertEqual(Avatar(initials="ada lovelace").initials, "AD")

    def test_banner_severity_colour(self):
        self.assertEqual(Banner("x", severity="error").color, Colors.ERROR)
        with self.assertRaises(ValueError):
            Banner("x", severity="purple")

    def test_tooltip_wraps_child(self):
        tip = Tooltip("Delete", child=Text("x"))
        self.assertEqual(len(tip.children), 1)
        self.assertEqual(tree(tip)["props"]["message"], "Delete")


class TestNavigationWidgets(unittest.TestCase):

    def test_tabs_render_only_selected_body(self):
        tabs = Tabs([
            Tab("One", content=Text("first")),
            Tab("Two", content=Text("second")),
        ], selected=1, key="t")
        data = tree(tabs)
        self.assertEqual(len(data["props"]["tabs"]), 2)
        self.assertEqual(data["props"]["selected"], 1)
        self.assertEqual(len(data["children"]), 1)
        self.assertEqual(data["children"][0]["props"]["value"], "second")

    def test_tabs_clamp_selection(self):
        tabs = Tabs([Tab("Only")], selected=7)
        self.assertEqual(tabs.selected, 0)
        self.assertEqual(tabs.current.label, "Only")

    def test_bottom_navigation(self):
        nav = BottomNavigationBar([
            NavItem("Home", icon=Icons.HOME, route="/"),
            NavItem("Inbox", icon=Icons.EMAIL, badge=3),
        ], selected=1, on_change=lambda e: None, key="nav")
        data = tree(nav)
        self.assertEqual(data["props"]["items"][1]["badge"], "3")
        self.assertEqual(data["props"]["selected"], 1)

    def test_navigation_rail(self):
        rail = NavigationRail([NavItem("A", icon=Icons.HOME)], extended=True)
        self.assertTrue(tree(rail)["props"]["extended"])

    def test_drawer_side_validated(self):
        with self.assertRaises(ValueError):
            Drawer(side="middle")
        drawer = Drawer(header=Text("Hi"), children=[Text("Item")], key="d")
        self.assertEqual(drawer.children[0].key, "d_header")
        self.assertEqual(len(drawer.children), 2)

    def test_segmented_single_and_multi(self):
        single = SegmentedButton(["Day", "Week"], selected=1)
        self.assertEqual(single.selected, 1)
        multi = SegmentedButton(["A", "B"], selected=[0, 1], multi=True)
        self.assertEqual(multi.selected, [0, 1])


class TestInputFeedbackWidgets(unittest.TestCase):

    def test_search_bar_events(self):
        bar = SearchBar("py", hint="Find", on_change=lambda e: None,
                        on_submit=lambda e: None, on_clear=lambda e: None)
        data = tree(bar)
        self.assertEqual(data["props"]["value"], "py")
        self.assertEqual(sorted(data["events"]), ["change", "clear", "submit"])

    def test_rating_clamped_and_readonly(self):
        self.assertEqual(Rating(9, count=5).value, 5.0)
        self.assertTrue(Rating(3).readonly)
        self.assertFalse(Rating(3, on_change=lambda e: None).readonly)

    def test_circular_progress_modes(self):
        self.assertTrue(CircularProgress().indeterminate)
        self.assertFalse(CircularProgress(0.5).indeterminate)
        self.assertEqual(CircularProgress(5).value, 1.0)

    def test_skeleton_defaults(self):
        self.assertEqual(Skeleton(lines=0).lines, 1)

    def test_refresh_indicator_event(self):
        widget = RefreshIndicator(child=Text("list"),
                                  on_refresh=lambda e: None)
        self.assertIn("refresh", tree(widget)["events"])

    def test_stepper_progress(self):
        stepper = Stepper(["Cart", "Address", "Pay"], current=1)
        self.assertAlmostEqual(stepper.progress, 0.5)
        self.assertFalse(stepper.is_last)
        self.assertEqual(Stepper(["only"]).progress, 1.0)
        with self.assertRaises(ValueError):
            Stepper(["a"], orientation="diagonal")


class TestMediaWidgets(unittest.TestCase):

    def test_webview_requires_source(self):
        with self.assertRaises(ValueError):
            WebView()
        web = WebView("https://example.com", on_message=lambda e: None)
        self.assertIn("message", tree(web)["events"])

    def test_video_player_props(self):
        video = VideoPlayer("movie.mp4", loop=True)
        data = tree(video)
        self.assertTrue(data["props"]["loop"])
        self.assertAlmostEqual(data["props"]["aspectRatio"], 1.7778, places=3)

    def test_chart_accepts_numbers_pairs_and_dicts(self):
        self.assertEqual(Chart([1, 2, 3]).values, [1.0, 2.0, 3.0])
        labelled = Chart([{"label": "Mon", "value": 4}, ("Tue", 6)])
        self.assertEqual(labelled.values, [4.0, 6.0])
        self.assertEqual(labelled.labels, ["Mon", "Tue"])
        self.assertEqual(labelled.max_value, 6.0)
        with self.assertRaises(ValueError):
            Chart([1], kind="donut")


class TestGestures(unittest.TestCase):

    def test_only_subscribed_gestures_are_sent(self):
        detector = GestureDetector(child=Text("photo"),
                                   on_double_tap=lambda e: None,
                                   on_swipe_left=lambda e: None)
        data = tree(detector)
        self.assertEqual(data["props"]["gestures"],
                         ["double_tap", "swipe_left"])

    def test_gesture_detector_without_handlers_is_quiet(self):
        self.assertEqual(tree(GestureDetector(child=Text("x")))
                         ["props"]["gestures"], [])

    def test_inkwell_carries_ripple_config(self):
        ink = InkWell(child=Text("tap"), on_click=lambda e: None, radius=12)
        data = tree(ink)
        self.assertEqual(data["props"]["radius"], 12)
        self.assertIn("click", data["events"])

    def test_dismissible_direction_validated(self):
        with self.assertRaises(ValueError):
            Dismissible(direction="sideways")
        row = Dismissible(child=Text("mail"), on_dismiss=lambda e: None,
                          direction="end", background=Colors.ERROR)
        self.assertIn("dismiss", tree(row)["events"])

    def test_draggable_axis_validated(self):
        with self.assertRaises(ValueError):
            Draggable(axis="diagonal")
        self.assertEqual(tree(Draggable(child=Text("x"), axis="horizontal"))
                         ["props"]["axis"], "horizontal")


class TestAnimation(unittest.TestCase):

    def test_animation_spec(self):
        spec = Animation(300, curve="bounce", delay=50).to_dict()
        self.assertEqual(spec, {"duration": 300, "curve": "bounce", "delay": 50})
        with self.assertRaises(ValueError):
            Animation(100, curve="warp")
        with self.assertRaises(ValueError):
            Animation(-1)

    def test_presets(self):
        self.assertEqual(Animation.fast().duration, 150)
        self.assertEqual(Animation.springy().curve, "overshoot")

    def test_animated_container_tracks_animated_props(self):
        box = AnimatedContainer(child=Text("x"), width=120, bg=Colors.PRIMARY,
                                animation=400)
        data = tree(box)
        self.assertEqual(data["style"]["animation"]["duration"], 400)
        self.assertEqual(data["props"]["animated"], ["bg", "width"])

    def test_animated_opacity_scale_rotation(self):
        self.assertEqual(AnimatedOpacity(0.5).style["opacity"], 0.5)
        self.assertEqual(AnimatedOpacity(9).opacity, 1.0)
        self.assertEqual(AnimatedScale(2).style["scale"], 2.0)
        self.assertEqual(AnimatedRotation(90).style["rotation"], 90.0)

    def test_switcher_tracks_child_key(self):
        switcher = AnimatedSwitcher(child=Text("a", key="loading"))
        self.assertEqual(tree(switcher)["props"]["childKey"], "loading")
        with self.assertRaises(ValueError):
            AnimatedSwitcher(transition="explode")

    def test_entrance_widgets(self):
        for widget in (FadeIn(child=Text("a")), ScaleIn(child=Text("b")),
                       SlideIn(child=Text("c"), direction="left")):
            self.assertTrue(tree(widget)["props"]["once"])
        with self.assertRaises(ValueError):
            SlideIn(direction="sideways")

    def test_hero_requires_tag(self):
        with self.assertRaises(ValueError):
            Hero("", child=Text("x"))
        self.assertEqual(tree(Hero("photo", child=Text("x")))["props"]["tag"],
                         "photo")

    def test_animate_helper_and_method(self):
        label = Text("hi")
        animate(label, 120, opacity=0.2)
        self.assertEqual(label.style["animation"]["duration"], 120)
        self.assertEqual(label.style["opacity"], 0.2)
        other = Text("yo").animate(Animation.slow(), scale=1.1)
        self.assertEqual(other.style["animation"]["duration"], 450)


class TestThemeSystem(unittest.TestCase):

    def tearDown(self):
        Theme.light()

    def test_color_scheme_from_seed(self):
        light = ColorScheme.from_seed(Colors.INDIGO)
        dark = ColorScheme.from_seed(Colors.INDIGO, dark=True)
        self.assertFalse(light.dark)
        self.assertTrue(dark.dark)
        self.assertNotEqual(light.surface, dark.surface)
        for role in ColorScheme.ROLES:
            self.assertRegex(getattr(dark, role), r"^#[0-9A-F]{8}$")

    def test_unknown_role_rejected(self):
        with self.assertRaises(ValueError):
            ColorScheme(primary="#FF000000", sparkle="#FFFFFFFF")

    def test_theme_use_adopts_scheme(self):
        Theme.use(ColorScheme.from_seed(Colors.TEAL, dark=True))
        self.assertTrue(Theme.dark_mode)
        self.assertEqual(Theme.text, Theme.scheme.on_surface)

    def test_typography_scale(self):
        scaled = Typography.scale(2.0)
        self.assertEqual(scaled["body"]["size"], 32.0)
        self.assertEqual(scaled["body"]["weight"], 400)


class TestScaffoldComposition(unittest.TestCase):

    def test_scaffold_hosts_new_slots(self):
        scaffold = Scaffold(
            key="s",
            body=Text("body"),
            drawer=Drawer(children=[Text("menu")], key="drawer"),
            bottom_navigation=BottomNavigationBar(
                [NavItem("A", icon=Icons.HOME)], key="bn"),
            banner=Banner("Offline", key="banner"),
        )
        keys = [node["key"] for node in _walk(tree(scaffold))]
        for expected in ("drawer", "bn", "banner"):
            self.assertIn(expected, keys)

    def test_drawer_is_tagged_with_its_side(self):
        drawer = Drawer(children=[Text("menu")], key="d", side="end")
        Scaffold(key="s", body=Text("b"), end_drawer=drawer).to_dict()
        self.assertEqual(drawer.style["drawerSide"], "end")

    def test_navigation_rail_sits_beside_the_body(self):
        scaffold = Scaffold(key="s", body=Text("body"),
                            navigation_rail=NavigationRail(
                                [NavItem("A", icon=Icons.HOME)], key="rail"))
        data = tree(scaffold)
        row = [n for n in _walk(data) if n["key"] == "s._railrow"]
        self.assertEqual(len(row), 1)
        self.assertEqual(len(row[0]["children"]), 2)

    def test_fab_position_validated(self):
        with self.assertRaises(ValueError):
            Scaffold(body=Text("x"), fab_position="middle")


class TestKeysAndSerialisation(unittest.TestCase):

    def test_every_new_widget_round_trips_through_json(self):
        widgets = [
            ListTile("a"), ExpansionTile("b"), Chip("c"), Badge(1),
            Avatar(initials="AB"), Banner("d"), Tooltip("e"),
            Tabs([Tab("f", content=Text("g"))]),
            BottomNavigationBar([NavItem("h", icon=Icons.HOME)]),
            NavigationRail([NavItem("i", icon=Icons.HOME)]),
            Drawer(children=[Text("j")]), SegmentedButton(["k"]),
            SearchBar(), Rating(1), CircularProgress(), Skeleton(),
            RefreshIndicator(child=Text("l")), Stepper(["m"]),
            WebView("https://x.dev"), VideoPlayer("v.mp4"), Chart([1, 2]),
            GestureDetector(child=Text("n")), InkWell(child=Text("o")),
            Dismissible(child=Text("p")), Draggable(child=Text("q")),
            AnimatedContainer(child=Text("r")), AnimatedOpacity(1),
            AnimatedScale(1), AnimatedRotation(0),
            AnimatedSwitcher(child=Text("s")), FadeIn(child=Text("t")),
            SlideIn(child=Text("u")), ScaleIn(child=Text("v")),
            Hero("w", child=Text("x")),
        ]
        for widget in widgets:
            with self.subTest(widget=type(widget).__name__):
                data = tree(widget)
                self.assertEqual(data["type"], widget._widget_type)
                self.assertIsInstance(data["props"], dict)

    def test_stable_keys_are_assigned_to_new_widgets(self):
        root = Tabs([Tab("One", content=Text("body"))], key="tabs")
        assign_stable_keys(root)
        for node, _depth in root.walk():
            self.assertTrue(node.key)


def _walk(node):
    yield node
    for child in node.get("children") or []:
        yield from _walk(child)


if __name__ == "__main__":
    unittest.main()


class TestExampleApps(unittest.TestCase):
    """The shipped examples must build and react, not just import."""

    def _load(self, name):
        import importlib.util
        import os

        path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "examples", f"{name}.py")
        spec = importlib.util.spec_from_file_location(f"example_{name}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_todo_example_builds_and_mutates(self):
        from pydrud import App

        todo = self._load("todo_app")
        todo.store.reset({"todos": [], "filter": 0, "query": "", "draft": ""})
        app = App(target=todo.main)
        self.assertIn("Nothing here yet.", _texts(app.build()))

        todo.add_todo("Buy milk")
        self.assertIn("Buy milk", _texts(app.build()))
        todo.toggle_todo(0)
        self.assertTrue(todo.store["todos"][0]["done"])
        todo.store.set("filter", 1)                 # Active only
        self.assertNotIn("Buy milk", _texts(app.build()))
        todo.delete_todo(0)
        self.assertEqual(todo.store["todos"], [])

    def test_weather_example_renders_skeletons_then_data(self):
        from pydrud import App

        weather = self._load("weather_app")
        app = App(target=weather.main)
        keys = [n["key"] for n in _walk(app.build().to_dict())]
        self.assertIn("sk_chart", keys)             # loading state

        weather.loading.value = False
        weather.forecast.value = [{"day": "06-01", "temp": 33.0},
                                  {"day": "06-02", "temp": 31.5}]
        data = app.build().to_dict()
        chart = [n for n in _walk(data) if n["key"] == "chart"][0]
        self.assertEqual(chart["props"]["values"], [33.0, 31.5])
        self.assertIn("Karachi", _texts(app.build()))


def _texts(widget):
    out = []
    for node in _walk(widget.to_dict()):
        value = node["props"].get("value") or node["props"].get("title")
        if isinstance(value, str):
            out.append(value)
    return out
