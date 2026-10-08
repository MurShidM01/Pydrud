"""CSS value-expression evaluation for PSS.

PSS captures declaration values as source fragments. This module gives those
fragments the *CSS numeric value language*: ``calc()``, ``min()``, ``max()``,
``clamp()``, ``env()`` and viewport units, evaluated against a live
:class:`ValueContext`.

The result is deliberately conservative. A fragment that evaluates to a number
becomes a device-independent pixel value; anything that cannot be resolved (a
percentage of an unknown parent, a colour, a bare keyword, an animation
shorthand) is returned unchanged so the renderer keeps its existing handling.
That is what lets ``clamp(16px, 5vw, 24px)`` collapse to a dp number while
``100%`` and ``#FF6366F1`` pass straight through.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class ValueContext:
    """The device metrics a CSS numeric expression resolves against.

    ``width``/``height`` are the viewport in **dp** — the same numbers
    :class:`~pydrud.core.responsive.MediaQuery` reports — so ``1vw`` is one
    percent of the live window width. The safe-area insets back
    ``env(safe-area-inset-*)``.
    """

    width: float = 360.0
    height: float = 640.0
    safe_top: float = 0.0
    safe_bottom: float = 0.0
    safe_left: float = 0.0
    safe_right: float = 0.0
    font_scale: float = 1.0

    @classmethod
    def from_media_query(cls) -> "ValueContext":
        """Snapshot the live :class:`MediaQuery` metrics."""
        from pydrud.core.responsive import MediaQuery

        def number(name: str, default: float = 0.0) -> float:
            value = getattr(MediaQuery, name, default)
            try:
                return float(value)
            except (TypeError, ValueError):  # pragma: no cover - defensive
                return default

        return cls(
            width=number("width", 360.0) or 360.0,
            height=number("height", 640.0) or 640.0,
            safe_top=number("padding_top"),
            safe_bottom=number("padding_bottom"),
            safe_left=number("padding_left"),
            safe_right=number("padding_right"),
            font_scale=number("text_scale", 1.0) or 1.0,
        )


#: ``env(...)`` names → :class:`ValueContext` attributes.
_ENV_ATTRIBUTES = {
    "safe-area-inset-top": "safe_top",
    "safe-area-inset-bottom": "safe_bottom",
    "safe-area-inset-left": "safe_left",
    "safe-area-inset-right": "safe_right",
}

#: Units whose value depends on the live window.
_CONTEXT_UNITS = frozenset({
    "vw", "dvw", "svw", "lvw",
    "vh", "dvh", "svh", "lvh",
    "vmin", "vmax",
})

#: Units that are already device-independent pixels.
_IDENTITY_UNITS = frozenset({"", "px", "dp", "dip"})


@dataclass(frozen=True)
class _Token:
    kind: str  # "num" | "ident" | "op" | "lparen" | "rparen" | "comma"
    value: Any = None
    unit: str = ""


class _Unresolved(Exception):
    """Raised internally when a fragment is not a resolvable number."""


_NUMBER = re.compile(r"(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
_UNIT = re.compile(r"dvw|dvh|svw|svh|lvw|lvh|vmin|vmax|dip|dp|px|vw|vh|%")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")


def _tokenize(text: str) -> Optional[list[_Token]]:
    """Tokenise a value fragment, or return ``None`` when it is not math."""
    tokens: list[_Token] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if char in "+-*/":
            tokens.append(_Token("op", char))
            index += 1
            continue
        if char == "(":
            tokens.append(_Token("lparen"))
            index += 1
            continue
        if char == ")":
            tokens.append(_Token("rparen"))
            index += 1
            continue
        if char == ",":
            tokens.append(_Token("comma"))
            index += 1
            continue
        number = _NUMBER.match(text, index)
        if number is not None:
            end = number.end()
            unit = _UNIT.match(text, end)
            unit_text = unit.group(0) if unit is not None else ""
            if unit is not None:
                end = unit.end()
            tokens.append(_Token("num", float(number.group(0)), unit_text))
            index = end
            continue
        identifier = _IDENT.match(text, index)
        if identifier is not None:
            tokens.append(_Token("ident", identifier.group(0)))
            index = identifier.end()
            continue
        return None
    return tokens


class _Evaluator:
    """Recursive-descent evaluator for the CSS math grammar."""

    def __init__(self, tokens: list[_Token], context: ValueContext) -> None:
        self.tokens = tokens
        self.pos = 0
        self.context = context

    def _peek(self) -> Optional[_Token]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _next(self) -> _Token:
        token = self._peek()
        if token is None:
            raise _Unresolved("unexpected end of expression")
        self.pos += 1
        return token

    def _expect(self, kind: str) -> _Token:
        token = self._next()
        if token.kind != kind:
            raise _Unresolved(f"expected {kind}, got {token.kind}")
        return token

    def parse(self) -> float:
        value = self._expression()
        if self._peek() is not None:
            raise _Unresolved("trailing tokens")
        return value

    def _expression(self) -> float:
        value = self._term()
        while True:
            token = self._peek()
            if token is not None and token.kind == "op" and token.value in "+-":
                self._next()
                operand = self._term()
                value = value + operand if token.value == "+" else value - operand
            else:
                return value

    def _term(self) -> float:
        value = self._factor()
        while True:
            token = self._peek()
            if token is not None and token.kind == "op" and token.value in "*/":
                self._next()
                operand = self._factor()
                if token.value == "*":
                    value = value * operand
                else:
                    if operand == 0:
                        raise _Unresolved("division by zero")
                    value = value / operand
            else:
                return value

    def _factor(self) -> float:
        token = self._peek()
        if token is not None and token.kind == "op" and token.value in "+-":
            self._next()
            value = self._factor()
            return value if token.value == "+" else -value
        return self._atom()

    def _atom(self) -> float:
        token = self._next()
        if token.kind == "num":
            return self._to_dp(token.value, token.unit)
        if token.kind == "lparen":
            value = self._expression()
            self._expect("rparen")
            return value
        if token.kind == "ident":
            if self._peek() is not None and self._peek().kind == "lparen":
                return self._function(token.value)
            raise _Unresolved(f"bare keyword {token.value!r}")
        raise _Unresolved(f"unexpected token {token.kind}")

    def _to_dp(self, value: float, unit: str) -> float:
        if unit in _IDENTITY_UNITS:
            return value
        if unit in ("vw", "dvw", "svw", "lvw"):
            return value / 100.0 * self.context.width
        if unit in ("vh", "dvh", "svh", "lvh"):
            return value / 100.0 * self.context.height
        if unit == "vmin":
            return value / 100.0 * min(self.context.width, self.context.height)
        if unit == "vmax":
            return value / 100.0 * max(self.context.width, self.context.height)
        raise _Unresolved(f"unit {unit!r} is not resolvable")

    def _function(self, name: str) -> float:
        self._expect("lparen")
        lowered = name.lower()
        if lowered == "env":
            return self._env()
        arguments: list[float] = []
        if self._peek() is not None and self._peek().kind == "rparen":
            self._next()
        else:
            while True:
                arguments.append(self._expression())
                token = self._next()
                if token.kind == "rparen":
                    break
                if token.kind != "comma":
                    raise _Unresolved("expected ',' or ')' in function")
        if lowered == "calc":
            if len(arguments) != 1:
                raise _Unresolved("calc() takes one expression")
            return arguments[0]
        if lowered == "min":
            if not arguments:
                raise _Unresolved("min() needs an argument")
            return min(arguments)
        if lowered == "max":
            if not arguments:
                raise _Unresolved("max() needs an argument")
            return max(arguments)
        if lowered == "clamp":
            if len(arguments) != 3:
                raise _Unresolved("clamp() takes three arguments")
            low, ideal, high = arguments
            return max(low, min(ideal, high))
        raise _Unresolved(f"unknown function {name!r}")

    def _env(self) -> float:
        token = self._next()
        if token.kind != "ident":
            raise _Unresolved("env() needs a name")
        attribute = _ENV_ATTRIBUTES.get(token.value.lower())
        fallback: Optional[float] = None
        if self._peek() is not None and self._peek().kind == "comma":
            self._next()
            fallback = self._expression()
        self._expect("rparen")
        if attribute is not None:
            return float(getattr(self.context, attribute))
        if fallback is not None:
            return fallback
        raise _Unresolved(f"unknown env({token.value})")


def evaluate_expression(text: str, context: ValueContext) -> Optional[float]:
    """Evaluate *text* as a CSS numeric expression, or return ``None``.

    ``None`` means "not a resolvable number" — the caller keeps the original
    fragment. A trivial literal such as ``"430px"`` is intentionally left
    alone (``None``) so only genuine computations collapse to a number.
    """
    tokens = _tokenize(text)
    if tokens is None or not tokens:
        return None

    # A single literal — optionally signed — is not a computation.
    significant = tokens
    if (len(significant) >= 2 and significant[0].kind == "op"
            and significant[0].value in "+-" and significant[1].kind == "num"):
        significant = significant[1:]
    interesting = any(
        token.kind in ("op", "lparen")
        or (token.kind == "num" and token.unit in _CONTEXT_UNITS)
        for token in significant
    )
    if not interesting:
        return None

    try:
        return _Evaluator(tokens, context).parse()
    except _Unresolved:
        return None


_DIMENSION_LITERAL = re.compile(
    r"^([+-]?(?:\d+\.?\d*|\.\d+))(?:px|dp|dip)?$", re.IGNORECASE)


def to_dp(value: Any, context: ValueContext) -> Any:
    """Coerce a dimension fragment to a dp number, or return it unchanged.

    Unlike :func:`evaluate` this also collapses a *trivial* literal such as
    ``"18px"`` or ``"0"`` to a number, because the renderer reads box and font
    values with ``optInt``/``optDouble`` — a string would be dropped. Colours,
    keywords and unresolved percentages pass through untouched.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        text = value.strip()
        literal = _DIMENSION_LITERAL.fullmatch(text)
        if literal is not None:
            return float(literal.group(1))
        resolved = evaluate_expression(text, context)
        if resolved is not None:
            return resolved
    return value


