"""The test harness must not report success before the app has caught up.

``AppTester.settle()`` used to look only at the event queue, so a tap whose
event was still travelling over the socket looked like a no-op and tests
flaked. These tests pin the contract: after an interaction returns, the
handler has run *and* the resulting render has reached the device.
"""

from __future__ import annotations

import unittest

from pydrud import App, Button, Column, State, Text
from pydrud.testing import AppTester


def _counter_app():
    count = State(0, name="settle_counter")

    def build(page):
        page.add(Column(key="root", children=[
            Text(str(count.value), key="label"),
            Button("Tap", key="btn").on_click(bump),
        ]))

    def bump(_event):
        count.value += 1
        app = App.current()
        if app is not None:
            app.update()

    return build, count


class TestSettle(unittest.TestCase):

    def test_tap_is_visible_immediately_after_it_returns(self):
        for attempt in range(5):
            build, count = _counter_app()
            with AppTester(build, title="settle") as tester:
                with self.subTest(attempt=attempt):
                    tester.tap("btn")
                    self.assertEqual(count.value, 1)
                    self.assertEqual(tester.prop("label", "value"), "1")

    def test_repeated_taps_all_land(self):
        build, count = _counter_app()
        with AppTester(build, title="settle") as tester:
            for expected in range(1, 6):
                tester.tap("btn")
                self.assertEqual(tester.prop("label", "value"), str(expected))
            self.assertEqual(count.value, 5)

    def test_device_counts_the_events_it_sends(self):
        build, _ = _counter_app()
        with AppTester(build, title="settle") as tester:
            before = tester.device.events_sent
            tester.tap("btn")
            self.assertGreater(tester.device.events_sent, before)
            self.assertGreaterEqual(tester.app._events_handled, before)


class TestAppCurrent(unittest.TestCase):

    def test_current_tracks_the_latest_app(self):
        first = App(target=lambda page: None, title="first")
        self.assertIs(App.current(), first)
        second = App(target=lambda page: None, title="second")
        self.assertIs(App.current(), second)

    def test_current_is_a_classmethod_on_instances_too(self):
        app = App(target=lambda page: None, title="only")
        self.assertIs(app.current(), app)


class TestRenderedTexts(unittest.TestCase):

    def test_list_tile_titles_count_as_visible_text(self):
        from pydrud.testing import RenderedNode

        node = RenderedNode({
            "type": "ListTile", "key": "tile",
            "props": {"title": "Buy milk", "subtitle": "today"},
            "children": [],
        })
        self.assertEqual(node.texts(), ["Buy milk", "today"])


if __name__ == "__main__":
    unittest.main()
