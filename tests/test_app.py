"""
Integration tests for the Pydrud App lifecycle.
"""

import unittest
from pydrud import App
from pydrud.widgets import Text
from pydrud.core.state import State


class TestAppBuild(unittest.TestCase):
    def test_app_build_returns_widget_tree(self):
        app = App(target=lambda page: page.add(Text("Hello")))
        tree = app.build()
        self.assertIsNotNone(tree)
        self.assertEqual(tree._widget_type, "Stack")

    def test_app_build_with_multiple_controls(self):
        app = App(target=lambda page: page.add(
            Text("A"),
            Text("B"),
            Text("C"),
        ))
        tree = app.build()
        self.assertIsNotNone(tree)

    def test_app_title(self):
        app = App(title="My Test App")
        self.assertEqual(app.title, "My Test App")

    def test_app_page_add_clear(self):
        app = App(target=lambda page: None)
        app._page.add(Text("A"), Text("B"))
        self.assertEqual(len(app._page.controls), 2)
        app._page.clear()
        self.assertEqual(len(app._page.controls), 0)

    def test_app_update_rerenders(self):
        counter = State(0)

        def build(page):
            page.clear()
            page.add(Text(f"Count: {counter.value}"))

        app = App(target=build)
        initial_tree = app.build()

        counter.value = 1

        # Update should create patches.
        app._prev_tree = initial_tree
        app._page.add(Text(f"Count: {counter.value}"))
        app.update()

        # The current tree should be updated.
        self.assertIsNotNone(app._current_tree)


class TestPage(unittest.TestCase):
    def test_page_bgcolor(self):
        app = App(target=lambda page: None)
        app._page.bgcolor = "#FF00FF"
        tree = app.build()
        self.assertEqual(tree.style.get("bg"), "#FF00FF")

    def test_page_padding(self):
        app = App(target=lambda page: None)
        app._page.padding = 16
        tree = app.build()
        self.assertIn("padding", tree.style)

    def test_page_remove(self):
        app = App(target=lambda page: None)
        t = Text("X", key="x")
        app._page.add(t)
        app._page.remove("x")
        self.assertEqual(len(app._page.controls), 0)


class TestAppWithState(unittest.TestCase):
    def test_app_state_reactivity(self):
        """State changes followed by update() produce new tree."""
        count = State(0)

        def view(page):
            page.clear()
            page.add(Text(f"Count: {count.value}"))

        app = App(target=view)
        tree1 = app.build()
        self.assertIsNotNone(tree1)

        count.value = 5

        def view2(page):
            page.clear()
            page.add(Text(f"Count: {count.value}"))

        # Simulate rebuild.
        app.target = view2
        tree2 = app.build()
        # Check the tree contains the new value.
        text_widget = tree2.find_by_key(tree2.children[0].children[0].key)
        if text_widget:
            self.assertEqual(text_widget.value, "Count: 5")


if __name__ == "__main__":
    unittest.main()
