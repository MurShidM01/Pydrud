"""Phase 3 widget additions — overlays, FAB variants and the chip icon.

These cover the declarative surface added on top of the existing imperative
``page.dialog`` API: the widget must serialise the props the native layer
reads, and the FAB must emit the Material 3 geometry for each variant.
"""

import json
import unittest

from pydrud import (
    AlertDialog, Chip, Dialog, FloatingActionButton, Icons, ModalBottomSheet,
    AnimatedSwitcher, Text,
)


def tree(widget):
    """Serialise and round-trip through JSON — the bridge does exactly this."""
    return json.loads(json.dumps(widget.to_dict()))


class TestFabVariants(unittest.TestCase):

    def test_regular_is_a_material_square(self):
        style = FloatingActionButton(icon=Icons.ADD).style
        self.assertEqual(style["width"], 56)
        self.assertEqual(style["height"], 56)
        self.assertEqual(style["borderRadius"], 16)
        self.assertEqual(style["position"], "absolute")

    def test_small_and_large_sizes(self):
        small = FloatingActionButton(icon=Icons.ADD, variant="small").style
        large = FloatingActionButton(icon=Icons.ADD, variant="large").style
        self.assertEqual((small["width"], small["borderRadius"]), (40, 12))
        self.assertEqual((large["width"], large["borderRadius"]), (96, 28))

    def test_regular_honours_the_fab_size_token(self):
        from pydrud import Tokens
        style = FloatingActionButton(icon=Icons.ADD).style
        self.assertEqual(style["width"], Tokens.fab_size)

    def test_extended_is_a_row_with_icon_and_label(self):
        fab = FloatingActionButton("Create", icon=Icons.ADD, variant="extended")
        self.assertNotIn("width", fab.style)      # hugs its content
        self.assertEqual(fab.style["height"], 56)
        self.assertEqual(fab.style["borderRadius"], 16)
        data = tree(fab)
        row = data["children"][0]
        self.assertEqual(row["type"], "Row")
        self.assertEqual([c["type"] for c in row["children"]], ["Icon", "Text"])

    def test_invalid_variant_is_rejected(self):
        with self.assertRaises(ValueError):
            FloatingActionButton(icon=Icons.ADD, variant="huge")


class TestChipIcon(unittest.TestCase):

    def test_icon_is_serialised(self):
        data = tree(Chip("Filter", icon=Icons.SETTINGS, key="c"))
        self.assertEqual(data["props"]["icon"], "settings")

    def test_icon_defaults_to_absent(self):
        data = tree(Chip("Filter", key="c"))
        self.assertNotIn("icon", data["props"])


class TestAlertDialog(unittest.TestCase):

    def test_props_and_actions(self):
        data = tree(AlertDialog(
            title="Delete?", message="Undo is not possible.",
            icon=Icons.WARNING,
            actions=[("Cancel", "cancel"), ("Delete", "delete")], key="d"))
        props = data["props"]
        self.assertEqual(props["title"], "Delete?")
        self.assertEqual(props["message"], "Undo is not possible.")
        self.assertEqual(props["icon"], "warning")
        self.assertEqual(props["actions"], [
            {"label": "Cancel", "value": "cancel"},
            {"label": "Delete", "value": "delete"},
        ])

    def test_bare_label_action_uses_the_label_as_its_value(self):
        data = tree(AlertDialog(actions=["OK"], key="d"))
        self.assertEqual(data["props"]["actions"],
                         [{"label": "OK", "value": "OK"}])

    def test_dialog_alias_serialises_as_alert_dialog(self):
        data = tree(Dialog(title="Hi", key="d"))
        self.assertEqual(data["type"], "AlertDialog")
        self.assertEqual(data["props"]["title"], "Hi")


class TestModalBottomSheet(unittest.TestCase):

    def test_props(self):
        data = tree(ModalBottomSheet(
            title="Share via", options=["Messages", "Email"],
            icons=[Icons.MESSAGE, Icons.EMAIL], key="s"))
        props = data["props"]
        self.assertEqual(props["title"], "Share via")
        self.assertEqual(props["options"], ["Messages", "Email"])
        self.assertEqual(props["icons"], ["message", "email"])


class TestAnimatedSwitcher(unittest.TestCase):

    def test_duration_is_serialised(self):
        data = tree(AnimatedSwitcher(
            child=Text("a", key="a"), transition="fade", key="sw"))
        self.assertEqual(data["props"]["duration"], 250)
        self.assertEqual(data["props"]["childKey"], "a")

    def test_invalid_transition_is_rejected(self):
        with self.assertRaises(ValueError):
            AnimatedSwitcher(child=Text("a"), transition="spin")


if __name__ == "__main__":
    unittest.main()
