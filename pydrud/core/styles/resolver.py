"""Platform-neutral PSS selector matching and style resolution.

Renderer-specific facts are supplied as optional :class:`RendererProfile`
data. The core resolver never imports a platform adapter or assumes a native
renderer; it only applies selector semantics and returns style dictionaries.

The resolver is where the CSS *authoring* surface becomes concrete:

* ``$token`` references resolve against the live :class:`Theme`/``Tokens``.
* ``var(--x)`` custom properties resolve against an inherited environment.
* ``:active`` and friends become renderer press/hover sub-specs.
* ``@media`` conditions are evaluated against the live window.
* ``clamp()``/``calc()``/``env()`` and viewport units are evaluated.
* CSS long-hands are folded into Pydrud composites (:mod:`.fold`).
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Number
import re
from typing import Iterable, Optional

from pydrud.core.styles.fold import finalize_style
from pydrud.core.styles.parser import (
    CompoundSelector,
    DeclarationBlock,
    MediaCondition,
    PseudoClass,
    Selector,
    StyleSheet,
)
from pydrud.core.styles.schema import KEY_KIND
from pydrud.core.styles.values import ValueContext, evaluate
from pydrud.widgets.base import Widget


@dataclass(frozen=True)
class RendererProfile:
    """Data-only description of optional renderer style behavior."""

    #: Widget types whose renderer-owned background may override ``bg``.
    background_owners: tuple[str, ...] = ()
    #: Property pairs with renderer-specific collisions.
    conflict_pairs: tuple[tuple[str, str], ...] = ()
    #: Style keys understood by this renderer, or ``None`` when unspecified.
    style_keys: frozenset[str] | None = None
    #: Widget types understood by this renderer, or ``None`` when unknown.
    widget_types: frozenset[str] | None = None


#: Transient interaction pseudo-classes → the style sub-spec the renderer
#: applies on touch-down / hover / focus. Their rules are captured whether or
#: not the widget is currently in that state, because the renderer drives the
#: timing.
_STATE_PSEUDOS = {
    ":active": "press",
    ":hover": "hover",
    ":focus": "focus",
}

#: Transient states always capture their rule as a sub-spec.
_TRANSIENT_STATES = frozenset({":active", ":hover", ":focus"})

#: Persistent states match against what the widget reports.
_PERSISTENT_STATES = frozenset({
    ":disabled", ":checked", ":selected", ":enabled",
    ":focus-within", ":focus-visible",
})


def _specificity(selector: Selector) -> tuple[int, int, int, int]:
    """Return CSS-like specificity (inline, ids, classes, widget types).

    Pseudo-classes count in the class column; pseudo-elements in the type
    column, as in CSS.
    """
    ids = sum(comp.id is not None for comp in selector.compounds)
    classes = 0
    types = 0
    for comp in selector.compounds:
        classes += len(comp.classes)
        for pseudo in comp.pseudos:
            if pseudo.is_element:
                types += 1
            else:
                classes += 1
        if comp.widget_type is not None:
            types += 1
    return (0, ids, classes, types)


def _widget_classes(widget: Widget) -> set[str]:
    """Get classes from the Python-only ``class_`` API.

    Read historical ``class_<name>`` markers too, so code that used the early
    PSS prototype still matches. Those markers are never serialized.
    """
    names = set(getattr(widget, "class_", ()) or ())
    names.update(
        key[len("class_"):]
        for key in widget.style
        if isinstance(key, str) and key.startswith("class_")
    )
    return names


def _widget_states(widget: Widget) -> set[str]:
    """The interaction states a widget currently reports."""
    states = set(getattr(widget, "_pseudo_states", ()) or ())
    state = widget.style.get("state")
    if isinstance(state, str):
        states.update(part for part in state.split() if part)
    props = getattr(widget, "props", None)
    if isinstance(props, dict):
        states.update(key for key in ("disabled", "checked", "selected")
                      if props.get(key))
    return states


def _matches_pseudo(
    pseudo: PseudoClass,
    widget: Widget,
    parents: dict[int, Optional[Widget]],
    sibling_info: dict[int, tuple[int, int]],
) -> bool:
    name = pseudo.name
    if pseudo.is_element:
        # Pydrud has no generated content, so ::before/::after never match.
        return False
    if name == ":root":
        # The document root maps to "global" in a widget tree.
        return True
    if name == ":not":
        inner = _parse_not_argument(pseudo.argument)
        if inner is None:
            return True
        return not _matches_compound(inner, widget, parents=parents,
                                     sibling_info=sibling_info)
    index, count = sibling_info.get(id(widget), (0, 1))
    if name == ":first-child":
        return index == 0
    if name == ":last-child":
        return index == count - 1
    if name == ":only-child":
        return count == 1
    if name == ":nth-child":
        return _nth_matches(pseudo.argument, index + 1)
    if name == ":empty":
        return not widget.children
    if name in _TRANSIENT_STATES:
        # Captured as a press/hover/focus sub-spec; the renderer times it.
        return True
    if name in _PERSISTENT_STATES:
        states = _widget_states(widget)
        key = name[1:]
        return key in states or (key == "enabled" and "disabled" not in states)
    return False


def _matches_compound(
    compound: CompoundSelector,
    widget: Widget,
    *,
    allow_id: bool = True,
    parents: Optional[dict[int, Optional[Widget]]] = None,
    sibling_info: Optional[dict[int, tuple[int, int]]] = None,
) -> bool:
    if compound.widget_type and widget._widget_type != compound.widget_type:
        return False
    if compound.id and (
            not allow_id
            or getattr(widget, "_auto_key", True)
            or widget.key != compound.id):
        return False
    classes = _widget_classes(widget)
    if not all(name in classes for name in compound.classes):
        return False
    if compound.pseudos:
        parents = parents or {}
        sibling_info = sibling_info or {}
        for pseudo in compound.pseudos:
            if not _matches_pseudo(pseudo, widget, parents, sibling_info):
                return False
    return True


def _match_selector(
    selector: Selector,
    widget: Widget,
    parents: dict[int, Optional[Widget]] | None = None,
    sibling_info: dict[int, tuple[int, int]] | None = None,
) -> bool:
    """Match a selector right-to-left against *widget* and its ancestors."""
    if not selector.compounds:
        return False
    parents = parents or {}
    sibling_info = sibling_info or {}

    def match_at(index: int, current: Widget) -> bool:
        if not _matches_compound(selector.compounds[index], current,
                                 parents=parents, sibling_info=sibling_info):
            return False
        if index == 0:
            return True
        parent = parents.get(id(current))
        combinator = selector.combinators[index - 1]
        if combinator == ">":
            return parent is not None and match_at(index - 1, parent)
        if combinator == " ":
            while parent is not None:
                if match_at(index - 1, parent):
                    return True
                parent = parents.get(id(parent))
            return False
        return False

    return match_at(len(selector.compounds) - 1, widget)


def _flatten_widgets(
    widgets: Iterable[Widget] | Widget,
) -> tuple[list[Widget], dict[int, Optional[Widget]]]:
    roots = [widgets] if isinstance(widgets, Widget) else list(widgets)
    ordered: list[Widget] = []
    parents: dict[int, Optional[Widget]] = {}
    seen: set[int] = set()
    stack = [(root, None) for root in reversed(roots) if isinstance(root, Widget)]
    while stack:
        widget, parent = stack.pop()
        identity = id(widget)
        if identity in seen:
            continue
        seen.add(identity)
        ordered.append(widget)
        parents[identity] = parent
        stack.extend((child, widget) for child in reversed(widget.children))
    return ordered, parents


def _sibling_info(
    ordered: list[Widget],
    parents: dict[int, Optional[Widget]],
    widgets: Iterable[Widget] | Widget,
) -> dict[int, tuple[int, int]]:
    """Map ``id(widget)`` → ``(index, sibling_count)`` for structural pseudos."""
    roots = [widgets] if isinstance(widgets, Widget) else list(widgets)
    info: dict[int, tuple[int, int]] = {}
    for widget in ordered:
        parent = parents.get(id(widget))
        group = parent.children if parent is not None else roots
        try:
            index = group.index(widget)
        except ValueError:  # pragma: no cover - defensive
            index = 0
        info[id(widget)] = (index, len(group))
    return info


_NTH = re.compile(r"^\s*(?:(?P<odd>odd)|(?P<even>even)|"
                  r"(?:(?P<a>[+-]?\d*)n\s*(?P<b>[+-]\s*\d+)?)|(?P<b2>[+-]?\d+))\s*$",
                  re.IGNORECASE)


def _nth_matches(expression: str, position: int) -> bool:
    """``an+b`` matching for ``:nth-child`` (1-based *position*)."""
    match = _NTH.match(expression or "")
    if match is None:
        return False
    if match.group("odd"):
        return position % 2 == 1
    if match.group("even"):
        return position % 2 == 0
    if match.group("b2") is not None:
        return position == int(match.group("b2"))
    raw_a = match.group("a")
    if raw_a in ("", "+"):
        a = 1
    elif raw_a == "-":
        a = -1
    else:
        a = int(raw_a)
    b_text = match.group("b")
    b = int(b_text.replace(" ", "")) if b_text else 0
    if a == 0:
        return position == b
    delta = position - b
    return delta % a == 0 and delta // a >= 0


_NOT_ARGUMENT = re.compile(
    r"^\s*(?P<type>[A-Za-z_][A-Za-z0-9_]*)?"
    r"(?P<classes>(?:\.[A-Za-z0-9_-]+)*)"
    r"(?P<id>#[A-Za-z0-9_-]+)?\s*$"
)


def _parse_not_argument(text: str) -> Optional[CompoundSelector]:
    match = _NOT_ARGUMENT.match(text or "")
    if match is None:
        return None
    classes = tuple(part for part in match.group("classes").split(".") if part)
    id_value = match.group("id")[1:] if match.group("id") else None
    if not (match.group("type") or classes or id_value):
        return None
    return CompoundSelector(match.group("type"), classes, id_value)


#: ``$token`` — a reference to a live theme colour role or design token.
_TOKEN_REF = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


def _theme_tokens() -> dict:
    """The token names a PSS ``$reference`` may resolve to.

    Colour roles come from :class:`~pydrud.widgets.theme.Theme` (so they track
    the active palette) and every design token from
    :class:`~pydrud.widgets.tokens.Tokens`.
    """
    from pydrud.widgets.theme import Theme
    from pydrud.widgets.tokens import Tokens

    names = ("primary", "secondary", "background", "surface",
             "surface_variant", "outline", "error", "text", "text_secondary",
             "on_primary")
    tokens = {name: getattr(Theme, name) for name in names
              if isinstance(getattr(Theme, name, None), (str, int, float))}
    for name in dir(Tokens):
        if name.startswith("_"):
            continue
        value = getattr(Tokens, name)
        if isinstance(value, (str, int, float)) and not callable(value):
            tokens.setdefault(name, value)
    return tokens


def _substitute_tokens(value, tokens: dict, missing: set):
    """Replace ``$name`` inside strings, recursing through composite values.

    A value that *is* a single reference keeps the token's own type, so
    ``borderRadius: $radius_card`` stays a number instead of the string
    ``"28"`` and never trips the value-kind check.
    """
    if isinstance(value, str):
        if "$" not in value:
            return value
        whole = value.strip()
        match = _TOKEN_REF.fullmatch(whole)
        if match is not None:
            name = match.group(1)
            if name in tokens:
                return tokens[name]
            missing.add(name)
            return value

        def replace(found: "re.Match[str]") -> str:
            name = found.group(1)
            if name in tokens:
                return str(tokens[name])
            missing.add(name)
            return found.group(0)

        return _TOKEN_REF.sub(replace, value)
    if isinstance(value, dict):
        return {k: _substitute_tokens(v, tokens, missing)
                for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_tokens(v, tokens, missing) for v in value]
    if isinstance(value, tuple):
        return tuple(_substitute_tokens(v, tokens, missing) for v in value)
    return value


def _contains_token_ref(value) -> bool:
    if isinstance(value, str):
        return "$" in value
    if isinstance(value, dict):
        return any(_contains_token_ref(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_token_ref(v) for v in value)
    return False


def _contains_variable(value) -> bool:
    if isinstance(value, str):
        return "var(" in value
    if isinstance(value, dict):
        return any(_contains_variable(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_variable(v) for v in value)
    return False


def _split_first_comma(text: str) -> tuple[str, Optional[str]]:
    depth = 0
    for index, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            return text[:index], text[index + 1:]
    return text, None


def _expand_vars_once(text: str, env: dict, missing: set) -> str:
    out: list[str] = []
    index = 0
    while True:
        start = text.find("var(", index)
        if start < 0:
            out.append(text[index:])
            break
        out.append(text[index:start])
        depth = 0
        cursor = start + 4
        while cursor < len(text):
            char = text[cursor]
            if char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    break
                depth -= 1
            cursor += 1
        inner = text[start + 4:cursor]
        name, fallback = _split_first_comma(inner)
        name = name.strip()
        if name in env:
            out.append(str(env[name]))
        elif fallback is not None:
            out.append(_expand_vars_once(fallback.strip(), env, missing))
        else:
            missing.add(name)
            out.append(text[start:cursor + 1])
        index = cursor + 1 if cursor < len(text) else len(text)
    return "".join(out)


def _substitute_variables(value, env: dict, missing: set):
    """Replace ``var(--x)`` recursively, allowing variables to reference others."""
    if isinstance(value, str):
        if "var(" not in value:
            return value
        text = value
        for _ in range(16):
            expanded = _expand_vars_once(text, env, missing)
            if expanded == text:
                break
            text = expanded
        return text
    if isinstance(value, dict):
        return {k: _substitute_variables(v, env, missing)
                for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_variables(v, env, missing) for v in value]
    if isinstance(value, tuple):
        return tuple(_substitute_variables(v, env, missing) for v in value)
    return value


def _media_matches(condition: MediaCondition, context: ValueContext) -> bool:
    if not condition.alternatives:
        return True
    for alternative in condition.alternatives:
        if all(_feature_matches(feature, context) for feature in alternative):
            return True
    return False


def _feature_matches(feature, context: ValueContext) -> bool:
    metric = context.width if feature.name == "width" else context.height
    if feature.op == "min":
        return metric >= feature.value
    if feature.op == "max":
        return metric <= feature.value
    return abs(metric - feature.value) < 1e-6


def _state_subject(compound: CompoundSelector) -> Optional[str]:
    """The press/hover/focus sub-spec a subject compound targets, if any."""
    for pseudo in compound.pseudos:
        sub = _STATE_PSEUDOS.get(pseudo.name)
        if sub is not None:
            return sub
    return None


_DIMENSION_KEYS = frozenset({
    "width", "height", "minWidth", "maxWidth", "minHeight", "maxHeight",
})
_DIMENSION_VALUE = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:dp|px|%|vw|vh|%[whs])$",
    re.IGNORECASE,
)
_DIMENSION_KEYWORDS = frozenset({
    "match", "match_parent", "fill", "100%", "expand",
    "wrap", "wrap_content", "auto",
})


def _value_kind_warning(key: str, value, widget: Widget) -> str | None:
    kind = KEY_KIND.get(key)
    if kind is None or kind == "any":
        return None
    valid = True
    if kind == "number":
        valid = isinstance(value, Number) and not isinstance(value, bool)
        if isinstance(value, str) and key in _DIMENSION_KEYS:
            normalized = value.strip().lower()
            valid = (
                normalized in _DIMENSION_KEYWORDS
                or bool(_DIMENSION_VALUE.fullmatch(normalized))
            )
    elif kind == "color":
        valid = isinstance(value, str) and bool(value.strip())
    elif kind == "keyword":
        valid = isinstance(value, (str, bool))
    elif kind == "composite":
        valid = isinstance(value, (dict, list, tuple))
    # ``shadow`` accepts a plain number (a quick elevation-style drop shadow)
    # as well as the full ``{offsetX, offsetY, blur, spread, color}`` form.
    if not valid and key == "shadow" and isinstance(value, Number) \
            and not isinstance(value, bool):
        valid = True
    if valid:
        return None
    return (
        f"Style property {key!r} has a value incompatible with its "
        f"{kind} schema on widget {widget.key!r}"
    )


def resolve_styles(
    stylesheet: StyleSheet,
    widgets: Iterable[Widget] | Widget,
    profile: Optional[RendererProfile] = None,
    *,
    context: Optional[ValueContext] = None,
) -> tuple[dict[str, dict], list[str]]:
    """Resolve matching rules to ``(widget_key -> style, warnings)``.

    ``widgets`` can be a root widget (for full descendant/child matching) or
    an iterable of roots. Explicit keys alone participate in ``#id`` rules;
    generated structural keys remain implementation details.
    """
    profile = profile or RendererProfile()
    context = context or ValueContext.from_media_query()
    ordered_widgets, parents = _flatten_widgets(widgets)
    sibling_info = _sibling_info(ordered_widgets, parents, widgets)
    result: dict[str, dict] = {}
    warnings: list[str] = []
    tokens: Optional[dict] = None
    missing_tokens: set[str] = set()
    missing_vars: set[str] = set()
    dropped_web: set[str] = set()
    widget_custom: dict[int, dict] = {}
    globals_ = dict(stylesheet.variables)
    keyframes = stylesheet.keyframes

    active_rules = [
        (order, rule)
        for order, rule in enumerate(stylesheet.rules)
        if rule.media is None or _media_matches(rule.media, context)
    ]

    def resolve_value(value, env: dict):
        if _contains_variable(value):
            value = _substitute_variables(value, env, missing_vars)
        if _contains_token_ref(value):
            nonlocal tokens
            if tokens is None:
                tokens = _theme_tokens()
            value = _substitute_tokens(value, tokens, missing_tokens)
        return value

    for widget in ordered_widgets:
        matched: list[tuple[tuple[int, int, int, int], int, DeclarationBlock]] = []
        state_decls: dict[str, list[tuple[tuple[int, int, int, int], int,
                                          DeclarationBlock]]] = {}
        custom: dict = {}

        for source_order, rule in active_rules:
            if not _match_selector(rule.selector, widget, parents, sibling_info):
                continue
            for key, value in rule.body.declarations:
                if isinstance(key, str) and key.startswith("--"):
                    custom[key] = value
            subject = rule.selector.compounds[-1]
            sub = _state_subject(subject)
            entry = (_specificity(rule.selector), source_order, rule.body)
            if sub is None:
                matched.append(entry)
            else:
                state_decls.setdefault(sub, []).append(entry)

        widget_custom[id(widget)] = custom

        if not matched and not state_decls:
            continue

        # Build this widget's custom-property environment: globals, then the
        # ancestors' declarations (outermost first), then its own.
        env = dict(globals_)
        chain: list[Widget] = []
        node = parents.get(id(widget))
        while node is not None:
            chain.append(node)
            node = parents.get(id(node))
        for node in reversed(chain):
            env.update(widget_custom.get(id(node), {}))
        env.update(custom)

        matched.sort(key=lambda item: (item[0], item[1]))
        merged: dict = {}
        for _, _, body in matched:
            for key, value in body.declarations:
                if isinstance(key, str) and key.startswith("--"):
                    continue
                merged[key] = resolve_value(value, env)

        for sub, entries in state_decls.items():
            entries.sort(key=lambda item: (item[0], item[1]))
            sub_style: dict = {}
            for _, _, body in entries:
                for key, value in body.declarations:
                    if isinstance(key, str) and key.startswith("--"):
                        continue
                    sub_style[key] = resolve_value(value, env)
            sub_style, _ = finalize_style(
                evaluate(sub_style, context), context, keyframes,
                widget._widget_type)
            merged[sub] = sub_style

        if not merged:
            continue

        merged = evaluate(merged, context)
        merged, dropped = finalize_style(
            merged, context, keyframes, widget._widget_type)
        dropped_web.update(dropped)
        result[widget.key] = merged

        for property_name, value in merged.items():
            value_warning = _value_kind_warning(property_name, value, widget)
            if value_warning:
                warnings.append(value_warning)
            if (profile.style_keys is not None
                    and property_name not in profile.style_keys):
                warnings.append(
                    f"Renderer profile does not declare style key "
                    f"{property_name!r} on widget {widget.key!r}"
                )

        if (profile.widget_types is not None
                and widget._widget_type not in profile.widget_types):
            warnings.append(
                f"Renderer profile does not declare widget type "
                f"{widget._widget_type!r} (key {widget.key!r})"
            )
        for first, second in profile.conflict_pairs:
            if first in merged and second in merged:
                warnings.append(
                    f"Conflicting properties {first!r} and {second!r} "
                    f"on widget {widget.key!r}"
                )
        if "bg" in merged and widget._widget_type in profile.background_owners:
            warnings.append(
                f"Renderer profile reports that {widget._widget_type} owns its "
                f"background; the 'bg' style may be ignored."
            )

    # Parser warnings are useful to callers that use the resolver directly;
    # errors are retained on StyleSheet.diagnostics and handled by loaders.
    warnings.extend(
        f"{diagnostic.filename}:{diagnostic.line}:{diagnostic.col}: "
        f"{diagnostic.message}"
        for diagnostic in stylesheet.diagnostics
        if diagnostic.kind == "warning"
    )
    if missing_tokens:
        warnings.append(
            "Unknown style token reference(s): "
            + ", ".join(f"${name}" for name in sorted(missing_tokens))
        )
    if missing_vars:
        warnings.append(
            "Unknown CSS variable reference(s): "
            + ", ".join(sorted(missing_vars))
        )
    if dropped_web:
        warnings.append(
            "Ignored web-only style declaration(s): "
            + ", ".join(sorted(dropped_web))
        )
    return result, warnings
