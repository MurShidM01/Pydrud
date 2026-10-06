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

__all__ = [
    "KEY_KIND",
    "VALID_STYLE_KEYS",
    "_KEBAB_CANONICAL",
    "normalize_key",
]
