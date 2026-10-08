"""
The Python API and the generated Java runtime must agree.

Two silent-failure modes used to slip through every other test:

* a Python service sends a command no Java class handles — the
  :class:`~pydrud.core.results.Result` never settles and the app hangs;
* the Java side emits an event ``App._handle_event`` ignores — the feature
  looks wired up but nothing happens.

Both are structural, so they can be checked statically.
"""

from __future__ import annotations

import os
import re
import unittest

from pydrud.services.native import UNIMPLEMENTED_COMMANDS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "pydrud", "android", "templates", "android")

#: Python modules that talk to the bridge.
SENDERS = [
    os.path.join("pydrud", "runtime", "app.py"),
    os.path.join("pydrud", "runtime", "page.py"),
    os.path.join("pydrud", "runtime", "_bridge.py"),
    os.path.join("pydrud", "services", "native", "__init__.py"),
    os.path.join("pydrud", "services", "native", "_base.py"),
    os.path.join("pydrud", "services", "native", "dialogs.py"),
    os.path.join("pydrud", "services", "native", "storage.py"),
    os.path.join("pydrud", "services", "native", "system.py"),
    os.path.join("pydrud", "services", "native", "secure.py"),
    os.path.join("pydrud", "services", "native", "background.py"),
    os.path.join("pydrud", "services", "native", "hardware.py"),
    os.path.join("pydrud", "runtime", "navigation.py"),
    os.path.join("pydrud", "data", "database.py"),
    os.path.join("pydrud", "commands", "packages.py"),
]

#: Commands the bridge answers structurally rather than by name.
INTERNAL = {"render", "full_render", "patch", "theme", "job_result"}


def read(path: str) -> str:
    with open(os.path.join(ROOT, path), encoding="utf-8") as handle:
        return handle.read()


def java_source() -> str:
    return "".join(
        read(os.path.join("pydrud", "android", "templates", "android", name))
        for name in sorted(os.listdir(TEMPLATES)) if name.endswith(".java.j2")
    )


def python_commands() -> set:
    pattern = re.compile(
        r'(?:_invoke|_send|invoke|encode_command)\(\s*"([a-z][a-z0-9_]*)"')
    found: set = set()
    for module in SENDERS:
        found |= set(pattern.findall(read(module)))
    return found - INTERNAL


class TestNativeCommandCoverage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.java = java_source()
        cls.commands = python_commands()

    def test_commands_are_handled_or_declared_unimplemented(self):
        unhandled = {cmd for cmd in self.commands
                     if f'"{cmd}"' not in self.java}
        surprises = sorted(unhandled - UNIMPLEMENTED_COMMANDS)
        self.assertEqual(
            [], surprises,
            "these Python commands reach no Java handler — implement them or "
            "add them to UNIMPLEMENTED_COMMANDS: " + ", ".join(surprises))

    def test_unimplemented_list_has_no_stale_entries(self):
        """Once a command is implemented natively, drop it from the list."""
        stale = sorted(cmd for cmd in UNIMPLEMENTED_COMMANDS
                       if f'"{cmd}"' in self.java)
        self.assertEqual([], stale,
                         "now handled in Java, remove from "
                         "UNIMPLEMENTED_COMMANDS: " + ", ".join(stale))

    def test_unimplemented_commands_are_all_reachable_from_python(self):
        orphans = sorted(UNIMPLEMENTED_COMMANDS - self.commands)
        self.assertEqual([], orphans,
                         "listed but no longer sent by any Python API: "
                         + ", ".join(orphans))

    def test_unknown_commands_get_an_error_reply(self):
        """A command nobody handles must fail the pending Result."""
        bridge = read(os.path.join(
            "pydrud", "android", "templates", "android",
            "BridgeService.java.j2"))
        self.assertIn("replyUnsupported", bridge)
        self.assertIn("unsupported native command", bridge)


class TestNativeEventCoverage(unittest.TestCase):

    def test_every_native_event_is_handled_in_python(self):
        java = java_source()
        events = set(re.findall(r'sendEvent\(\s*"([a-z_]+)"', java))
        main = read(os.path.join("pydrud", "runtime", "app.py"))
        missing = sorted(e for e in events if f'"{e}"' not in main)
        self.assertEqual(
            [], missing,
            "native events with no handler in App._handle_event: "
            + ", ".join(missing))


class TestWidgetCoverage(unittest.TestCase):

    def test_every_widget_type_is_rendered_natively(self):
        import inspect

        java = "".join(
            read(os.path.join("pydrud", "android", "templates", "android", n))
            for n in sorted(os.listdir(TEMPLATES)) if n.endswith(".j2"))
        types = set()
        for module in ("basic", "layout", "material", "advanced", "forms"):
            mod = __import__(f"pydrud.widgets.{module}", fromlist=["x"])
            for _name, obj in vars(mod).items():
                widget_type = getattr(obj, "_widget_type", None)
                if (inspect.isclass(obj) and isinstance(widget_type, str)
                        and widget_type != "Widget"):
                    types.add(widget_type)
        missing = sorted(t for t in types if f'"{t}"' not in java)
        self.assertEqual([], missing,
                         "widgets with no native renderer: " + ", ".join(missing))


