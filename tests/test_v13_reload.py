"""Stateful hot reload: bound State/Store values survive a module reload."""

from __future__ import annotations

import unittest

from pydrud import App, State, Store, Text
from pydrud.runtime.navigation import Router


class TestStateSnapshots(unittest.TestCase):

    def test_capture_and_restore_states_positionally(self):
        count = State(0, name="count")
        draft = State("", name="draft")
        app = App(target=lambda page: page.add(Text("x")))
        app.bind(count, draft)

        count.value = 7
        draft.value = "hello"
        snapshot = app.capture_state()
        self.assertEqual(snapshot["states"], [("count", 7), ("draft", "hello")])

        # A reload rebuilds the module-level objects with their defaults.
        fresh_count, fresh_draft = State(0, name="count"), State("", name="draft")
        reloaded = App(target=lambda page: page.add(Text("x")))
        reloaded.bind(fresh_count, fresh_draft)
        reloaded.restore_state(snapshot)
        self.assertEqual(fresh_count.value, 7)
        self.assertEqual(fresh_draft.value, "hello")

    def test_restore_tolerates_a_changed_number_of_states(self):
        app = App(target=lambda page: None)
        only_one = State(0)
        app.bind(only_one)
        app.restore_state({"states": [("", 3), ("", 4), ("", 5)]})
        self.assertEqual(only_one.value, 3)

        app2 = App(target=lambda page: None)
        a, b = State(1), State(2)
        app2.bind(a, b)
        app2.restore_state({"states": [("", 9)]})       # fewer than bound
        self.assertEqual((a.value, b.value), (9, 2))

    def test_restore_ignores_incompatible_values(self):
        app = App(target=lambda page: None)
        state = State(0)
        app.bind(state)
        app.restore_state({"states": [("other", "text")]})
        # Name mismatch or type mismatch must never crash the reload.
        self.assertIn(state.value, (0, "text"))

    def test_stores_are_snapshotted(self):
        store = Store({"user": "ada", "theme": "dark"})
        app = App(target=lambda page: None)
        app.bind(store)
        store["theme"] = "light"
        snapshot = app.capture_state()

        fresh = Store({"user": "ada", "theme": "dark"})
        app2 = App(target=lambda page: None)
        app2.bind(fresh)
        app2.restore_state(snapshot)
        self.assertEqual(fresh["theme"], "light")

    def test_route_is_restored(self):
        router = Router()
        router.define("/", lambda page: None)
        router.define("/items/:id", lambda page, params: None)
        router.initial("/")

        app = App(target=lambda page: None)
        app.attach_router(router)
        router.push("/items/4")
        snapshot = app.capture_state()
        self.assertEqual(snapshot["params"]["id"], 4)

        router2 = Router()
        router2.define("/", lambda page: None)
        router2.define("/items/:id", lambda page, params: None)
        router2.initial("/")
        app2 = App(target=lambda page: None)
        app2.attach_router(router2)
        app2.restore_state(snapshot)
        self.assertEqual(router2.current_params.get("id"), 4)

    def test_route_restore_skips_routes_that_no_longer_exist(self):
        router = Router()
        router.define("/", lambda page: None)
        router.initial("/")
        app = App(target=lambda page: None)
        app.attach_router(router)
        app.restore_state({"route": "/deleted-screen", "params": {}})
        self.assertEqual(router.current_route, "/")

    def test_preserve_state_can_be_switched_off(self):
        app = App(target=lambda page: None)
        self.assertTrue(app._preserve_state)
        app.preserve_state(False)
        self.assertFalse(app._preserve_state)
        self.assertIs(app.preserve_state(True), app)

    def test_capture_never_raises_on_broken_objects(self):
        class Grumpy:
            def subscribe(self, fn):
                return self

            def snapshot(self):
                raise RuntimeError("no")

        app = App(target=lambda page: None)
        app.bind(Grumpy())
        self.assertIsInstance(app.capture_state(), dict)


if __name__ == "__main__":
    unittest.main()
