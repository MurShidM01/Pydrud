"""PSS must reach the screen — the stylesheet engine's contract with the UI.

A stylesheet can be *syntactically* perfect and still do nothing: the resolver
runs on the Python side, the widget tree is serialised, and the Android
renderer re-reads the style dict key by key. Anything the resolver emits that
the renderer does not read is a property the user writes, the analyser
accepts, and the device silently drops — the worst failure mode in the
styling pipeline, because nothing anywhere reports an error.

This module pins both halves of that contract:

* every style key the resolver can emit is one the native renderer knows, and
* every Material 3 colour role is reachable from a stylesheet as a ``$token``
  and ships in the theme payload the renderer receives.

It also holds the documented stylesheets to the same standard: a ``.pss``
example in the docs that no longer parses is a broken promise.
"""

from __future__ import annotations

import json
import pathlib
import re
import unittest

import jinja2

import pydrud as pd
from pydrud.core.styles import parse_pss, resolve_styles
from pydrud.core.styles.schema import (
    KEY_KIND,
    VALID_STYLE_KEYS,
    WEB_ONLY_STYLE_KEYS,
)

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "pydrud" / "android" / "templates" / "android"
DOCS = ROOT / "docs"

RENDER_CONTEXT = {
    "package": "com.example.app",
    "android_package": "com.example.app",
    "app_id": "com.example.app",
    "app_name": "Demo",
    "project_name": "Demo",
    "label": "Demo",
    "min_sdk": 24,
    "target_sdk": 34,
    "version_name": "2.1.5",
    "version_code": 21,
    "runtime": "chaquopy",
    "bridge_port": 8765,
    "python_version": "3.11",
    "pydrud_import": "pydrud",
    "deep_link_scheme": "demo",
    "theme_mode": "light",
    "permissions": [],
    "uses_cleartext": False,
    "splash": False,
    "icon": None,
    "entry_point": "app.py",
    "include_icons": True,
    "has_camera": False,
    "has_firebase": False,
}


def _render(name: str) -> str:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES)), keep_trailing_newline=True
    )
    return env.get_template(name).render(**RENDER_CONTEXT)


def _native_known_keys() -> set:
    """The keys ``ViewStyler`` will not report as unhandled."""
    block = re.search(
        r"KNOWN_KEYS =.*?split\(\" \"\)\)\);", _render("ViewStyler.java.j2"), re.S
    ).group(0)
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", block)) - {
        "KNOWN_KEYS", "new", "java", "util", "HashSet", "Arrays", "asList",
        "Set", "String", "split", "trim", "private", "static", "final",
    }


#: Plausible values per key kind, so the audit exercises real declarations.
_KEYWORD_VALUES = {
    "textAlign": "center", "alignment": "center", "visible": "true",
    "tooltip": "tip", "fit": "cover", "bgImage": "none", "position": "absolute",
    "mainAxis": "vertical", "crossAxisAlignment": "center", "scroll": "vertical",
    "variant": "filled", "icon": "home", "disabled": "false", "multiline": "true",
    "password": "true", "readOnly": "false", "keyboard": "text",
    "icon_brightness": "light", "circular": "true", "overflow": "hidden",
    "selectable": "false", "tristate": "false", "mainAxisAlignment": "center",
    "drawerSide": "start", "fabPosition": "end", "safeArea": "true",
    "resizeForKeyboard": "true", "role": "primary", "pill": "false",
    "ripple": "true", "transformOrigin": "center",
    "overflowX": "hidden", "overflowY": "any",
}

_COMPOSITE_VALUES = {
    "padding": "1", "margin": "1", "border": "1px solid #FF112233",
    "font": "16", "shadow": "0 2 8 #FF000000",
    "gradient": "linear #FF112233 #FF445566",
    "press": "scale(0.9)", "hover": "bg #FF334455", "focus": "bg #FF556677",
    "transition": "all 200ms ease",
}


def _value_for(key: str):
    if key in _KEYWORD_VALUES:
        return _KEYWORD_VALUES[key]
    kind = KEY_KIND.get(key, "any")
    if kind == "color":
        return "#FF112233"
    if kind == "number":
        return "8"
    if kind == "composite":
        return _COMPOSITE_VALUES.get(key, "1")
    return "rotate(10deg)"


