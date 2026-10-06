"""``PopupMenu`` / ``DropdownMenu`` — the anchored overflow menu (PYDRUD §15.2).

Python owns the entry list; the native side is a real
``android.widget.PopupMenu`` anchored to the trigger. The Java cannot run
here, so the last section pins the contract the generated
``MaterialViews``/``ViewFactory`` implements — including the choices that
make the menu stay in step with a rebuild: it is rebuilt from the node's
props on every tap, and an item change forces a ``recreateInPlace``.
"""

from __future__ import annotations

import os
import re
import unittest

from pydrud import (DropdownMenu, Icons, MenuDivider, MenuItem, PopupMenu,
                    PopupMenuButton, Text)
from pydrud.core.diff import TreeDiff
from pydrud.testing import AppTester

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "pydrud", "android", "templates", "android")


def _read(name: str) -> str:
    with open(os.path.join(TEMPLATES, name), encoding="utf-8") as handle:
        return handle.read()


class TestMenuItem(unittest.TestCase):

    def test_the_value_defaults_to_the_label(self):
        self.assertEqual(MenuItem("Rename").value, "Rename")

    def test_the_value_can_be_overridden(self):
        self.assertEqual(MenuItem("Rename", value="rename").value, "rename")

    def test_a_checked_item_is_checkable(self):
        item = MenuItem("Bold", checked=True)
        self.assertTrue(item.checkable)

    def test_a_plain_item_is_not_checkable(self):
        self.assertFalse(MenuItem("Open").checkable)

    def test_a_divider_serialises_as_a_divider_only(self):
        self.assertEqual(MenuDivider().to_dict(), {"divider": True})

    def test_a_disabled_item_is_serialised_as_false(self):
        self.assertEqual(MenuItem("Cut", enabled=False).to_dict()["enabled"], False)

    def test_a_danger_item_is_flagged(self):
        self.assertTrue(MenuItem("Delete", danger=True).to_dict()["danger"])

    def test_a_submenu_is_serialised_recursively(self):
        node = MenuItem("Move to", submenu=[MenuItem("Inbox"),
                                            MenuItem("Archive")]).to_dict()
        self.assertEqual([e["label"] for e in node["submenu"]],
                         ["Inbox", "Archive"])

    def test_a_plain_item_has_no_submenu_key(self):
        self.assertNotIn("submenu", MenuItem("Open").to_dict())

    def test_repr_names_a_divider(self):
        self.assertEqual(repr(MenuDivider()), "MenuDivider()")


class TestCoercion(unittest.TestCase):

    def test_a_bare_string_becomes_an_item(self):
        items = PopupMenu(["Open"]).items
        self.assertEqual(items[0].label, "Open")

    def test_a_tuple_becomes_a_labelled_icon_item(self):
        item = PopupMenu([("Share", Icons.SHARE)]).items[0]
        self.assertEqual((item.label, item.icon), ("Share", "share"))

    def test_a_dict_becomes_an_item(self):
        item = PopupMenu([{"label": "Bold", "checked": True}]).items[0]
        self.assertTrue(item.checked)

    def test_a_menu_item_is_passed_through(self):
        item = MenuItem("Open")
        self.assertIs(PopupMenu([item]).items[0], item)

    def test_an_empty_tuple_becomes_an_empty_item(self):
        self.assertEqual(PopupMenu([()]).items[0].label, "")


