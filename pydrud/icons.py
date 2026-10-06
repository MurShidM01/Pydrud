"""
The icon catalogue the Android renderer understands.

``pydrud.icons`` answers the two questions an app, a test or the analyzer
actually has — *is this icon name supported?* and *what names are there?*::

    from pydrud import icons

    icons.has("rocket_launch")        # True  (a shipped alias)
    icons.has("not_a_real_icon")      # False
    len(icons.available())            # every supported name
    icons.suggest("rocket_lunch")     # ['rocket_launch']

The catalogue is parsed from the generated ``PydrudIcons`` Java template —
the exact class that ships in every built app — so it can never drift from
what actually renders. It grows with icons registered at runtime through
:meth:`Icons.register` / :meth:`Icons.load_pack`.

Custom iconography does not have to live in this list: :meth:`Icon.svg`
renders arbitrary 24x24 SVG path data, so an app can ship its own icons
without touching the framework.
"""

from __future__ import annotations

import difflib
import functools
import re
from pathlib import Path
from typing import Optional

__all__ = ["available", "canonical", "closest", "has", "shipped", "suggest"]

_TEMPLATE = (Path(__file__).resolve().parent
             / "android" / "templates" / "android" / "PydrudIcons.java.j2")

_PATHS_RE = re.compile(r'PATHS\.put\(\s*"([^"]+)"')
_ALIASES_RE = re.compile(r'ALIASES\.put\(\s*"([^"]+)"\s*,\s*"([^"]+)"')


@functools.lru_cache(maxsize=1)
def _catalogue() -> tuple[frozenset, dict]:
    """Parse the generated icon class once.

    Returns ``(names, aliases)`` where *names* is every icon or alias the
    Java ``PydrudIcons`` class recognises and *aliases* maps each alias to
    the canonical path name it resolves to.
    """
    try:
        text = _TEMPLATE.read_text(encoding="utf-8")
    except OSError:  # pragma: no cover - template always ships
        return frozenset(), {}
    paths = set(_PATHS_RE.findall(text))
    aliases = {alias: target for alias, target in _ALIASES_RE.findall(text)}
    return frozenset(paths | set(aliases)), aliases


def _normalise(name: str) -> str:
    from pydrud.widgets.theme import Icons
    return Icons.normalize(name)


def shipped() -> frozenset:
    """Icon names and aliases compiled into the Android renderer."""
    return _catalogue()[0]


def available() -> set:
    """Every icon name the renderer accepts.

    The union of the shipped vector icons and any icons registered at
    runtime with :meth:`Icons.register` / :meth:`Icons.load_pack`.
    """
    from pydrud.widgets.theme import Icons
    return set(shipped()) | set(Icons.all())


def canonical(name: str) -> Optional[str]:
    """The shipped path name *name* resolves to, or ``None`` if unknown.

    Aliases resolve to their target (``"rocket_launch"`` → ``"rocket"``);
    a canonical name resolves to itself. Runtime-registered pack icons are
    not in the shipped class, so they resolve to ``None`` here even though
    :func:`has` reports them as available.
    """
    if not isinstance(name, str) or not name.strip():
        return None
    key = _normalise(name)
    names, aliases = _catalogue()
    if key in aliases:
        return aliases[key]
    return key if key in names else None


def has(name: str) -> bool:
    """True when the renderer has an icon (or alias) called *name*."""
    if not isinstance(name, str) or not name.strip():
        return False
    return _normalise(name) in available()


def suggest(name: str, limit: int = 3) -> list:
    """The closest supported icon names to *name* (best match first)."""
    if not isinstance(name, str) or not name.strip():
        return []
    return difflib.get_close_matches(_normalise(name), sorted(available()),
                                     n=limit, cutoff=0.5)


#: Alias kept for the CHANGELOG's wording; ``suggest`` is the primary name.
closest = suggest
