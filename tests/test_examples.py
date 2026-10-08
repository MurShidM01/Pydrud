"""The bundled example apps must keep working.

``examples/todo_app.py`` and ``examples/weather_app.py`` are the first thing
a reader runs, so they are driven end-to-end through :class:`AppTester` here
— add, toggle, filter, search, swipe-to-delete, clear, and the weather app's
bottom navigation — rather than only being import-checked.
"""

from __future__ import annotations

import os
import sys
import unittest

from pydrud import App
from pydrud.testing import AppTester

_EXAMPLES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")
if _EXAMPLES not in sys.path:
    sys.path.insert(0, _EXAMPLES)

import todo_app      # noqa: E402  (path is set above)
import weather_app   # noqa: E402


def _todo_app() -> App:
    app = App(target=todo_app.main, title="Todo", dev_server=False)
    app.bind(todo_app.store)
    return app


class TestTodoExample(unittest.TestCase):

    def setUp(self):
        todo_app.store.set("todos", [])
        todo_app.store.set("filter", 0)
        todo_app.store.set("query", "")
        todo_app.store.set("draft", "")

    def test_add_toggle_and_filter(self):
        with AppTester(app=_todo_app()) as t:
            self.assertTrue(t.shows("Nothing here yet."))
            t.type_in("draft", "Buy milk")
            t.tap("add")
            t.type_in("draft", "Walk the dog")
            t.tap("add")
            self.assertIn("Buy milk", t.texts)
            self.assertIn("Walk the dog", t.texts)

            # Toggling marks the first done; the Done filter then hides the
            # second, untouched one.
            t.tap("tile_0")
            t.device.change("filter", 2)
            t.settle()
            self.assertIn("Buy milk", t.texts)
            self.assertNotIn("Walk the dog", t.texts)

    def test_swipe_to_delete_a_row(self):
        todo_app.store.set("todos", [
            {"text": "Buy milk", "done": False},
            {"text": "Walk the dog", "done": False},
        ])
        with AppTester(app=_todo_app()) as t:
            t.device.dismiss("row_0", "end")
            t.settle()
            self.assertNotIn("Buy milk", t.texts)
            self.assertIn("Walk the dog", t.texts)

    def test_search_filters_the_list(self):
        todo_app.store.set("todos", [
            {"text": "Buy milk", "done": False},
            {"text": "Walk the dog", "done": False},
        ])
        with AppTester(app=_todo_app()) as t:
            t.device.change("search", "walk")
            t.settle()
            self.assertIn("Walk the dog", t.texts)
            self.assertNotIn("Buy milk", t.texts)

    def test_the_body_is_inset_from_the_screen_edges(self):
        with AppTester(app=_todo_app()) as t:
            body = t.node("todo._body.0Column")
            self.assertEqual(body.style["padding"],
                             {"left": 16, "right": 16, "top": 12, "bottom": 12})


class TestWeatherExample(unittest.TestCase):

    def setUp(self):
        weather_app.screen.value = 0
        weather_app.loading.value = False
        weather_app.place.value = "Karachi"
        weather_app.forecast.value = [{"day": "06-01", "temp": 33.0}]

    def _app(self) -> App:
        app = App(target=weather_app.main, title="Weather", dev_server=False)
        app.bind(weather_app.screen, weather_app.loading,
                 weather_app.forecast, weather_app.place)
        return app

    def test_today_shows_the_forecast(self):
        with AppTester(app=self._app()) as t:
            self.assertTrue(t.shows("Weather"))
            self.assertIn("Karachi", t.texts)
            self.assertIn("06-01", t.texts)

    def test_bottom_navigation_switches_screens(self):
        with AppTester(app=self._app()) as t:
            t.device.change("nav", 1)
            t.settle()
            self.assertEqual(weather_app.screen.value, 1)
            self.assertIn("Lahore", t.texts)

            t.device.change("nav", 2)
            t.settle()
            self.assertIn("Use my location", t.texts)


if __name__ == "__main__":
    unittest.main()