class TestSerialisation(unittest.TestCase):

    def test_the_type_and_events_are_sent(self):
        node = PopupMenu(["Open"], on_select=lambda e: None, key="m").to_dict()
        self.assertEqual(node["type"], "PopupMenu")
        self.assertEqual(node["events"], ["select"])

    def test_the_items_are_props(self):
        node = PopupMenu(["Open", "Save"]).to_dict()
        self.assertEqual([i["label"] for i in node["props"]["items"]],
                         ["Open", "Save"])

    def test_the_default_trigger_is_the_overflow_icon(self):
        props = PopupMenu(["Open"]).to_dict()["props"]
        self.assertEqual(props["icon"], "more_vert")
        self.assertNotIn("customTrigger", props)

    def test_a_label_makes_a_text_trigger(self):
        self.assertEqual(PopupMenu(["Open"], label="More").to_dict()
                         ["props"]["label"], "More")

    def test_a_custom_trigger_is_flagged_and_the_icon_dropped(self):
        props = PopupMenu(["Open"], trigger=Text("Menu")).to_dict()["props"]
        self.assertTrue(props["customTrigger"])
        self.assertNotIn("icon", props)

    def test_item_icons_are_on_by_default(self):
        self.assertNotIn("itemIcons", PopupMenu(["Open"]).to_dict()["props"])

    def test_item_icons_can_be_disabled(self):
        self.assertFalse(PopupMenu(["Open"], item_icons=False)
                         .to_dict()["props"]["itemIcons"])

    def test_add_appends_an_entry(self):
        menu = PopupMenu(["Open"])
        menu.add("Save", MenuItem("Delete"))
        self.assertEqual([i.label for i in menu.items], ["Open", "Save", "Delete"])

    def test_has_custom_trigger_reports_the_truth(self):
        self.assertFalse(PopupMenu(["Open"]).has_custom_trigger)
        self.assertTrue(PopupMenu(["Open"], trigger=Text("x")).has_custom_trigger)

    def test_a_custom_trigger_gets_a_stable_key(self):
        menu = PopupMenu(["Open"], key="m", trigger=Text("Menu"))
        self.assertEqual(menu.children[0].key, "m_trigger")


class TestAliases(unittest.TestCase):

    def test_dropdown_menu_is_the_same_widget(self):
        self.assertIs(DropdownMenu, PopupMenu)

    def test_popup_menu_button_is_the_same_widget(self):
        self.assertIs(PopupMenuButton, PopupMenu)


class TestHarness(unittest.TestCase):

    def test_it_renders_with_its_items(self):
        with AppTester(lambda page: page.add(
                PopupMenu(["Open", "Save"], key="m"))) as app:
            self.assertEqual(app.node("m").type, "PopupMenu")
            self.assertEqual(len(app.prop("m", "items")), 2)

    def test_it_renders_a_custom_trigger_child(self):
        with AppTester(lambda page: page.add(
                PopupMenu(["Open"], key="m", trigger=Text("Menu")))) as app:
            node = app.node("m")
            self.assertEqual(len(node.children), 1)
            self.assertTrue(app.prop("m", "customTrigger"))

    def test_a_selection_event_is_dispatched(self):
        seen: list = []

        def main(page):
            page.add(PopupMenu(["Open", "Save"], key="m", on_select=seen.append))

        with AppTester(main) as app:
            app.device.send_event("select", "m", {"index": 1, "value": "Save"})
            app.settle()

        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["index"], 1)
        self.assertEqual(seen[0]["value"], "Save")

    def test_a_selection_reaches_the_widget_control(self):
        seen: list = []

        def main(page):
            page.add(PopupMenu(["Open"], key="m", on_select=seen.append))

        with AppTester(main) as app:
            app.device.send_event("select", "m", {"index": 0, "value": "Open"})
            app.settle()

        self.assertEqual(seen[0].control.key, "m")


class TestDiffing(unittest.TestCase):

    def test_a_new_item_is_an_in_place_update(self):
        patches = TreeDiff.diff(PopupMenu(["Open"], key="m"),
                                PopupMenu(["Open", "Save"], key="m"))
        self.assertEqual([p.op for p in patches], ["update"], patches)
        self.assertEqual(len(patches[0].props["items"]), 2)

    def test_renaming_an_item_is_an_update(self):
        patches = TreeDiff.diff(PopupMenu(["Open"], key="m"),
                                PopupMenu(["Open file"], key="m"))
        self.assertEqual(patches[0].props["items"][0]["label"], "Open file")

    def test_adding_a_handler_is_an_events_update(self):
        patches = TreeDiff.diff(PopupMenu(["Open"], key="m"),
                                PopupMenu(["Open"], key="m",
                                          on_select=lambda e: None))
        self.assertEqual(patches[0].props["_events"], ["select"])