class TestTransformStyleCoverage(unittest.TestCase):
    """Transform keys must be honoured on the patch path, not just on create.

    ``applyTransforms`` runs only when a view is first built, so anything it
    handles that the patch path (``applyStyle``) does not would silently stop
    updating after the first frame.
    """

    def test_apply_style_reapplies_every_transform_key(self):
        from tests import all_java_templates

        body = re.search(r"void applyStyle\(View view, JSONObject s\) \{(.*?)\n    \}",
                         all_java_templates(), re.S).group(1)
        for key in ("opacity", "rotate", "scale", "blur"):
            self.assertIn(f's.has("{key}")', body,
                          f"applyStyle must re-apply {key} on a patch")


class TestTextViewRestyleStability(unittest.TestCase):
    """A re-styled TextView must not re-layout when nothing actually changed.

    ``applyStyle`` runs on every style patch, and an animated widget is
    patched on every frame. Applying both the derived *and* the explicit
    letter-spacing / line-height left the two disagreeing on every call, so
    the TextView nulled its layout and re-measured continuously — and a
    single-line reading (the Heartbeat number) flashed a stale glyph on the
    device. Each property is now applied once, and only on a real change.
    """

    def test_tracking_and_leading_are_applied_once_and_guarded(self):
        from tests import all_java_templates

        block = re.search(
            r"// Font — real weights \(API 28\+\), tuned tracking and line height\."
            r"(.*?)// Text alignment",
            all_java_templates(), re.S).group(1)
        self.assertEqual(block.count("setLetterSpacing("), 1,
                         "letter spacing must be applied once, not twice")
        self.assertEqual(block.count("setLineSpacing("), 1,
                         "line spacing must be applied once, not twice")
        self.assertIn("tv.getLetterSpacing() != tracking", block,
                      "an unchanged tracking value must not invalidate the layout")
        self.assertIn("tv.getLineSpacingMultiplier() != leading", block,
                      "an unchanged leading value must not invalidate the layout")


class TestBlurStyleCoverage(unittest.TestCase):
    """``blur`` is declared in the Python schema, so the renderer must honour it.

    The key is inert if the native side ignores it — the exact silent-failure
    this module exists to catch — so pin the implementation to the vocabulary.
    """

    def test_blur_is_declared_and_implemented_natively(self):
        from pydrud.core.styles.schema import KEY_KIND, VALID_STYLE_KEYS
        from tests import all_java_templates

        self.assertIn("blur", VALID_STYLE_KEYS)
        self.assertEqual(KEY_KIND["blur"], "number")

        java = all_java_templates()
        self.assertIn("void applyBlur(View view, JSONObject s)", java)
        self.assertIn("RenderEffect.createBlurEffect", java)
        self.assertIn("applyBlur(view, s)", java,
                      "applyStyle must route the blur key to applyBlur()")

    def test_blur_needs_a_hardware_layer_and_warns_before_api_31(self):
        from tests import all_java_templates

        body = re.search(r"void applyBlur\(.*?\n    \}",
                         all_java_templates(), re.S).group(0)
        self.assertIn("SDK_INT >= 31", body)
        self.assertIn("LAYER_TYPE_HARDWARE", body)
        self.assertIn("Log.w", body, "older devices must be told once")


class TestReusableViewRegistration(unittest.TestCase):
    """A reused view must be re-registered in ``viewMap``.

    ``buildTree()`` clears ``viewMap`` before rebuilding the tree, and
    ``recreateInPlace()`` drops a key through ``removeViewTree()``. The
    reusable fast path in ``createView`` returns the existing native view
    instead of building a new one, so if it did not put the view *back* the
    widget would still render but be invisible to every later patch. That is
    exactly the ``update: unknown key`` flood a ``Canvas`` — the only
    reusable widget in the starter — produced after the second snapshot.
    """

    def test_reusable_branch_reregisters_the_view(self):
        from tests import all_java_templates

        body = re.search(
            r"if \(reusable != null && reusable\.type\.equals\(type\).*?"
            r"return view;",
            all_java_templates(), re.S).group(0)
        self.assertIn("vf.viewMap.put(key, view)", body,
                      "a reused view must go back into viewMap")
        self.assertIn("vf.elementMap.put(key,", body,
                      "the element index must survive a rebuild too")


