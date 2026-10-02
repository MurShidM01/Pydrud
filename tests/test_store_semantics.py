"""Store/Computed/Selector semantics pinned by the 1.5.2 audit."""

import unittest

from pydrud.core.state import State
from pydrud.core.store import Computed, Store


class TestMutateRemovals(unittest.TestCase):
    def test_in_place_draft_can_delete_keys(self):
        store = Store({"a": 1, "b": 2})
        store.mutate(lambda draft: draft.pop("a"))
        self.assertNotIn("a", store.state)
        self.assertEqual(store.get("b"), 2)

    def test_returned_dict_still_merges(self):
        store = Store({"a": 1, "b": 2})
        store.mutate(lambda draft: {"b": 3})
        self.assertEqual(store.state, {"a": 1, "b": 3})

    def test_in_place_edit_notifies(self):
        store = Store({"items": []})
        seen = []
        store.subscribe(lambda state, changed: seen.append(changed))
        store.mutate(lambda draft: draft["items"].append("x"))
        self.assertEqual(store.get("items"), ["x"])
        self.assertEqual(seen, [{"items"}])


class TestSelectorDispose(unittest.TestCase):
    def test_dispose_detaches_from_the_store(self):
        store = Store({"n": 0})
        selector = store.select("n")
        seen = []
        selector.listen(seen.append)
        store.set("n", 1)
        selector.dispose()
        store.set("n", 2)
        self.assertEqual(seen, [1])
        self.assertEqual(store._selectors, [])


class TestComputedLaziness(unittest.TestCase):
    def test_no_recompute_without_subscribers(self):
        source = State(1)
        calls = []

        def compute():
            calls.append(1)
            return source.value * 2

        derived = Computed(compute, sources=[source])
        self.assertEqual(derived.value, 2)
        self.assertEqual(len(calls), 1)
        source.value = 5
        self.assertEqual(len(calls), 1)      # still lazy
        self.assertEqual(derived.value, 10)  # recomputed on read
        self.assertEqual(len(calls), 2)

    def test_subscribers_are_notified_eagerly(self):
        source = State(1)
        derived = Computed(lambda: source.value * 2, sources=[source])
        seen = []
        derived.subscribe(seen.append)
        source.value = 4
        self.assertEqual(seen, [8])


if __name__ == "__main__":
    unittest.main()