class TestGeneratedJava(unittest.TestCase):

    def setUp(self):
        self.material = _read("MaterialViews.java.j2")
        from tests import all_java_templates
        self.factory = all_java_templates()

    def test_the_material_class_handles_the_type(self):
        self.assertIn('case "PopupMenu":', self.material)

    def test_the_trigger_is_built_when_no_child_is_given(self):
        self.assertIn("createPopupMenu", self.material)
        self.assertIn('p.optBoolean("customTrigger", false)', self.material)

    def test_the_trigger_is_a_48dp_target(self):
        body = re.search(r"View createPopupMenu\(.*?\n    \}",
                         self.material, re.S).group(0)
        self.assertIn("touchTarget()", body)
        self.assertIn("more_vert", body)

    def test_the_menu_is_a_real_native_popup(self):
        self.assertIn("new android.widget.PopupMenu(vf.activity, anchor)",
                      self.factory)
        self.assertIn("menu.show();", self.factory)

    def test_a_selection_dispatches_index_and_value(self):
        body = re.search(r"void showPopupMenu\(.*?\n    \}",
                         self.factory, re.S).group(0)
        self.assertIn('d.put("index", item.getItemId());', body)
        self.assertIn('d.put("value",', body)
        self.assertIn('eventDispatcher.dispatch("select", key, d);', body)

    def test_it_is_bound_on_the_trigger(self):
        self.assertIn("bindPopupMenu", self.factory)
        self.assertIn("setOnClickListener(v -> {", self.factory)
        self.assertIn("showPopupMenu(v, json, key);", self.factory)

    def test_a_subscribed_click_still_fires(self):
        # An on_click handler must not be silently dropped by the menu branch.
        self.assertIn('if (events.contains("click")) vf.eventDispatcher.dispatch("click", key);',
                      self.factory)

    def test_submenus_are_native(self):
        self.assertIn("addSubMenu", self.factory)

    def test_a_submenu_icon_uses_the_submenu_overload(self):
        # SubMenu extends Menu, not MenuItem — the two are unrelated types,
        # so the icon has to be set through an overload or it will not compile.
        self.assertIn("void applyMenuIcon(android.view.SubMenu", self.factory)
        self.assertIn("void applyMenuIcon(android.view.MenuItem", self.factory)

    def test_the_menu_icon_uses_the_factorys_own_helper(self):
        # Inside ViewFactory the icon helper is `icon(...)`, not
        # `factory.icon(...)` — `factory` is MaterialViews' field. A real
        # javac caught this; javacheck cannot see framework symbols.
        body = re.search(r"void applyMenuIcon\(android.view.MenuItem"
                         r".*?\n    \}", self.factory, re.S).group(0)
        self.assertIn("setIcon(vf.icon(name, tint, vf.mStyler.dp(20)))", body)
        self.assertNotIn("factory.", body)

    def test_dividers_start_a_new_group(self):
        self.assertIn("setGroupDividerEnabled(true)", self.factory)

    def test_the_menu_reopens_even_without_a_handler(self):
        # bindEvents must not bail out before the PopupMenu branch.
        self.assertIn('!"PopupMenu".equals(json.optString("type", ""))',
                      self.factory)

    def test_its_keys_are_known_renderer_keys(self):
        block = re.search(r"KNOWN_KEYS =.*?\.split\(\" \"\)\)\);",
                          self.factory, re.S).group(0)
        known = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", block))
        for key in ("customTrigger", "itemIcons", "checkable", "danger",
                    "submenu"):
            self.assertIn(key, known)

    def test_its_props_are_all_read_natively(self):
        props = PopupMenu(["Open"], label="More")._serialise_props()
        for name in props:
            self.assertIn(f'"{name}"', self.material + self.factory,
                          f"prop {name!r} is serialised but never read")


if __name__ == "__main__":
    unittest.main()
