"""Accessibility: content descriptions, contrast and touch targets (§14.7).

Pydrud can render a beautiful screen that a screen-reader user cannot use
and a low-vision user cannot read. These tests pin the three pieces that
close that gap:

* a ``semantics`` label that reaches Android's ``contentDescription`` and
  survives the incremental-diff update path;
* a WCAG contrast checker (``Colors.contrast`` plus a ``pydrud analyze``
  lint) so an unreadable text/background pair is caught at build time;
* a 48 dp touch-target lint for interactive widgets.

The Java renderer cannot run here, so the last section pins the exact
contract the generated ``ViewFactory`` implements.
"""

from __future__ import annotations

import os
import re
import unittest

from pydrud import (Button, Colors, Column, Container, IconButton,
                    Icons, State, Text)
from pydrud.commands.analyzer import _analyze_file
from pydrud.core.diff import TreeDiff
from pydrud.testing import AppTester

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEW_FACTORY = os.path.join(ROOT, "pydrud", "android", "templates",
                            "android", "ViewFactory.java.j2")


def _java() -> str:
    with open(VIEW_FACTORY, encoding="utf-8") as handle:
        return handle.read()


def messages(source: str) -> list:
    return [i["message"] for i in _analyze_file(source, "x.py")]


# ── content descriptions ────────────────────────────────────────────────────


class TestSemanticsSerialisation(unittest.TestCase):

    def test_semantics_is_sent_at_the_node_level(self):
        node = Text("Save", semantics="Save the document").to_dict()
        self.assertEqual(node["semantics"], "Save the document")

    def test_the_default_is_null(self):
        self.assertIsNone(Text("Save").to_dict()["semantics"])

    def test_an_icon_only_button_can_be_labelled(self):
        node = IconButton(icon=Icons.SAVE, semantics="Save").to_dict()
        self.assertEqual(node["semantics"], "Save")

    def test_a_button_forwards_the_label(self):
        self.assertEqual(Button("Save", semantics="Save file").to_dict()["semantics"],
                         "Save file")

    def test_a_container_forwards_the_label(self):
        node = Container(child=Text("x"), semantics="Summary card").to_dict()
        self.assertEqual(node["semantics"], "Summary card")


class TestSemanticsDiff(unittest.TestCase):

    def test_changing_the_label_emits_an_update(self):
        patches = TreeDiff.diff(Text("x", semantics="old", key="g"),
                                Text("x", semantics="new", key="g"))
        self.assertEqual([p.op for p in patches], ["update"], patches)
        self.assertEqual(patches[0].props["_semantics"], "new")

    def test_an_unchanged_label_is_not_resent(self):
        patches = TreeDiff.diff(Text("x", semantics="same", key="g"),
                                Text("x", semantics="same", key="g"))
        self.assertEqual(patches, [])

    def test_removing_the_label_sends_null(self):
        patches = TreeDiff.diff(Text("x", semantics="label", key="g"),
                                Text("x", key="g"))
        self.assertEqual([p.op for p in patches], ["update"], patches)
        self.assertIsNone(patches[0].props["_semantics"])


class TestSemanticsInTheHarness(unittest.TestCase):

    def test_the_rendered_node_mirrors_the_label(self):
        with AppTester(lambda page: page.add(
                IconButton(icon=Icons.SAVE, semantics="Save the file",
                           key="save"))) as app:
            self.assertEqual(app.node("save").semantics, "Save the file")

    def test_a_label_change_reaches_the_device(self):
        label = State("Save")

        def main(page):
            def relabel(_event):
                label.value = "Saving…"
                page.update()

            page.add(Column(children=[
                IconButton(icon=Icons.SAVE, semantics=label.value, key="save"),
                Text("change", key="go", on_click=relabel),
            ]))

        with AppTester(main) as app:
            self.assertEqual(app.node("save").semantics, "Save")
            app.tap("go")
            self.assertEqual(app.node("save").semantics, "Saving…")


# ── WCAG contrast maths ─────────────────────────────────────────────────────


class TestContrastMath(unittest.TestCase):

    def test_black_on_white_is_maximal(self):
        self.assertAlmostEqual(
            Colors.contrast(Colors.BLACK, Colors.WHITE), 21.0, places=2)

    def test_a_colour_against_itself_is_one(self):
        self.assertAlmostEqual(
            Colors.contrast(Colors.PRIMARY, Colors.PRIMARY), 1.0, places=3)

    def test_it_is_symmetric(self):
        self.assertEqual(Colors.contrast(Colors.BLACK, Colors.WHITE),
                         Colors.contrast(Colors.WHITE, Colors.BLACK))

    def test_it_accepts_six_and_eight_digit_hex(self):
        self.assertAlmostEqual(Colors.contrast("#000000", "#FFFFFF"),
                               Colors.contrast("#FF000000", "#FFFFFFFF"),
                               places=3)

    def test_the_default_palette_reads_on_surface(self):
        self.assertTrue(Colors.meets_contrast(Colors.TEXT, Colors.SURFACE))
        self.assertTrue(Colors.meets_contrast(Colors.TEXT_SECONDARY,
                                              Colors.SURFACE))

    def test_light_grey_on_white_fails(self):
        self.assertFalse(Colors.meets_contrast(Colors.GREY_LIGHT,
                                               Colors.WHITE))

    def test_large_text_uses_a_lower_threshold(self):
        grey = "#FF7A7A7A"  # 4.3:1 on white — fails AA normal, passes large
        self.assertFalse(Colors.meets_contrast(grey, Colors.WHITE))
        self.assertTrue(Colors.meets_contrast(grey, Colors.WHITE, large=True))


