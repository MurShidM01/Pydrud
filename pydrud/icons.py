"""
The icon catalogue the Android renderer understands.

``pydrud.icons`` answers the two questions an app, a test or the analyzer
actually has — *is this icon name supported?* and *what names are there?*::

    from pydrud import icons

    icons.has("rocket_launch")        # True  (a shipped alias)
    icons.has("not_a_real_icon")      # False
    len(icons.available())            # every supported name
    icons.suggest("rocket_lunch")     # ['rocket_launch']

The catalogue is generated from the same table that produces the
``PydrudIcons`` Java class and vendored as plain data, so it reports the
truth both on a build machine and inside a running app — the Java template
itself is build-time only and never reaches the APK. A test pins the data
and the template together so they cannot drift. The set grows with icons
registered at runtime through :meth:`Icons.register` /
:meth:`Icons.load_pack`.

Custom iconography does not have to live in this list: :meth:`Icon.svg`
renders arbitrary 24x24 SVG path data, so an app can ship its own icons
without touching the framework.
"""

from __future__ import annotations

import difflib
from typing import Optional

from pydrud.core.icon_data import ALIASES as _ALIASES
from pydrud.core.icon_data import PATHS as _PATHS

__all__ = ["available", "canonical", "closest", "has", "shipped", "suggest"]

#: Path names plus alias names — everything the renderer resolves.
_NAMES: frozenset = frozenset(_PATHS | set(_ALIASES))


def _normalise(name: str) -> str:
    from pydrud.widgets.theme import Icons
    return Icons.normalize(name)


def shipped() -> frozenset:
    """Icon names and aliases compiled into the Android renderer."""
    return _NAMES


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
    if key in _ALIASES:
        return _ALIASES[key]
    return key if key in _PATHS else None


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