def _sample_tree():
    return pd.Column(
        key="root",
        children=[
            pd.Text("hi", key="w", class_="card notice"),
            pd.Button("go", key="b", class_="btn"),
            pd.TextField(key="f"),
        ],
    )


class TestEveryEmittableKeyReachesTheRenderer(unittest.TestCase):
    """The core contract: PSS output ⊆ what the native renderer reads."""

    def test_every_key_pss_can_emit_is_known_to_the_renderer(self):
        keys = sorted(VALID_STYLE_KEYS - WEB_ONLY_STYLE_KEYS)
        declarations = " ".join(
            f"{key}: "
            f"{json.dumps(value) if isinstance(value, dict) else value};"
            for key, value in ((k, _value_for(k)) for k in keys)
        )
        resolved, _ = resolve_styles(
            parse_pss("#w { " + declarations + " }"), _sample_tree()
        )
        emitted = set()
        for style in resolved.values():
            emitted |= set(style)

        unknown = sorted(key for key in emitted if key not in _native_known_keys())
        self.assertEqual(
            [],
            unknown,
            "these keys reach the device but no factory reads them, so the "
            "renderer logs 'unhandled style key' and the property silently "
            "does nothing: " + ", ".join(unknown),
        )
        # A sanity floor: the audit must actually be exercising the vocabulary.
        self.assertGreater(len(emitted), 40)

    def test_web_only_keys_never_reach_the_renderer(self):
        """A web declaration is dropped, not forwarded."""
        resolved, _ = resolve_styles(
            parse_pss("#w { display: flex; cursor: pointer; float: left; }"),
            _sample_tree(),
        )
        emitted = set(resolved.get("w", {}))
        for key in ("display", "cursor", "float"):
            self.assertNotIn(key, emitted, f"{key} is web-only and must be dropped")

    def test_resolved_style_survives_serialisation(self):
        """What the resolver produced is what the wire carries."""
        widget = pd.Text("hi", key="w")
        root = pd.Column(key="root", children=[widget])
        resolved, _ = resolve_styles(
            parse_pss("#w { bg: #FF123456; font-size: 20; padding-top: 4; }"), root
        )
        widget._resolved_style = dict(resolved.get("w", {}))
        style = widget.to_dict()["style"]
        self.assertEqual(style["bg"], "#FF123456")
        self.assertEqual(style["font"]["size"], 20)
        self.assertEqual(style["padding"]["top"], 4)
        json.dumps(style)  # the frame must be JSON-serialisable