# ── the analyzer contrast lint ──────────────────────────────────────────────


class TestContrastLint(unittest.TestCase):

    def test_an_unreadable_button_is_flagged(self):
        source = ('from pydrud import Button, Colors\n'
                  'Button("Save", color=Colors.WHITE, bg_color=Colors.WHITE)\n')
        found = messages(source)
        self.assertTrue(any("Low contrast" in m for m in found), found)

    def test_a_readable_pair_is_clean(self):
        source = ('from pydrud import Button, Colors\n'
                  'Button("Save", color=Colors.TEXT, bg_color=Colors.WHITE)\n')
        self.assertEqual(messages(source), [])

    def test_the_finding_names_the_ratio_and_the_fix(self):
        source = ('from pydrud import Button, Colors\n'
                  'Button("Save", color=Colors.WHITE, bg_color=Colors.WHITE)\n')
        message = next(m for m in messages(source) if "Low contrast" in m)
        self.assertIn("1.0:1", message)
        self.assertIn("4.5:1", message)
        self.assertIn("Colors.on(", message)

    def test_a_hex_pair_is_checked(self):
        source = ('from pydrud import Text\n'
                  'Text("hi", color="#FFDDDDDD", style={"bg": "#FFEFEFEF"})\n')
        self.assertTrue(any("Low contrast" in m for m in messages(source)))

    def test_a_container_background_and_child_text_are_compared(self):
        source = ('from pydrud import Container, Text, Colors\n'
                  'Container(style={"bg": Colors.WHITE}, '
                  'child=Text("hi", color=Colors.GREY_LIGHT))\n')
        found = messages(source)
        self.assertTrue(any("Low contrast" in m for m in found), found)

    def test_a_transparent_background_is_not_measured(self):
        source = ('from pydrud import Text, Colors\n'
                  'Text("hi", color=Colors.WHITE, '
                  'style={"bg": Colors.TRANSPARENT})\n')
        self.assertFalse(any("Low contrast" in m for m in messages(source)))

    def test_large_text_gets_the_lower_threshold(self):
        grey = "#FF7A7A7A"  # 4.3:1 — fails normal, passes large
        normal = ('from pydrud import Text\n'
                  f'Text("hi", color="{grey}", style={{"bg": "#FFFFFFFF"}})\n')
        large = ('from pydrud import Text\n'
                 f'Text("hi", color="{grey}", '
                 'style={"bg": "#FFFFFFFF", "font": {"size": 24}})\n')
        self.assertTrue(any("Low contrast" in m for m in messages(normal)))
        self.assertFalse(any("Low contrast" in m for m in messages(large)))


# ── the analyzer touch-target lint ──────────────────────────────────────────


class TestTouchTargetLint(unittest.TestCase):

    def test_a_shrunken_icon_button_is_flagged(self):
        source = ('from pydrud import IconButton, Icons\n'
                  'IconButton(icon=Icons.SAVE, style={"width": 24, "height": 24})\n')
        found = messages(source)
        self.assertTrue(any("touch target" in m for m in found), found)

    def test_a_comfortable_button_is_clean(self):
        source = ('from pydrud import IconButton, Icons\n'
                  'IconButton(icon=Icons.SAVE, style={"width": 48, "height": 48})\n')
        self.assertEqual(messages(source), [])

    def test_a_dp_suffixed_size_is_understood(self):
        source = ('from pydrud import Button\n'
                  'Button("Go", style={"height": "32dp"})\n')
        self.assertTrue(any("touch target" in m for m in messages(source)))

    def test_a_shrunken_menu_trigger_is_flagged(self):
        source = ('from pydrud import PopupMenu\n'
                  'PopupMenu(["Open"], style={"width": 24, "height": 24})\n')
        found = messages(source)
        self.assertTrue(any("touch target" in m for m in found), found)

    def test_a_non_interactive_widget_is_not_flagged(self):
        source = ('from pydrud import Icon, Icons\n'
                  'Icon(Icons.SAVE, style={"width": 24, "height": 24})\n')
        self.assertEqual(messages(source), [])


# ── the generated Java contract ─────────────────────────────────────────────


class TestGeneratedJava(unittest.TestCase):

    def setUp(self):
        self.source = _java()

    def test_create_path_applies_the_label(self):
        self.assertIn("applySemantics(view, json);", self.source)

    def test_the_reuse_path_applies_the_label(self):
        # A snapshot rebuild reuses the view, so it must re-apply too.
        self.assertGreaterEqual(self.source.count("applySemantics(view, json);"),
                                2)

    def test_the_helper_sets_a_content_description(self):
        self.assertIn("view.setContentDescription(", self.source)
        self.assertIn("desc.isEmpty() ? null : desc", self.source)

    def test_the_update_path_handles_a_changed_label(self):
        self.assertIn('if (p.has("_semantics"))', self.source)

    def test_semantics_is_a_known_renderer_key(self):
        block = re.search(r"KNOWN_KEYS =.*?\.split\(\" \"\)\)\);",
                          self.source, re.S).group(0)
        known = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", block))
        self.assertIn("semantics", known)

    def test_it_clears_the_description_when_the_label_is_removed(self):
        body = re.search(r"private void applySemantics"
                         r"\(.*?\n    \}", self.source, re.S).group(0)
        self.assertIn("isNull", body)


if __name__ == "__main__":
    unittest.main()