class TestFabFeedbackOwnership(unittest.TestCase):
    """A FAB's touch feedback belongs to ``styleFab``.

    ``createView`` styles a ``_fab`` node with the design's circular ripple
    and press-and-shrink. ``bindEvents`` then runs the *generic*
    ``addTouchFeedback``, whose rounded-rect path would replace that
    background — so the generic path has to step aside for a FAB.
    """

    def test_generic_touch_feedback_skips_a_fab(self):
        from tests import all_java_templates

        body = re.search(
            r"void addTouchFeedback\(View view, JSONObject json\) \{.*?"
            r"if \(view instanceof Button",
            all_java_templates(), re.S).group(0)
        self.assertIn('vf.props(json).optBoolean("_fab", false)', body,
                      "the generic ripple must not override styleFab")

    def test_active_scale_reaches_a_material_button(self):
        """A `:active` scale must not be swallowed by the Button early-return.

        Material Buttons draw their own ripple, so the generic path steps
        aside — but the stylesheet's explicit press scale still applies.
        """
        from tests import all_java_templates

        java = all_java_templates()
        block = re.search(
            r"if \(view instanceof Button \|\| view instanceof CompoundButton"
            r".*?return;", java, re.S).group(0)
        self.assertIn("pressScale > 0f", block,
                      "a Material button drops its `:active` scale")
        self.assertIn("pressFeedback(view, pressScale", block)


class TestPreviewParity(unittest.TestCase):
    """`tools/preview_ui.py` must agree with the renderer about layout.

    The previewer exists to show what the device will draw; when its
    fill-width list drifts from ``ViewFactory.fillsWidthByDefault`` it
    quietly lies about every screen.
    """

    #: Types the renderer stretches through a dedicated branch rather than
    #: the switch (they fill both axes).
    SPECIAL = {"Stack", "Center"}

    def test_fill_width_lists_match(self):
        from tests import all_java_templates
        java = all_java_templates()
        body = re.search(
            r"fillsWidthByDefault\(String type\) \{(.*?)\n    \}",
            java, re.S)
        self.assertIsNotNone(body, "fillsWidthByDefault() not found")
        native = set(re.findall(r'case "(\w+)"', body.group(1)))

        preview = read(os.path.join("tools", "preview_ui.py"))
        listing = re.search(r"FILL_BY_DEFAULT = \{(.*?)\}", preview, re.S)
        self.assertIsNotNone(listing, "FILL_BY_DEFAULT not found")
        previewed = set(re.findall(r'"(\w+)"', listing.group(1)))

        self.assertEqual(set(), native - previewed,
                         "renderer stretches types the previewer does not")
        self.assertEqual(set(), previewed - native - self.SPECIAL,
                         "previewer stretches types the renderer does not")


class TestDeclarativeAnimationCoverage(unittest.TestCase):
    """A PSS ``animation``/``transition``/``:active`` rule must reach native code.

    The resolver emits a `keyframes` timeline, a `transition` list and a
    `press` sub-spec; if the renderer ignores any of them the feature is
    silently inert — the failure this module exists to catch.
    """

    def test_keyframes_playback_is_implemented(self):
        from tests import all_java_templates

        java = all_java_templates()
        self.assertIn("void applyAnimation(View view, JSONObject style)", java)
        self.assertIn("void applyKeyframe(View view, JSONArray frames, float t)", java)
        self.assertIn('optJSONArray("keyframes")', java)
        self.assertIn("android.animation.ValueAnimator.ofFloat(0f, 1f)", java)
        self.assertIn("ValueAnimator.INFINITE", java,
                      "an infinite CSS iteration count must repeat")

    def test_keyframe_loop_starts_on_create_and_update_and_stops_on_delete(self):
        from tests import all_java_templates

        java = all_java_templates()
        self.assertIn("vf.mAnimator.applyAnimation(view, style)", java,
                      "a newly created view must start its loop")
        self.assertIn("vf.mAnimator.applyAnimation(v, merged)", java,
                      "a patched view must restart its loop")
        self.assertIn("vf.mAnimator.stopAnimation(old)", java,
                      "a removed view must stop its loop")

    def test_interpolator_understands_the_css_curves(self):
        from tests import all_java_templates

        body = re.search(r"android.view.animation.Interpolator interpolator\(.*?\n    \}",
                         all_java_templates(), re.S).group(0)
        for curve in ('"ease"', '"ease_in"', '"ease_out"', '"ease_in_out"'):
            self.assertIn(curve, body, f"the CSS {curve} timing must be mapped")
        self.assertIn("cubic-bezier(", body)
        self.assertIn("PathInterpolator", all_java_templates())

    def test_transition_spec_tweens_a_property_change(self):
        from tests import all_java_templates

        java = all_java_templates()
        self.assertIn("JSONObject transitionFor(JSONObject style, JSONObject changed)",
                      java)
        self.assertIn('optJSONArray("transition")', java)
        self.assertIn("animateBackground", java,
                      "a `transition: background` must tween the fill")

    def test_active_press_spec_is_read_by_the_feedback_paths(self):
        from tests import all_java_templates

        java = all_java_templates()
        self.assertIn('optJSONObject("press")', java)
        self.assertIn("pressScale", java)

    def test_press_hover_focus_are_declared_in_the_schema(self):
        from pydrud.core.styles.schema import KEY_KIND, VALID_STYLE_KEYS

        for key in ("press", "hover", "focus", "transition"):
            self.assertIn(key, VALID_STYLE_KEYS)
        self.assertEqual(KEY_KIND["press"], "composite")


if __name__ == "__main__":
    unittest.main()
