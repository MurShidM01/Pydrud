"""PSS (Pydrud Style Sheet) syntax tree and parser.

PSS supports type, class, id, and universal selectors; compounds; descendant
and direct child combinators; comma-separated selector lists; pseudo-classes;
``@media`` and ``@keyframes`` at-rules; CSS custom properties; and typed,
schema-aware style declarations. Parsing is non-fatal: malformed input is
returned as source-located diagnostics so an editor can keep the last
known-good sheet.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from pydrud.core.styles.lexer import LexerError, Token, TokenKind, lex
from pydrud.core.styles.schema import normalize_key


@dataclass(frozen=True)
class Diagnostic:
    filename: str
    line: int
    col: int
    message: str
    kind: str = "error"  # "error" | "warning"


@dataclass(frozen=True)
class PseudoClass:
    """A ``:name`` / ``::name`` selector fragment, optionally with an argument."""

    name: str
    argument: str = ""

    @property
    def is_element(self) -> bool:
        """True for a pseudo-element (``::before``), false for a pseudo-class."""
        return self.name.startswith("::")


@dataclass
class CompoundSelector:
    widget_type: Optional[str] = None
    classes: tuple[str, ...] = ()
    id: Optional[str] = None
    pseudos: tuple[PseudoClass, ...] = ()
    universal: bool = False


@dataclass
class Selector:
    """A chain of compound selectors joined by CSS-like combinators."""

    compounds: tuple[CompoundSelector, ...] = ()
    combinators: tuple[str, ...] = ()  # one fewer than compounds


@dataclass(frozen=True)
class MediaFeature:
    """One media feature test, e.g. ``(max-width: 699px)``."""

    name: str  # "width" | "height"
    op: str    # "min" | "max" | "exact"
    value: float


@dataclass(frozen=True)
class MediaCondition:
    """A media query: an OR of ANDs, mirroring ``a and b, c and d``."""

    alternatives: tuple[tuple[MediaFeature, ...], ...] = ()

    def and_with(self, other: "MediaCondition") -> "MediaCondition":
        if not self.alternatives:
            return other
        if not other.alternatives:
            return self
        return MediaCondition(tuple(
            left + right
            for left in self.alternatives
            for right in other.alternatives
        ))


@dataclass
class DeclarationBlock:
    declarations: list[tuple[str, Any]] = field(default_factory=list)


@dataclass
class Rule:
    selector: Selector
    body: DeclarationBlock
    media: Optional[MediaCondition] = None


@dataclass
class Keyframe:
    offset: float
    declarations: list[tuple[str, Any]] = field(default_factory=list)


@dataclass
class Keyframes:
    name: str
    frames: list[Keyframe] = field(default_factory=list)


@dataclass
class StyleSheet:
    rules: list[Rule] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    filename: str = ""
    variables: dict[str, str] = field(default_factory=dict)
    keyframes: dict[str, Keyframes] = field(default_factory=dict)


_NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")


def _parse_collection(source: str) -> Any:
    """Parse PSS object/array values with JSON or CSS-style bare keys."""
    class Reader:
        def __init__(self, text: str) -> None:
            self.text = text
            self.pos = 0

        def whitespace(self) -> None:
            while self.pos < len(self.text) and self.text[self.pos].isspace():
                self.pos += 1

        def string(self) -> str:
            quote = self.text[self.pos]
            start = self.pos
            self.pos += 1
            escaped = False
            while self.pos < len(self.text):
                char = self.text[self.pos]
                self.pos += 1
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    raw = self.text[start:self.pos]
                    try:
                        value = ast.literal_eval(raw)
                    except (SyntaxError, ValueError) as exc:
                        raise ValueError("invalid quoted value") from exc
                    if not isinstance(value, str):
                        raise ValueError("expected a string")
                    return value
            raise ValueError("unterminated quoted value")

        def value(self) -> Any:
            self.whitespace()
            if self.pos >= len(self.text):
                raise ValueError("missing value")
            char = self.text[self.pos]
            if char == "{":
                return self.object()
            if char == "[":
                return self.array()
            if char in ("'", '"'):
                return self.string()
            return _parse_value(self.bare())

        def bare(self) -> str:
            start = self.pos
            parens = 0
            while self.pos < len(self.text):
                char = self.text[self.pos]
                if char == "(":
                    parens += 1
                elif char == ")" and parens:
                    parens -= 1
                elif parens == 0 and char in ",]};" :
                    break
                self.pos += 1
            value = self.text[start:self.pos].strip()
            if not value:
                raise ValueError("missing value")
            return value

        def object(self) -> dict:
            result = {}
            self.pos += 1  # opening brace
            self.whitespace()
            if self.pos < len(self.text) and self.text[self.pos] == "}":
                self.pos += 1
                return result
            while True:
                self.whitespace()
                if self.pos >= len(self.text):
                    raise ValueError("unterminated object")
                if self.text[self.pos] in ("'", '"'):
                    key = self.string()
                else:
                    start = self.pos
                    while self.pos < len(self.text) and self.text[self.pos] not in ":,};" \
                            and not self.text[self.pos].isspace():
                        self.pos += 1
                    key = self.text[start:self.pos]
                    if not key:
                        raise ValueError("missing object key")
                self.whitespace()
                if self.pos >= len(self.text) or self.text[self.pos] != ":":
                    raise ValueError("expected ':' after object key")
                self.pos += 1
                result[key] = self.value()
                self.whitespace()
                # A composite block may separate entries with ',' or ';' —
                # both read naturally inside a PSS declaration block.
                if self.pos < len(self.text) and self.text[self.pos] in ",;":
                    self.pos += 1
                    self.whitespace()
                    if self.pos < len(self.text) and self.text[self.pos] == "}":
                        self.pos += 1
                        return result
                    continue
                if self.pos < len(self.text) and self.text[self.pos] == "}":
                    self.pos += 1
                    return result
                raise ValueError("expected ',', ';' or '}' in object")

        def array(self) -> list:
            result = []
            self.pos += 1  # opening bracket
            self.whitespace()
            if self.pos < len(self.text) and self.text[self.pos] == "]":
                self.pos += 1
                return result
            while True:
                result.append(self.value())
                self.whitespace()
                if self.pos < len(self.text) and self.text[self.pos] in ",;":
                    self.pos += 1
                    self.whitespace()
                    if self.pos < len(self.text) and self.text[self.pos] == "]":
                        self.pos += 1
                        return result
                    continue
                if self.pos < len(self.text) and self.text[self.pos] == "]":
                    self.pos += 1
                    return result
                raise ValueError("expected ',', ';' or ']' in array")

    reader = Reader(source)
    value = reader.value()
    reader.whitespace()
    if reader.pos != len(source):
        raise ValueError("unexpected trailing text")
    return value


def _parse_value(source: str) -> Any:
    """Convert PSS scalar/JSON-style values to Python primitives.

    Bare names, CSS units, colour literals and renderer-specific function
    expressions remain strings. JSON arrays/objects are accepted for style
    properties whose schema kind is ``composite``.
    """
    raw = source.strip()
    if not raw:
        return ""
    lower = raw.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if lower == "null":
        return None
    if _NUMBER.fullmatch(raw):
        try:
            number = float(raw) if any(c in raw for c in ".eE") else int(raw)
            if isinstance(number, float) and number.is_integer() and not any(
                    c in raw for c in ".eE"):
                return int(number)
            return number
        except (ValueError, OverflowError):  # pragma: no cover - guarded by regex
            return raw

    if raw[:1] in ("'", '"') and raw[-1:] == raw[:1]:
        try:
            value = ast.literal_eval(raw)
            if isinstance(value, str):
                return value
        except (SyntaxError, ValueError):
            return raw[1:-1]
        return raw[1:-1]

    if raw[:1] in ("{", "["):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            try:
                value = ast.literal_eval(raw)
                if isinstance(value, (dict, list, tuple)):
                    return value
            except (SyntaxError, ValueError):
                pass
            try:
                return _parse_collection(raw)
            except (ValueError, SyntaxError):
                pass

    return raw


# ── animation / transition shorthands ───────────────────────────────────────

_TIME = re.compile(r"^([0-9.]+)(ms|s)$", re.IGNORECASE)
_EASINGS = {
    "linear": "linear",
    "ease": "ease_in_out",
    "ease-in": "ease_in",
    "ease-out": "ease_out",
    "ease-in-out": "ease_in_out",
    "step-start": "linear",
    "step-end": "linear",
}
_DIRECTIONS = {"normal", "reverse", "alternate", "alternate-reverse"}
_FILLS = {"forwards", "backwards", "both"}
_TIMING_FUNCTIONS = ("cubic-bezier(", "steps(", "linear(")


def _time_to_ms(text: str) -> Optional[float]:
    match = _TIME.match(text)
    if match is None:
        return None
    value = float(match.group(1))
    return value * 1000.0 if match.group(2).lower() == "s" else value


def parse_animation_shorthand(text: str) -> dict:
    """Parse a CSS ``animation`` shorthand into a renderer spec.

    ``animation: glow 1.12s ease-out infinite`` →
    ``{"name": "glow", "duration": 1120, "curve": "ease_out",
       "iterations": "infinite"}``. Durations are milliseconds, matching the
    renderer's existing ``animation`` spec.
    """
    spec: dict = {}
    tokens = text.split()
    times: list[float] = []
    for token in tokens:
        lowered = token.lower()
        if lowered == "none":
            spec["name"] = "none"
            continue
        time = _time_to_ms(token)
        if time is not None:
            times.append(time)
            continue
        if lowered == "infinite":
            spec["iterations"] = "infinite"
            continue
        if lowered in _EASINGS:
            spec["curve"] = _EASINGS[lowered]
            continue
        if any(lowered.startswith(prefix) for prefix in _TIMING_FUNCTIONS):
            spec["curve"] = token
            continue
        if lowered in _DIRECTIONS:
            spec["direction"] = lowered
            continue
        if lowered in _FILLS:
            spec["fill"] = lowered
            continue
        if _NUMBER.fullmatch(token):
            spec["iterations"] = float(token)
            continue
        spec.setdefault("name", token)
    if times:
        spec["duration"] = times[0]
    if len(times) > 1:
        spec["delay"] = times[1]
    return spec


def parse_transition_shorthand(text: str) -> list[dict]:
    """Parse a CSS ``transition`` list into renderer specs."""
    result: list[dict] = []
    for part in _split_top_level(text, ","):
        part = part.strip()
        if not part:
            continue
        spec: dict = {}
        times: list[float] = []
        for token in part.split():
            lowered = token.lower()
            if lowered == "none":
                spec["property"] = "none"
                continue
            time = _time_to_ms(token)
            if time is not None:
                times.append(time)
                continue
            if lowered in _EASINGS:
                spec["curve"] = _EASINGS[lowered]
                continue
            if any(lowered.startswith(prefix) for prefix in _TIMING_FUNCTIONS):
                spec["curve"] = token
                continue
            spec.setdefault("property", token)
        if times:
            spec["duration"] = times[0]
        if len(times) > 1:
            spec["delay"] = times[1]
        result.append(spec)
    return result


def _split_top_level_whitespace(text: str) -> list[str]:
    """Split *text* on whitespace outside parentheses and quotes."""
    parts: list[str] = []
    depth = 0
    quote: Optional[str] = None
    current: list[str] = []
    for char in text:
        if quote is not None:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
            current.append(char)
            continue
        if char == "(":
            depth += 1
            current.append(char)
            continue
        if char == ")":
            depth = max(0, depth - 1)
            current.append(char)
            continue
        if char.isspace() and depth == 0:
            if current:
                parts.append("".join(current))
                current = []
            continue
        current.append(char)
    if current:
        parts.append("".join(current))
    return parts


_BORDER_STYLES = frozenset({
    "solid", "dashed", "dotted", "double", "none", "hidden",
    "groove", "ridge", "inset", "outset",
})


def _expand_box_shorthand(text: str) -> Optional[dict]:
    """Expand a CSS ``padding``/``margin`` shorthand (1–4 values) to a dict.

    A single length/function becomes ``{all: …}`` so the renderer's object
    reader still sees it; a bare number is wrapped the same way by
    :meth:`_Parser._declaration_value` before it ever reaches here.
    """
    parts = _split_top_level_whitespace(text)
    if not 1 <= len(parts) <= 4:
        return None
    values = [_parse_value(part) for part in parts]
    if len(parts) == 1:
        value = values[0]
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return {"all": value}
        if isinstance(value, str) and value and value.lower() not in ("auto", "none"):
            return {"all": value}
        return None
    if len(parts) == 2:
        vertical, horizontal = values
        return {"top": vertical, "bottom": vertical,
                "left": horizontal, "right": horizontal}
    if len(parts) == 3:
        top, horizontal, bottom = values
        return {"top": top, "bottom": bottom,
                "left": horizontal, "right": horizontal}
    top, right, bottom, left = values
    return {"top": top, "right": right, "bottom": bottom, "left": left}


def _expand_border_shorthand(text: str) -> Optional[dict]:
    """Expand ``border: <width> <style> <color>`` to ``{width, color}``."""
    parts = _split_top_level_whitespace(text)
    if not parts:
        return None
    if len(parts) == 1:
        value = _parse_value(parts[0])
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return {"width": value}
        if isinstance(value, str) and value.lower() in ("none", "0"):
            return {"width": 0}
        return None
    width: Any = None
    color: Any = None
    for part in parts:
        lowered = part.lower()
        if lowered in _BORDER_STYLES:
            continue
        if width is None and (
                _NUMBER.fullmatch(part)
                or part[:1].isdigit() or part[:1] == "."):
            width = _parse_value(part)
            continue
        if width is None and part[:1] in "+-":
            width = _parse_value(part)
            continue
        if color is None and (part[:1] == "#" or lowered.startswith("rgb")
                              or lowered in ("transparent", "currentcolor")):
            color = part
            continue
        if width is None:
            width = _parse_value(part)
        elif color is None:
            color = part
    result: dict = {}
    if width is not None:
        result["width"] = width
    if color is not None:
        result["color"] = color
    return result or None


def _split_top_level(text: str, separator: str) -> list[str]:
    """Split *text* on *separator* outside parentheses and quotes."""
    parts: list[str] = []
    depth = 0
    quote: Optional[str] = None
    start = 0
    for index, char in enumerate(text):
        if quote is not None:
            if char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char == separator and depth == 0:
            parts.append(text[start:index])
            start = index + 1
    parts.append(text[start:])
    return parts


_MEDIA_FEATURE = re.compile(
    r"\(\s*(min-|max-)?(width|height)\s*:\s*([0-9.]+)\s*(?:px|dp|dip)?\s*\)",
    re.IGNORECASE,
)
_MEDIA_RANGE = re.compile(
    r"\(\s*(width|height)\s*(>=|<=|>|<)\s*([0-9.]+)\s*(?:px|dp|dip)?\s*\)",
    re.IGNORECASE,
)


def parse_media_condition(text: str) -> MediaCondition:
    """Parse a ``@media`` prelude into a :class:`MediaCondition`."""
    alternatives: list[tuple[MediaFeature, ...]] = []
    for part in _split_top_level(text, ","):
        part = part.strip()
        if not part:
            continue
        features: list[MediaFeature] = []
        for feature_text in re.split(r"\s+and\s+", part, flags=re.IGNORECASE):
            feature_text = feature_text.strip()
            if not feature_text:
                continue
            match = _MEDIA_FEATURE.fullmatch(feature_text)
            if match is not None:
                prefix, name, value = match.groups()
                op = "exact"
                if prefix == "min-":
                    op = "min"
                elif prefix == "max-":
                    op = "max"
                features.append(MediaFeature(name.lower(), op, float(value)))
                continue
            match = _MEDIA_RANGE.fullmatch(feature_text)
            if match is not None:
                name, operator, value = match.groups()
                op = "min" if operator in (">=", ">") else "max"
                features.append(MediaFeature(name.lower(), op, float(value)))
                continue
            raise ValueError(f"Unsupported media feature {feature_text!r}")
        if features:
            alternatives.append(tuple(features))
    if not alternatives:
        raise ValueError("Empty media query")
    return MediaCondition(tuple(alternatives))


class Parser:
    """Recursive-descent parser with rule-level error recovery."""

    def __init__(self, tokens: list[Token], filename: str = "") -> None:
        self.tokens = tokens
        self.pos = 0
        self.filename = filename
        self.diagnostics: list[Diagnostic] = []

    def current(self) -> Token:
        return self.tokens[min(self.pos, len(self.tokens) - 1)]

    def peek(self, offset: int = 0) -> Token:
        return self.tokens[min(self.pos + offset, len(self.tokens) - 1)]

    def advance(self) -> Token:
        token = self.current()
        if token.kind != TokenKind.EOF:
            self.pos += 1
        return token

    def error(self, message: str, token: Token | None = None,
              *, kind: str = "error") -> None:
        token = token or self.current()
        self.diagnostics.append(Diagnostic(
            filename=self.filename,
            line=token.line,
            col=token.col,
            message=message,
            kind=kind,
        ))

    def parse(self) -> StyleSheet:
        rules: list[Rule] = []
        keyframes: dict[str, Keyframes] = {}
        variables: dict[str, str] = {}
        while self.current().kind != TokenKind.EOF:
            before = self.pos
            try:
                if self.current().kind == TokenKind.AT:
                    self.parse_at_rule(rules, keyframes, variables, media=None)
                else:
                    rules.extend(self.parse_rule(media=None))
            except Exception as exc:  # keep the editor/runtime resilient
                self.error(f"Could not parse rule: {exc}")
                self.skip_to_next_rule()
            if self.pos == before:
                self.advance()
        for name, value in _root_variables(rules):
            variables.setdefault(name, value)
        return StyleSheet(
            rules=rules,
            diagnostics=self.diagnostics,
            filename=self.filename,
            variables=variables,
            keyframes=keyframes,
        )

    # ── at-rules ────────────────────────────────────────────────────────

    def parse_at_rule(
        self,
        rules: list[Rule],
        keyframes: dict[str, Keyframes],
        variables: dict[str, str],
        media: Optional[MediaCondition],
    ) -> None:
        at = self.advance()
        name = at.value.lower()
        prelude = ""
        if self.current().kind == TokenKind.PRELUDE:
            prelude = self.advance().value

        if name in ("keyframes", "-webkit-keyframes", "-moz-keyframes",
                    "-o-keyframes"):
            self.parse_keyframes(prelude, keyframes)
            return
        if name in ("media", "supports", "layer", "container", "scope",
                    "document"):
            condition = media
            if name == "media":
                try:
                    parsed = parse_media_condition(prelude)
                except ValueError as exc:
                    self.error(f"Invalid @media query: {exc}", at)
                    parsed = None
                if parsed is not None:
                    condition = parsed if media is None else media.and_with(parsed)
            if self.current().kind != TokenKind.LBRACE:
                self.error(f"Expected '{{' after @{at.value}", self.current())
                self.skip_to_next_rule()
                return
            self.advance()
            while self.current().kind not in (TokenKind.RBRACE, TokenKind.EOF):
                before = self.pos
                try:
                    if self.current().kind == TokenKind.AT:
                        self.parse_at_rule(rules, keyframes, variables, condition)
                    else:
                        rules.extend(self.parse_rule(media=condition))
                except Exception as exc:
                    self.error(f"Could not parse rule: {exc}")
                    self.skip_to_next_rule()
                if self.pos == before:
                    self.advance()
            if self.current().kind == TokenKind.RBRACE:
                self.advance()
            else:
                self.error(f"Expected '}}' to close @{at.value}")
            return

        self.error(f"Unsupported at-rule '@{at.value}'", at, kind="warning")
        self.skip_block()

    def parse_keyframes(self, prelude: str,
                        keyframes: dict[str, Keyframes]) -> None:
        name = prelude.strip()
        if self.current().kind != TokenKind.LBRACE:
            self.error("Expected '{' after @keyframes", self.current())
            self.skip_to_next_rule()
            return
        self.advance()
        frames: list[Keyframe] = []
        while self.current().kind not in (TokenKind.RBRACE, TokenKind.EOF):
            offsets = self.parse_keyframe_selectors()
            if self.current().kind != TokenKind.LBRACE:
                self.error("Expected '{' after keyframe selector", self.current())
                self.skip_to_next_rule()
                continue
            self.advance()
            body = self.parse_declarations()
            if self.current().kind == TokenKind.RBRACE:
                self.advance()
            else:
                self.error("Expected '}' to close keyframe block")
            for offset in offsets:
                frames.append(Keyframe(offset, list(body.declarations)))
        if self.current().kind == TokenKind.RBRACE:
            self.advance()
        else:
            self.error("Expected '}' to close @keyframes")
        if name:
            keyframes[name] = Keyframes(name, frames)
        else:
            self.error("A @keyframes block needs a name")

    def parse_keyframe_selectors(self) -> list[float]:
        offsets: list[float] = []
        while True:
            token = self.current()
            if token.kind == TokenKind.KEYFRAME_SEL:
                offsets.append(_keyframe_offset(token.value))
                self.advance()
            elif token.kind == TokenKind.COMBINATOR and token.value == ",":
                self.advance()
                continue
            else:
                self.error("Expected a keyframe selector", token)
                break
            if not (self.current().kind == TokenKind.COMBINATOR
                    and self.current().value == ","):
                break
        return offsets

    # ── rules ───────────────────────────────────────────────────────────

    def parse_rule(self, media: Optional[MediaCondition] = None) -> list[Rule]:
        selectors = self.parse_selector_list()
        if self.current().kind != TokenKind.LBRACE:
            self.error("Expected '{' after selector")
            self.skip_to_next_rule()
            return []
        self.advance()
        body = self.parse_declarations()
        if self.current().kind == TokenKind.RBRACE:
            self.advance()
        else:
            self.error("Expected '}' to close declaration block")
        return [Rule(selector=selector, body=body, media=media)
                for selector in selectors]

    def parse_selector_list(self) -> list[Selector]:
        selectors: list[Selector] = []
        compounds: list[CompoundSelector] = []
        combinators: list[str] = []

        while self.current().kind not in (TokenKind.LBRACE, TokenKind.EOF,
                                          TokenKind.RBRACE):
            compound = self.parse_compound_selector()
            if compound is not None:
                compounds.append(compound)
                token = self.current()
                if token.kind == TokenKind.COMBINATOR and token.value in (" ", ">"):
                    combinators.append(token.value)
                    self.advance()
                    if self.current().kind in (
                            TokenKind.LBRACE, TokenKind.EOF, TokenKind.RBRACE):
                        self.error("Expected selector after combinator", token)
                        break
                    continue
                if token.kind == TokenKind.COMBINATOR and token.value == ",":
                    self._append_selector(selectors, compounds, combinators, token)
                    compounds, combinators = [], []
                    self.advance()
                    if self.current().kind in (
                            TokenKind.LBRACE, TokenKind.EOF, TokenKind.RBRACE):
                        self.error("Expected selector after ','", token)
                        break
                    continue
                if token.kind == TokenKind.LBRACE:
                    break
                if token.kind == TokenKind.EOF:
                    break
                self.error(f"Unexpected token {token.value!r} in selector", token)
                self._recover_selector()
                break

            token = self.current()
            self.error(f"Expected selector, got {token.kind.name}", token)
            self._recover_selector()
            break

        if compounds:
            self._append_selector(selectors, compounds, combinators, self.current())
        return selectors

    def _append_selector(
        self,
        selectors: list[Selector],
        compounds: list[CompoundSelector],
        combinators: list[str],
        token: Token,
    ) -> None:
        if not compounds:
            self.error("Empty selector", token)
            return
        if len(combinators) != len(compounds) - 1:
            self.error("Selector combinator is missing a compound selector", token)
            return
        selectors.append(Selector(tuple(compounds), tuple(combinators)))

    def parse_compound_selector(self) -> Optional[CompoundSelector]:
        widget_type: Optional[str] = None
        classes: list[str] = []
        id_value: Optional[str] = None
        pseudos: list[PseudoClass] = []
        universal = False
        consumed = False

        while True:
            token = self.current()
            if token.kind == TokenKind.TYPE_SEL:
                consumed = True
                if widget_type is not None:
                    self.error("A compound selector cannot contain two type selectors", token)
                widget_type = token.value
                self.advance()
            elif token.kind == TokenKind.CLASS_SEL:
                consumed = True
                # Preserve the established .name.Widget shorthand: a final
                # uppercase class in a multi-part compound is its widget type.
                if (widget_type is not None or id_value is not None) and token.value[:1].isupper():
                    widget_type = token.value
                else:
                    classes.append(token.value)
                self.advance()
            elif token.kind == TokenKind.ID_SEL:
                consumed = True
                if id_value is not None:
                    self.error("A compound selector cannot contain two id selectors", token)
                id_value = token.value
                self.advance()
            elif token.kind == TokenKind.UNIVERSAL_SEL:
                consumed = True
                universal = True
                self.advance()
            elif token.kind == TokenKind.PSEUDO:
                consumed = True
                pseudos.append(_parse_pseudo(token.value))
                self.advance()
            else:
                break

        if not consumed:
            return None
        if widget_type is None and len(classes) > 1 and classes[-1][:1].isupper():
            widget_type = classes.pop()
        # Keep source order but discard duplicated class names.
        unique_classes = tuple(dict.fromkeys(classes))
        return CompoundSelector(widget_type, unique_classes, id_value,
                                tuple(pseudos), universal)

    def parse_declarations(self) -> DeclarationBlock:
        declarations: list[tuple[str, Any]] = []
        while self.current().kind not in (TokenKind.RBRACE, TokenKind.EOF):
            token = self.current()
            if token.kind == TokenKind.SEMI:
                self.advance()
                continue
            if token.kind != TokenKind.PROP:
                self.error(f"Expected property name, got {token.kind.name}", token)
                self._recover_declaration()
                continue

            property_token = self.advance()
            if self.current().kind != TokenKind.COLON:
                self.error("Expected ':' after property name", self.current())
                self._recover_declaration()
                continue
            self.advance()
            if self.current().kind != TokenKind.VALUE:
                self.error("Expected declaration value", self.current())
                self._recover_declaration()
                continue
            value_token = self.advance()

            name = property_token.value
            if name.startswith("--"):
                # A CSS custom property: kept verbatim, never schema-checked.
                declarations.append((name, value_token.value))
            else:
                canonical = normalize_key(name)
                if canonical is None:
                    self.error(
                        f"Unknown style property {name!r}",
                        property_token,
                        kind="warning",
                    )
                    key = name
                else:
                    key = canonical
                declarations.append(
                    (key, self._declaration_value(key, value_token.value)))

            if self.current().kind == TokenKind.SEMI:
                self.advance()
            elif self.current().kind not in (TokenKind.RBRACE, TokenKind.EOF):
                self.error("Expected ';' between declarations", self.current())
                self._recover_declaration()

        return DeclarationBlock(declarations)

    def _declaration_value(self, key: str, text: str) -> Any:
        """Parse a declaration value, expanding box/border shorthands."""
        parsed = _parse_value(text)
        if key in ("padding", "margin"):
            # A single bare number is the CSS uniform shorthand
            # (``padding: 24`` == all four sides). Wrap it so the renderer's
            # object reader sees a composite rather than a scalar it drops.
            if isinstance(parsed, (int, float)) and not isinstance(parsed, bool):
                return {"all": parsed}
            if isinstance(parsed, str):
                expanded = _expand_box_shorthand(parsed)
                if expanded is not None:
                    return expanded
        elif key == "border" and isinstance(parsed, str):
            expanded = _expand_border_shorthand(parsed)
            if expanded is not None:
                return expanded
        return parsed

    def _recover_selector(self) -> None:
        while self.current().kind not in (
                TokenKind.COMBINATOR, TokenKind.LBRACE, TokenKind.RBRACE,
                TokenKind.EOF):
            self.advance()
        if self.current().kind == TokenKind.COMBINATOR:
            self.advance()

    def _recover_declaration(self) -> None:
        while self.current().kind not in (
                TokenKind.SEMI, TokenKind.RBRACE, TokenKind.EOF):
            self.advance()
        if self.current().kind == TokenKind.SEMI:
            self.advance()

    def skip_to_next_rule(self) -> None:
        """Skip a malformed rule body without consuming the next valid rule."""
        while self.current().kind not in (TokenKind.LBRACE, TokenKind.RBRACE,
                                          TokenKind.EOF):
            self.advance()
        if self.current().kind == TokenKind.LBRACE:
            self.advance()
            depth = 1
            while self.current().kind != TokenKind.EOF and depth:
                token = self.advance()
                if token.kind == TokenKind.LBRACE:
                    depth += 1
                elif token.kind == TokenKind.RBRACE:
                    depth -= 1
        elif self.current().kind == TokenKind.RBRACE:
            self.advance()

    def skip_block(self) -> None:
        """Skip an at-rule block (or its terminating ';')."""
        while self.current().kind not in (TokenKind.LBRACE, TokenKind.RBRACE,
                                          TokenKind.SEMI, TokenKind.EOF):
            self.advance()
        if self.current().kind == TokenKind.SEMI:
            self.advance()
            return
        if self.current().kind == TokenKind.LBRACE:
            self.advance()
            depth = 1
            while self.current().kind != TokenKind.EOF and depth:
                token = self.advance()
                if token.kind == TokenKind.LBRACE:
                    depth += 1
                elif token.kind == TokenKind.RBRACE:
                    depth -= 1
        elif self.current().kind == TokenKind.RBRACE:
            self.advance()


def _parse_pseudo(text: str) -> PseudoClass:
    """Split a ``PSEUDO`` token into a :class:`PseudoClass`."""
    if "(" in text and text.endswith(")"):
        name, _, argument = text.partition("(")
        return PseudoClass(name, argument[:-1].strip())
    return PseudoClass(text)


def _keyframe_offset(text: str) -> float:
    lowered = text.strip().lower()
    if lowered == "from":
        return 0.0
    if lowered == "to":
        return 1.0
    if lowered.endswith("%"):
        try:
            return float(lowered[:-1]) / 100.0
        except ValueError:
            return 0.0
    try:
        return float(lowered)
    except ValueError:
        return 0.0


def _root_variables(rules: list[Rule]) -> list[tuple[str, str]]:
    """Collect ``--custom`` declarations from ``:root``/``*`` rules."""
    found: list[tuple[str, str]] = []
    for rule in rules:
        compounds = rule.selector.compounds
        if len(compounds) != 1:
            continue
        compound = compounds[0]
        if compound.widget_type or compound.classes or compound.id:
            continue
        is_root = compound.universal or any(
            pseudo.name == ":root" for pseudo in compound.pseudos)
        if not is_root:
            continue
        for key, value in rule.body.declarations:
            if isinstance(key, str) and key.startswith("--"):
                found.append((key, value))
    return found


def parse_pss(source: str, filename: str = "") -> StyleSheet:
    """Parse *source* to a :class:`StyleSheet`, returning diagnostics on errors."""
    try:
        tokens = lex(source, filename)
    except (LexerError, TypeError) as exc:
        return StyleSheet(
            rules=[],
            diagnostics=[Diagnostic(
                filename=filename,
                line=getattr(exc, "line", 1),
                col=getattr(exc, "col", 1),
                message=str(exc),
            )],
            filename=filename,
        )
    parser = Parser(tokens, filename)
    return parser.parse()