class TestCascadeOverWidgetDefaults(unittest.TestCase):
    """A stylesheet must be able to restyle a component.

    Widgets write their own defaults into ``style`` as they initialise — a
    ``Card`` pulls its surface colour out of the theme, a ``Column`` sets its
    ``mainAxis``, a ``SizedBox`` records its size. Those defaults used to be
    indistinguishable from values the caller passed, so they *were* the inline
    layer, and PSS could not touch them: ``Card { bg: … }`` or
    ``Column { spacing: 24 }`` resolved cleanly, serialised, and then lost to
    the widget's own default with no warning. 22 widget types were affected,
    including every layout container.

    The documented contract is the three-layer one: widget defaults are weakest,
    PSS sits in the middle, and the caller's own values — a keyword argument or
    ``style={...}`` — win.
    """

    PSS = (
        "Column { spacing: 24; }\n"
        "Card { bg: #FF112233; borderRadius: 2; }\n"
        "Divider { color: #FF445566; thickness: 3; }\n"
        "SizedBox { height: 99; width: 77; }\n"
    )

    def _render(self, main):
        app = pd.App(target=main, dev_server=False)
        app.add_stylesheet_source(self.PSS)
        self.addCleanup(app.stop)
        return app.build().to_dict()

    @staticmethod
    def _style(tree, key):
        stack = [tree]
        while stack:
            node = stack.pop()
            if node.get("key") == key:
                return node.get("style") or {}
            stack.extend(node.get("children") or [])
        raise AssertionError(f"{key} missing from the tree")

    def _tree(self):
        return self._render(lambda page: page.add(pd.Column(key="col", children=[
            pd.Card(key="card", children=[pd.Text("hi", key="t")]),
            pd.Divider(key="div"),
            pd.SizedBox(key="box"),
        ])))

    def test_pss_overrides_widget_defaults(self):
        tree = self._tree()
        self.assertEqual(self._style(tree, "col")["spacing"], 24)
        card = self._style(tree, "card")
        self.assertEqual(card["bg"], "#FF112233")
        self.assertEqual(card["borderRadius"], 2)
        self.assertEqual(self._style(tree, "div")["color"], "#FF445566")
        self.assertEqual(self._style(tree, "div")["thickness"], 3)
        self.assertEqual(self._style(tree, "box")["height"], 99)
        self.assertEqual(self._style(tree, "box")["width"], 77)

    def test_keyword_arguments_still_beat_the_stylesheet(self):
        tree = self._render(lambda page: page.add(pd.Column(key="col", spacing=4, children=[
            pd.Card(key="card", bg="#FF00FF00", border_radius=1),
            pd.Divider(key="div", color="#FF0000FF", thickness=9),
            pd.SizedBox(key="box", height=10),
        ])))
        self.assertEqual(self._style(tree, "col")["spacing"], 4)
        self.assertEqual(self._style(tree, "card")["bg"], "#FF00FF00")
        self.assertEqual(self._style(tree, "card")["borderRadius"], 1)
        self.assertEqual(self._style(tree, "div")["color"], "#FF0000FF")
        self.assertEqual(self._style(tree, "div")["thickness"], 9)
        self.assertEqual(self._style(tree, "box")["height"], 10)

    def test_inline_style_still_beats_the_stylesheet(self):
        tree = self._render(lambda page: page.add(
            pd.Column(key="col", style={"spacing": 3}, children=[
                pd.Card(key="card", style={"bg": "#FFABCDEF"}),
            ])))
        self.assertEqual(self._style(tree, "col")["spacing"], 3)
        self.assertEqual(self._style(tree, "card")["bg"], "#FFABCDEF")

    def test_inline_style_is_not_clobbered_by_the_constructor(self):
        """The widget's own default must not overwrite what the caller passed.

        ``Column`` assigned ``style["spacing"]`` unconditionally, so
        ``Column(style={"spacing": 3})`` reached the renderer as 0 before the
        cascade was fixed.
        """
        from pydrud.widgets.theme import Theme

        Theme.seed("#6366F1")
        column = pd.Column(key="c", style={"spacing": 3})
        self.assertEqual(column.style["spacing"], 3)
        card = pd.Card(key="k", style={"bg": "#FF010203", "elevation": 7})
        self.assertEqual(card.style["bg"], "#FF010203")
        self.assertEqual(card.style["elevation"], 7)

    def test_a_copied_widget_keeps_the_same_split(self):
        import copy

        card = pd.Card(key="card", bg="#FF010203")
        clone = copy.deepcopy(card)
        self.assertEqual(card._split_style()[0], clone._split_style()[0])
        self.assertEqual(clone._split_style()[1]["bg"], "#FF010203")

    def test_an_unknown_split_treats_every_key_as_caller_supplied(self):
        """Without the metaclass's record nothing is demoted.

        That is the pre-existing behaviour, so a widget reaching this path —
        one unpickled, or hand-built in a test — cannot lose a value to a
        stylesheet it never knew about.
        """
        card = pd.Card(key="card")
        card._explicit_style_keys = None
        derived, inline = card._split_style()
        self.assertEqual(derived, {})
        self.assertEqual(inline, dict(card.style))

    def test_no_pss_rule_leaves_the_widget_defaults_intact(self):
        from pydrud.widgets.theme import Theme

        Theme.seed("#6366F1")
        app = pd.App(target=lambda page: page.add(
            pd.Card(key="card", children=[pd.Text("hi")])), dev_server=False)
        self.addCleanup(app.stop)
        style = self._style(app.build().to_dict(), "card")
        self.assertEqual(style["bg"], Theme.surface)
        self.assertEqual(style["borderRadius"], 12)


