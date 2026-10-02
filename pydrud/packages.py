"""Deprecated alias for :mod:`pydrud.commands.packages`.

``pydrud pip`` is build tooling, not runtime code, so it moved in with the
rest of the CLI in 2.0::

    from pydrud.commands.packages import Requirements

This shim will be removed in 3.0.
"""

from __future__ import annotations

import warnings

from pydrud.commands.packages import *  # noqa: F401,F403
from pydrud.commands.packages import (  # noqa: F401
    PackageError, Requirements, by_category, installed_summary, search,
    sync_gradle,
)

warnings.warn(
    "pydrud.packages is deprecated; import from pydrud.commands.packages",
    DeprecationWarning,
    stacklevel=2,
)
