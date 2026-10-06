"""``PageView`` / ``Carousel`` — the snapping page container (PYDRUD §15.2).

Python owns the page list and the initial index; the native side is a
snapping RecyclerView of full-size pages. The Java cannot run here, so the
last section pins the contract the generated ``AdvancedViews``/``ViewFactory``
implements — including the choice that gives the pager structural-patch
support for free: its adapter extends the virtualised-list adapter.
"""

from __future__ import annotations

import os
import re
import unittest

from pydrud import Carousel, PageView, Text
from pydrud.core.diff import TreeDiff
from pydrud.testing import AppTester

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "pydrud", "android", "templates", "android")


def _read(name: str) -> str:
    with open(os.path.join(TEMPLATES, name), encoding="utf-8") as handle:
        return handle.read()


class TestSerialisation(unittest.TestCase):

    def test_the_type_and_children_are_sent(self):
        node = PageView([Text("a"), Text("b")]).to_dict()
        self.assertEqual(node["type"], "PageView")
        self.assertEqual(len(node["children"]), 2)

    def test_it_fills_both_axes_by_default(self):
        style = PageView().to_dict()["style"]
        self.assertEqual(style["width"], "match")
        self.assertEqual(style["height"], "match")

    def test_the_initial_page_is_a_prop(self):
        node = PageView(initial_page=2).to_dict()
        self.assertEqual(node["props"]["initialPage"], 2)

    def test_the_orientation_is_a_style_key(self):
        node = PageView(orientation="vertical").to_dict()
        self.assertEqual(node["style"]["orientation"], "vertical")

    def test_a_negative_initial_page_is_clamped(self):
        self.assertEqual(PageView(initial_page=-4).initial_page, 0)

    def test_the_initial_page_setter_clamps(self):
        widget = PageView()
        widget.initial_page = -1
        self.assertEqual(widget.initial_page, 0)
        widget.initial_page = 5
        self.assertEqual(widget.initial_page, 5)

    def test_peek_is_a_style_key(self):
        node = PageView(peek=16).to_dict()
        self.assertEqual(node["style"]["peek"], 16)

    def test_no_peek_means_no_style_key(self):
        self.assertNotIn("peek", PageView().to_dict()["style"])

    def test_add_appends_a_page(self):
        widget = PageView([Text("a")])
        widget.add(Text("b"))
        self.assertEqual(len(widget.children), 2)


class TestCarousel(unittest.TestCase):

    def test_it_renders_as_a_page_view(self):
        self.assertEqual(Carousel([Text("a")]).to_dict()["type"], "PageView")

    def test_it_peeks_by_default(self):
        self.assertEqual(Carousel().to_dict()["style"]["peek"], 24)

    def test_the_peek_can_be_overridden(self):
        self.assertEqual(Carousel(peek=8).to_dict()["style"]["peek"], 8)


class TestValidation(unittest.TestCase):

    def test_orientation_must_be_known(self):
        with self.assertRaises(ValueError):
            PageView(orientation="diagonal")

    def test_peek_must_not_be_negative(self):
        with self.assertRaises(ValueError):
            PageView(peek=-1)


class TestHarness(unittest.TestCase):

    def test_it_renders_with_its_pages(self):
        with AppTester(lambda page: page.add(
                PageView([Text("one"), Text("two")], key="p"))) as app:
            node = app.node("p")
            self.assertEqual(node.type, "PageView")
            self.assertEqual(len(node.children), 2)
            self.assertEqual(app.prop("p", "initialPage"), 0)

    def test_a_page_change_event_is_dispatched(self):
        seen: list = []

        def main(page):
            page.add(PageView([Text("a"), Text("b")], key="p",
                              on_change=seen.append))

        with AppTester(main) as app:
            app.device.send_event("change", "p", {"index": 1})
            app.settle()

        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["index"], 1)


class TestDiffing(unittest.TestCase):

    def test_a_page_change_is_an_in_place_update(self):
        patches = TreeDiff.diff(PageView([Text("a")], initial_page=0, key="p"),
                                PageView([Text("a")], initial_page=2, key="p"))
        self.assertEqual([p.op for p in patches], ["update"], patches)
        self.assertEqual(patches[0].props["initialPage"], 2)

    def test_adding_a_page_is_a_create(self):
        patches = TreeDiff.diff(PageView([Text("a", key="a")], key="p"),
                                PageView([Text("a", key="a"),
                                          Text("b", key="b")], key="p"))
        self.assertIn("create", [p.op for p in patches])


class TestGeneratedJava(unittest.TestCase):

    def setUp(self):
        self.advanced = _read("AdvancedViews.java.j2")
        self.factory = _read("ViewFactory.java.j2")

    def test_the_type_is_dispatched(self):
        self.assertIn('case "PageView":', self.factory)

    def test_the_pager_is_a_snapping_recycler_view(self):
        self.assertIn("PagerSnapHelper", self.advanced)
        self.assertIn("createPager", self.advanced)

    def test_the_adapter_extends_the_list_adapter(self):
        # This is what gives the pager structural-patch support for free.
        self.assertIn("class PagerAdapter extends ViewAdapter", self.advanced)

    def test_pages_fill_the_viewport(self):
        body = re.search(r"class PagerAdapter extends ViewAdapter"
                         r" \{(.*?)\n    \}", self.advanced, re.S).group(0)
        self.assertIn("ViewGroup.LayoutParams.MATCH_PARENT", body)
        self.assertIn("FrameLayout", body)

    def test_peek_disables_clip_to_padding(self):
        self.assertIn("setClipToPadding(false)", self.advanced)

    def test_a_settled_page_is_reported_once(self):
        self.assertIn("findFirstCompletelyVisibleItemPosition", self.advanced)
        self.assertIn('data.put("index", pos);', self.advanced)
        self.assertIn('events.dispatch("change", key, data);', self.advanced)

    def test_the_first_settle_does_not_echo(self):
        self.assertIn("private int last = initialPage;", self.advanced)

    def test_the_initial_page_is_applied(self):
        self.assertIn("scrollToPosition(initial)", self.factory)

    def test_the_update_path_handles_the_initial_page(self):
        self.assertIn('if (p.has("initialPage"))', self.factory)

    def test_it_fills_the_width_by_default(self):
        body = re.search(r"fillsWidthByDefault\(String type\) \{(.*?)\n    \}",
                         self.factory, re.S).group(0)
        self.assertIn('case "PageView":', body)

    def test_its_keys_are_known_renderer_keys(self):
        block = re.search(r"KNOWN_KEYS =.*?\.split\(\" \"\)\)\);",
                          self.factory, re.S).group(0)
        known = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", block))
        for key in ("initialPage", "peek"):
            self.assertIn(key, known)


if __name__ == "__main__":
    unittest.main()