class TestStateRulesHaveConsumers(unittest.TestCase):
    """``:hover`` / ``:focus`` / ``:active`` must draw something on device."""

    @classmethod
    def setUpClass(cls):
        cls.styler = _render("ViewStyler.java.j2")
        cls.theme = _render("PydrudTheme.java.j2")

    def test_pseudo_classes_become_renderer_sub_specs(self):
        resolved, _ = resolve_styles(
            parse_pss(
                "#w { bg: #FFFFFFFF; }\n"
                "#w:hover { bg: #FFEEEEEE; }\n"
                "#w:focus { bg: #FFDDDDDD; }\n"
                "#w:active { scale: 0.92; }\n"
            ),
            _sample_tree(),
        )
        style = resolved["w"]
        self.assertIn("hover", style)
        self.assertIn("focus", style)
        self.assertIn("press", style)
        self.assertEqual(style["hover"]["bg"], "#FFEEEEEE")

    def test_every_state_sub_spec_has_a_native_consumer(self):
        for state in ("press", "hover", "focus"):
            self.assertIn(
                f'optJSONObject("{state}")',
                self.styler,
                f"nothing on the device reads the '{state}' sub-spec",
            )

    def test_hover_and_focus_install_platform_listeners(self):
        self.assertIn("setOnHoverListener", self.styler)
        self.assertIn("setOnFocusChangeListener", self.styler)
        self.assertIn("ACTION_HOVER_ENTER", self.styler)
        self.assertIn("ACTION_HOVER_EXIT", self.styler)
        self.assertIn("applyStateSpecs", self.styler)

    def test_leaving_a_state_restores_the_base_style(self):
        self.assertIn("stateBaseStyles", self.styler)
        self.assertIn("restoreBaseStyle", self.styler)

    def test_restyling_does_not_stack_listeners(self):
        """A tree patch re-applies the style; the listeners must not double up."""
        self.assertIn("stateWired", self.styler)
        self.assertIn("applyingState", self.styler)

    def test_state_layers_use_the_m3_opacities(self):
        """GAP #10 — the state-layer tokens were published but never consumed."""
        for token in ("stateHover", "stateFocus"):
            self.assertIn(
                f"PydrudTheme.{token}", self.styler,
                f"{token} is defined but nothing draws it",
            )

    def test_a_colour_only_state_rule_is_a_state_layer(self):
        self.assertIn("PydrudTheme.blend", self.styler)
        self.assertIn("toHex", self.theme, "state layers need a hex formatter")
        self.assertIn("toHex", self.styler)

    def test_transform_origin_moves_the_pivot(self):
        self.assertIn("applyTransformOrigin", self.styler)
        self.assertIn("setPivotX", self.styler)
        self.assertIn("setPivotY", self.styler)
        self.assertIn("originAxis", self.styler)


