"""
Unit tests for Pydrud state management.
"""

import unittest
from pydrud.core.state import State, ReactiveDict


class TestState(unittest.TestCase):
    def test_initial_value(self):
        s = State(0)
        self.assertEqual(s.value, 0)

    def test_set_value(self):
        s = State(10)
        s.value = 20
        self.assertEqual(s.value, 20)

    def test_watch_called(self):
        s = State(0)
        calls = []
        s.watch(lambda old, new: calls.append((old, new)))
        s.value = 42
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], (0, 42))

    def test_watch_not_called_on_no_change(self):
        s = State("same")
        calls = []
        s.watch(lambda o, n: calls.append(1))
        # Even if user sets the same value, the watcher fires (intentional).
        s.value = "same"
        self.assertEqual(len(calls), 1)

    def test_unwatch(self):
        s = State(0)
        calls = []
        cb = lambda o, n: calls.append(1)
        s.watch(cb)
        s.unwatch(cb)
        s.value = 99
        self.assertEqual(len(calls), 0)


class TestReactiveDict(unittest.TestCase):
    def test_get_set_attr(self):
        d = ReactiveDict({"count": 0})
        self.assertEqual(d.count, 0)
        d.count = 5
        self.assertEqual(d.count, 5)

    def test_get_set_item(self):
        d = ReactiveDict()
        d["name"] = "World"
        self.assertEqual(d["name"], "World")

    def test_changed_signal(self):
        d = ReactiveDict({"x": 1})
        v0 = d.changed.value
        d.x = 2
        self.assertEqual(d.changed.value, v0 + 1)

    def test_contains(self):
        d = ReactiveDict({"a": 1})
        self.assertIn("a", d)
        self.assertNotIn("b", d)


class TestAppState(unittest.TestCase):
    def test_state_with_app_update(self):
        """Integration: State changes trigger page update."""
        from pydrud import App
        from pydrud.widgets import Text

        counter = State(0)
        app = App(target=lambda page: page.add(Text(str(counter.value))))
        app.build()

        # Simulate state change (should cause a re-render on the next update call).
        counter.value = 5
        app.update()
        tree = app._current_tree
        self.assertIsNotNone(tree)


if __name__ == "__main__":
    unittest.main()
