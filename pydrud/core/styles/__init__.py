"""Cross-platform neutral style vocabulary (.pss stylesheet engine).

See ``schema.py`` for the canonical key registry. This package exposes the
vocabulary so the analyzer and the PSS engine share one source of truth.
"""

from __future__ import annotations

from pydrud.core.styles.schema import (
    KEY_KIND,
    VALID_STYLE_KEYS,
    _KEBAB_CANONICAL,
    normalize_key,
)
from pydrud.core.styles.lexer import lex, Token, TokenKind, LexerError
from pydrud.core.styles.parser import (
    parse_pss,
    StyleSheet,
    Rule,
    Selector,
    CompoundSelector,
    DeclarationBlock,
    Diagnostic,
)
from pydrud.core.styles.resolver import (
    resolve_styles,
    RendererProfile,
    AndroidRendererProfile,
)

__all__ = [
    "KEY_KIND",
    "VALID_STYLE_KEYS",
    "_KEBAB_CANONICAL",
    "normalize_key",
    "lex",
    "Token",
    "TokenKind",
    "LexerError",
    "parse_pss",
    "StyleSheet",
    "Rule",
    "Selector",
    "CompoundSelector",
    "DeclarationBlock",
    "Diagnostic",
    "resolve_styles",
    "RendererProfile",
    "AndroidRendererProfile",
]
