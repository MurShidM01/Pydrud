"""Deprecated alias for :mod:`pydrud.runtime.navigation`.

Navigation moved next to the app that drives it in 2.0. Import from the
public namespace instead::

    from pydrud import Router, Route

This shim will be removed in 3.0.
"""

from __future__ import annotations

import warnings

from pydrud.runtime.navigation import *  # noqa: F401,F403
from pydrud.runtime.navigation import (  # noqa: F401
    TRANSITIONS, NavigationStack, Route, Router, parse_url,
)

warnings.warn(
    "pydrud.navigation is deprecated; import from pydrud "
    "(or pydrud.runtime.navigation)",
    DeprecationWarning,
    stacklevel=2,
)