class TestMaterial3TokensAreReachable(unittest.TestCase):
    """A stylesheet must be writable entirely in M3 roles."""

    @classmethod
    def setUpClass(cls):
        from pydrud.core.styles.resolver import _theme_tokens
        from pydrud.widgets.theme.colors import ColorScheme
        from pydrud.widgets.theme.hct import DynamicScheme

        cls.roles = tuple(ColorScheme.ROLES)
        cls.scheme_roles = set(DynamicScheme.from_seed(0xFF6750A4).to_dict()) - {"dark"}
        cls.tokens = _theme_tokens()

    def test_the_scheme_defines_exactly_the_roles_the_scheme_advertises(self):
        """No role may exist in the generated scheme but be unreachable."""
        missing = sorted(self.scheme_roles - set(self.roles))
        self.assertEqual(
            [],
            missing,
            "these roles are generated but absent from ColorScheme.ROLES, so "
            "they never reach the theme payload or a $token: " + ", ".join(missing),
        )

    def test_every_role_is_a_token_in_both_spellings(self):
        for role in self.roles:
            with self.subTest(role=role):
                self.assertIn(role, self.tokens)
                self.assertIn(f"md_sys_color_{role}", self.tokens)

    def test_fixed_accents_are_tone_locked(self):
        """M3 pins the fixed roles to the same tones in light and dark."""
        from pydrud.widgets.theme.hct import DynamicScheme

        light = DynamicScheme.from_seed(0xFF6750A4).to_dict()
        dark = DynamicScheme.from_seed(0xFF6750A4, dark=True).to_dict()
        for role in (
            "primary_fixed", "primary_fixed_dim", "on_primary_fixed",
            "on_primary_fixed_variant", "secondary_fixed", "secondary_fixed_dim",
            "on_secondary_fixed", "on_secondary_fixed_variant", "tertiary_fixed",
            "tertiary_fixed_dim", "on_tertiary_fixed", "on_tertiary_fixed_variant",
        ):
            with self.subTest(role=role):
                self.assertEqual(light[role], dark[role])

    def test_every_role_ships_in_the_theme_payload(self):
        from pydrud.widgets.theme import Theme

        payload = Theme.payload()
        missing = sorted(
            role for role in self.roles
            if not (isinstance(payload.get(role), str) and payload[role])
        )
        self.assertEqual(
            [], missing, f"roles missing from the renderer payload: {missing}"
        )

    def test_token_references_resolve_inside_a_rule(self):
        from pydrud.widgets.theme import Theme

        Theme.seed("#6750A4")
        resolved, warnings = resolve_styles(
            parse_pss(
                "#w {\n"
                "  bg: $surface_container_high;\n"
                "  color: $md_sys_color_on_surface;\n"
                "  border-color: $outline_variant;\n"
                "  padding-top: $gutter;\n"
                "}\n"
            ),
            _sample_tree(),
        )
        style = resolved["w"]
        self.assertRegex(style["bg"], r"^#[0-9A-Fa-f]{6,8}$")
        self.assertRegex(style["font"]["color"], r"^#[0-9A-Fa-f]{6,8}$")
        self.assertRegex(style["border"]["color"], r"^#[0-9A-Fa-f]{6,8}$")
        # Design tokens resolve too, not just colours.
        self.assertEqual(style["padding"]["top"], 16)
        self.assertEqual([], warnings)

    def test_an_unknown_token_is_reported_not_silently_ignored(self):
        _, warnings = resolve_styles(
            parse_pss("#w { bg: $no_such_token_anywhere; }"), _sample_tree()
        )
        self.assertTrue(
            any("no_such_token_anywhere" in w for w in warnings),
            f"an unresolved $token must warn; got {warnings}",
        )

    def test_media_queries_and_variables_still_resolve(self):
        resolved, warnings = resolve_styles(
            parse_pss(
                ":root { --brand: #FF00AA88; }\n"
                "#w { bg: var(--brand); }\n"
                "@media (min-width: 600px) { #w { color: $on_surface; } }\n"
            ),
            _sample_tree(),
        )
        self.assertEqual(resolved["w"]["bg"], "#FF00AA88")
        self.assertEqual([], warnings)


class TestDocumentedStylesheetsWork(unittest.TestCase):
    """Every ``pss`` example in the docs must parse and resolve."""

    def test_documented_stylesheets_parse_and_resolve(self):
        blocks = []
        for path in sorted(DOCS.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            for number, block in enumerate(
                re.findall(r"```pss\n(.*?)```", text, re.S), start=1
            ):
                blocks.append((f"{path.name} block {number}", block))
        self.assertGreater(blocks, [], "no pss examples found to verify")

        for label, block in blocks:
            with self.subTest(block=label):
                sheet = parse_pss(block)
                errors = [
                    d for d in getattr(sheet, "diagnostics", [])
                    if str(getattr(d, "severity", "")).lower() in ("error", "warning")
                ]
                self.assertEqual([], errors, f"{label} has diagnostics")
                _, warnings = resolve_styles(sheet, _sample_tree())
                self.assertEqual([], warnings, f"{label} does not resolve cleanly")


if __name__ == "__main__":
    unittest.main()
