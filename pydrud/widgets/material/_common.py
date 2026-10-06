"""
Shared helpers for the material widget modules.
"""

from __future__ import annotations


def _nav_height() -> float:
    from pydrud.widgets.tokens import Tokens

    return Tokens.nav_height


def _clean(d: dict) -> dict:
    """Drop None values so JSON payloads stay small and defaults stay native."""
    return {k: v for k, v in d.items() if v is not None}