def evaluate(value: Any, context: ValueContext) -> Any:
    """Collapse CSS numeric expressions inside *value*, recursing composites.

    Strings that resolve to a number become that number; everything else —
    colours, keywords, unresolved percentages, animation shorthands — is
    returned unchanged.
    """
    if isinstance(value, str):
        result = evaluate_expression(value, context)
        return result if result is not None else value
    if isinstance(value, dict):
        return {key: evaluate(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [evaluate(item, context) for item in value]
    if isinstance(value, tuple):
        return tuple(evaluate(item, context) for item in value)
    return value


_TRANSFORM_FUNCTION = re.compile(r"([A-Za-z]+)\(([^)]*)\)")
_ANGLE = re.compile(r"^([+-]?(?:\d+\.?\d*|\.\d+))(deg|grad|rad|turn)?$")


def _number(text: str, context: ValueContext) -> Optional[float]:
    """Parse a plain or computed number (used where a bare literal is valid)."""
    value = evaluate_expression(text, context)
    if value is not None:
        return value
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _angle(text: str) -> Optional[float]:
    """Parse a CSS angle to degrees."""
    match = _ANGLE.match(text.strip())
    if match is None:
        return None
    value = float(match.group(1))
    unit = match.group(2) or "deg"
    if unit == "grad":
        return value * 0.9
    if unit == "rad":
        return value * 57.29577951308232
    if unit == "turn":
        return value * 360.0
    return value


def decompose_transform(text: str, context: ValueContext) -> dict:
    """Split a CSS ``transform`` fragment into Pydrud transform properties.

    ``scale()`` maps to ``scale`` and ``rotate()`` to ``rotation``. Translation
    and ``matrix()`` are layout, not style, and are dropped — the caller may
    warn about them. Returns an empty dict when nothing maps.
    """
    result: dict = {}
    for name, raw in _TRANSFORM_FUNCTION.findall(text or ""):
        function = name.strip().lower()
        arguments = [part.strip() for part in raw.split(",") if part.strip()]
        if function == "scale" and arguments:
            scale = _number(arguments[0], context)
            if scale is not None:
                result["scale"] = scale
        elif function == "rotate" and arguments:
            rotation = _angle(arguments[0])
            if rotation is not None:
                result["rotation"] = rotation
    return result


__all__ = [
    "ValueContext",
    "evaluate",
    "evaluate_expression",
    "to_dp",
    "decompose_transform",
]
